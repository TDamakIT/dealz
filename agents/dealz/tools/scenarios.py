"""Scénarios de démonstration : injecte des données FICTIVES (marquées « démo ») et fait réagir les vrais agents.

Usage (sur la VM) :
  docker compose exec agents python -m dealz.tools.scenarios airfryer     # de la rumeur au produit en rayon
  docker compose exec agents python -m dealz.tools.scenarios prix         # un concurrent casse les prix
  docker compose exec agents python -m dealz.tools.scenarios rupture      # rupture proche (lien en veille avant lancement)
  docker compose exec agents python -m dealz.tools.scenarios rupture --ventes   # la même, liens « après lancement » activés
  docker compose exec agents python -m dealz.tools.scenarios priorites    # le Stratège fixe les priorités
  docker compose exec agents python -m dealz.tools.scenarios tous
  docker compose exec agents python -m dealz.tools.scenarios reset        # efface toutes les données de démo

Les messages partent vraiment sur Telegram. Sans clé Claude, les textes marketing sont remplacés par une trame.
"""
import os
import sys
from datetime import date, timedelta

from .. import bus, db, links
from ..agents.base import get_woo
from ..agents.tendances import market_price

DEMO = "(démo)"


def step(txt):
    print(f"\n▶ {txt}")


def show_reactions(eid):
    for r in bus.reactions(eid):
        print(f"   ↳ {r['subscriber']} : {r['result']}")


def airfryer():
    produit = f"Friteuse à air 5 L {DEMO}"
    step("1. Relevés concurrents des 7 derniers jours : la friteuse à air 5 L est n°2 des ventes chez Tunisianet")
    for i in range(7, 0, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        db.save_tendances(d, [
            {"site": "Tunisianet", "categorie": "petit_electro", "page": f"Petit électro {DEMO}", "tri": "ventes", "rang": 2,
             "pid": "demo-1", "nom": "Friteuse à air 5L 1500W noire", "prix": 189.0 if i > 2 else 179.0, "en_stock": 1},
            {"site": "Tunisianet", "categorie": "petit_electro", "page": f"Petit électro {DEMO}", "tri": "ventes", "rang": 5,
             "pid": "demo-2", "nom": "Bouilloire électrique 1.7L", "prix": 49.0, "en_stock": int(i > 1)}])
    prix = market_price("friteuse air 5l", db.tendances_snapshot((date.today() - timedelta(days=1)).isoformat()))
    print(f"   prix marché relevé : {prix} DT")

    step("2. Mercredi, l'expert Tendances propose l'opportunité (score 3, canal fournisseur local)")
    oid = db.add_opportunite({"agent": f"Expert Tendances {DEMO}", "produit": produit, "categorie": "petit_electro",
                              "canal": "fournisseur local", "score": 3, "prix_marche": prix,
                              "pourquoi": "Top 2 des ventes Tunisianet depuis 7 jours, prix en baisse (189 → 179 DT).",
                              "preuves": ["Tunisianet : n°2 des ventes 7 jours sur 7"], "dedupe": "opp:demo friteuse a air 5 l"})
    print(f"   opportunité #{oid} créée")

    step("3. Ta sœur envoie /signal avec la capture d'un groupe de Sfax (ici simulée, sans données personnelles)")
    eid = bus.publish("signal_terrain", f"Sœur {DEMO}", "[demande] friteuse à air 5 L, 180 DT — intérêt 162",
                      {"type": "demande", "produit": "friteuse à air 5 L", "categorie": "petit_electro", "prix_affiche_tnd": 180,
                       "commentaires": 150, "reactions": 12, "interet": 162, "region": "Sfax",
                       "resume": "Demande dans un groupe d'achat-vente de Sfax : qui vend une friteuse à air 5 L autour de 180 DT ?"}, mock=True)
    bus.dispatch()
    show_reactions(eid)

    step("4. Vous validez : /opportunite {} go".format(oid))
    print(links.validate_go(oid, mock=True))
    print("\n   À vérifier : file de prospection =", [x["segment"] for x in db.get_state("prospection_file", [])])
    print("   Ensuite : /prospection (les fournisseurs de friteuses passent en premier), /sourcing", oid, "pour comparer avec l'import.")


def prix():
    step("Un concurrent est nettement moins cher sur deux de nos produits (données fictives)")
    cas = [{"id": 0, "produit": f"PC portable i5 16 Go {DEMO}", "notre_prix": 2499, "median_marche": 2190, "cout_achat": 2050},
           {"id": 0, "produit": f"Imprimante laser {DEMO}", "notre_prix": 459, "median_marche": 399, "cout_achat": 250}]
    for c in cas:
        eid = bus.publish("prix_concurrent", f"Veille {DEMO}", f"{c['produit']} : {(c['notre_prix'] / c['median_marche'] - 1) * 100:.0f} % au-dessus du marché",
                          c, mock=True)
        bus.dispatch()
        print(f" • {c['produit']}")
        show_reactions(eid)
    print("\n   Dimanche, le Marketing utilisera l'angle « service plutôt que prix » pour le PC.")


def rupture(ventes=False):
    if ventes:
        os.environ["LIENS_VENTES"] = "1"
    step(f"Le cartable à 39 DT part vite : 12 en stock pour 40 ventes en 30 jours (liens après lancement : {'ACTIVÉS' if ventes else 'en veille'})")
    eid = bus.publish("rupture_proche", f"Achats & stock {DEMO}", f"Cartable 2 compartiments {DEMO} : 12 en stock pour 40 ventes/30 j",
                      {"produit": f"Cartable 2 compartiments {DEMO}", "stock": 12, "ventes_30j": 40, "fournisseur": "Office House"}, mock=True)
    bus.dispatch()
    show_reactions(eid)
    if not ventes:
        print("\n   Relance avec --ventes pour voir la réaction une fois la boutique lancée.")


def priorites():
    step("Lundi, le Stratège fixe 3 priorités (ici écrites à la main)")
    items = links.set_priorities([
        {"titre": f"Trouver un fournisseur de petit électroménager {DEMO}", "pourquoi": "rayon vide, demande visible",
         "responsable": "père", "segments_prospection": [f"grossistes en petit électroménager à Sfax {DEMO}"]},
        {"titre": f"Préparer 5 packs rentrée par niveau {DEMO}", "pourquoi": "temps fort dans 8 mois, anticiper les achats",
         "responsable": "sœur", "segments_prospection": []},
        {"titre": f"Signer 3 écoles privées de Sfax {DEMO}", "pourquoi": "volume B2B récurrent", "responsable": "sœur",
         "segments_prospection": [f"écoles primaires privées à Sfax {DEMO}"]}], f"Stratège {DEMO}", mock=True)
    ev = bus.events("priorites", limit=1)[0]
    for i, p in enumerate(items, 1):
        print(f"   {i}. {p['titre']}")
    show_reactions(ev["id"])
    print("   Vérifie sur Telegram : /priorites et /tableau")


def reset():
    n = bus.clear_mock()
    with db.conn() as c:
        opp_ids = [r[0] for r in c.execute("SELECT id FROM opportunites WHERE produit LIKE ?", (f"%{DEMO}%",))]
        c.execute("DELETE FROM opportunites WHERE produit LIKE ?", (f"%{DEMO}%",))
        c.execute("DELETE FROM tendances_snap WHERE page LIKE ?", (f"%{DEMO}%",))
        c.execute("DELETE FROM alerts WHERE title LIKE ?", (f"%{DEMO}%",))
        c.execute("DELETE FROM reports WHERE title LIKE ?", (f"%{DEMO}%",))
    db.set_state("prospection_file", [x for x in db.get_state("prospection_file", []) if DEMO not in x["segment"]])
    for k in ("marketing_lancements", "marketing_angles", "marketing_ne_pas_pousser"):
        db.set_state(k, [x for x in db.get_state(k, []) if DEMO not in x.get("produit", "")])
    if DEMO in str((db.get_state("priorites") or {}).get("par", "")):
        db.set_state("priorites", None)
    woo, removed = get_woo(), 0
    for oid in opp_ids if woo else []:
        for p in woo.get("products", sku=f"OPP-{oid}", status="any"):
            woo.delete(f"products/{p['id']}")
            removed += 1
    print(f"Démo effacée : {n} événement(s), {len(opp_ids)} opportunité(s), {removed} fiche(s) brouillon.")


def main(argv):
    db.init()
    name = argv[0] if argv else "tous"
    if name == "reset":
        return reset()
    runs = {"airfryer": airfryer, "prix": prix, "priorites": priorites, "rupture": lambda: rupture("--ventes" in argv)}
    for n in (runs if name == "tous" else [name]):
        if n not in runs:
            print(__doc__)
            return
        print(f"\n===== Scénario {n} =====")
        runs[n]()
    print("\nTout est marqué « démo ». Pour effacer : python -m dealz.tools.scenarios reset")


if __name__ == "__main__":
    main(sys.argv[1:])
