"""Agent Achats & stock — tous les jours.

Règles : ruptures, stock bas, marge sous le seuil, couverture de stock selon les ventes des 30 derniers jours.
Claude (modèle rapide) rédige ensuite la commande de réassort à envoyer au fournisseur, en français simple.
"""
import json
from collections import Counter
from datetime import date

from .. import llm
from ..config import settings
from ..woo import meta, to_float
from .base import Agent, get_woo

SYSTEM = """Tu es l'acheteur de Dealz (Sfax). On te donne les produits en rupture, en stock bas et à marge faible,
avec les ventes des 30 derniers jours. Rédige en français :
1) la commande de réassort à envoyer au fournisseur (tableau court : produit, quantité proposée, pourquoi) ;
2) 1 à 3 actions sur les prix ou les marges.
Quantité proposée = de quoi couvrir 45 jours de ventes, minimum 10. N'invente aucun chiffre."""


class StockAgent(Agent):
    name = "stock"
    label = "Achats & stock"

    def run(self):
        woo = get_woo()
        if not woo:
            self.log.info("WooCommerce non configuré : agent stock ignoré")
            return None
        today = date.today().isoformat()
        products = [p for p in woo.products(status="publish") if p.get("type") == "simple"]
        sold = Counter()
        for o in woo.orders_last_days(30):
            if o.get("status") in ("cancelled", "failed", "refunded"):
                continue
            for li in o.get("line_items", []):
                sold[li.get("product_id")] += int(li.get("quantity", 0))

        rupture, bas, marge = [], [], []
        for p in products:
            stock = p.get("stock_quantity")
            prix = to_float(p.get("price"))
            achat = to_float(meta(p, "_cout_achat"), None)
            row = {"id": p["id"], "produit": p["name"], "stock": stock, "ventes_30j": sold.get(p["id"], 0),
                   "fournisseur": meta(p, "_fournisseur", "?")}
            if p.get("manage_stock") and stock is not None:
                if stock <= 0:
                    rupture.append(row)
                elif stock < settings.seuil_stock_bas or (row["ventes_30j"] and stock < row["ventes_30j"]):
                    bas.append(row)
            if achat and prix:
                m = (prix - achat) / prix * 100
                if m < settings.seuil_marge_pct:
                    marge.append({**row, "prix": prix, "achat": achat, "marge_pct": round(m, 1)})

        from .. import bus
        for r in bas:   # stock pour moins de 15 jours de ventes : on prévient les autres agents
            if r["ventes_30j"] and r["stock"] is not None and r["stock"] < r["ventes_30j"] / 2:
                bus.publish("rupture_proche", self.label, f"{r['produit']} : {r['stock']} en stock pour {r['ventes_30j']} ventes/30 j",
                            r, key=f"rupture-proche:{r['id']}:{date.today().isocalendar()[1]}")
        for r in rupture:
            if r["ventes_30j"] > 0:
                self.alert("critique", f"Rupture : {r['produit']}",
                           f"0 en stock alors qu'il s'en est vendu {r['ventes_30j']} en 30 jours. Fournisseur : {r['fournisseur']}.",
                           key=f"rupture:{today}:{r['id']}")
        if not (rupture or bas or marge):
            return {"rupture": 0, "bas": 0, "marge": 0}

        data = {"ruptures": rupture[:40], "stock_bas": bas[:40], "marge_faible": marge[:40]}
        text = llm.ask(self.name, SYSTEM, json.dumps(data, ensure_ascii=False), max_tokens=900)
        body = f"{len(rupture)} rupture(s), {len(bas)} stock(s) bas, {len(marge)} marge(s) sous {settings.seuil_marge_pct:.0f} %."
        if getattr(text, "simulated", False):
            body += "\n\nÀ réassortir : " + ", ".join(r["produit"] for r in (rupture + bas)[:15])
        else:
            body += "\n\n" + text
        self.report(f"Stock et marges du {today}", body)
        return {"rupture": len(rupture), "bas": len(bas), "marge": len(marge)}
