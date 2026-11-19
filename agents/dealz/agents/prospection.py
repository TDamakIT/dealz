"""Agent Prospection — tous les jours à 09:00 (et à la demande avec /prospection).

Chaque jour il traite un segment CLIENTS et un segment FOURNISSEURS (en rotation) :
il cherche sur le web des organisations, relève leurs coordonnées PUBLIQUES (téléphone, email, site, adresse)
avec la page où il les a trouvées, propose une accroche, puis t'envoie le rapport sur Telegram.

Règles (données personnelles et bon sens commercial) :
  - seulement des organisations (écoles, entreprises, grossistes…), jamais des particuliers ;
  - seulement les coordonnées publiées par l'organisation elle-même ou un annuaire professionnel ;
  - chaque coordonnée a sa source ; un email ou un numéro deviné est interdit ;
  - l'agent ne contacte personne : il trouve et prépare, un humain appelle ou écrit.
Coût : recherche web de l'API Claude (10 $ les 1 000 recherches) + tokens. Plafonné par PROSPECTION_RECHERCHES_MAX.
"""
import json
import os
import re
import unicodedata
from datetime import date

from .. import db, llm, telegram
from ..config import settings
from .base import Agent

WEB_SEARCH_TOOL = os.getenv("WEB_SEARCH_TOOL", "web_search_20260209")
MAX_SEARCHES = int(os.getenv("PROSPECTION_RECHERCHES_MAX", "5"))
MAX_RESULTS = int(os.getenv("PROSPECTION_RESULTATS_MAX", "8"))

SEGMENTS_CLIENTS = [
    "écoles primaires privées à Sfax",
    "collèges et lycées privés à Sfax",
    "crèches et jardins d'enfants à Sfax",
    "cabinets d'expertise comptable à Sfax",
    "cabinets d'avocats et études de notaires à Sfax",
    "cliniques et cabinets médicaux de groupe à Sfax (fournitures de bureau)",
    "PME industrielles de la zone industrielle de Sfax (fournitures de bureau, informatique)",
    "centres de formation et écoles de langues à Sfax",
    "écoles primaires privées à Sousse",
    "écoles primaires privées à Tunis et Ariana",
    "associations qui distribuent des kits scolaires en Tunisie",
]
SEGMENTS_FOURNISSEURS = [
    # Priorité : les deux rayons sans aucun fournisseur
    "importateurs et distributeurs de petit électroménager en Tunisie",
    "fabricants tunisiens de mobilier de bureau et mobilier scolaire",
    "grossistes en petit électroménager à Sfax et Sousse",
    "fabricants tunisiens de meubles en kit et mobilier pour la maison",
    "transitaires et commissionnaires en douane à Sfax (import depuis la Chine)",
    "fabricants tunisiens de cahiers et articles de papeterie",
    "grossistes et importateurs de fournitures scolaires en Tunisie",
    "fabricants et importateurs de cartables et sacs à dos en Tunisie",
    "grossistes et distributeurs informatique en Tunisie (PC, accessoires)",
    "sociétés de livraison e-commerce avec paiement à la livraison en Tunisie",
    "fabricants d'emballages et cartons d'expédition en Tunisie",
]

SYSTEM = """Tu es le chargé de prospection de Dealz, boutique en ligne familiale tunisienne basée à Sfax
(papeterie et fournitures scolaires, informatique et bureau ; bientôt petit électroménager et mobilier ; vente aux particuliers et aux pros).
Utilise la recherche web pour trouver des organisations RÉELLES du segment demandé, et leurs coordonnées professionnelles publiques.

Règles strictes :
- Uniquement des organisations, jamais de particuliers.
- Une coordonnée (téléphone, email) n'est donnée que si elle apparaît sur une page que tu as consultée : celle de l'organisation ou un annuaire professionnel. Jamais de coordonnée devinée ou reconstruite (pas de contact@nomdusite.tn inventé).
- Chaque organisation a une "source_url" : la page où tu as trouvé ses coordonnées.
- Si tu ne trouves pas de téléphone ou d'email, laisse le champ vide plutôt que d'inventer.
- Ignore les organisations de la liste « déjà connues ».

Réponds UNIQUEMENT avec un tableau JSON (au plus {max} éléments) :
[{{"nom": "", "type": "", "ville": "", "telephone": "", "email": "", "site": "", "adresse": "", "source_url": "",
  "pertinence": 1-5, "pourquoi": "pourquoi c'est une bonne cible pour Dealz (1 phrase)",
  "accroche": "première phrase à dire au téléphone ou à écrire (1 à 2 phrases, en français)"}}]"""


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn")).strip()


def clean_phone(p: str) -> str:
    """Garde un numéro tunisien plausible (8 chiffres, avec ou sans +216), sinon vide."""
    d = re.sub(r"\D", "", p or "")
    if d.startswith("00216"):
        d = d[5:]
    elif d.startswith("216"):
        d = d[3:]
    return f"+216 {d[:2]} {d[2:5]} {d[5:]}" if re.fullmatch(r"[2-9]\d{7}", d) else ""


def clean_email(e: str) -> str:
    e = (e or "").strip().lower()
    return e if re.fullmatch(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", e) else ""


def validate(items, kind, segment):
    out = []
    for it in items if isinstance(items, list) else []:
        nom = (it.get("nom") or "").strip()
        src = (it.get("source_url") or "").strip()
        if not nom or not src.startswith("http"):
            continue
        tel, mail = clean_phone(it.get("telephone")), clean_email(it.get("email"))
        site = (it.get("site") or "").strip()
        if not (tel or mail or site):
            continue
        out.append({"kind": kind, "segment": segment, "nom": nom[:150], "type": (it.get("type") or "")[:80],
                    "ville": (it.get("ville") or "")[:60], "telephone": tel, "email": mail, "site": site[:200],
                    "adresse": (it.get("adresse") or "")[:200], "source_url": src[:300],
                    "pertinence": max(1, min(5, int(it.get("pertinence") or 3))),
                    "pourquoi": (it.get("pourquoi") or "")[:300], "accroche": (it.get("accroche") or "")[:400],
                    "dedupe": f"{kind}:{_norm(nom)}:{_norm(it.get('ville'))}"})
    return out


class ProspectionAgent(Agent):
    name = "prospection"
    label = "Prospection"

    def _segment(self, kind, segments):
        if kind == "fournisseur":   # les autres agents peuvent mettre un segment en tête de file (links.py)
            from ..links import pop_segment
            q = pop_segment()
            if q:
                return q["segment"]
        i = db.get_state(f"prospection_idx_{kind}", 0)
        db.set_state(f"prospection_idx_{kind}", (i + 1) % len(segments))
        return segments[i % len(segments)]

    def search(self, kind, segment):
        known = db.known_prospect_names(kind)
        user = (f"Segment : {segment}\nType de cible : {'client' if kind == 'client' else 'fournisseur'}\n"
                f"Déjà connues (à ignorer) : {', '.join(known[:150]) or 'aucune'}")
        tools = [{"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": MAX_SEARCHES, "user_location":
                  {"type": "approximate", "country": "TN", "city": "Sfax", "timezone": "Africa/Tunis"}}]
        raw = llm.ask(f"prospection-{kind}", SYSTEM.format(max=MAX_RESULTS), user, model=settings.model_fast,
                      max_tokens=3000, tools=tools, tool_impl={}, max_turns=6)
        if getattr(raw, "simulated", False):
            return None
        m = re.search(r"\[[\s\S]*\]", raw or "")
        try:
            return validate(json.loads(m.group(0)), kind, segment) if m else []
        except json.JSONDecodeError:
            return []

    def run(self):
        if not llm.available():
            self.log.info("Prospection : pas de clé API ou budget atteint, rien à faire")
            return None
        today = date.today().isoformat()
        sections, total = [], 0
        for kind, segs in (("client", SEGMENTS_CLIENTS), ("fournisseur", SEGMENTS_FOURNISSEURS)):
            seg = self._segment(kind, segs)
            found = self.search(kind, seg) or []
            new = [p for p in found if db.add_prospect(p)]
            total += len(new)
            lines = [f"<b>{'Clients' if kind == 'client' else 'Fournisseurs'} — {telegram.esc(seg)}</b> : {len(new)} nouveau(x)"]
            for p in sorted(new, key=lambda x: -x["pertinence"]):
                contact = " · ".join(x for x in (p["telephone"], p["email"], p["site"]) if x)
                lines.append(f"\n{'★' * p['pertinence']} <b>{telegram.esc(p['nom'])}</b> ({telegram.esc(p['ville'])})\n"
                             f"{telegram.esc(contact)}\n<i>{telegram.esc(p['pourquoi'])}</i>\n"
                             f"Accroche : {telegram.esc(p['accroche'])}\nSource : {telegram.esc(p['source_url'])}")
            sections.append("\n".join(lines))
        body = "\n\n".join(sections) + "\n\nSuivi : /prospects · changer un statut : /prospect 12 contacte"
        telegram.send(f"🎯 <b>Prospection du {today}</b> — {total} nouvelle(s) cible(s)\n\n{body}")
        db.add_report(self.label, f"Prospection du {today}", re.sub(r"<[^>]+>", "", body))
        return {"nouveaux": total}
