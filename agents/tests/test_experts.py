from fastapi.testclient import TestClient

from dealz import bot, db, import_calc, scraper, web
from dealz.agents.sourcing import SourcingAgent, evaluate, validate
from dealz.agents.tendances import TendancesAgent, market_price, signals


def test_landed_cost_and_verdict():
    c = import_calc.landed_cost(5.0, 500, "petit_electro", prix_vente_ttc=189)
    d = c["detail_tnd"]
    assert d["fob"] == 7500 and c["autofinancement_bct"] and c["controle_technique"]
    # le coût de revient exclut TVA et avance d'impôt (récupérables) mais la trésorerie les inclut
    assert c["tresorerie_tnd"] > c["cout_revient_unitaire_tnd"] * 500
    assert c["verdict"] in ("à creuser", "limite", "non rentable")
    assert import_calc.landed_cost(20, 100, "papeterie", 30)["verdict"] == "non rentable"
    txt = import_calc.format_calc(c)
    assert "BCT" in txt and "transitaire" in txt


def _row(day, rang, nom, prix, stock=1, tri="ventes", pid=None):
    return {"date": day, "site": "Tunisianet", "categorie": "petit_electro", "page": "Petit électro", "tri": tri,
            "rang": rang, "pid": pid or nom, "nom": nom, "prix": prix, "en_stock": stock}


def test_signals():
    days = [f"2026-11-{d:02d}" for d in range(10, 18)]
    hist = {d: [_row(d, 1, "Airfryer XL 5L", 189.0 if i < 6 else 165.0), _row(d, 8, "Bouilloire 1.7L", 49.0, stock=int(i < 7))]
            for i, d in enumerate(days)}
    hist[days[-1]].append(_row(days[-1], 2, "Machine à popcorn", 79.0))
    types = {(s["type"], s["nom"]) for s in signals(hist)}
    assert ("best-seller stable", "Airfryer XL 5L") in types
    assert ("nouvel entrant", "Machine à popcorn") in types
    assert ("rupture", "Bouilloire 1.7L") in types
    assert ("baisse de prix", "Airfryer XL 5L") in types
    # sans classement des ventes, pas de « best-seller »
    hist2 = {d: [_row(d, 1, "X", 10.0, tri="defaut")] for d in days}
    assert not [s for s in signals(hist2) if s["type"] == "best-seller stable"]
    assert market_price("airfryer 5l", hist[days[-1]]) == 165.0


def test_sales_sort_detection():
    html_page = '<a href="?order=product.sales.desc">Meilleures ventes</a><article class="product-miniature" data-id-product="7">' \
                '<h2 class="product-title">Airfryer 5L</h2><span class="price">189,000 DT</span> En stock</article>'
    assert scraper.sales_sort_available(html_page)
    items, _ = scraper.parse_listing(html_page, "petit_electro")
    assert items[0]["prix"] == 189.0 and items[0]["en_stock"]


def test_sourcing_validation_drops_unsourced():
    res = validate({"categorie": "petit_electro",
                    "offres_chine": [{"fournisseur": "A", "prix_min_usd": 9, "prix_max_usd": 12, "moq": 500, "url": "https://alibaba.com/x"},
                                     {"fournisseur": "Sans source", "prix_min_usd": 3, "prix_max_usd": 4},
                                     {"fournisseur": "Absurde", "prix_min_usd": 1, "prix_max_usd": 900, "url": "https://x.cn"}],
                    "prix_tunisie": [{"boutique": "B", "prix_ttc": "199,000", "url": "https://b.tn/p"}, {"boutique": "C", "prix_ttc": 150}]})
    assert [o["fournisseur"] for o in res["offres_chine"]] == ["A"]
    assert [p["boutique"] for p in res["prix_tunisie"]] == ["B"]
    ev = evaluate("Airfryer 5L", res, 300)
    assert ev["qte"] == 500 and ev["prix_marche"] == 199.0 and len(ev["scenarios"]) == 2
    assert evaluate("Rien", validate({}), 300)["verdict"] == "pas assez de données"


def test_bot_and_dashboard():
    assert "IA inactive" in SourcingAgent().study("friteuse")
    assert SourcingAgent().run() is None
    out = bot.handle("/import 6.5 500 petit_electro 189", {})
    assert "Coût de revient" in out and "BCT" in out
    assert "Exemple" in bot.handle("/import abc", {})
    oid = db.add_opportunite({"agent": "test", "produit": "Airfryer 5L", "categorie": "petit_electro", "canal": "import Chine à étudier",
                              "score": 4, "dedupe": "opp:airfryer 5l", "prix_marche": 189.0})
    assert "Airfryer" in bot.handle("/opportunites", {})
    assert "mis à jour" in bot.handle(f"/opportunite {oid} chiffree", {})
    r = TestClient(web.app).get("/")
    assert r.status_code == 200 and "Opportunités" in r.text and "Airfryer" in r.text


def test_tendances_analyse_without_ai(monkeypatch):
    db.save_tendances("2026-11-17", [{"site": "Tunisianet", "categorie": "petit_electro", "page": "Petit électro", "tri": "ventes",
                                      "rang": 1, "pid": "1", "nom": "Airfryer", "prix": 189.0, "en_stock": 1}])
    monkeypatch.setattr(TendancesAgent, "collect", lambda self, client=None: 0)
    assert TendancesAgent().analyse() == {"opportunites": 0}
    assert any("Tendances" in r["title"] for r in db.recent_reports(5))
