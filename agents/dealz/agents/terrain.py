"""Signaux terrain : /signal avec une capture d'écran (groupe Facebook, page, Marketplace…) ou un texte.

L'IA (modèle rapide, vision) lit la capture et en tire le produit, le prix affiché et l'intérêt
(commentaires, réactions). AUCUN nom, numéro ou email de particulier n'est gardé : consigne au modèle,
puis filtre dans le code. Le signal part sur le tableau partagé ; l'expert Tendances le rattache
à une opportunité ou le garde pour son analyse du mercredi.
"""
import json
import re

from .. import bus, llm
from ..links import strip_personal

SYSTEM = """Tu lis une capture d'écran (ou un texte) venant d'un groupe Facebook tunisien d'achat-vente, d'une page de boutique ou d'un échange client.
Extrais uniquement l'information commerciale. Ne recopie JAMAIS un nom de personne, un numéro de téléphone, un email ou une adresse précise.
Réponds UNIQUEMENT en JSON :
{"type": "demande|offre|pub|avis|autre", "produit": "type de produit précis", "categorie": "papeterie|cartables|informatique|petit_electro|mobilier|jouets_deco|autre",
 "prix_affiche_tnd": null, "commentaires": null, "reactions": null, "partages": null, "region": "gouvernorat si visible, sinon null",
 "resume": "1 phrase factuelle, sans aucune donnée personnelle"}
Mets null quand l'information n'est pas visible. N'invente rien."""


def _int(x):
    try:
        return int(str(x).replace(" ", "").replace("k", "000").replace("K", "000"))
    except (TypeError, ValueError):
        return None


def clean(d: dict, fallback_text: str = "") -> dict:
    out = {"type": d.get("type") if d.get("type") in ("demande", "offre", "pub", "avis", "autre") else "autre",
           "produit": strip_personal(str(d.get("produit") or fallback_text[:60]))[:100],
           "categorie": str(d.get("categorie") or "autre")[:30],
           "prix_affiche_tnd": None, "commentaires": _int(d.get("commentaires")), "reactions": _int(d.get("reactions")),
           "partages": _int(d.get("partages")), "region": strip_personal(str(d.get("region") or ""))[:40] or None,
           "resume": strip_personal(str(d.get("resume") or fallback_text))[:240]}
    try:
        out["prix_affiche_tnd"] = float(str(d.get("prix_affiche_tnd")).replace(",", ".")) if d.get("prix_affiche_tnd") not in (None, "") else None
    except ValueError:
        pass
    out["interet"] = sum(x or 0 for x in (out["commentaires"], out["reactions"], out["partages"]))
    return out


def record(texte: str = "", image=None, par: str = "Équipe", mock: bool = False):
    """Analyse et publie un signal. image = (media_type, base64). Renvoie (event_id, signal)."""
    texte = (texte or "").strip()
    sig = None
    if image or texte:
        raw = llm.ask("signal", SYSTEM, texte or "Analyse la capture.", max_tokens=400, images=[image] if image else None)
        if not getattr(raw, "simulated", False):
            m = re.search(r"\{[\s\S]*\}", raw or "")
            try:
                sig = clean(json.loads(m.group(0)), texte) if m else None
            except json.JSONDecodeError:
                sig = None
    if sig is None:  # sans IA : on garde le texte (nettoyé)
        if not texte:
            return None, None
        sig = clean({"produit": texte[:60], "resume": texte}, texte)
    prix = f", {sig['prix_affiche_tnd']:.0f} DT" if sig["prix_affiche_tnd"] else ""
    resume = f"[{sig['type']}] {sig['produit']}{prix} — intérêt {sig['interet']}"
    eid = bus.publish("signal_terrain", par, resume, sig, mock=mock)
    bus.dispatch()
    return eid, sig
