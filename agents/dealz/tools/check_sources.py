"""Vérifie les pages suivies par l'expert Tendances : produits lus ? tri « meilleures ventes » disponible ?
Usage : docker compose exec agents python -m dealz.tools.check_sources
"""
from .. import scraper
from ..agents.tendances import sources


def main():
    with scraper.new_client() as client:
        for s in sources():
            try:
                items, tri = scraper.fetch_ranked(s["url"], client, cat=s["categorie"])
                etat = "OK" if items else "AUCUN PRODUIT LU (sélecteurs à adapter)"
                print(f"[{etat}] {s['site']} — {s['nom']} : {len(items)} produits, tri = {tri}")
                for it in items[:3]:
                    print(f"     {it['rang']}. {it['nom'][:70]} — {it['prix']:.3f} DT {'(en stock)' if it['en_stock'] else ''}")
            except Exception as e:
                print(f"[ERREUR] {s['site']} — {s['nom']} : {e}")


if __name__ == "__main__":
    main()
