from datetime import datetime, timedelta, timezone

from conftest import FakeWoo
from dealz import db, llm
from dealz.agents import base, liste
from dealz.agents.commandes import CommandesAgent, confirmation_message, normalize_phone, risk
from dealz.agents.stock import StockAgent
from dealz.agents.veille import VeilleAgent
from dealz.scraper import parse_listing, parse_price
from dealz.segments import aggregate, gamme

HTML = """<html><body><div>Il y a 849 produits.</div>
<article class="product-miniature" data-id-product="101159"><h2 class="product-title"><a>Pc Portable BMAX MaxBook X15 / N4100 / 8 Go / 256 Go SSD</a></h2>
<span class="price">1 099,000 DT</span><div>En stock</div></article>
<article class="product-miniature" data-id-product="2"><h2 class="product-title"><a>HP Laptop 15 / i5-1334U / 16 Go / 512 Go SSD</a></h2>
<span class="price">2 469,000 DT</span><div>Sur commande</div></article>
</body></html>"""


def test_parse_listing():
    items, total = parse_listing(HTML, "P")
    assert total == 849 and len(items) == 2
    assert items[0]["prix"] == 1099.0 and items[0]["en_stock"] and not items[1]["en_stock"]
    assert parse_price("17 339,000 DT") == 17339.0


def test_segments():
    assert gamme("HP / i5-1334U / 16 Go") == "i5 / Core 5 / Ultra 5 / Ryzen 5"
    assert gamme("Lenovo IdeaPad 1 / Celeron N4500") == "Entrée"
    segs = aggregate([{"cat": "P", "nom": "x i3-1315U", "prix": 2000}, {"cat": "P", "nom": "y i3-1215U", "prix": 2200},
                      {"cat": "P", "nom": "MSI Cyborg RTX 4050 i7-13620H", "prix": 4000}])
    d = {(s["type"], s["gamme"]): s for s in segs}
    assert d[("Portable", "i3 / Core 3 / Ryzen 3")]["median"] == 2100
    assert ("Portable", "i7 / Core 7 / Ultra 7 / Ryzen 7 gamer") in d


def test_llm_simulation_without_key():
    out = llm.ask("test", "sys", "bonjour")
    assert getattr(out, "simulated", False)
    assert not llm.available()


def test_liste_local_match():
    text = """3 cahiers 96 pages grands carreaux
2 cahiers 48 pages
1 cahier de dessin
stylos bleu, rouge, vert
2 crayons HB + gomme
1 boîte de crayons de couleur 12
colle en bâton x2
1 règle 20 cm
1 compas
protège-cahiers
livre de lecture « Mon ami le livre »"""
    res = liste.match(text)
    assert res["mode"] == "regles"
    reconnues = [l for l in res["lignes"] if l["sku"] or "rupture" in l["note"]]
    assert len(reconnues) >= 10
    by_line = {l["ligne"]: l for l in res["lignes"]}
    assert by_line["3 cahiers 96 pages grands carreaux"]["qte"] == 3
    assert by_line["colle en bâton x2"]["qte"] == 2
    assert by_line["livre de lecture « Mon ami le livre »"]["sku"] is None


def test_commandes_risk_and_message():
    o = {"number": 1043, "total": "420.000", "payment_method": "cod",
         "billing": {"first_name": "Amira", "phone": "22 345 678", "state": "Tataouine"},
         "line_items": [{"name": "Pack lycée", "quantity": 1}]}
    score, why = risk(o, 0)
    assert score >= 50 and "premier achat" in why
    assert normalize_phone("22 345 678") == "21622345678"
    assert "1043" in confirmation_message(o)


def test_commandes_agent_alerts_once():
    now = datetime.now(timezone.utc)
    order = {"id": 7, "number": 1050, "status": "processing", "total": "98.900", "payment_method": "cod",
             "payment_method_title": "Paiement à la livraison", "date_created_gmt": (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%S"),
             "billing": {"first_name": "Hela", "last_name": "M.", "phone": "+216 22 111 222", "city": "Sfax"},
             "line_items": [{"name": "Cahier", "quantity": 3}], "meta_data": []}
    base.set_woo(FakeWoo(orders=[order]))
    CommandesAgent().run()
    titles = [a["title"] for a in db.recent_alerts(50)]
    assert "Nouvelle commande n°1050" in titles
    assert "Commande n°1050 non confirmée depuis 24 h" in titles
    n = len(db.recent_alerts(100))
    CommandesAgent().run()  # pas de doublon
    assert len(db.recent_alerts(100)) == n


def test_stock_agent():
    products = [
        {"id": 1, "name": "Cahier 96 p.", "type": "simple", "status": "publish", "manage_stock": True, "stock_quantity": 0,
         "price": "1.900", "meta_data": [{"key": "_cout_achat", "value": "1.100"}, {"key": "_fournisseur", "value": "Office House"}]},
        {"id": 2, "name": "Clé USB 64 Go", "type": "simple", "status": "publish", "manage_stock": True, "stock_quantity": 300,
         "price": "19.900", "meta_data": [{"key": "_cout_achat", "value": "15.900"}]},
    ]
    orders = [{"status": "completed", "line_items": [{"product_id": 1, "quantity": 12}]}]
    base.set_woo(FakeWoo(products=products, orders=orders))
    res = StockAgent().run()
    assert res == {"rupture": 1, "bas": 0, "marge": 1}
    assert any(a["title"] == "Rupture : Cahier 96 p." for a in db.recent_alerts(50))


def test_veille_agent_detects_price_moves(monkeypatch):
    items = [{"id": str(i), "cat": "P", "nom": f"PC {i} i5-1334U", "prix": 2800 + i, "en_stock": True} for i in range(60)]
    product = {"id": 9, "name": "Ordinateur portable 14 pouces (bureau)", "status": "publish", "price": "3500.000",
               "meta_data": [{"key": "_veille_gamme", "value": "Portable|i5 / Core 5 / Ultra 5 / Ryzen 5"}]}
    base.set_woo(FakeWoo(products=[product]))
    # relevé d'hier, plus bas de 10 %
    from datetime import date
    yday = (date.today() - timedelta(days=1)).isoformat()
    db.save_veille(yday, "Tunisianet", [], [{"type": "Portable", "gamme": "i5 / Core 5 / Ultra 5 / Ryzen 5", "modeles": 60,
                                              "min": 2500, "median": 2550, "max": 2600}])
    summary = VeilleAgent(scraper=lambda: items).run()
    assert summary["pc_releves"] == 60
    assert summary["variations"] and summary["variations"][0]["variation_pct"] > 5
    assert summary["nos_prix"][0]["ecart_pct"] > 8
    assert any(a["title"].startswith("Trop cher") for a in db.recent_alerts(50))


def test_import_payloads():
    from dealz.catalog import load_catalog
    from dealz.tools.import_catalog import pack_payload, product_payload
    cat = load_catalog()
    ids = {p["categorie"]: 1 for p in cat["produits"]} | {"__rentree": 2, "__cadeaux": 3}
    soon = next(p for p in cat["produits"] if p["bientot"])
    assert product_payload(soon, ids)["status"] == "draft"
    laptop = next(p for p in cat["produits"] if p["nom"].startswith("Ordinateur portable 15,6"))
    assert any(m["key"] == "_veille_gamme" for m in product_payload(laptop, ids)["meta_data"])
    assert pack_payload(cat["packs"][0], cat, ids)["sku"].startswith("PK-")


def test_import_categories_survive_html_entities():
    from dealz.tools.import_catalog import ensure_categories

    class W:
        def __init__(self):
            self.cats = [{"id": 16, "name": "Papeterie &amp; scolaire"}]
            self.posted = []

        def get_all(self, path, **kw):
            return self.cats

        def post(self, path, data):
            if data["name"] == "Papeterie & scolaire":
                raise RuntimeError('400 : {"code":"term_exists","data":{"status":400,"resource_id":16}}')
            self.posted.append(data["name"])
            return {"id": 100 + len(self.posted)}

    w = W()
    cat = {"rubriques": [{"id": "papeterie", "nom": "Papeterie & scolaire"}],
           "produits": [{"rubrique": "papeterie", "categorie": "Cahiers"}]}
    ids = ensure_categories(w, cat)
    assert "Papeterie & scolaire" not in w.posted and ids["Cahiers"] > 100
