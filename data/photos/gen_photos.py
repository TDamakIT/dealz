"""Images FICTIVES des produits de démo : une image par modèle (type d'article × couleur × motif × gamme).

Usage (machine avec Playwright) : python3 data/photos/gen_photos.py
Sortie : data/photos/img/<clé>.jpg et data/photos/index.json ({sku: fichier}), utilisés par l'import.
À remplacer par les vraies photos des produits.
"""
import asyncio
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).parent
CATALOG = HERE.parent / "catalog.json"
OUT = HERE / "img"

COL = {"bleu": "#1b4fd1", "noir": "#2a2d36", "vert": "#2e8b57", "gris": "#8a93a6", "marine": "#1b2a5c", "rose": "#ec6fa0",
       "violet": "#8e5cc8", "corail": "#f27a6b", "turquoise": "#22aaa6", "lilas": "#b79ae0", "rouge": "#d93b3b",
       "jaune": "#f2b10a", "ciel": "#6fb8f2", "orange": "#f28c28", "blanc": "#e9edf3", "bleue": "#1b4fd1", "rouge_": "#d93b3b",
       "verte": "#2e8b57", "violette": "#8e5cc8"}
DESC_COL = {"modèle classique": "blanc", "pointe fine": "gris", "grip confort": "noir", "corps triangulaire": "orange",
            "séchage rapide": "ciel", "boîte carton": "orange", "boîte métal": "gris", "étui zippé": "noir", "coloris vifs": "rouge",
            "coloris pastel": "lilas", "transparent": "blanc", "coloré": "turquoise", "flexible": "vert", "métal": "gris", "à motifs": "violet"}


def sh(h, f):
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    if f >= 0:
        r, g, b = (int(c + (255 - c) * f) for c in (r, g, b))
    else:
        r, g, b = (int(c * (1 + f)) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------------------------------------------------------------- analyse du modèle
def analyse(p, eviter=()):
    """→ dict(type, taille, couleur, motif, gamme, desc) à partir du nom et des champs du catalogue."""
    base = p["nom"].split(" — ")[0].lower()
    parts = [x.strip() for x in p["nom"].split(" — ")[1:]]
    desc = next((x for x in parts if x not in ("petit prix", "haut de gamme")), "")
    gamme = p.get("gamme", "standard")
    motif, couleur = "", None
    d = desc.lower()
    if d.startswith(("garçon", "fille")):
        rest = d.split(",", 1)[1].strip()          # « bleu motif foot », « marine rayé »
        couleur = rest.split()[0]
        motif = rest.split("motif", 1)[1].strip() if "motif" in rest else ("rayé" if "rayé" in rest else "")
    elif d.endswith(" uni"):
        couleur = d.replace(" uni", "").replace("bleu ciel", "ciel").strip()
    elif d.startswith("couverture"):
        couleur = d.split()[-1]
    elif d in ("bleu", "rouge", "vert", "jaune", "noir"):
        couleur = d
    elif d in DESC_COL:
        couleur = DESC_COL[d]
    if not couleur:   # produit de base : une couleur que ses modèles n'utilisent pas déjà
        libres = [c for c in ("vert", "jaune", "violet", "orange", "turquoise", "rose", "bleu", "rouge") if c not in eviter]
        couleur = (libres or ["vert"])[int(hashlib.md5(base.encode()).hexdigest(), 16) % max(1, min(3, len(libres)))]
    t = type_of(base)
    return {"type": t, "base": base, "couleur": couleur, "motif": motif, "gamme": gamme, "desc": d}


def type_of(b):
    rules = [("roulettes", "cartable_roues"), ("cartable", "cartable"), ("maternelle", "sac_mini"), ("sac à dos", "sac"),
             ("sac de sport", "sport"), ("boîte à goûter", "lunch"), ("gourde", "gourde"), ("plumier", "plumier"),
             ("trousse garnie", "trousse_garnie"), ("double compartiment", "trousse_double"), ("trousse", "trousse"),
             ("cahier de textes", "agenda"), ("agenda", "agenda"), ("spirale", "spirale"), ("répertoire", "repertoire"),
             ("cahier de dessin", "dessin"), ("musique", "musique"), ("cahier", "cahier"), ("lot 4 stylos", "stylos4"),
             ("plume", "plume"), ("effaceur", "effaceur"), ("stylo", "stylo"), ("lot 3 crayons", "crayons3"),
             ("crayon à papier", "crayon"), ("porte-mine", "portemine"), ("surligneur", "surligneurs"),
             ("feutre ardoise", "marqueur"), ("correcteur", "correcteur"), ("gomme", "gomme"), ("taille-crayon", "taille"),
             ("crayons de couleur", "boite_crayons"), ("crayons de cire", "boite_cire"), ("feutres", "boite_feutres"),
             ("gouache", "gouache"), ("pinceaux", "pinceaux"), ("pâte à modeler", "pate"), ("canson", "canson"),
             ("ciseaux", "ciseaux"), ("colle en bâton", "colle_baton"), ("colle liquide", "colle_liquide"), ("règle", "regle"),
             ("équerre", "equerre"), ("rapporteur", "rapporteur"), ("compas", "compas"), ("kit géométrie", "kit"),
             ("graphique", "calc_graph"), ("scientifique", "calc_sci"), ("calculatrice", "calc"), ("ardoise", "ardoise"),
             ("lot 10 protège", "proteges"), ("protège-cahier", "protege"), ("classeur", "classeur"),
             ("intercalaires", "intercalaires"), ("pochettes", "pochettes"), ("copies", "copies"), ("chemise", "chemise"),
             ("étiquettes", "etiquettes"), ("ramette", "ramette")]
    for k, t in rules:
        if k in b:
            return t
    return "boite"


def key_of(a):
    raw = f"v3|{a['type']}|{a['base'] if a['type'] in ('regle', 'stylo', 'boite_crayons', 'boite_feutres') else ''}|{a['couleur']}|{a['motif']}|{a['gamme']}|{a['desc']}"
    return f"{a['type']}-{hashlib.md5(raw.encode()).hexdigest()[:8]}"


# ---------------------------------------------------------------- dessin
def defs(c, c2=None):
    c2 = c2 or sh(c, -.35)
    return (f'<defs><linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{sh(c, .18)}"/><stop offset="1" stop-color="{sh(c, -.2)}"/></linearGradient>'
            f'<linearGradient id="p" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{sh(c2, .15)}"/><stop offset="1" stop-color="{sh(c2, -.2)}"/></linearGradient>'
            '<linearGradient id="hl" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity=".33"/><stop offset=".4" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset=".85" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".16"/></linearGradient>'
            '<linearGradient id="gd" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#ffe6a3"/><stop offset=".5" stop-color="#c99a2e"/><stop offset="1" stop-color="#f2cf73"/></linearGradient>'
            '<radialGradient id="sd"><stop offset="0" stop-color="#000" stop-opacity=".25"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient></defs>')


def frame(body, c, c2=None, shadow=True):
    s = '<ellipse cx="200" cy="364" rx="140" ry="16" fill="url(#sd)"/>' if shadow else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="400" height="400">{defs(c, c2)}<rect width="400" height="400" fill="#fff"/>{s}{body}</svg>'


def motif_svg(m, cx, cy, s=1.0):
    """Petit décor centré en (cx, cy)."""
    g = lambda inner: f'<g transform="translate({cx} {cy}) scale({s})">{inner}</g>'
    star = lambda x, y, r, col: f'<path transform="translate({x} {y}) scale({r / 14})" d="M0 -14 l4 10 h11 l-9 7 3 11 -9 -6 -9 6 3 -11 -9 -7 h11z" fill="{col}"/>'
    if m == "foot":
        return g('<circle r="26" fill="#fff"/><path d="M0 -13 l12 9 -5 14 h-14 l-5 -14z" fill="#222"/><circle r="26" fill="none" stroke="#222" stroke-width="3"/>')
    if m == "dinosaures":
        return g('<path d="M-30 14 q4 -26 26 -24 q12 -16 26 -6 q4 8 -6 10 h-6 q2 14 -6 20 h-8 v-8 h-10 v8 h-8 q-6 0 -8 0z" fill="#7bd389"/><circle cx="14" cy="-14" r="2.5" fill="#222"/>'
                 '<path d="M-24 -6 l4 -8 4 8 M-12 -14 l4 -8 4 8 M0 -18 l4 -8 4 8" fill="#4caf6a"/>')
    if m == "espace":
        return g('<circle cx="-8" cy="4" r="20" fill="#f2b10a"/><ellipse cx="-8" cy="4" rx="32" ry="8" fill="none" stroke="#fff" stroke-width="4"/>' + star(24, -18, 9, "#fff") + star(22, 18, 6, "#fff"))
    if m == "voitures":
        return g('<path d="M-30 6 h60 v-10 q0 -6 -6 -6 h-10 l-8 -10 h-18 l-8 10 h-6 q-4 0 -4 6z" fill="#e2463b"/><circle cx="-16" cy="8" r="7" fill="#222"/><circle cx="16" cy="8" r="7" fill="#222"/>'
                 '<path d="M-10 -18 h14 l6 8 h-26z" fill="#bfe0ff"/>')
    if m == "rayé":
        return g("".join(f'<rect x="-40" y="{y}" width="80" height="6" rx="3" fill="#fff" opacity=".85"/>' for y in (-18, -6, 6, 18)))
    if m == "fleurs":
        fl = lambda x, y, col: f'<g transform="translate({x} {y})">' + "".join(f'<circle cx="{8 * math.cos(a * 1.2566):.1f}" cy="{8 * math.sin(a * 1.2566):.1f}" r="7" fill="{col}"/>' for a in range(5)) + '<circle r="5" fill="#f2b10a"/></g>'
        return g(fl(-18, -6, "#fff") + fl(16, 4, "#ffe3ef") + fl(-2, 18, "#fff"))
    if m == "licorne":
        return g('<path d="M-18 18 q-4 -26 14 -30 l8 -22 4 22 q18 6 12 30z" fill="#fff"/><path d="M4 -34 l4 22" stroke="#f2b10a" stroke-width="4"/>'
                 '<path d="M-14 -8 q-10 4 -8 16 q6 -10 12 -10z" fill="#c59bff"/><circle cx="6" cy="2" r="2.5" fill="#222"/>' + star(24, -22, 6, "#ffd23f"))
    if m == "papillons":
        return g('<ellipse cx="-12" cy="-8" rx="14" ry="11" fill="#fff"/><ellipse cx="12" cy="-8" rx="14" ry="11" fill="#fff"/>'
                 '<ellipse cx="-9" cy="10" rx="10" ry="8" fill="#ffe3ef"/><ellipse cx="9" cy="10" rx="10" ry="8" fill="#ffe3ef"/><rect x="-2" y="-16" width="4" height="34" rx="2" fill="#5b2a6e"/>')
    if m == "étoiles":
        return g(star(-16, -8, 13, "#fff") + star(16, 4, 10, "#ffe68a") + star(-4, 20, 8, "#fff"))
    if m == "cœurs":
        h = lambda x, y, s_, col: f'<path transform="translate({x} {y}) scale({s_})" d="M0 8 C-14 -2 -12 -14 -4 -14 Q0 -14 0 -8 Q0 -14 4 -14 C12 -14 14 -2 0 8z" fill="{col}"/>'
        return g(h(-14, -6, 1.3, "#fff") + h(14, 4, 1.0, "#ffd6e5") + h(-2, 20, .8, "#fff"))
    return ""


def premium_badge(x, y):
    return f'<rect x="{x}" y="{y}" width="34" height="34" rx="9" fill="url(#gd)"/><path d="M{x + 17} {y + 7} l3 7 8 1 -6 5 2 8 -7 -4 -7 4 2 -8 -6 -5 8 -1z" fill="#7a5600"/>'


def bag(a, mini=False, wheels=False, tall=False):
    c = COL.get(a["couleur"], "#1b4fd1")
    c2 = sh(c, -.32)
    eco, prem = a["gamme"] == "eco", a["gamme"] == "premium"
    w, h = (190, 210) if mini else ((210, 290) if tall else (224, 262))
    x, y = 200 - w / 2, (350 - h) if not wheels else (330 - h)
    body = f'<path d="M{200 - 36} {y + 8} q36 -56 72 0" fill="none" stroke="{c2}" stroke-width="15" stroke-linecap="round"/>'
    body += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="44" fill="url(#b)"/>'
    if not eco:
        body += f'<path d="M{x + 16} {y + 40} q{w / 2 - 16} -40 {w - 32} 0" fill="none" stroke="{sh(c, -.4)}" stroke-width="4" stroke-dasharray="3 4"/>'
        body += f'<rect x="{x + 24}" y="{y + h * .45}" width="{w - 48}" height="{h * .45}" rx="28" fill="url(#p)"/>'
        body += f'<path d="M{x + 36} {y + h * .45 + 14} h{w - 72}" stroke="{sh(c2, -.45)}" stroke-width="4" stroke-dasharray="3 4"/>'
    else:
        body += f'<rect x="{x + 30}" y="{y + h * .5}" width="{w - 60}" height="{h * .36}" rx="12" fill="{sh(c, -.12)}"/>'
    if prem:
        body += f'<rect x="{x}" y="{y + h * .3}" width="{w}" height="12" fill="#dfe6ee"/>' + premium_badge(x + w - 50, y + 16)
    body += motif_svg(a["motif"], 200, y + h * .68, .95 if not mini else .8)
    if wheels:
        body += f'<rect x="{x + w - 6}" y="{y - 60}" width="10" height="{h + 40}" rx="5" fill="#9aa3b5"/><circle cx="{x + 40}" cy="{y + h + 10}" r="18" fill="#2a2d36"/><circle cx="{x + w - 40}" cy="{y + h + 10}" r="18" fill="#2a2d36"/>'
    body += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="44" fill="url(#hl)"/>'
    return frame(body, c, c2)


def pouch(a, double=False, garnie=False, rigid=False):
    c = COL.get(a["couleur"], "#1b4fd1")
    prem = a["gamme"] == "premium"
    if rigid:
        body = '<rect x="70" y="150" width="260" height="130" rx="22" fill="url(#b)"/><rect x="70" y="150" width="260" height="40" rx="18" fill="url(#p)"/>'
        body += motif_svg(a["motif"], 200, 238, .8)
    else:
        top = 130 if not double else 112
        body = f'<path d="M66 {top + 40} q0 -40 40 -40 h188 q40 0 40 40 v{176 - top + 52} q0 40 -40 40 h-188 q-40 0 -40 -40z" fill="url(#b)"/>'
        for k in range(2 if double else 1):
            yy = top + 20 + k * 30
            body += f'<path d="M80 {yy} q120 -24 240 0" fill="none" stroke="{sh(c, -.45)}" stroke-width="5" stroke-dasharray="3 4"/><rect x="300" y="{yy - 14}" width="12" height="28" rx="4" fill="{sh(c, -.55)}"/>'
        if garnie:
            for i, col in enumerate(("#d93b3b", "#f2b10a", "#2e8b57", "#1b4fd1")):
                body = f'<rect x="{120 + i * 28}" y="{top - 46}" width="16" height="80" rx="6" fill="{col}" transform="rotate({-8 + i * 5} {128 + i * 28} {top})"/>' + body
        body += motif_svg(a["motif"], 200, 252, .9)
    if prem:
        body += premium_badge(282, 214)
    body += '<rect x="66" y="130" width="268" height="180" rx="40" fill="url(#hl)" opacity=".7"/>'
    return frame(body, c)


def book(a, kind="cahier"):
    c = COL.get(a["couleur"], "#1b4fd1")
    eco, prem = a["gamme"] == "eco", a["gamme"] == "premium"
    if prem:
        c = sh(c, -.35)
    landscape = kind == "dessin"
    x, y, w, h = (70, 110, 260, 200) if landscape else (104, 70, 192, 270)
    body = f'<rect x="{x + 8}" y="{y + 6}" width="{w}" height="{h}" rx="8" fill="#e6e6e6"/><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{c if eco else "url(#b)"}"/>'
    if kind == "spirale":
        body += "".join(f'<rect x="{x - 10}" y="{y + 16 + i * 22}" width="22" height="8" rx="4" fill="#9aa3b5"/>' for i in range(11))
    else:
        body += f'<rect x="{x}" y="{y}" width="20" height="{h}" fill="#000" opacity=".12"/>'
    if kind == "repertoire":
        body += "".join(f'<rect x="{x + w}" y="{y + 20 + i * 34}" width="16" height="26" rx="4" fill="{col}"/>' for i, col in enumerate(("#d93b3b", "#f2b10a", "#2e8b57", "#1b4fd1", "#8e5cc8", "#f27a6b", "#22aaa6")))
    lx, ly = x + w / 2 - 70, y + (40 if not landscape else 30)
    body += f'<rect x="{lx}" y="{ly}" width="140" height="54" rx="8" fill="#fff"/>'
    if kind == "musique":
        body += "".join(f'<path d="M{lx + 10} {ly + 12 + i * 8}h120" stroke="#9aa6cc" stroke-width="2"/>' for i in range(5)) + f'<circle cx="{lx + 60}" cy="{ly + 36}" r="6" fill="#222"/>'
    else:
        body += f'<path d="M{lx + 12} {ly + 20}h100M{lx + 12} {ly + 36}h70" stroke="#9aa6cc" stroke-width="5"/>'
    if kind in ("agenda",):
        body += f'<rect x="{x + w - 40}" y="{y}" width="12" height="{h}" fill="{sh(c, -.5)}"/>'
    body += motif_svg(a["motif"], x + w / 2, y + h * .68, .9)
    if not eco and not prem and not a["motif"]:
        body += "".join(f'<circle cx="{x + 40 + i * 50}" cy="{y + h - 50 + (i % 2) * 18}" r="{18 + i * 4}" fill="#fff" opacity=".14"/>' for i in range(3))
    if prem:
        body += f'<path d="M{x} {y + 26} h26 l-26 -26z M{x + w} {y + 26} h-26 l26 -26z" fill="#c99a2e" transform=""/>' + premium_badge(x + w - 50, y + h - 50)
        body += f'<rect x="{x + w - 30}" y="{y}" width="10" height="{h}" fill="#111" opacity=".6"/>'
    body += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="url(#hl)"/>'
    return frame(body, c)


def pen(a, ink="#1b4fd1", kind="stylo"):
    body_col = COL.get(a["couleur"], "#e9edf3")
    prem, eco = a["gamme"] == "premium", a["gamme"] == "eco"
    if prem:
        body_col = "#23262e"
    clear = body_col in ("#e9edf3",) and not prem
    tip = "#c8cfdc" if not prem else "url(#gd)"
    parts = f'<rect x="-140" y="-15" width="250" height="30" rx="{6 if eco else 14}" fill="{body_col}" opacity="{.75 if clear else 1}"/>'
    if clear:
        parts += f'<rect x="-130" y="-4" width="230" height="8" rx="4" fill="{ink}"/>'
    if a["desc"] == "grip confort" or (not eco and not prem and not clear):
        parts += "".join(f'<rect x="{-128 + i * 11}" y="-17" width="6" height="34" rx="3" fill="#1c1f2b"/>' for i in range(5))
    if a["desc"] == "corps triangulaire":
        parts += '<path d="M-140 0 h250" stroke="#000" stroke-opacity=".25" stroke-width="3"/>'
    parts += f'<path d="M-140 -13 l-38 13 38 13z" fill="{tip}"/><path d="M-178 0 l-8 0" stroke="{ink}" stroke-width="5"/>'
    parts += f'<rect x="60" y="-18" width="{70 if kind != "plume" else 80}" height="36" rx="10" fill="{ink if not prem else "#23262e"}"/>'
    parts += f'<rect x="80" y="-26" width="56" height="10" rx="4" fill="{ink if not prem else "url(#gd)"}"/>'
    if prem:
        parts += '<rect x="56" y="-18" width="6" height="36" fill="url(#gd)"/>'
    if kind == "plume":
        parts += '<path d="M-150 -10 l-40 10 40 10z" fill="url(#gd)"/>'
    if kind == "effaceur":
        parts += '<rect x="110" y="-14" width="40" height="28" rx="10" fill="#fff" stroke="#9aa3b5" stroke-width="3"/>'
    hl = '<rect x="-140" y="-15" width="250" height="10" rx="5" fill="#fff" opacity=".25"/>'
    return frame(f'<g transform="translate(210 205) rotate(-32)">{parts}{hl}</g>', body_col)


def multi_pens(cols, a, kind="stylo"):
    g = ""
    for i, ink in enumerate(cols):
        g += f'<g transform="translate({120 + i * 50} 205) rotate(-70)"><rect x="-120" y="-12" width="220" height="24" rx="10" fill="{ink if kind != "crayon" else "#f2b10a"}"/>'
        g += f'<path d="M-120 -11 l-30 11 30 11z" fill="{"#e8c79a" if kind == "crayon" else "#c8cfdc"}"/><path d="M-150 0 l-6 0" stroke="{ink if kind != "crayon" else "#333"}" stroke-width="5"/>'
        if kind == "surligneur":
            g = g.replace(f'rx="10" fill="{ink}"', f'rx="6" fill="{ink}"')
        g += f'<rect x="70" y="-14" width="40" height="28" rx="6" fill="{sh(ink, -.3) if kind != "crayon" else "#ec6fa0"}"/></g>'
    if a["gamme"] == "premium":
        g += premium_badge(300, 300)
    return frame(g, cols[0])


def boxed(a, n=12, kind="crayons"):
    c = COL.get(a["couleur"], "#1b4fd1")
    metal = a["desc"] == "boîte métal"
    pastel = a["desc"] == "coloris pastel"
    cols = ["#d93b3b", "#f28c28", "#f2b10a", "#2e8b57", "#22aaa6", "#1b4fd1", "#8e5cc8", "#ec6fa0", "#6b4a2b", "#2a2d36", "#8a93a6", "#7bd389"]
    if pastel:
        cols = [sh(x, .45) for x in cols]
    k = min(n, 12)
    w = 230 if n <= 12 else 280
    x0 = 200 - w / 2
    items = ""
    for i in range(k):
        xx = x0 + 14 + i * ((w - 28) / k)
        ww = (w - 28) / k - 4
        if kind == "feutres":
            items += f'<rect x="{xx}" y="96" width="{ww}" height="150" rx="6" fill="{cols[i]}"/><rect x="{xx}" y="96" width="{ww}" height="34" rx="6" fill="{sh(cols[i], -.3)}"/>'
        else:
            items += f'<rect x="{xx}" y="{110 - (i % 3) * 8}" width="{ww}" height="140" rx="3" fill="{cols[i]}"/><path d="M{xx} {110 - (i % 3) * 8} l{ww / 2} -22 {ww / 2} 22z" fill="#e8c79a"/>'
    box = f'<rect x="{x0}" y="170" width="{w}" height="170" rx="{8 if metal else 14}" fill="{"#c8cfdc" if metal else "url(#b)"}"/>'
    box += f'<rect x="{x0 + 20}" y="214" width="{w - 40}" height="70" rx="10" fill="#fff"/>'
    box += "".join(f'<rect x="{x0 + 34 + i * 26}" y="236" width="18" height="26" rx="4" fill="{cols[i]}"/>' for i in range(min(6, int((w - 60) / 26))))
    if a["gamme"] == "premium":
        box += premium_badge(x0 + w - 48, 292)
    return frame(items + box + f'<rect x="{x0}" y="170" width="{w}" height="170" rx="12" fill="url(#hl)"/>', c)


def simple_shape(a):
    """Formes simples pour le reste de la papeterie, colorées selon le modèle."""
    t = a["type"]
    c = COL.get(a["couleur"], "#1b4fd1")
    prem, eco = a["gamme"] == "premium", a["gamme"] == "eco"
    clear = a["desc"] == "transparent"
    fillc = "url(#b)" if not clear else "#dbe9ff"
    op = ' opacity=".75"' if clear else ""
    b = ""
    if t == "regle":
        L = 300 if "30" in a["base"] else 240
        b = f'<g transform="translate(200 200) rotate(-18)"><rect x="{-L / 2}" y="-30" width="{L}" height="60" rx="8" fill="{fillc}"{op}/>'
        b += "".join(f'<path d="M{-L / 2 + 12 + i * (L - 24) / 20} -30 v{18 if i % 5 == 0 else 10}" stroke="#222" stroke-width="2"/>' for i in range(21)) + "</g>"
    elif t == "equerre":
        b = f'<path d="M100 320 L100 90 L320 320z" fill="{fillc}"{op}/><path d="M140 290 L140 190 L240 290z" fill="#fff"/>'
    elif t == "rapporteur":
        b = f'<path d="M70 300 A130 130 0 0 1 330 300z" fill="{fillc}"{op}/><path d="M130 300 A70 70 0 0 1 270 300z" fill="#fff"/>'
        b += "".join(f'<path d="M{200 + 120 * math.cos(math.pi * i / 18):.0f} {300 - 120 * math.sin(math.pi * i / 18):.0f} L{200 + 108 * math.cos(math.pi * i / 18):.0f} {300 - 108 * math.sin(math.pi * i / 18):.0f}" stroke="#222" stroke-width="2"/>' for i in range(19))
    elif t == "compas":
        b = f'<circle cx="200" cy="96" r="18" fill="{c}"/><path d="M196 110 L130 320 M204 110 L270 320" stroke="{sh(c, -.2) if not prem else "#c99a2e"}" stroke-width="16" stroke-linecap="round"/><rect x="258" y="300" width="20" height="40" rx="4" fill="#f2b10a"/>'
    elif t == "kit":
        b = (f'<rect x="60" y="250" width="280" height="44" rx="6" fill="{fillc}"{op}/><path d="M80 230 L80 90 L200 230z" fill="{fillc}"{op}/>'
             f'<path d="M220 230 A80 80 0 0 1 340 230z" fill="{fillc}"{op}/>')
    elif t in ("calc", "calc_sci", "calc_graph"):
        big = t == "calc_graph"
        b = f'<rect x="120" y="60" width="160" height="290" rx="22" fill="{"#2a2d36" if t != "calc" else "url(#b)"}"/><rect x="138" y="80" width="124" height="{110 if big else 60}" rx="8" fill="#cfe3c4"/>'
        rows = 4 if big else 5
        b += "".join(f'<rect x="{142 + (i % 4) * 30}" y="{(206 if big else 160) + (i // 4) * 32}" width="22" height="22" rx="5" fill="{"#f2b10a" if i % 4 == 3 else "#e9edf3"}"/>' for i in range(4 * rows))
    elif t == "ardoise":
        b = f'<rect x="60" y="90" width="280" height="220" rx="14" fill="{c}"/><rect x="76" y="106" width="248" height="188" rx="8" fill="#fff"/><path d="M110 170 q40 -40 80 0 t80 0" stroke="#1b4fd1" stroke-width="6" fill="none"/>'
    elif t in ("protege", "proteges", "chemise", "classeur", "intercalaires", "pochettes"):
        if t == "proteges":
            cols = ["#d93b3b", "#f2b10a", "#2e8b57", "#1b4fd1", "#8e5cc8"]
            b = "".join(f'<rect x="{110 + i * 14}" y="{70 + i * 14}" width="180" height="250" rx="8" fill="{x}"/>' for i, x in enumerate(cols))
        elif t == "classeur":
            b = f'<rect x="90" y="70" width="230" height="280" rx="10" fill="url(#b)"/><rect x="90" y="70" width="34" height="280" fill="#000" opacity=".15"/>' + "".join(f'<circle cx="107" cy="{120 + i * 60}" r="7" fill="#c8cfdc"/>' for i in range(4)) + '<rect x="170" y="110" width="110" height="60" rx="8" fill="#fff"/>'
        elif t == "intercalaires":
            cols = ["#d93b3b", "#f2b10a", "#2e8b57", "#1b4fd1", "#8e5cc8", "#ec6fa0"]
            b = '<rect x="100" y="70" width="200" height="280" rx="6" fill="#f4f4f4"/>' + "".join(f'<rect x="300" y="{80 + i * 42}" width="26" height="36" rx="5" fill="{x}"/>' for i, x in enumerate(cols))
        elif t == "pochettes":
            b = "".join(f'<rect x="{100 + i * 8}" y="{70 + i * 8}" width="200" height="270" rx="4" fill="#e3ecff" opacity=".7" stroke="#9aa6cc"/>' for i in range(4))
        else:
            b = f'<rect x="100" y="70" width="200" height="280" rx="8" fill="{fillc}"{op}/>'
            if t == "chemise":
                b += f'<path d="M100 120 h200" stroke="#000" stroke-opacity=".15" stroke-width="4"/><rect x="130" y="70" width="10" height="280" fill="{sh(c, -.5)}"/>'
            b += motif_svg(a["motif"], 200, 230, 1)
    elif t in ("copies", "canson", "ramette", "etiquettes"):
        if t == "ramette":
            b = f'<rect x="90" y="150" width="220" height="150" rx="6" fill="{"#fff" if not prem else "#f6f1e4"}" stroke="#ccc"/><rect x="90" y="150" width="220" height="60" fill="{c}"/><text x="200" y="190" font-size="30" font-family="sans-serif" font-weight="700" fill="#fff" text-anchor="middle">A4 · 80 g</text>'
        elif t == "etiquettes":
            b = '<rect x="110" y="70" width="180" height="260" rx="6" fill="#fff" stroke="#ccc"/>' + "".join(f'<rect x="{126 + (i % 2) * 80}" y="{86 + (i // 2) * 46}" width="68" height="36" rx="8" fill="{c}" opacity=".85"/>' for i in range(10))
        else:
            fill = ["#d93b3b", "#f2b10a", "#2e8b57", "#1b4fd1"] if "couleur" in a["base"] else ["#fff"] * 4
            b = "".join(f'<rect x="{100 + i * 10}" y="{80 + i * 10}" width="200" height="260" rx="4" fill="{fill[i]}" stroke="#d0d4dc"/>' for i in range(4))
            if t == "copies":
                b += "".join(f'<path d="M145 {140 + i * 20}h180" stroke="#9aa6cc" stroke-width="1.5"/>' for i in range(9))
    elif t == "gomme":
        b = f'<g transform="rotate(-12 200 220)"><rect x="110" y="170" width="180" height="90" rx="14" fill="#fff" stroke="#d0d4dc" stroke-width="3"/><rect x="170" y="170" width="120" height="90" rx="10" fill="{c}"/></g>'
    elif t == "taille":
        b = f'<rect x="130" y="150" width="140" height="150" rx="20" fill="url(#b)"/><rect x="150" y="170" width="100" height="40" rx="8" fill="#c8cfdc"/><circle cx="200" cy="190" r="10" fill="#2a2d36"/>'
    elif t == "correcteur":
        b = f'<rect x="110" y="150" width="190" height="110" rx="40" fill="url(#b)"/><rect x="280" y="190" width="40" height="30" rx="6" fill="#fff" stroke="#ccc"/>'
    elif t == "marqueur":
        return pen({**a, "couleur": "blanc"}, ink=c, kind="stylo")
    elif t == "colle_baton":
        b = f'<rect x="160" y="90" width="80" height="230" rx="16" fill="url(#b)"/><rect x="160" y="90" width="80" height="60" rx="16" fill="{sh(c, -.35)}"/><rect x="176" y="190" width="48" height="70" rx="6" fill="#fff"/>'
    elif t == "colle_liquide":
        b = f'<path d="M150 150 h100 v170 q0 20 -20 20 h-60 q-20 0 -20 -20z" fill="url(#b)"/><path d="M180 150 l10 -60 h20 l10 60z" fill="#fff" stroke="#ccc"/><rect x="164" y="220" width="72" height="60" rx="6" fill="#fff"/>'
    elif t == "ciseaux":
        b = f'<circle cx="150" cy="290" r="36" fill="none" stroke="{c}" stroke-width="18"/><circle cx="250" cy="290" r="36" fill="none" stroke="{c}" stroke-width="18"/><path d="M168 260 L240 80 M232 260 L160 80" stroke="#b7c2d6" stroke-width="16" stroke-linecap="round"/>'
    elif t == "gouache":
        cols = ["#d93b3b", "#f2b10a", "#2e8b57", "#1b4fd1", "#2a2d36", "#fff"]
        b = "".join(f'<g transform="translate({90 + i * 46} 120)"><rect width="38" height="160" rx="8" fill="#e9edf3" stroke="#ccc"/><rect y="50" width="38" height="60" fill="{x}"/><rect x="10" y="-20" width="18" height="22" rx="3" fill="#2a2d36"/></g>' for i, x in enumerate(cols))
    elif t == "pinceaux":
        b = "".join(f'<g transform="translate({140 + i * 60} 200) rotate({-8 + i * 8})"><rect x="-6" y="-120" width="12" height="190" rx="5" fill="{c}"/><rect x="-8" y="60" width="16" height="30" fill="#c8cfdc"/><path d="M-8 90 q8 50 16 0z" fill="#3a2a1a"/></g>' for i in range(3))
    elif t == "pate":
        cols = ["#d93b3b", "#f2b10a", "#2e8b57", "#1b4fd1", "#8e5cc8", "#ec6fa0"]
        b = "".join(f'<rect x="{90 + (i % 3) * 76}" y="{130 + (i // 3) * 90}" width="66" height="76" rx="12" fill="{x}"/>' for i, x in enumerate(cols))
    elif t == "sport":
        b = f'<rect x="70" y="170" width="260" height="150" rx="70" fill="url(#b)"/><path d="M140 170 q60 -80 120 0" stroke="{sh(c, -.4)}" stroke-width="14" fill="none"/><path d="M90 245 h220" stroke="#fff" stroke-width="10" opacity=".7"/>'
    elif t == "lunch":
        b = f'<rect x="70" y="170" width="200" height="150" rx="24" fill="url(#b)"/><rect x="70" y="170" width="200" height="40" rx="20" fill="{sh(c, -.3)}"/>' + motif_svg(a["motif"], 170, 262, .9)
        b += f'<rect x="282" y="120" width="60" height="200" rx="20" fill="{sh(c, .3)}"/><rect x="294" y="96" width="36" height="30" rx="8" fill="#2a2d36"/>'
    elif t == "gourde":
        b = f'<rect x="150" y="110" width="100" height="230" rx="36" fill="url(#b)"/><rect x="168" y="70" width="64" height="50" rx="12" fill="#2a2d36"/>' + motif_svg(a["motif"], 200, 240, .8)
    else:
        b = f'<rect x="110" y="110" width="180" height="200" rx="20" fill="url(#b)"/>'
    if prem and t not in ("gouache",):
        b += premium_badge(300, 300)
    return frame(b, c)


def draw(a):
    t = a["type"]
    if t in ("cartable", "cartable_roues", "sac", "sac_mini"):
        return bag(a, mini=t == "sac_mini", wheels=t == "cartable_roues", tall=t == "sac")
    if t in ("trousse", "trousse_double", "trousse_garnie", "plumier"):
        return pouch(a, double=t == "trousse_double", garnie=t == "trousse_garnie", rigid=t == "plumier")
    if t in ("cahier", "spirale", "repertoire", "dessin", "musique", "agenda"):
        return book(a, t)
    if t in ("stylo", "plume", "effaceur"):
        ink = next((COL[w] for w in ("bleu", "rouge", "vert", "noir") if w in a["base"]), "#1b4fd1")
        return pen(a, ink, t)
    if t == "stylos4":
        return multi_pens(["#1b4fd1", "#d93b3b", "#2e8b57", "#2a2d36"], a)
    if t in ("crayon", "crayons3", "portemine"):
        return multi_pens(["#f2b10a"] * (3 if t == "crayons3" else 1), a, kind="crayon")
    if t == "surligneurs":
        return multi_pens(["#f6e600", "#ff6fae", "#5fd16b", "#59c3ff"], a, kind="surligneur")
    if t in ("boite_crayons", "boite_cire", "boite_feutres"):
        n = 24 if "24" in a["base"] else 12
        return boxed(a, n, "feutres" if t == "boite_feutres" else "crayons")
    return simple_shape(a)


async def main():
    from playwright.async_api import async_playwright
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    index, todo = {}, {}
    papeterie = [p for p in cat["produits"] if p["rubrique"] == "papeterie"]
    couleurs_famille = {}
    for p in papeterie:
        if p["id"] != p.get("famille", p["id"]):
            c = analyse(p)["couleur"]
            couleurs_famille.setdefault(p["famille"], set()).update({c, {"bleue": "bleu", "verte": "vert", "violette": "violet"}.get(c, c)})
    for p in papeterie:
        a = analyse(p, couleurs_famille.get(p["id"], ()) if p["id"] == p.get("famille", p["id"]) else ())
        k = key_of(a)
        index[p["id"]] = f"{k}.jpg"
        todo.setdefault(k, a)
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page(viewport={"width": 400, "height": 400})
        for k, a in todo.items():
            await pg.set_content(f'<html><body style="margin:0">{draw(a)}</body></html>')
            await pg.screenshot(path=str(OUT / f"{k}.jpg"), type="jpeg", quality=82)
        await b.close()
    (HERE / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(todo)} images pour {len(index)} produits")


if __name__ == "__main__":
    asyncio.run(main())
