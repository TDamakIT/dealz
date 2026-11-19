from conftest import FakeWoo
from dealz.agents import base
from dealz.agents.seo import SeoAgent, audit_product, rollback, validate
from dealz.woo import meta


def _product():
    return {"id": 5, "name": "Cahier 96 pages grands carreaux", "status": "publish", "description": "", "short_description": "",
            "categories": [{"id": 1}], "images": [{"id": 70, "alt": ""}], "meta_data": [{"key": "_nom_ar", "value": "كراس"}]}


def test_audit_and_validate():
    a = audit_product(_product())
    assert a["score"] >= 5
    p = _product()
    good = {"meta_title": "Cahier 96 pages grands carreaux | Dealz",
            "meta_description": "Cahier 96 pages grands carreaux pour l'école : commandez en ligne, livraison partout en Tunisie et paiement à la livraison.",
            "description_fr": "<p>" + "mot " * 120 + "</p>", "description_ar": "<p>نص</p>", "short_description_fr": "Un cahier solide."}
    assert validate(good, p) == []
    bad = dict(good, meta_description=good["meta_description"] + " Seulement 2,900 DT !")
    assert any("prix" in e or "chiffres" in e for e in validate(bad, p))


def test_seo_applies_and_rolls_back():
    p = _product()
    cats = [{"id": 1, "name": "Cahiers", "description": "", "count": 12}]
    woo = FakeWoo(products=[p], categories=cats)
    base.set_woo(woo)
    res = SeoAgent().run(auto=True)
    assert res["fiches"] == 1 and res["categories"] == 1
    assert meta(p, "rank_math_title").endswith("| Dealz")
    assert p["images"][0]["alt"] == "Cahier 96 pages grands carreaux"
    assert "Tunisie" in cats[0]["description"]
    msg = rollback(res["run_id"])
    assert "annulé" in msg
    assert meta(p, "rank_math_title") == "" and p["images"][0]["alt"] == "" and cats[0]["description"] == ""


def test_seo_no_auto_changes_nothing():
    p = _product()
    woo = FakeWoo(products=[p], categories=[])
    base.set_woo(woo)
    SeoAgent().run(auto=False)
    assert not [c for c in woo.calls if c[0] == "PUT"]
