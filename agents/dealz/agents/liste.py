"""Agent Liste scolaire — à la demande (appelé par la page « Ma liste scolaire » du site).

Photo ou texte de la liste → lignes associées aux produits du catalogue.
Avec l'IA : Claude (modèle rapide, vision). Sans IA ou en cas d'échec : correspondance par mots-clés.
"""
import json
import re
import unicodedata

from .. import llm
from ..catalog import load_catalog

SYSTEM = """Tu transformes une liste de fournitures scolaires tunisienne (photo ou texte, français ou arabe) en panier.
Règles : une ligne = un article + une quantité (par défaut 1). Associe chaque ligne au produit le plus proche du catalogue
(format, nombre de pages, carreaux). En cas de doute, choisis le plus courant et signale-le dans "note".
Si rien ne correspond, mets "sku": null. Les livres et manuels ne sont pas au catalogue : sku null, note "livre".
Réponds UNIQUEMENT avec un tableau JSON : [{"ligne": "...", "sku": "DZ-0001" ou null, "qte": 1, "note": ""}]"""


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[«»\"'’.,;:()]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


NUMW = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "dix": 10, "douze": 12}
SYN = [(r"stylo|bic", "stylo"), (r"crayons? (de )?couleur", "crayons couleur"), (r"\bhb\b|crayon noir|crayon a papier", "crayon papier hb"),
       (r"feutre", "feutres"), (r"colle", "colle"), (r"ciseau", "ciseaux"), (r"regle", "regle"), (r"equerre", "equerre"),
       (r"rapporteur", "rapporteur"), (r"compas", "compas"), (r"gomme", "gomme"), (r"taille", "taille crayon"),
       (r"protege", "protege cahier"), (r"ardoise", "ardoise"), (r"trousse", "trousse"), (r"cartable|sac", "sac"),
       (r"calculat", "calculatrice"), (r"copies? double", "copies doubles"), (r"copies? simple", "copies simples"),
       (r"classeur", "classeur"), (r"pochette", "pochettes"), (r"dessin", "cahier dessin"), (r"musique", "cahier musique"),
       (r"texte", "cahier textes"), (r"agenda", "agenda"), (r"gouache|peinture", "gouache"), (r"pinceau", "pinceaux"),
       (r"pate a modeler", "pate modeler"), (r"canson", "canson"), (r"surligneur|fluo", "surligneurs"),
       (r"blanco|correcteur", "correcteur"), (r"plume", "stylo plume"), (r"porte mine|criterium", "porte mine")]


GAMMES = ("eco", "standard", "premium")
GENRES = ("fille", "garcon")
GAMME_LIB = {"eco": "petit prix", "standard": "moyenne gamme", "premium": "haut de gamme"}


def _papeterie():
    return [p for p in load_catalog()["produits"] if p["rubrique"] == "papeterie"]


def _scolaire():
    """Produits de référence (un par famille) : c'est sur eux que la liste est lue, même s'ils sont en rupture."""
    return [p for p in _papeterie() if p.get("famille", p["id"]) == p["id"]]


def options_for(sku, genre, gamme, prods=None):
    """Modèles proposés pour une ligne : même famille, en stock, du genre choisi OU mixtes.
    Classés du plus adapté (gamme demandée, puis genre exact plutôt que mixte) au moins adapté."""
    prods = prods or _papeterie()
    by = {p["id"]: p for p in prods}
    if sku not in by:
        return []
    fam = by[sku].get("famille", sku)
    want = GAMMES.index(gamme) if gamme in GAMMES else 1
    opts = [p for p in prods if p.get("famille", p["id"]) == fam and p["stock"] > 0 and p.get("genre", "mixte") in (genre, "mixte")]

    def score(p):
        return (4 - 2 * abs(GAMMES.index(p.get("gamme", "standard")) - want)) + (2 if p.get("genre") == genre else 1)
    opts.sort(key=lambda p: (-score(p), p["prix_vente"]))
    return [{"sku": p["id"], "nom": p["nom"], "prix": p["prix_vente"], "gamme": p.get("gamme", "standard"),
             "genre": p.get("genre", "mixte")} for p in opts[:40]]


def with_options(lignes, genre, gamme):
    prods = _papeterie()
    for l in lignes:
        if not l.get("sku"):
            l["options"] = []
            continue
        opts = options_for(l["sku"], genre, gamme, prods)
        l["options"] = opts
        if not opts:
            l["sku"], l["note"] = None, "en rupture : l'équipe vous propose une alternative"
            continue
        l["sku"] = opts[0]["sku"]
        l["gammes"] = [g for g in GAMMES if any(o["gamme"] == g for o in opts)]   # filtres proposés sur la ligne
    return lignes


def local_match(text: str) -> list:
    prods = _scolaire()
    by_start = lambda s: next((p["id"] for p in prods if p["nom"].startswith(s)), None)
    out = []
    for raw in re.split(r"\n|;", text):
        raw = raw.strip()
        if not raw:
            continue
        l, qte = norm(raw), 1
        m = re.match(r"^(\d+)\s*(x\s*)?(?!\s*(pages|cm|go|ml|mm|g)\b)", l) or re.search(r"\bx\s*(\d+)\b", l)
        if m:
            qte = int(m.group(1))
        if l.split(" ")[0] in NUMW:
            qte = NUMW[l.split(" ")[0]]
        if re.search(r"livre|manuel|roman|dictionnaire", l):
            out.append({"ligne": raw, "sku": None, "qte": qte, "note": "livre"}); continue
        if "stylo" in l and re.search(r"bleu.*rouge|rouge.*vert|bleu.*vert", l):
            out.append({"ligne": raw, "sku": by_start("Lot 4 stylos bille"), "qte": 1, "note": ""}); continue
        couleurs = [c for c in ("bleu", "rouge", "vert", "noir") if c in l]
        if "stylo" in l and len(couleurs) == 1 and "plume" not in l:
            out.append({"ligne": raw, "sku": by_start(f"Stylo bille {couleurs[0]}"), "qte": qte, "note": ""}); continue
        if "crayon" in l and "gomme" in l:
            out.append({"ligne": raw, "sku": by_start("Lot 3 crayons à papier HB"), "qte": 1, "note": ""})
            out.append({"ligne": raw, "sku": by_start("Gomme blanche"), "qte": 1, "note": ""}); continue
        key = l
        for pat, k in SYN:
            if re.search(pat, l):
                key = k + " " + l
                break
        best, score = None, 0.0
        for p in prods:
            pn, s = norm(p["nom"]), 0.0
            for tk in key.split(" "):
                if len(tk) > 1 and tk in pn:
                    s += 2 if re.search(r"\d", tk) else 1
            if "cahier" in key and "cahier" not in pn:
                s -= 3
            if "compas" in key and "kit" in pn:
                s -= 1
            if "couleur" in key and "x12" in pn and "24" not in l:
                s += 0.5
            if "protege" in key and "lot 10" in pn:
                s += 0.5
            if s > score:
                best, score = p, s
        out.append({"ligne": raw, "sku": best["id"] if score >= 1.5 else None, "qte": qte,
                    "note": "" if score >= 1.5 else "à vérifier par l'équipe"})
    return out


def match(text: str = "", image=None, genre: str = "garcon", gamme: str = "standard") -> dict:
    """image : (media_type, base64) ou None. genre : fille|garcon.
    La gamme se choisit ligne par ligne sur le site : `gamme` ne fixe que le choix proposé par défaut (moyenne gamme).
    Renvoie {"lignes": [{ligne, qte, note, sku (choix par défaut), options: [...], gammes: [...]}], "mode": "ia"|"regles"}."""
    genre = genre if genre in GENRES else "garcon"
    gamme = gamme if gamme in GAMMES else "standard"
    res = _match(text, image)
    res["lignes"] = with_options(res["lignes"], genre, gamme)
    res.update(genre=genre, gamme=gamme)
    return res


def _match(text: str = "", image=None) -> dict:
    prods = _scolaire()
    skus = {p["id"] for p in prods}
    if llm.available() and (text or image):
        cat = "\n".join(f"{p['id']} | {p['nom']}" for p in prods)
        user = f"CATALOGUE (sku | nom) :\n{cat}\n\n" + (f"TEXTE DE LA LISTE :\n{text}\n" if text else "La liste est sur la photo jointe.")
        try:
            raw = llm.ask("liste", SYSTEM, user, max_tokens=1500, images=[image] if image else None)
            m = re.search(r"\[[\s\S]*\]", raw)
            if m:
                lignes = json.loads(m.group(0))
                for l in lignes:
                    if l.get("sku") not in skus:
                        l["sku"] = None
                    l["qte"] = max(1, int(l.get("qte") or 1))
                return {"lignes": lignes, "mode": "ia"}
        except Exception:
            pass
    if not text:
        return {"lignes": [], "mode": "regles", "erreur": "Sans IA, il faut le texte de la liste."}
    return {"lignes": local_match(text), "mode": "regles"}
