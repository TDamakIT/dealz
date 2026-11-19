"""Calcul du coût de revient d'un produit importé de Chine (sans IA, déterministe).

Toutes les hypothèses sont dans data/import_params.json. Ce sont des ESTIMATIONS :
le vrai taux dépend du code SH du produit, à confirmer avec un transitaire avant de commander.
TVA et avance d'impôt sont payées à la douane (trésorerie) mais récupérables : elles ne sont pas dans le coût de revient.
"""
import json
import os
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parents[2] / "data" / "import_params.json"


def params() -> dict:
    p = Path(os.getenv("IMPORT_PARAMS_PATH", "/app/data/import_params.json"))
    return json.loads((p if p.exists() else _DEFAULT).read_text(encoding="utf-8"))


def landed_cost(fob_usd: float, qte: int, categorie: str = "autre", prix_vente_ttc: float = None, p: dict = None) -> dict:
    """Coût de revient unitaire, trésorerie à mobiliser et marge, pour `qte` unités à `fob_usd` pièce."""
    p = p or params()
    cat = p["categories"].get(categorie) or p["categories"]["autre"]
    qte = max(1, int(qte))
    fob = fob_usd * p["usd_tnd"] * qte                                   # TND, toute la commande
    fret = fob * p["fret_pct_fob"] / 100
    assurance = (fob + fret) * p["assurance_pct"] / 100
    valeur_douane = fob + fret + assurance                               # valeur CAF
    droits = valeur_douane * cat["droit_douane_pct"] / 100
    redevance = droits * p["redevance_douane_pct_droits"] / 100
    conso = (valeur_douane + droits) * cat["droit_conso_pct"] / 100
    fodec = valeur_douane * p["fodec_pct"] / 100
    base_tva = valeur_douane + droits + redevance + conso + fodec
    tva = base_tva * p["tva_pct"] / 100
    avance = (base_tva + tva) * p["avance_impot_pct"] / 100
    transitaire = p["transitaire_tnd_par_envoi"]
    cout_total = base_tva + transitaire                                  # hors TVA et avance (récupérables)
    cout_u = cout_total / qte
    out = {
        "categorie": categorie, "qte": qte, "fob_usd": fob_usd, "usd_tnd": p["usd_tnd"],
        "cout_revient_unitaire_tnd": round(cout_u, 3),
        "tresorerie_tnd": round(cout_total + tva + avance, 0),
        "detail_tnd": {k: round(v, 0) for k, v in (("fob", fob), ("fret", fret), ("assurance", assurance), ("droits", droits),
                                                    ("redevance", redevance), ("droit_conso", conso), ("fodec", fodec),
                                                    ("tva_recuperable", tva), ("avance_impot", avance), ("transitaire", transitaire))},
        "autofinancement_bct": cat["autofinancement_bct"], "controle_technique": cat["controle_technique"], "note": cat["note"],
    }
    if prix_vente_ttc:
        ht = prix_vente_ttc / (1 + p["tva_pct"] / 100)
        frais = ht * p["frais_vente_pct"] / 100 + p["livraison_tnd_par_unite"]
        marge = (ht - cout_u - frais) / ht * 100
        out.update(prix_vente_ttc=prix_vente_ttc, prix_vente_ht=round(ht, 3), frais_vente_unitaire=round(frais, 3),
                   marge_nette_pct=round(marge, 1), prix_mini_ttc_pour_marge_bonne=round(
                       (cout_u + p["livraison_tnd_par_unite"]) / (1 - (p["seuil_marge_bonne_pct"] + p["frais_vente_pct"]) / 100)
                       * (1 + p["tva_pct"] / 100), 3))
        out["verdict"] = verdict(marge, p)
    return out


def verdict(marge_pct: float, p: dict) -> str:
    if marge_pct >= p["seuil_marge_bonne_pct"]:
        return "à creuser"
    if marge_pct >= p["seuil_marge_limite_pct"]:
        return "limite"
    return "non rentable"


def format_calc(c: dict) -> str:
    d = c["detail_tnd"]
    lines = [f"{c['qte']} pièces à {c['fob_usd']} $ FOB ({c['categorie']}, 1 $ = {c['usd_tnd']} DT)",
             f"Coût de revient : {c['cout_revient_unitaire_tnd']:.3f} DT / pièce",
             f"Trésorerie à mobiliser : ~{c['tresorerie_tnd']:,.0f} DT (dont TVA {d['tva_recuperable']:,.0f} et avance d'impôt {d['avance_impot']:,.0f}, récupérables)".replace(",", " "),
             f"Détail : FOB {d['fob']:.0f} · fret {d['fret']:.0f} · droits {d['droits']:.0f} · FODEC {d['fodec']:.0f} · transitaire {d['transitaire']:.0f}"]
    if "marge_nette_pct" in c:
        lines.append(f"Vendu {c['prix_vente_ttc']:.3f} DT TTC → marge nette {c['marge_nette_pct']} % → {c['verdict'].upper()}")
        lines.append(f"Prix mini pour une bonne marge : {c['prix_mini_ttc_pour_marge_bonne']:.3f} DT TTC")
    if c["autofinancement_bct"]:
        lines.append("⚠️ Catégorie sur la liste BCT « non prioritaire » : import à financer à 100 % sur fonds propres (pas de crédit bancaire).")
    if c["controle_technique"]:
        lines.append("⚠️ Contrôle technique / conformité à l'import probable : prévoir certificats et délai.")
    lines.append("Estimation : taux à confirmer avec un transitaire selon le code SH.")
    return "\n".join(lines)
