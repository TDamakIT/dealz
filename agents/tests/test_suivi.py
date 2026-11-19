from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from conftest import FakeWoo
from dealz import db, suivi, web
from dealz.agents import base


def _order(oid, status="processing", hours=2, confirmed=False, phone="22123456"):
    created = (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(tzinfo=None).isoformat(timespec="seconds")
    return {"id": oid, "number": 1000 + oid, "status": status, "total": "57.000", "payment_method": "cod",
            "payment_method_title": "Paiement à la livraison", "date_created_gmt": created,
            "billing": {"first_name": "Client", "last_name": f"{oid}", "phone": phone, "state": "Sfax"},
            "meta_data": [{"key": "_dealz_confirmee", "value": "oui"}] if confirmed else [],
            "line_items": [{"product_id": 1, "quantity": 2, "total": "50.000", "name": "Cartable"}]}


PRODUCTS = [{"id": 1, "name": "Cartable", "type": "simple", "price": "25.000", "stock_quantity": 10, "sku": "DZ-1",
             "categories": [{"name": "Cartables"}], "meta_data": [{"key": "_cout_achat", "value": "20.000"}]},
            {"id": 2, "name": "Ordinateur portable 14 pouces (bureau)", "type": "simple", "price": "2000", "stock_quantity": 3,
             "sku": "DZ-2", "categories": [{"name": "Ordinateurs"}],
             "meta_data": [{"key": "_cout_achat", "value": "1700"},
                           {"key": "_veille_gamme", "value": "Portable|i5 / Core 5 / Ultra 5 / Ryzen 5"}]}]


@pytest.fixture
def woo():
    w = FakeWoo(products=[dict(p) for p in PRODUCTS],
                orders=[_order(1, hours=30), _order(2, confirmed=True), _order(3, status="cancelled"), _order(4, status="completed")])
    base.set_woo(w)
    suivi.clear_cache()
    yield w
    base.set_woo(None)
    suivi.clear_cache()


def test_commandes_etapes_retard_et_marge(woo):
    rows = {r["id"]: r for r in suivi.commandes()}
    assert rows[1]["etape"] == "à confirmer" and rows[1]["en_retard"]
    assert rows[2]["etape"] == "confirmée" and not rows[2]["en_retard"]
    assert rows[3]["etape"] == "annulée" and rows[4]["etape"] == "livrée"
    assert rows[1]["marge"] == 10.0   # 50 DT vendus - 2 × 20 DT d'achat
    assert rows[1]["wa"].startswith("https://wa.me/21622123456")


def test_page_commandes_et_actions(woo):
    c = TestClient(web.app)
    r = c.get("/commandes")
    assert r.status_code == 200 and "class='retard'" in r.text and "n°1001" in r.text
    assert c.post("/api/commandes/1/confirmee").status_code == 401
    assert c.post("/api/commandes/1/supprimer", headers={"X-Dealz-Token": "test-token"}).status_code == 400
    assert c.post("/api/commandes/1/confirmee", headers={"X-Dealz-Token": "test-token"}).json()["ok"]
    assert c.post("/api/commandes/2/annulee", headers={"X-Dealz-Token": "test-token"}).json()["ok"]
    puts = [(p, d) for m, p, d in woo.calls if m == "PUT"]
    assert ("orders/1", {"meta_data": [{"key": "_dealz_confirmee", "value": "oui"}]}) in puts
    assert ("orders/2", {"status": "cancelled"}) in puts
    assert any(m == "POST" and p == "orders/2/notes" for m, p, _ in woo.calls)


def test_commandes_sans_boutique():
    base.set_woo(None)
    r = TestClient(web.app).get("/commandes")
    assert r.status_code == 200 and "pas connectée" in r.text


def test_marges(woo):
    m = suivi.marges()
    assert m["source"] == "boutique"
    cartable = next(p for p in m["produits"] if p["id"] == 1)
    assert cartable["marge_pct"] == 20.0 and cartable["valeur_stock"] == 200.0
    assert [p["id"] for p in m["faibles"]] == [2, 1]   # 15 % puis 20 %, sous le seuil de 25 %
    assert m["realisee"]["commandes"] == 3 and m["realisee"]["marge"] == 30.0
    r = TestClient(web.app).get("/marges?tri=stock")
    assert r.status_code == 200 and "Cartables" in r.text


def test_marges_catalogue_local():
    base.set_woo(None)
    suivi.clear_cache()
    m = suivi.marges()
    assert m["source"] == "catalogue" and len(m["produits"]) > 500 and m["moyenne_pct"]
    r = TestClient(web.app).get("/marges?tout=1&categorie=Cahiers")
    assert r.status_code == 200 and "catalogue local fictif" in r.text


def test_prix_compare_et_recherche(woo):
    day = datetime.now().date().isoformat()
    items = [{"cat": "P", "nom": f"PC Portable HP i5-1335U 16Go {i}", "prix": 1800 + i * 20, "en_stock": 1} for i in range(10)]
    db.save_veille(day, "Tunisianet", items, [{"type": "Portable", "gamme": "i5 / Core 5 / Ultra 5 / Ryzen 5",
                                                "modeles": 10, "min": 1800, "median": 1890, "max": 1980}])
    _, gammes = suivi.comparer_gammes()
    assert gammes[0]["id"] == 2 and gammes[0]["ecart_pct"] == pytest.approx(5.8, abs=0.1)
    nous, eux = suivi.rechercher("portable 14")
    assert [p["id"] for p in nous] == [2] and eux == []
    nous, eux = suivi.rechercher("i5 16GO")
    assert len(eux) == 10 and eux[0]["prix"] == 1800
    r = TestClient(web.app).get("/prix?q=i5")
    assert r.status_code == 200 and "Chez les concurrents (10)" in r.text
