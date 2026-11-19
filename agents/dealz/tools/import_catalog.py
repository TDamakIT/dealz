"""Import du catalogue fictif dans WooCommerce (relançable sans créer de doublons).

  docker compose exec agents python -m dealz.tools.import_catalog

Crée : la zone de livraison Tunisie (7 DT, offerte dès 150 DT), les rayons et catégories,
les produits (les produits « bientôt » restent en brouillon) et les packs / coffrets.
"""
import html
import json
import os
import sys
from pathlib import Path

from ..catalog import load_catalog
from ..woo import Woo

VEILLE_GAMME = {
    "Ordinateur portable 15,6 pouces (étudiant)": "Portable|i3 / Core 3 / Ryzen 3",
    "Ordinateur portable 14 pouces (bureau)": "Portable|i5 / Core 5 / Ultra 5 / Ryzen 5",
}


def ensure_shipping(woo: Woo):
    zones = woo.get("shipping/zones")
    zone = next((z for z in zones if z["name"] == "Tunisie"), None)
    if zone:
        print("Zone de livraison Tunisie : déjà là")
        return
    zone = woo.post("shipping/zones", {"name": "Tunisie"})
    woo.put(f"shipping/zones/{zone['id']}/locations", [{"code": "TN", "type": "country"}])
    woo.post(f"shipping/zones/{zone['id']}/methods",
             {"method_id": "flat_rate", "settings": {"title": "Livraison à domicile (48 à 72 h)", "cost": "7"}})
    woo.post(f"shipping/zones/{zone['id']}/methods",
             {"method_id": "free_shipping", "settings": {"title": "Livraison offerte", "requires": "min_amount", "min_amount": "150"}})
    print("Zone de livraison Tunisie : créée (7 DT, offerte dès 150 DT)")


def ensure_categories(woo: Woo, cat: dict) -> dict:
    # WooCommerce renvoie « Papeterie &amp; scolaire » : on compare les noms décodés
    existing = {html.unescape(c["name"]): c["id"] for c in woo.get_all("products/categories", hide_empty=False)}

    def get_or_create(name, parent=0):
        if name in existing:
            return existing[name]
        try:
            c = woo.post("products/categories", {"name": name, "parent": parent})
            existing[name] = c["id"]
        except RuntimeError as e:   # déjà là sous un autre libellé : WooCommerce donne son identifiant
            m = __import__("re").search(r'"resource_id":(\d+)', str(e))
            if not m:
                raise
            existing[name] = int(m.group(1))
        return existing[name]

    ids = {}
    rub_ids = {r["id"]: get_or_create(r["nom"]) for r in cat["rubriques"]}
    for p in cat["produits"]:
        ids.setdefault(p["categorie"], get_or_create(p["categorie"], rub_ids[p["rubrique"]]))
    ids["__rentree"] = get_or_create("Packs rentrée")
    ids["__cadeaux"] = get_or_create("Idées cadeaux")
    print(f"Catégories : {len(existing)}")
    return ids


PHOTOS_DIR = Path(os.getenv("PHOTOS_DIR", "/app/data/photos-demo"))


def ensure_photos(woo: Woo) -> dict:
    """Envoie une fois les photos de démo dans la médiathèque. Renvoie {nom: id_media}."""
    ids = {}
    if not PHOTOS_DIR.exists():
        print("Photos de démo : dossier absent, produits sans photo")
        return ids
    for f in sorted(PHOTOS_DIR.glob("*.png")):
        nom = f"dealz-demo-{f.stem}"
        found = [m for m in woo.find_media(nom) if m.get("slug", "").startswith(nom)]
        ids[f.stem] = found[0]["id"] if found else woo.upload_media(f, f"{nom}.png")["id"]
    print(f"Photos de démo : {len(ids)}")
    return ids


def photo_for(p):
    """Photo de démo selon le type d'article (seulement pour les familles qu'on a photographiées)."""
    n, g, gm = p["nom"].lower(), p.get("genre", "mixte"), p.get("gamme", "standard")
    if "cartable" in n or "sac à dos" in n:
        if g in ("fille", "garcon"):
            return f"cartable-{g}"
        return {"eco": "cartable-eco", "premium": "cartable-premium"}.get(gm, "cartable-mixte")
    if "trousse" in n or "plumier" in n:
        return "trousse-fille" if g == "fille" else "trousse-garcon"
    if "stylo" in n:
        return f"stylo-{gm}"
    if "cahier" in n and "textes" not in n and "protège" not in n:
        return f"cahier-{gm}"
    return None


def product_payload(p, cat_ids, photos=None):
    meta = [{"key": "_cout_achat", "value": f"{p['prix_achat']:.3f}"},
            {"key": "_fournisseur", "value": p["fournisseur"]},
            {"key": "_nom_ar", "value": p["nom_ar"]},
            {"key": "_famille", "value": p.get("famille", p["id"])},
            {"key": "_gamme", "value": p.get("gamme", "standard")},
            {"key": "_genre", "value": p.get("genre", "mixte")},
            {"key": "_choix", "value": p.get("choix", "parent")}]
    if p["nom"] in VEILLE_GAMME:
        meta.append({"key": "_veille_gamme", "value": VEILLE_GAMME[p["nom"]]})
    payload = {"name": p["nom"], "type": "simple", "sku": p["id"], "regular_price": f"{p['prix_vente']:.3f}",
               "manage_stock": True, "stock_quantity": p["stock"], "status": "draft" if p["bientot"] else "publish",
               # les modèles d'une famille n'encombrent pas la boutique : ils sont sur la fiche du produit principal
               "catalog_visibility": "visible" if p.get("famille", p["id"]) == p["id"] else "hidden",
               "short_description": f"<p dir='rtl'>{p['nom_ar']}</p><p><em>Produit et prix fictifs (démo).</em></p>",
               "categories": [{"id": cat_ids[p["categorie"]]}], "meta_data": meta}
    key = photo_for(p)
    if photos and key in photos:
        payload["images"] = [{"id": photos[key]}]
    return payload


def pack_payload(pk, cat, cat_ids):
    by = {p["id"]: p for p in cat["produits"]}
    items = "".join(f"<li>{i['qte']} × {by[i['id']]['nom']}</li>" for i in pk["items"])
    return {"name": pk["nom"], "type": "simple", "sku": pk["id"], "regular_price": f"{pk['prix_pack']:.3f}",
            "manage_stock": False, "status": "publish",
            "description": f"<p>Contenu du pack :</p><ul>{items}</ul><p><em>Prix fictif (démo).</em></p>",
            "short_description": f"<p>{pk['niveau']} — {len(pk['items'])} références, {pk['prix_detail'] - pk['prix_pack']:.3f} DT d'économie.</p>",
            "categories": [{"id": cat_ids["__rentree" if pk["type"] == "rentree" else "__cadeaux"]}],
            "meta_data": [{"key": "_cout_achat", "value": f"{pk['cout_achat']:.3f}"},
                          {"key": "_pack_items", "value": json.dumps(pk["items"])},
                          {"key": "_nom_ar", "value": pk["nom_ar"]}]}


def main():
    woo = Woo()
    cat = load_catalog()
    ensure_shipping(woo)
    cat_ids = ensure_categories(woo, cat)
    photos = ensure_photos(woo)
    existing = {p["sku"]: p["id"] for p in woo.products(status="any") if p.get("sku")}
    payloads = [product_payload(p, cat_ids, photos) for p in cat["produits"]] + [pack_payload(pk, cat, cat_ids) for pk in cat["packs"]]
    create = [x for x in payloads if x["sku"] not in existing]
    update = [{**x, "id": existing[x["sku"]]} for x in payloads if x["sku"] in existing]
    errors = []
    for key, rows in (("create", create), ("update", update)):
        for i in range(0, len(rows), 50):
            res = woo.post("products/batch", {key: rows[i:i + 50]})
            errors += [r["error"].get("message", "?") for r in res.get(key, []) if r.get("error")]
    print(f"Produits : {len(create)} créés, {len(update)} mis à jour, {len(errors)} erreur(s)")
    for e in errors[:10]:
        print("  -", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
