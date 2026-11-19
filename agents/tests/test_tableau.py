import os

from fastapi.testclient import TestClient

from conftest import FakeWoo
from dealz import bot, bus, db, links, web
from dealz.agents.base import set_woo
from dealz.agents.terrain import clean
from dealz.tools import scenarios


def test_strip_personal_and_clean_signal():
    t = links.strip_personal("Appelez Sami au 98 765 432 ou +216 74123456, sami@gmail.com")
    assert "98" not in t and "74123456" not in t and "gmail" not in t
    s = clean({"type": "demande", "produit": "friteuse à air", "commentaires": "150", "reactions": "1K",
               "resume": "Sami (22 333 444) cherche une friteuse"})
    assert s["interet"] == 1150 and "22 333 444" not in s["resume"]


def test_go_triggers_agents_and_creates_draft():
    woo = FakeWoo(products=[])
    set_woo(woo)
    try:
        oid = db.add_opportunite({"agent": "t", "produit": "Mixeur plongeant", "categorie": "petit_electro",
                                  "canal": "fournisseur local", "score": 3, "dedupe": "opp:mixeur plongeant"})
        msg = links.validate_go(oid)
        assert "Prospection" in msg and "brouillon OPP-" in msg
        draft = [p for p in woo._products if p.get("sku") == f"OPP-{oid}"][0]
        assert draft["status"] == "draft" and "price" not in draft and "regular_price" not in draft  # jamais de prix inventé
        assert links.pop_segment()["segment"].startswith("fournisseurs, grossistes et importateurs de Mixeur plongeant")
        bus.dispatch()  # rien de neuf : pas de deuxième réaction
        ev = [e for e in bus.events("opportunite_go") if e["payload"]["id"] == oid][0]
        assert len(bus.reactions(ev["id"])) == 3
    finally:
        set_woo(None)


def test_signal_text_without_ai_and_bot_commands():
    db.add_opportunite({"agent": "t", "produit": "Bouilloire électrique 1.7L", "categorie": "petit_electro",
                        "canal": "fournisseur local", "score": 2, "dedupe": "opp:bouilloire"})
    out = bot.handle("/signal bouilloire électrique demandée dans un groupe, appeler 98 111 222", {})
    assert "Signal #" in out and "98 111 222" not in out and "score 2 → 3" in out
    assert "signal_terrain" in bot.handle("/tableau", {})
    assert "enregistrées" in bot.handle("/priorites Trouver un fournisseur ; Signer 3 écoles", {})
    assert "Signer 3 écoles" in bot.handle("/priorites", {})


def test_after_launch_links_are_dormant_then_active(monkeypatch):
    monkeypatch.delenv("LIENS_VENTES", raising=False)
    e1 = bus.publish("rupture_proche", "t", "x", {"produit": "Cartable", "fournisseur": "OH"})
    bus.dispatch()
    assert all("en veille" in r["result"] for r in bus.reactions(e1))
    monkeypatch.setenv("LIENS_VENTES", "1")
    e2 = bus.publish("rupture_proche", "t", "y", {"produit": "Cartable B", "fournisseur": "OH"})
    bus.dispatch()
    assert any("second fournisseur" in r["result"] for r in bus.reactions(e2))


def test_prix_link_decides():
    e = bus.publish("prix_concurrent", "t", "pc", {"produit": "PC", "notre_prix": 2499, "median_marche": 2190, "cout_achat": 2050})
    bus.dispatch()
    assert "Ne pas s'aligner" in bus.reactions(e)[0]["result"]


def test_scenarios_and_reset(monkeypatch):
    monkeypatch.delenv("LIENS_VENTES", raising=False)
    scenarios.main(["tous"])
    assert TestClient(web.app).get("/").text.count("(démo)") > 0
    scenarios.main(["reset"])
    assert not [e for e in bus.events(limit=500) if e["mock"]]
    assert not [o for o in db.opportunites(limit=500) if "(démo)" in o["produit"]]
