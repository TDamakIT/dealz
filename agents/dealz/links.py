"""Les liens entre agents : qui réagit à quoi, et comment (règles simples, l'IA seulement pour rédiger).

Actifs dès maintenant :
  opportunite_go  → Prospection : met « fournisseurs de <produit> » en tête de sa file
                  → SEO         : crée une fiche produit BROUILLON (sans prix : c'est à vous de le fixer)
                  → Marketing   : prépare 3 publications de lancement (à valider)
  signal_terrain  → Tendances   : rattache le signal à une opportunité proche (+1 au score) ; sinon le garde pour l'analyse du mercredi
  prix_concurrent → Stock       : calcule la marge si on s'aligne et tranche (s'aligner / tenir le prix + angle service)
  priorites       → Prospection : met les segments prioritaires dans sa file
                  → Marketing   : centre les publications de la semaine sur les priorités
Après le lancement (LIENS_VENTES=1) :
  rupture_proche  → Prospection : cherche un second fournisseur ; Marketing : arrête de pousser le produit
"""
import os
import re
from datetime import datetime, timedelta, timezone

from . import db, telegram
from .config import settings


def sales_links_enabled() -> bool:
    return os.getenv("LIENS_VENTES", "0") == "1"


def _norm(s):
    from .agents.tendances import norm
    return norm(s)


# --- Files d'attente partagées (dans la table state) ----------------------------

def queue_segment(segment: str, origine: str):
    file = db.get_state("prospection_file", [])
    if any(_norm(x["segment"]) == _norm(segment) for x in file):
        return False
    file.append({"segment": segment, "origine": origine})
    db.set_state("prospection_file", file[-20:])
    return True


def pop_segment():
    file = db.get_state("prospection_file", [])
    if not file:
        return None
    first, rest = file[0], file[1:]
    db.set_state("prospection_file", rest)
    return {**first, "segment": first["segment"].replace(" (démo)", "")}


def _remember(key, item, days=21, maxlen=15):
    now = datetime.now(timezone.utc)
    items = [x for x in db.get_state(key, []) if datetime.fromisoformat(x["ts"]) > now - timedelta(days=days)]
    items.append({**item, "ts": now.isoformat(timespec="seconds")})
    db.set_state(key, items[-maxlen:])


def recent(key, days=21):
    now = datetime.now(timezone.utc)
    return [x for x in db.get_state(key, []) if datetime.fromisoformat(x["ts"]) > now - timedelta(days=days)]


# --- Réactions -----------------------------------------------------------------

def prospection_on_go(ev):
    p = ev["payload"]
    seg = f"fournisseurs, grossistes et importateurs de {p['produit']} en Tunisie (de préférence Sfax)"
    return "ajouté en tête de la file de prospection" if queue_segment(seg, f"opportunité #{p.get('id')}") else "déjà dans la file"


def seo_on_go(ev):
    from .agents.base import get_woo
    p = ev["payload"]
    woo = get_woo()
    if not woo:
        return "boutique non connectée : fiche brouillon non créée"
    sku = f"OPP-{p.get('id')}"
    if woo.get("products", sku=sku):
        return f"fiche {sku} déjà créée"
    res = woo.post("products", {
        "name": p["produit"][:120], "status": "draft", "sku": sku, "type": "simple",
        "short_description": f"<p>{telegram.esc(p['produit'])} — fiche préparée par les agents, à compléter.</p>",
        "meta_data": [{"key": "_dealz_opportunite", "value": str(p.get("id"))},
                      {"key": "_a_completer", "value": "prix, photos, stock, fournisseur"}]})
    return f"fiche brouillon {sku} créée (id {res.get('id', '?')}) : ajoutez prix, photos et stock, puis publiez ; le SEO l'optimisera ensuite"


def marketing_on_go(ev):
    from .agents.marketing import MarketingAgent
    p = ev["payload"]
    _remember("marketing_lancements", {"produit": p["produit"], "prix_marche": p.get("prix_marche")})
    MarketingAgent().launch(p["produit"], p.get("prix_marche"))
    return "publications de lancement proposées (rapport Marketing)"


def tendances_on_signal(ev):
    s = ev["payload"]
    mots = {m for m in _norm(s.get("produit", "")).split() if len(m) > 2}
    if not mots:
        return "signal gardé pour l'analyse du mercredi"
    best, score = None, 0
    for o in db.opportunites(limit=100):
        if o["statut"] in ("abandon",):
            continue
        common = len(mots & set(_norm(o["produit"]).split()))
        if common > score:
            best, score = o, common
    if best and score >= max(1, min(2, len(mots))):
        new_score = min(5, (best["score"] or 3) + 1)
        with db.conn() as c:
            c.execute("UPDATE opportunites SET score=?, pourquoi=pourquoi || ? WHERE id=?",
                      (new_score, f" | Signal terrain #{ev['id']} : {s.get('resume', '')[:120]}", best["id"]))
        return f"rattaché à l'opportunité #{best['id']} ({best['produit']}) : score {best['score']} → {new_score}"
    return "aucune opportunité proche : gardé pour l'analyse du mercredi"


def stock_on_prix(ev):
    p = ev["payload"]
    achat, median, notre = p.get("cout_achat"), p.get("median_marche"), p.get("notre_prix")
    if not (achat and median and notre):
        return "coût d'achat inconnu : impossible de trancher"
    marge_alignee = (median - achat) / median * 100
    marge_actuelle = (notre - achat) / notre * 100
    if marge_alignee >= settings.seuil_marge_pct:
        decision = (f"S'aligner est possible : à {median:.0f} DT la marge passe de {marge_actuelle:.0f} % à {marge_alignee:.0f} %.")
        lvl = "opportunite"
    else:
        decision = (f"Ne pas s'aligner : à {median:.0f} DT la marge tomberait à {marge_alignee:.0f} % (seuil {settings.seuil_marge_pct:.0f} %). "
                    f"Tenir {notre:.0f} DT et vendre le service (livraison 24 h à Sfax, paiement à la livraison, conseil).")
        lvl = "important"
        _remember("marketing_angles", {"produit": p["produit"], "angle": "service plutôt que prix"})
    aid = db.add_alert("Achats & stock", lvl, f"Prix concurrent : {p['produit']}", decision, f"prixlien:{ev['id']}")
    if aid and telegram.send(telegram.format_alert(lvl, "Achats & stock (lien Veille)", f"Prix concurrent : {p['produit']}", decision)):
        db.mark_sent(aid)
    return decision


def prospection_on_priorites(ev):
    segs = [s for pr in ev["payload"].get("priorites", []) for s in pr.get("segments_prospection", [])][:3]
    added = [s for s in segs if queue_segment(s, "priorités de la semaine")]
    return f"{len(added)} segment(s) ajouté(s) à la file" if added else "aucun segment de prospection dans les priorités"


def marketing_on_priorites(ev):
    return "les publications de dimanche suivront les priorités"   # lues dans MarketingAgent.run


def prospection_on_rupture(ev):
    p = ev["payload"]
    seg = f"autres fournisseurs de {p['produit']} en Tunisie (aujourd'hui : {p.get('fournisseur', '?')})"
    return "second fournisseur cherché à la prochaine prospection" if queue_segment(seg, f"rupture proche #{ev['id']}") else "déjà dans la file"


def marketing_on_rupture(ev):
    _remember("marketing_ne_pas_pousser", {"produit": ev["payload"]["produit"]}, days=14)
    return "le Marketing ne mettra plus ce produit en avant pendant 14 jours"


LINKS = [
    {"nom": "Prospection ← opportunité validée", "sujets": ("opportunite_go",), "reagir": prospection_on_go},
    {"nom": "SEO ← opportunité validée", "sujets": ("opportunite_go",), "reagir": seo_on_go},
    {"nom": "Marketing ← opportunité validée", "sujets": ("opportunite_go",), "reagir": marketing_on_go},
    {"nom": "Tendances ← signal terrain", "sujets": ("signal_terrain",), "reagir": tendances_on_signal},
    {"nom": "Stock ← prix concurrent", "sujets": ("prix_concurrent",), "reagir": stock_on_prix},
    {"nom": "Prospection ← priorités", "sujets": ("priorites",), "reagir": prospection_on_priorites},
    {"nom": "Marketing ← priorités", "sujets": ("priorites",), "reagir": marketing_on_priorites},
    {"nom": "Prospection ← rupture proche", "sujets": ("rupture_proche",), "reagir": prospection_on_rupture, "apres_lancement": True},
    {"nom": "Marketing ← rupture proche", "sujets": ("rupture_proche",), "reagir": marketing_on_rupture, "apres_lancement": True},
]


def validate_go(oid: int, mock=False):
    """Passe une opportunité en « go » et prévient les agents. Renvoie un message pour l'équipe."""
    from . import bus
    o = db.opportunite(oid)
    if not o:
        return "Opportunité introuvable."
    db.set_opportunite_status(oid, "go")
    bus.publish("opportunite_go", "Équipe", f"GO sur #{oid} {o['produit']}",
                {"id": oid, "produit": o["produit"], "categorie": o["categorie"], "prix_marche": o["prix_marche"]},
                key=f"go:{oid}", mock=mock)
    bus.dispatch()
    lines = [f"✅ GO sur #{oid} {o['produit']}. Les agents ont réagi :"]
    ev = bus.events("opportunite_go", limit=20)
    mine = next((e for e in ev if e["payload"].get("id") == oid), None)
    for r in bus.reactions(mine["id"]) if mine else []:
        lines.append(f"• {r['subscriber'].split(' ←')[0]} : {r['result']}")
    return "\n".join(lines)


def set_priorities(items: list, agent: str, mock=False):
    """items = [{"titre", "pourquoi", "segments_prospection": [...], "produits": [...]}]"""
    from . import bus
    items = [i for i in items if i.get("titre")][:3]
    db.set_state("priorites", {"ts": db.now_iso(), "par": agent, "priorites": items})
    bus.publish("priorites", agent, " · ".join(i["titre"] for i in items), {"priorites": items}, mock=mock)
    bus.dispatch()
    return items


def strip_personal(text: str) -> str:
    """Retire numéros de téléphone et emails d'un texte venant d'un groupe (données de particuliers)."""
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[email retiré]", text or "")
    return re.sub(r"(?:\+?216[\s.-]?)?(?:\d[\s.-]?){8}", "[numéro retiré]", text)
