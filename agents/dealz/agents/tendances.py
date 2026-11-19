"""Expert Tendances (category manager) — ce qui se vend chez les concurrents.

Chaque jour à 06:45, SANS IA : relève la 1re page des catégories suivies (data/tendances_sources.json),
triée par « meilleures ventes » quand la boutique le permet, et calcule des signaux :
  - best-seller stable : dans le top 10 des ventes au moins 5 des 7 derniers relevés ;
  - nouvel entrant : dans le top 5 des ventes aujourd'hui, absent du top 24 les 7 jours précédents ;
  - rupture : produit du top passé « en stock » → « épuisé » (il s'est vendu) ;
  - baisse de prix : -10 % ou plus en 7 jours.
Chaque mercredi à 08:30 (ou /tendances), l'expert (modèle « smart » + 3 recherches web) lit ces signaux,
notre catalogue et le calendrier, et propose 3 à 6 opportunités, chacune avec un canal :
fournisseur local, import Chine à étudier (transmis à l'expert Sourcing), ou pas maintenant.

Limites assumées : aucun concurrent ne publie ses ventes. Le tri « meilleures ventes » est le meilleur indice
public ; sans lui, on ne garde que les ruptures. L'expert ne cite aucun prix qui ne vient pas des relevés.
"""
import json
import os
import re
import statistics
import time
import unicodedata
from datetime import date
from pathlib import Path

from .. import bus, data, db, llm, scraper, telegram
from ..links import sales_links_enabled
from ..config import settings
from .base import Agent

WEB_SEARCH_TOOL = os.getenv("WEB_SEARCH_TOOL", "web_search_20260209")
_DEFAULT_SOURCES = Path(__file__).resolve().parents[3] / "data" / "tendances_sources.json"
CANAUX = ("fournisseur local", "import Chine à étudier", "pas maintenant")


def sources() -> list:
    p = Path(os.getenv("TENDANCES_SOURCES_PATH", "/app/data/tendances_sources.json"))
    return json.loads((p if p.exists() else _DEFAULT_SOURCES).read_text(encoding="utf-8"))["sources"]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn")).strip()


def signals(history: dict) -> list:
    """history = {date: [lignes tendances_snap]} (dates triées, la plus récente en dernier). Renvoie les signaux."""
    days = sorted(history)
    if not days:
        return []
    today, prev = days[-1], days[-8:-1]
    out = []
    by_key = lambda rows: {(r["site"], r["page"], r["pid"]): r for r in rows}
    cur = by_key(history[today])
    for key, r in cur.items():
        if r["tri"] != "ventes":
            continue
        top10_days = sum(1 for d in days[-7:] if any(x["rang"] <= 10 and (x["site"], x["page"], x["pid"]) == key and x["tri"] == "ventes"
                                                      for x in history[d]))
        if top10_days >= 5:
            out.append({"type": "best-seller stable", "force": 3, **_pub(r), "detail": f"top 10 des ventes {top10_days} jours sur 7"})
        elif r["rang"] <= 5 and prev and not any((x["site"], x["page"], x["pid"]) == key for d in prev for x in history[d]):
            out.append({"type": "nouvel entrant", "force": 2, **_pub(r), "detail": f"n°{r['rang']} des ventes, absent la semaine passée"})
    if len(days) >= 2:
        yday = by_key(history[days[-2]])
        for key, r in cur.items():
            y = yday.get(key)
            if y and y["en_stock"] and not r["en_stock"]:
                out.append({"type": "rupture", "force": 2, **_pub(r), "detail": "passé en rupture depuis hier (vendu)"})
    if len(days) >= 7:
        old = by_key(history[days[-7]])
        for key, r in cur.items():
            o = old.get(key)
            if o and o["prix"] and r["prix"] and r["prix"] <= o["prix"] * 0.9:
                out.append({"type": "baisse de prix", "force": 1, **_pub(r),
                            "detail": f"{o['prix']:.3f} → {r['prix']:.3f} DT en 7 jours"})
    return sorted(out, key=lambda s: (-s["force"], s.get("rang") or 99))


def _pub(r):
    return {"site": r["site"], "page": r["page"], "categorie": r["categorie"], "nom": r["nom"], "prix": r["prix"], "rang": r["rang"]}


def market_price(nom_ou_mots: str, rows: list):
    """Prix médian observé chez les concurrents pour les produits dont le nom contient tous les mots donnés."""
    mots = [m for m in norm(nom_ou_mots).split() if len(m) > 2]
    prix = [r["prix"] for r in rows if r["prix"] and mots and all(m in norm(r["nom"]) for m in mots)]
    return round(statistics.median(prix), 3) if prix else None


SYSTEM = """Tu es l'expert catégorie (category manager) de Dealz, boutique en ligne familiale tunisienne basée à Sfax.
Catalogue actuel : papeterie & scolaire, informatique & bureau ; petit électroménager et mobilier prévus mais SANS fournisseur.
Le père gère Office House (grossiste fournitures scolaires, entrepôt à Sfax) et Dartech (informatique & bureautique) : ce sont nos fournisseurs locaux naturels.

Ta mission : à partir des signaux de ventes des concurrents, des signaux terrain (captures de groupes Facebook envoyées par l'équipe : demandes, offres, intérêt) (données réelles ci-dessous), de notre catalogue et du calendrier,
dire QUOI vendre ensuite et PAR QUEL CANAL. Tu peux faire quelques recherches web pour comprendre la demande en Tunisie
(saisons, tendances, réglementation), mais :
- Les prix cités doivent venir des relevés fournis. N'invente aucun chiffre ; si tu ne sais pas, écris « inconnu ».
- Un « nouvel entrant » ou une « rupture » isolés sont des indices faibles : dis-le.
- Le petit électroménager, les jouets et la déco sont sur la liste BCT des importations « non prioritaires » (circulaire 2026-04) :
  import à financer à 100 % sur fonds propres. Pour une jeune boutique, préfère d'abord un fournisseur local, puis l'import une fois la demande prouvée.
- Sois direct : si rien ne vaut le coup cette semaine, dis-le.

Réponds UNIQUEMENT en JSON :
{"synthese": "3 phrases max",
 "opportunites": [{"produit": "type de produit précis (ex : friteuse à air 4-5 L)", "mots_cles": "2-3 mots pour retrouver les relevés",
   "categorie": "papeterie|cartables|informatique|petit_electro|mobilier|jouets_deco|autre",
   "canal": "fournisseur local|import Chine à étudier|pas maintenant", "score": 1-5,
   "pourquoi": "2 phrases", "preuves": ["signal ou source"], "risques": "1 phrase", "prochaine_action": "1 phrase"}]}"""


class TendancesAgent(Agent):
    name = "tendances"
    label = "Expert Tendances"

    def collect(self, client=None):
        """Relevé du jour (sans IA). Renvoie le nombre de produits relevés."""
        rows, own = [], client is None
        client = client or scraper.new_client()
        try:
            for s in sources():
                try:
                    items, tri = scraper.fetch_ranked(s["url"], client, cat=s["categorie"])
                except Exception as e:
                    self.log.warning("%s : %s", s["url"], e)
                    continue
                rows += [{"site": s["site"], "categorie": s["categorie"], "page": s["nom"], "tri": tri, **it} for it in items]
                time.sleep(settings.veille_delai)
        finally:
            if own:
                client.close()
        if rows:
            db.save_tendances(date.today().isoformat(), rows)
        return len(rows)

    def history(self, days=14):
        return {d: db.tendances_snapshot(d) for d in db.tendances_dates(days)}

    def run(self):
        """Quotidien : relevé + alerte sur les signaux forts. Aucun appel IA."""
        n = self.collect()
        sig = signals(self.history())
        strong = [s for s in sig if s["type"] in ("nouvel entrant", "best-seller stable") and (s["rang"] or 99) <= 3]
        for s in strong[:3]:
            self.alert("info", f"Ça se vend chez {s['site']} : {s['nom'][:70]}",
                       f"{s['type']} ({s['detail']}) — {s['page']}, {s['prix']:.3f} DT",
                       key=f"tend:{s['type']}:{s['site']}:{norm(s['nom'])[:60]}:{date.today().isocalendar()[1]}")
        return {"produits": n, "signaux": len(sig)}

    def analyse(self):
        """Hebdo : l'expert transforme les signaux en opportunités."""
        hist = self.history()
        if not hist:
            self.collect()
            hist = self.history()
        sig = signals(hist)
        last = hist[max(hist)] if hist else []
        tri_info = {(r["site"], r["page"]): r["tri"] for r in last}
        user = json.dumps({
            "signaux": sig[:40],
            "pages_suivies": [{"site": k[0], "page": k[1], "tri": v} for k, v in tri_info.items()],
            "top_du_jour": [_pub(r) for r in last if r["rang"] <= 10][:60],
            "notre_catalogue": data.stock_summary(), "temps_forts": data.upcoming_events(90),
            "signaux_terrain_30j": [{"resume": e["resume"], **{k: e["payload"].get(k) for k in ("type", "produit", "interet", "prix_affiche_tnd", "region")}}
                                    for e in bus.events("signal_terrain", days=30, limit=40)],
            "nos_ventes_28j": data.sales_summary(28) if sales_links_enabled() else "pas encore lancé",
        }, ensure_ascii=False, default=str)
        tools = [{"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": 3,
                  "user_location": {"type": "approximate", "country": "TN", "city": "Sfax", "timezone": "Africa/Tunis"}}]
        raw = llm.ask("tendances", SYSTEM, user, model=settings.model_smart, max_tokens=2500, tools=tools, tool_impl={})
        if getattr(raw, "simulated", False):
            body = "IA inactive : voici les signaux bruts.\n" + "\n".join(
                f"• [{s['type']}] {s['nom'][:60]} — {s['site']} {s['prix']:.3f} DT ({s['detail']})" for s in sig[:15])
            self.report("Tendances concurrents (signaux)", body or "Pas encore de relevé.")
            return {"opportunites": 0}
        m = re.search(r"\{[\s\S]*\}", raw or "")
        try:
            res = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            res = {}
        saved = []
        for o in res.get("opportunites", [])[:6]:
            if not o.get("produit"):
                continue
            canal = o.get("canal") if o.get("canal") in CANAUX else "pas maintenant"
            prix = market_price(o.get("mots_cles") or o["produit"], last)   # prix tiré des relevés, jamais du modèle
            oid = db.add_opportunite({"agent": self.label, "produit": o["produit"][:120], "categorie": o.get("categorie", "autre"),
                                      "canal": canal, "score": max(1, min(5, int(o.get("score") or 3))),
                                      "pourquoi": f"{o.get('pourquoi', '')} Risques : {o.get('risques', '')} → {o.get('prochaine_action', '')}"[:900],
                                      "preuves": o.get("preuves", [])[:6], "prix_marche": prix,
                                      "statut": "a_etudier" if canal == "import Chine à étudier" else "nouveau",
                                      "dedupe": "opp:" + norm(o["produit"])[:80]})
            saved.append((oid, o, canal, prix))
        lines = [res.get("synthese", "")]
        for oid, o, canal, prix in saved:
            lines.append(f"\n#{oid} {'★' * int(o.get('score') or 3)} {o['produit']} — {canal}"
                         f"{f' (prix marché ~{prix:.3f} DT)' if prix else ''}\n{o.get('pourquoi', '')}\nÀ faire : {o.get('prochaine_action', '')}")
        lines.append("\nImport à chiffrer : /sourcing <id>  ·  liste : /opportunites")
        self.report("Expert Tendances — opportunités de la semaine", "\n".join(lines))
        return {"opportunites": len(saved)}
