from dealz.agents import liste


def test_garcon_gets_garcon_and_mixte_never_fille():
    res = liste.match("1 cartable primaire classique\n1 trousse simple", genre="garcon", gamme="standard")
    cartable = res["lignes"][0]
    genres = {o["genre"] for o in cartable["options"]}
    assert "fille" not in genres and {"garcon", "mixte"} <= genres
    assert cartable["options"][0]["genre"] == "garcon" and cartable["options"][0]["gamme"] == "standard"
    assert cartable["sku"] == cartable["options"][0]["sku"]


def test_gamme_choice_drives_default():
    prem = liste.match("1 cartable primaire classique", genre="fille", gamme="premium")["lignes"][0]
    assert prem["options"][0]["gamme"] == "premium" and prem["options"][0]["genre"] == "fille"
    eco = liste.match("3 cahiers 96 pages grands carreaux", genre="fille", gamme="eco")["lignes"][0]
    assert eco["options"][0]["gamme"] == "eco" and eco["qte"] == 3
    # chaque ligne indique les gammes disponibles, pour le filtre du site
    l = liste.match("1 cartable primaire classique", genre="garcon")["lignes"][0]
    assert l["gammes"] == ["eco", "standard", "premium"] and l["options"][0]["gamme"] == "standard"
    assert liste.match("1 règle 20 cm", genre="garcon")["lignes"][0]["gammes"] == ["eco", "standard", "premium"]


def test_out_of_stock_family_is_flagged():
    prods = [{"id": "X-1", "famille": "X-1", "stock": 0, "gamme": "standard", "genre": "mixte", "nom": "x", "prix_vente": 1}]
    assert liste.options_for("X-1", "fille", "standard", prods) == []
    l = liste.with_options([{"ligne": "x", "sku": "INCONNU", "qte": 1, "note": ""}], "fille", "standard")[0]
    assert l["sku"] is None and "rupture" in l["note"]


def test_more_choice_when_the_child_chooses():
    # l'enfant choisit : au moins 5 modèles par genre et par gamme
    for genre in ("fille", "garcon"):
        opts = liste.match("1 cartable primaire classique", genre=genre)["lignes"][0]["options"]
        for gamme in ("eco", "standard", "premium"):
            assert sum(o["gamme"] == gamme for o in opts) >= 5, (genre, gamme)
        assert all(o["genre"] in (genre, "mixte") for o in opts)
    # les parents choisissent : peu de modèles, mais les 3 gammes
    for ligne in ("2 stylos bleu", "1 règle 20 cm", "3 cahiers 96 pages grands carreaux"):
        opts = liste.match(ligne, genre="garcon")["lignes"][0]["options"]
        for gamme in ("eco", "standard", "premium"):
            assert 1 <= sum(o["gamme"] == gamme for o in opts) <= 3, (ligne, gamme)


def test_single_colour_pen_is_not_the_pack():
    l = liste.match("2 stylos bleu", genre="garcon")["lignes"][0]
    assert l["qte"] == 2 and "Stylo bille bleu" in l["options"][0]["nom"]
    assert l["gammes"] == ["eco", "standard", "premium"]


def test_bad_values_fallback():
    res = liste.match("1 gomme", genre="mixte", gamme="luxe")
    assert res["genre"] == "garcon" and res["gamme"] == "standard"
