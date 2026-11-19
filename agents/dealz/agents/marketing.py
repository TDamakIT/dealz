"""Agent Marketing — chaque dimanche soir.

Regarde les temps forts des 6 prochaines semaines, les produits en stock avec une bonne marge et la veille,
puis propose 3 publications Facebook/Instagram (en derja + français) à valider par l'équipe.
Rien n'est publié automatiquement : l'agent propose, un humain valide.
"""
import json

from .. import data, db, llm
from ..woo import meta, to_float
from .base import Agent, get_woo

SYSTEM = """Tu es le community manager de Dealz, boutique en ligne tunisienne (Sfax, livraison partout en Tunisie).
Ton : chaleureux, drôle, local. Écris en derja tunisienne (lettres arabes) avec une ligne en français.
Propose exactement 3 publications pour la semaine. Pour chacune :
- Jour et heure conseillés
- Accroche (derja), texte (derja, 3 lignes max), version française (1 ligne)
- Visuel ou vidéo à faire (une phrase)
- Produit(s) mis en avant, avec le prix fourni
Jamais de fausse promotion, de faux avis ou de fausse urgence. N'utilise que les prix et produits fournis.
Si des priorités de la semaine, des lancements validés ou des angles conseillés sont fournis, centre les publications dessus.
Ne mets jamais en avant un produit de « ne_pas_mettre_en_avant »."""


class MarketingAgent(Agent):
    name = "marketing"
    label = "Marketing"

    def run(self):
        produits = []
        woo = get_woo()
        if woo:
            for p in woo.products(status="publish", stock_status="instock"):
                achat, prix = to_float(meta(p, "_cout_achat"), None), to_float(p.get("price"))
                if achat and prix and (prix - achat) / prix >= 0.30:
                    produits.append({"nom": p["name"], "prix": prix})
        from ..links import recent
        ne_pas = {x["produit"] for x in recent("marketing_ne_pas_pousser", 14)}
        prio = (db.get_state("priorites") or {}).get("priorites", [])
        ctx = {"temps_forts": data.upcoming_events(42), "produits_bonne_marge": [p for p in produits if p["nom"] not in ne_pas][:25],
               "ventes_7j": data.sales_summary(7), "priorites_de_la_semaine": prio,
               "lancements_valides": recent("marketing_lancements"), "angles_conseilles": recent("marketing_angles"),
               "ne_pas_mettre_en_avant": sorted(ne_pas)}
        text = llm.ask(self.name, SYSTEM, json.dumps(ctx, ensure_ascii=False, default=str), max_tokens=1200)
        if getattr(text, "simulated", False):
            text = f"{text}\n\nTemps forts à préparer : " + (", ".join(e["nom"] for e in ctx["temps_forts"]) or "aucun")
        self.report("Idées de publications de la semaine (à valider)", text)
        return text

    def launch(self, produit, prix_marche=None):
        """Lien « opportunité validée » : 3 publications de lancement, à valider."""
        ctx = {"lancement": produit, "prix_marche_concurrents": prix_marche,
               "consigne": "Notre prix n'est pas encore fixé : écris [PRIX] à la place. Teaser, lancement, preuve/usage."}
        text = llm.ask("marketing-lancement", SYSTEM, json.dumps(ctx, ensure_ascii=False, default=str), max_tokens=1000)
        if getattr(text, "simulated", False):
            text = (f"{text}\n\nTrame : 1) teaser « جديد في Dealz… » ; 2) lancement de {produit} à [PRIX] avec livraison partout en Tunisie ; "
                    "3) vidéo courte du produit en usage.")
        self.report(f"Lancement : {produit} — publications à valider", text)
        return text
