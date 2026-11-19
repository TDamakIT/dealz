from fastapi.testclient import TestClient

from dealz import bot, db, web
from dealz.agents.prospection import ProspectionAgent, clean_email, clean_phone, validate


def test_cleaning():
    assert clean_phone("74 123 456") == "+216 74 123 456"
    assert clean_phone("+216 98-765-432") == "+216 98 765 432"
    assert clean_phone("123") == ""
    assert clean_email("Contact@Ecole.TN ") == "contact@ecole.tn"
    assert clean_email("pas un mail") == ""


def test_validate_requires_source_and_contact():
    items = [
        {"nom": "École Les Oliviers", "ville": "Sfax", "telephone": "74 000 111", "source_url": "https://exemple.tn/ecole", "pertinence": 5},
        {"nom": "Sans source", "telephone": "74 000 112"},
        {"nom": "Sans contact", "source_url": "https://exemple.tn/x"},
    ]
    out = validate(items, "client", "écoles privées à Sfax")
    assert [o["nom"] for o in out] == ["École Les Oliviers"]
    assert db.add_prospect(out[0]) is not None
    assert db.add_prospect(out[0]) is None  # dédoublonné


def test_simulation_and_bot():
    assert ProspectionAgent().run() is None  # pas de clé API : ne fait rien
    assert "#" in bot.handle("/prospects", {})
    pid = db.prospects(limit=1)[0]["id"]
    assert "mis à jour" in bot.handle(f"/prospect {pid} contacte", {})
    assert "Exemple" in bot.handle("/prospect x", {})


def test_csv_requires_token():
    c = TestClient(web.app)
    assert c.get("/prospects.csv").status_code == 401
    r = c.get("/prospects.csv?token=test-token")
    assert r.status_code == 200 and "École Les Oliviers" in r.text
