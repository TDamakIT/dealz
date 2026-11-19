"""Synthèses de données partagées par les agents (et outils proposés à Claude)."""
from collections import Counter
from datetime import date, timedelta

from . import db
from .config import TEMPS_FORTS, settings
from .scraper import SOURCE
from .woo import meta, to_float
from .agents.base import get_woo


def sales_summary(days: int = 7) -> dict:
    woo = get_woo()
    if not woo:
        return {"disponible": False, "raison": "WooCommerce non configuré"}
    orders = [o for o in woo.orders_last_days(days) if o.get("status") not in ("cancelled", "failed", "refunded")]
    by_product = Counter()
    ca = 0.0
    for o in orders:
        ca += to_float(o.get("total"))
        for li in o.get("line_items", []):
            by_product[li.get("name")] += int(li.get("quantity", 0))
    cod = [o for o in orders if o.get("payment_method") == "cod"]
    return {"jours": days, "commandes": len(orders), "chiffre_affaires_dt": round(ca, 3),
            "panier_moyen_dt": round(ca / len(orders), 3) if orders else 0,
            "part_paiement_livraison": round(len(cod) / len(orders) * 100) if orders else None,
            "top_produits": by_product.most_common(10)}


def stock_summary() -> dict:
    woo = get_woo()
    if not woo:
        return {"disponible": False}
    rupt, bas, marges = [], [], []
    for p in woo.products(status="publish"):
        st = p.get("stock_quantity")
        if p.get("manage_stock") and st is not None:
            if st <= 0:
                rupt.append(p["name"])
            elif st < settings.seuil_stock_bas:
                bas.append(p["name"])
        achat, prix = to_float(meta(p, "_cout_achat"), None), to_float(p.get("price"))
        if achat and prix:
            marges.append((prix - achat) / prix * 100)
    return {"ruptures": rupt[:30], "stock_bas": bas[:30],
            "marge_moyenne_pct": round(sum(marges) / len(marges), 1) if marges else None}


def veille_summary() -> dict:
    dates = db.veille_dates(SOURCE)
    if not dates:
        return {"disponible": False, "raison": "aucun relevé pour l'instant"}
    last = dates[-1]
    segs = db.veille_segments(last, SOURCE)
    prev = {}
    old = [d for d in dates if d <= (date.fromisoformat(last) - timedelta(days=7)).isoformat()]
    if old:
        prev = {(s["type"], s["gamme"]): s["prix_median"] for s in db.veille_segments(old[-1], SOURCE)}
    return {"source": SOURCE, "date": last, "segments": [
        {"type": s["type"], "gamme": s["gamme"], "modeles": s["modeles"], "median": s["prix_median"],
         "variation_7j_pct": round((s["prix_median"] - prev[(s["type"], s["gamme"])]) / prev[(s["type"], s["gamme"])] * 100, 1)
         if prev.get((s["type"], s["gamme"])) else None}
        for s in segs if s["modeles"] >= 5]}


def upcoming_events(days: int = 60) -> list:
    today = date.today()
    out = []
    for e in TEMPS_FORTS:
        d0, d1 = date.fromisoformat(e["debut"]), date.fromisoformat(e["fin"])
        if d1 >= today and (d0 - today).days <= days:
            out.append({**e, "dans_jours": max(0, (d0 - today).days)})
    return sorted(out, key=lambda e: e["debut"])


def search_products(texte: str = "", limite: int = 20) -> list:
    woo = get_woo()
    if not woo:
        return []
    res = woo.get("products", search=texte, per_page=min(limite, 50))
    return [{"id": p["id"], "nom": p["name"], "prix": to_float(p.get("price")), "stock": p.get("stock_quantity"),
             "achat": to_float(meta(p, "_cout_achat"), None), "statut": p.get("status")} for p in res]


TOOLS = [
    {"name": "ventes", "description": "Résumé des ventes Dealz sur N jours : commandes, CA, panier moyen, top produits.",
     "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "default": 7}}}},
    {"name": "stock", "description": "Ruptures, stocks bas et marge moyenne du catalogue Dealz.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "veille", "description": "Prix médians des PC chez Tunisianet (dernier relevé) et variation sur 7 jours.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "temps_forts", "description": "Temps forts commerciaux à venir (Ramadan, Aïd, rentrée, Black Friday…).",
     "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "default": 60}}}},
    {"name": "chercher_produits", "description": "Cherche des produits du catalogue Dealz (prix, stock, prix d'achat).",
     "input_schema": {"type": "object", "properties": {"texte": {"type": "string"}, "limite": {"type": "integer", "default": 20}}}},
    {"name": "alertes_recentes", "description": "Les 20 dernières alertes émises par les agents.",
     "input_schema": {"type": "object", "properties": {}}},
]
TOOL_IMPL = {
    "ventes": lambda days=7: sales_summary(days),
    "stock": lambda: stock_summary(),
    "veille": lambda: veille_summary(),
    "temps_forts": lambda days=60: upcoming_events(days),
    "chercher_produits": lambda texte="", limite=20: search_products(texte, limite),
    "alertes_recentes": lambda: [{k: a[k] for k in ("ts", "agent", "level", "title")} for a in db.recent_alerts(20)],
}
