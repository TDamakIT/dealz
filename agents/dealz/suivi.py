"""Données des pages Commandes, Prix et Marges du tableau de bord (sans IA).

Les produits viennent de WooCommerce ; tant que la boutique n'est pas connectée, du catalogue local
(data/catalog.json, fictif) pour que les pages Prix et Marges restent lisibles.
"""
import html
import time
import unicodedata
from datetime import datetime, timezone

from . import db
from .agents.base import get_woo
from .agents.commandes import normalize_phone, risk, wa_link
from .catalog import load_catalog
from .config import settings
from .scraper import SOURCE
from .woo import meta, to_float

ANNULEES = ("cancelled", "failed", "refunded")
_cache = {}


def _cached(key, ttl, fn):
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (time.monotonic(), val)
    return val


def clear_cache():
    _cache.clear()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


# --- Produits ---------------------------------------------------------------

def _from_woo(p):
    cats = p.get("categories") or [{}]
    return {"id": p["id"], "sku": p.get("sku", ""), "nom": html.unescape(p.get("name", "")),
            "categorie": html.unescape(cats[0].get("name", "")), "prix": to_float(p.get("price")),
            "achat": to_float(meta(p, "_cout_achat"), None), "stock": p.get("stock_quantity"),
            "fournisseur": meta(p, "_fournisseur", "") or "", "veille_gamme": meta(p, "_veille_gamme", "") or "",
            "principal": p.get("catalog_visibility", "visible") != "hidden"}


def _from_catalog():
    from .tools.import_catalog import VEILLE_GAMME
    out = []
    for p in load_catalog()["produits"]:
        if p.get("bientot"):
            continue
        out.append({"id": p["id"], "sku": p["id"], "nom": p["nom"], "categorie": p["categorie"],
                    "prix": p["prix_vente"], "achat": p["prix_achat"], "stock": p["stock"],
                    "fournisseur": p["fournisseur"], "veille_gamme": VEILLE_GAMME.get(p["nom"], ""),
                    "principal": p.get("famille", p["id"]) == p["id"]})
    return out


def produits():
    """(source, liste de produits normalisés). source = 'boutique' ou 'catalogue'."""
    woo = get_woo()
    if not woo:
        return "catalogue", _from_catalog()
    return "boutique", _cached("produits", 120, lambda: [
        _from_woo(p) for p in woo.products(status="publish") if p.get("type", "simple") == "simple"])


def marge(prix, achat):
    if not prix or achat is None:
        return None, None
    return round(prix - achat, 3), round((prix - achat) / prix * 100, 1)


# --- Commandes --------------------------------------------------------------

def etape(o) -> str:
    st = o.get("status")
    if st in ANNULEES:
        return "annulée"
    if st == "completed":
        return "livrée"
    if meta(o, "_dealz_confirmee") == "oui":
        return "confirmée"
    return "à confirmer"


def commandes(jours=30, now=None):
    """Commandes des N derniers jours avec étape, score de risque, lien WhatsApp et marge estimée."""
    woo = get_woo()
    if not woo:
        return None
    now = now or datetime.now(timezone.utc)
    orders = woo.orders_last_days(jours)
    couts = {p["id"]: p["achat"] for p in produits()[1]}
    par_tel = {}
    for o in orders:
        par_tel.setdefault(normalize_phone(o.get("billing", {}).get("phone", "")), []).append(o["id"])
    out = []
    for o in orders:
        b = o.get("billing", {})
        tel = normalize_phone(b.get("phone", ""))
        score, why = risk(o, len([i for i in par_tel.get(tel, []) if i != o["id"]]))
        created = o.get("date_created_gmt")
        age_h = (now - datetime.fromisoformat(created).replace(tzinfo=timezone.utc)).total_seconds() / 3600 if created else 0
        step = etape(o)
        cout, complet = 0.0, True
        for li in o.get("line_items", []):
            c = couts.get(li.get("product_id"))
            if c is None:
                complet = False
            else:
                cout += c * int(li.get("quantity", 0))
        ventes = sum(to_float(li.get("total")) for li in o.get("line_items", []))
        out.append({"id": o["id"], "numero": o.get("number"), "date": (created or "")[:16].replace("T", " "),
                    "client": f"{b.get('first_name', '')} {b.get('last_name', '')}".strip(),
                    "gouvernorat": b.get("state") or b.get("city") or "", "telephone": b.get("phone", ""),
                    "total": to_float(o.get("total")), "paiement": o.get("payment_method_title") or o.get("payment_method", ""),
                    "articles": sum(int(li.get("quantity", 0)) for li in o.get("line_items", [])),
                    "etape": step, "score": score, "raisons": why, "wa": wa_link(o) if tel else "",
                    "en_retard": step == "à confirmer" and age_h > 24, "age_h": round(age_h),
                    "marge": round(ventes - cout, 3) if complet and o.get("line_items") else None})
    return sorted(out, key=lambda r: r["date"], reverse=True)


def changer_etape(order_id: int, action: str) -> str:
    """Confirmée / annulée / livrée depuis le tableau de bord. Ajoute une note dans WooCommerce."""
    woo = get_woo()
    if not woo:
        raise RuntimeError("WooCommerce n'est pas configuré.")
    if action == "confirmee":
        woo.put(f"orders/{order_id}", {"meta_data": [{"key": "_dealz_confirmee", "value": "oui"}]})
        note = "Confirmée par le client (tableau de bord Dealz)."
    elif action == "annulee":
        woo.put(f"orders/{order_id}", {"status": "cancelled"})
        note = "Annulée depuis le tableau de bord Dealz."
    elif action == "livree":
        woo.put(f"orders/{order_id}", {"status": "completed"})
        note = "Livrée (tableau de bord Dealz)."
    else:
        raise ValueError("Action inconnue")
    woo.post(f"orders/{order_id}/notes", {"note": note, "customer_note": False})
    return note


# --- Prix -------------------------------------------------------------------

def comparer_gammes():
    """Nos PC rattachés à une gamme de la veille, comparés à la médiane du marché."""
    dates = db.veille_dates(SOURCE)
    if not dates:
        return None, []
    by = {f"{s['type']}|{s['gamme']}": s for s in db.veille_segments(dates[-1], SOURCE)}
    out = []
    for p in produits()[1]:
        s = by.get(p["veille_gamme"])
        if not s or not p["prix"]:
            continue
        ecart = (p["prix"] - s["prix_median"]) / s["prix_median"] * 100
        out.append({**p, "gamme": p["veille_gamme"].replace("|", " · "), "min": s["prix_min"], "median": s["prix_median"],
                    "max": s["prix_max"], "modeles": s["modeles"], "ecart_pct": round(ecart, 1),
                    "trop_cher": ecart > settings.seuil_prix_pct})
    return dates[-1], sorted(out, key=lambda r: -r["ecart_pct"])


def _match(q, nom):
    mots = norm(q).split()
    n = norm(nom)
    return bool(mots) and all(m in n for m in mots)


def rechercher(q: str, limite=40):
    """Cherche un produit chez nous et chez les concurrents (derniers relevés veille + tendances)."""
    if not q.strip():
        return [], []
    nous = [p for p in produits()[1] if _match(q, p["nom"])][:limite]
    eux = []
    dates = db.veille_dates(SOURCE)
    if dates:
        with db.conn() as c:
            rows = c.execute("SELECT source site, nom, prix, en_stock, date FROM veille_items WHERE date=?", (dates[-1],)).fetchall()
        eux += [dict(r) for r in rows if _match(q, r["nom"])]
    tdays = db.tendances_dates(1)
    if tdays:
        eux += [{"site": r["site"], "nom": r["nom"], "prix": r["prix"], "en_stock": r["en_stock"], "date": r["date"]}
                for r in db.tendances_snapshot(tdays[0]) if _match(q, r["nom"])]
    seen, uniq = set(), []
    for r in sorted(eux, key=lambda r: r["prix"]):
        k = (r["site"], r["nom"])
        if k not in seen:
            seen.add(k); uniq.append(r)
    return nous, uniq[:limite]


# --- Marges -----------------------------------------------------------------

def marges():
    source, prods = produits()
    rows = []
    for p in prods:
        m_dt, m_pct = marge(p["prix"], p["achat"])
        rows.append({**p, "marge_dt": m_dt, "marge_pct": m_pct,
                     "valeur_stock": round(p["achat"] * p["stock"], 3) if p["achat"] is not None and p["stock"] else 0.0})
    avec = [r for r in rows if r["marge_pct"] is not None]
    cats = {}
    for r in avec:
        c = cats.setdefault(r["categorie"] or "—", {"categorie": r["categorie"] or "—", "produits": 0, "ca": 0.0, "achat": 0.0,
                                                     "faibles": 0, "valeur_stock": 0.0})
        c["produits"] += 1
        c["ca"] += r["prix"]; c["achat"] += r["achat"]
        c["faibles"] += r["marge_pct"] < settings.seuil_marge_pct
        c["valeur_stock"] += r["valeur_stock"]
    for c in cats.values():
        c["marge_pct"] = round((c["ca"] - c["achat"]) / c["ca"] * 100, 1) if c["ca"] else None
    return {"source": source, "produits": rows,
            "categories": sorted(cats.values(), key=lambda c: c["marge_pct"] or 0),
            "moyenne_pct": round(sum(r["marge_pct"] for r in avec) / len(avec), 1) if avec else None,
            "faibles": sorted([r for r in avec if r["marge_pct"] < settings.seuil_marge_pct], key=lambda r: r["marge_pct"]),
            "sans_cout": len(rows) - len(avec),
            "valeur_stock": round(sum(r["valeur_stock"] for r in rows), 3),
            "realisee": marge_realisee(prods)}


def marge_realisee(prods, jours=30):
    """Marge réellement faite sur les commandes non annulées des N derniers jours (si la boutique est branchée)."""
    woo = get_woo()
    if not woo:
        return None
    couts = {p["id"]: p["achat"] for p in prods}
    ca = cout = 0.0
    n = inconnus = 0
    for o in woo.orders_last_days(jours):
        if o.get("status") in ANNULEES:
            continue
        n += 1
        for li in o.get("line_items", []):
            c = couts.get(li.get("product_id"))
            if c is None:
                inconnus += 1
                continue
            ca += to_float(li.get("total"))
            cout += c * int(li.get("quantity", 0))
    return {"jours": jours, "commandes": n, "ca": round(ca, 3), "marge": round(ca - cout, 3),
            "marge_pct": round((ca - cout) / ca * 100, 1) if ca else None, "lignes_sans_cout": inconnus}
