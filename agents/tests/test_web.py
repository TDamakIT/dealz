from fastapi.testclient import TestClient

from dealz import bot, web


def test_health_and_dashboard():
    c = TestClient(web.app)
    assert c.get("/api/health").json()["ok"] is True
    r = c.get("/")
    assert r.status_code == 200 and "Dealz" in r.text


def test_liste_requires_token():
    c = TestClient(web.app)
    assert c.post("/api/liste", data={"texte": "1 compas"}).status_code == 401
    r = c.post("/api/liste", data={"texte": "1 compas\n2 colle en bâton"}, headers={"X-Dealz-Token": "test-token"})
    assert r.status_code == 200
    assert len([l for l in r.json()["lignes"] if l["sku"]]) == 2


def test_bot_commands():
    assert "/rapport" in bot.handle("/aide", {})
    assert "simulation" in bot.handle("/budget", {})
    assert "Écris ta question" in bot.handle("/ask", {})
