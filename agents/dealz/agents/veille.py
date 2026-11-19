"""Agent Veille prix — tous les matins.

1. Relève les PC de Tunisianet et calcule les prix par gamme.
2. Compare à la veille : alerte si une médiane bouge de plus de 5 %.
3. Compare nos produits (méta _veille_gamme) à la médiane du marché : alerte si on est trop cher.
4. Demande à Claude (modèle rapide) 3 lignes de lecture et une opportunité éventuelle.
"""
import json
from datetime import date

from .. import db, llm
from ..config import settings
from ..scraper import SOURCE, scrape
from ..segments import aggregate
from ..woo import meta, to_float
from .base import Agent, get_woo

SYSTEM = """Tu es l'analyste veille prix de Dealz, boutique en ligne tunisienne (Sfax) qui vend papeterie, informatique et bureau.
On te donne les prix médians des PC chez Tunisianet aujourd'hui, leur évolution depuis le dernier relevé, et nos propres prix.
Écris en français, 5 lignes maximum, sans formule de politesse :
- ce qui a bougé et ce que ça veut dire pour nous ;
- UNE opportunité concrète s'il y en a une (gamme où le marché monte, gamme peu fournie, prix à ajuster), sinon dis qu'il n'y en a pas.
N'invente aucun chiffre : utilise seulement ceux fournis."""


class VeilleAgent(Agent):
    name = "veille"
    label = "Veille prix"

    def __init__(self, scraper=scrape):
        super().__init__()
        self.scraper = scraper

    def run(self):
        today = date.today().isoformat()
        items = self.scraper()
        if len(items) < 50:
            self.alert("important", "Veille prix : relevé incomplet",
                       f"Seulement {len(items)} PC relevés. Le site a peut-être changé ou bloque le relevé.",
                       key=f"veille-incomplet:{today}")
            if not items:
                return None
        segs = aggregate(items)
        db.save_veille(today, SOURCE, items, segs)

        dates = [d for d in db.veille_dates(SOURCE) if d < today]
        prev = {(s["type"], s["gamme"]): s for s in db.veille_segments(dates[-1], SOURCE)} if dates else {}
        moves = []
        for s in segs:
            p = prev.get((s["type"], s["gamme"]))
            if p and p["prix_median"] and s["modeles"] >= 5:
                pct = (s["median"] - p["prix_median"]) / p["prix_median"] * 100
                if abs(pct) >= 5:
                    moves.append({**s, "median_avant": p["prix_median"], "variation_pct": round(pct, 1)})
        for m in moves:
            self.alert("info", f"{m['type']} {m['gamme']} : médiane {m['variation_pct']:+.1f} %",
                       f"Tunisianet : {m['median_avant']:.0f} → {m['median']:.0f} DT ({m['modeles']} modèles).",
                       key=f"veille-move:{today}:{m['type']}:{m['gamme']}")

        ours = self.compare_ours(segs, today)
        summary = {"date": today, "pc_releves": len(items),
                   "segments": [{k: s[k] for k in ("type", "gamme", "modeles", "median")} for s in segs if s["modeles"] >= 5],
                   "variations": moves, "nos_prix": ours}
        text = llm.ask(self.name, SYSTEM, json.dumps(summary, ensure_ascii=False), max_tokens=500)
        body = f"{len(items)} PC relevés, {len(segs)} gammes. {len(moves)} variation(s) notable(s)."
        if not getattr(text, "simulated", False):
            body += "\n\n" + text
        self.report(f"Veille prix du {today}", body, notify=bool(moves or ours))
        return summary

    def compare_ours(self, segs, today):
        woo = get_woo()
        if not woo:
            return []
        by = {f"{s['type']}|{s['gamme']}": s for s in segs}
        out = []
        for p in woo.products(status="publish"):
            g = meta(p, "_veille_gamme")
            if not g or g not in by:
                continue
            ref = by[g]
            prix = to_float(p.get("price"))
            ecart = (prix - ref["median"]) / ref["median"] * 100
            out.append({"produit": p["name"], "notre_prix": prix, "median_marche": ref["median"], "ecart_pct": round(ecart, 1)})
            if ecart > settings.seuil_prix_pct:
                from .. import bus
                bus.publish("prix_concurrent", self.label, f"{p['name']} : {ecart:.0f} % au-dessus du marché",
                            {"id": p["id"], "produit": p["name"], "notre_prix": prix, "median_marche": ref["median"],
                             "cout_achat": to_float(meta(p, "_cout_achat"), None), "gamme": g},
                            key=f"prix:{today}:{p['id']}")
                self.alert("important", f"Trop cher : {p['name']}",
                           f"Notre prix {prix:.3f} DT est {ecart:.0f} % au-dessus de la médiane Tunisianet ({ref['median']:.0f} DT) pour {g}.",
                           key=f"trop-cher:{today}:{p['id']}")
        return out
