"""Expert Sourcing Chine — chiffre une opportunité d'import, avec preuves.

Déclenché par /sourcing <id d'opportunité | produit> [quantité], et chaque jeudi à 09:30
pour les opportunités marquées « import Chine à étudier » par l'expert Tendances (2 au plus).

Étapes :
  1. recherche web (modèle rapide, 5 recherches max) : annonces fournisseurs chinois (prix FOB, MOQ, certifications)
     et prix de vente en Tunisie, CHAQUE chiffre avec l'URL de sa page ;
  2. tout chiffre sans source est jeté ; prix marché pris d'abord dans nos relevés concurrents ;
  3. calcul déterministe du coût de revient (import_calc, taux dans data/import_params.json) ;
  4. verdict par règles : à creuser / limite / non rentable, plus les alertes (liste BCT, contrôle technique, trésorerie).
L'expert ne commande rien et ne contacte aucun fournisseur. Les prix trouvés en ligne sont des prix d'appel :
le vrai prix se négocie, et l'échantillon passe avant toute commande.
"""
import json
import os
import re
import statistics
from datetime import date

from .. import db, import_calc, llm, telegram
from ..config import settings
from .base import Agent
from .tendances import market_price, norm

WEB_SEARCH_TOOL = os.getenv("WEB_SEARCH_TOOL", "web_search_20260209")
MAX_SEARCHES = int(os.getenv("SOURCING_RECHERCHES_MAX", "5"))
QTE_DEFAUT = int(os.getenv("SOURCING_QTE_DEFAUT", "300"))

SYSTEM = """Tu es l'expert sourcing et import de Dealz (boutique en ligne tunisienne, Sfax). 15 ans d'import Chine → Maghreb.
On te donne un produit. Avec la recherche web, trouve :
1. 2 à 4 offres de fournisseurs chinois (Alibaba, Made-in-China, Global Sources, sites d'usines) : prix FOB en USD (fourchette), MOQ, certifications mentionnées ;
2. 2 à 4 prix de vente actuels en Tunisie (boutiques en ligne tunisiennes) en DT TTC ;
3. ce qui bloque à l'import en Tunisie pour ce produit (normes, homologation, liste BCT des importations non prioritaires…).

Règles strictes :
- Chaque prix a l'URL de la page où il apparaît. Pas de page = pas de prix. N'invente rien, n'estime rien.
- Un prix d'appel Alibaba n'est pas un prix négocié : signale les fourchettes trop larges ou suspectes.
- Si tu ne trouves rien de fiable, renvoie des listes vides.

Réponds UNIQUEMENT en JSON :
{"categorie": "papeterie|cartables|informatique|petit_electro|mobilier|jouets_deco|autre",
 "offres_chine": [{"fournisseur": "", "prix_min_usd": 0, "prix_max_usd": 0, "moq": 0, "certifications": "", "url": ""}],
 "prix_tunisie": [{"boutique": "", "produit": "", "prix_ttc": 0, "url": ""}],
 "reglementation": "2 phrases max", "conseil_expert": "3 phrases max : qualité, pièges, comment négocier/tester"}"""


def _num(x):
    try:
        v = float(str(x).replace(",", ".").replace(" ", ""))
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def validate(res: dict) -> dict:
    """Ne garde que les chiffres sourcés et plausibles."""
    offres = []
    for o in res.get("offres_chine") or []:
        lo, hi = _num(o.get("prix_min_usd")), _num(o.get("prix_max_usd"))
        if not str(o.get("url", "")).startswith("http") or not (lo or hi):
            continue
        lo, hi = lo or hi, hi or lo
        if hi < lo or hi > 50 * lo:   # fourchette incohérente
            continue
        offres.append({"fournisseur": str(o.get("fournisseur", ""))[:80], "prix_min_usd": lo, "prix_max_usd": hi,
                       "moq": int(_num(o.get("moq")) or 0), "certifications": str(o.get("certifications", ""))[:120], "url": o["url"][:300]})
    prix_tn = [{"boutique": str(p.get("boutique", ""))[:60], "produit": str(p.get("produit", ""))[:100], "prix_ttc": _num(p.get("prix_ttc")),
                "url": p["url"][:300]} for p in res.get("prix_tunisie") or []
               if str(p.get("url", "")).startswith("http") and _num(p.get("prix_ttc"))]
    return {"categorie": res.get("categorie") if res.get("categorie") in import_calc.params()["categories"] else "autre",
            "offres_chine": offres, "prix_tunisie": prix_tn,
            "reglementation": str(res.get("reglementation", ""))[:400], "conseil_expert": str(res.get("conseil_expert", ""))[:600]}


def evaluate(produit: str, found: dict, qte: int, prix_releves=None) -> dict:
    """Calcule les scénarios bas / haut. Prix marché : nos relevés d'abord, sinon médiane des prix tunisiens sourcés."""
    prix_marche, source_prix = prix_releves, "relevés concurrents"
    if not prix_marche and found["prix_tunisie"]:
        prix_marche, source_prix = round(statistics.median(p["prix_ttc"] for p in found["prix_tunisie"]), 3), "recherche web"
    if not found["offres_chine"]:
        return {"produit": produit, "prix_marche": prix_marche, "source_prix": source_prix, "scenarios": [],
                "verdict": "pas assez de données", **found}
    moq = max([o["moq"] for o in found["offres_chine"]] + [0])
    qte = max(qte, min(moq, 5000)) if moq else qte
    lo = statistics.median(o["prix_min_usd"] for o in found["offres_chine"])
    hi = statistics.median(o["prix_max_usd"] for o in found["offres_chine"])
    scen = [import_calc.landed_cost(fob, qte, found["categorie"], prix_marche) for fob in sorted({lo, hi})]
    if prix_marche:
        verdict = scen[-1]["verdict"] if scen[-1]["verdict"] == scen[0]["verdict"] else f"{scen[0]['verdict']} → {scen[-1]['verdict']} selon le prix négocié"
    else:
        verdict = "prix marché inconnu"
    return {"produit": produit, "prix_marche": prix_marche, "source_prix": source_prix, "qte": qte, "scenarios": scen,
            "verdict": verdict, **found}


def format_report(ev: dict, oid=None) -> str:
    e = telegram.esc
    out = [f"🚢 <b>Sourcing Chine — {e(ev['produit'])}</b>{f' (#{oid})' if oid else ''}",
           f"Verdict : <b>{e(ev['verdict'].upper())}</b>",
           f"Prix marché Tunisie : {ev['prix_marche']:.3f} DT TTC ({e(ev['source_prix'])})" if ev["prix_marche"] else "Prix marché Tunisie : inconnu"]
    for s in ev["scenarios"]:
        out.append("\n" + e(import_calc.format_calc(s)))
    if ev["offres_chine"]:
        out.append("\n<b>Offres trouvées</b>")
        out += [f"• {e(o['fournisseur'])} : {o['prix_min_usd']}–{o['prix_max_usd']} $ · MOQ {o['moq'] or '?'} · {e(o['certifications'])}\n  {e(o['url'])}"
                for o in ev["offres_chine"]]
    if ev["prix_tunisie"]:
        out.append("\n<b>Prix en Tunisie</b>")
        out += [f"• {e(p['boutique'])} : {p['prix_ttc']:.3f} DT — {e(p['url'])}" for p in ev["prix_tunisie"]]
    if ev.get("reglementation"):
        out.append(f"\n<b>Réglementation</b> : {e(ev['reglementation'])}")
    if ev.get("conseil_expert"):
        out.append(f"<b>L'expert</b> : {e(ev['conseil_expert'])}")
    out.append("\n<i>Avant toute commande : devis transitaire (code SH), échantillon, vérification du fournisseur.</i>")
    return "\n".join(out)


class SourcingAgent(Agent):
    name = "sourcing"
    label = "Expert Sourcing Chine"

    def study(self, cible: str, qte: int = QTE_DEFAUT):
        """cible = id d'opportunité ou nom de produit. Renvoie le rapport (texte HTML Telegram)."""
        opp = db.opportunite(int(cible)) if str(cible).isdigit() else None
        produit = opp["produit"] if opp else cible.strip()
        if not produit:
            return "Indique un produit ou un n° d'opportunité : /sourcing 4  ou  /sourcing friteuse à air 5L 500"
        if not llm.available():
            return "IA inactive (pas de clé ou budget atteint) : utilise /import pour un calcul manuel."
        tools = [{"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": MAX_SEARCHES}]
        raw = llm.ask("sourcing", SYSTEM, f"Produit : {produit}\nQuantité envisagée : {qte}", model=settings.model_fast,
                      max_tokens=2500, tools=tools, tool_impl={}, max_turns=8)
        m = re.search(r"\{[\s\S]*\}", raw or "")
        try:
            found = validate(json.loads(m.group(0)) if m else {})
        except json.JSONDecodeError:
            found = validate({})
        last_day = (db.tendances_dates(1) or [None])[0]
        releves = market_price(produit, db.tendances_snapshot(last_day)) if last_day else None
        ev = evaluate(produit, found, qte, (opp or {}).get("prix_marche") or releves)
        oid = db.add_opportunite({"agent": self.label, "produit": produit[:120], "categorie": found["categorie"],
                                  "canal": "import Chine à étudier", "score": (opp or {}).get("score", 3),
                                  "pourquoi": (opp or {}).get("pourquoi", "Demande manuelle"), "prix_marche": ev["prix_marche"],
                                  "preuves": json.loads((opp or {}).get("preuves") or "[]"), "analyse": ev,
                                  "dedupe": "opp:" + norm(produit)[:80]})
        db.set_opportunite_status(oid, "chiffree")
        report = format_report(ev, oid)
        db.add_report(self.label, f"Sourcing — {produit}", re.sub(r"<[^>]+>", "", report))
        return report

    def run(self):
        """Hebdo : chiffre les 2 meilleures opportunités en attente d'étude."""
        todo = sorted(db.opportunites(statut="a_etudier"), key=lambda o: -(o["score"] or 0))[:2]
        if not todo or not llm.available():
            return None
        for o in todo:
            telegram.send(self.study(str(o["id"])))
        return {"chiffrees": len(todo)}
