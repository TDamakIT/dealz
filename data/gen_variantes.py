"""Catalogue de démo. Données FICTIVES.

Règle « qui choisit ? » :
  - l'ENFANT choisit (cartable, sac, trousse, plumier, gourde, boîte à goûter, agenda, cahier de textes, protège-cahier) :
    par gamme 3 modèles garçon + 3 fille + 2 mixtes → au moins 5 modèles par genre et par gamme ;
  - les PARENTS choisissent (stylos, cahiers, règles, colle…) : 2 modèles par gamme, pas de genre ;
  - chaque produit de papeterie existe en 3 gammes : petit prix (eco), moyenne gamme (standard), haut de gamme (premium) ;
  - le champ "choix" (enfant | parent) est à renseigner aussi dans le vrai catalogue ;
  - tous les modèles ajoutés sont en stock.
Usage : python3 data/gen_variantes.py   (idempotent : repart des 104 produits de base)
"""
import csv
import json
import random
from pathlib import Path

P = Path(__file__).with_name("catalog.json")
random.seed(7)

GENRE = {"DZ-0009", "DZ-0052", "DZ-0062", "DZ-0063", "DZ-0064", "DZ-0065", "DZ-0066", "DZ-0067", "DZ-0068", "DZ-0069",
         "DZ-0071", "DZ-0073", "DZ-0074"}
GAMME = {"eco": ("petit prix", "سوم صغير", 0.70, 0.28), "standard": ("", "", 1.0, None), "premium": ("haut de gamme", "راقي", 1.70, 0.42)}
DESC = {  # 5 déclinaisons par catégorie (articles sans genre)
    "Cahiers": [("couverture bleue", "غلاف أزرق"), ("couverture rouge", "غلاف أحمر"), ("couverture verte", "غلاف أخضر"),
                ("couverture jaune", "غلاف أصفر"), ("couverture violette", "غلاف بنفسجي")],
    "Écriture": [("modèle classique", "كلاسيك"), ("pointe fine", "رأس رقيق"), ("grip confort", "مسكة مريحة"),
                 ("corps triangulaire", "شكل مثلث"), ("séchage rapide", "ينشف بالزربة")],
    "Couleurs & arts": [("boîte carton", "علبة كرتون"), ("boîte métal", "علبة حديد"), ("étui zippé", "بسوستة"),
                        ("coloris vifs", "ألوان حية"), ("coloris pastel", "ألوان فاتحة")],
    "Géométrie & calcul": [("transparent", "شفاف"), ("coloré", "ملوّن"), ("flexible", "يتلوى"), ("métal", "حديد"), ("à motifs", "مزوّق")],
    "Classement & papeterie": [("bleu", "أزرق"), ("rouge", "أحمر"), ("vert", "أخضر"), ("jaune", "أصفر"), ("noir", "أكحل")],
}
MOTIFS = {
    "garcon": [("garçon, bleu motif foot", "أولاد، أزرق بالكورة"), ("garçon, noir motif dinosaures", "أولاد، أكحل بالديناصورات"),
               ("garçon, vert motif espace", "أولاد، أخضر بالفضاء"), ("garçon, gris motif voitures", "أولاد، رمادي بالكراهب"),
               ("garçon, marine rayé", "أولاد، كحلي مخطط")],
    "fille": [("fille, rose motif fleurs", "بنات، وردي بالورود"), ("fille, violet motif licorne", "بنات، بنفسجي باللّيكورن"),
              ("fille, corail motif papillons", "بنات، مرجاني بالفراشات"), ("fille, turquoise motif étoiles", "بنات، فيروزي بالنجوم"),
              ("fille, lilas motif cœurs", "بنات، ليلكي بالقلوب")],
    "mixte": [("rouge uni", "أحمر سادة"), ("jaune uni", "أصفر سادة"), ("gris uni", "رمادي سادة"), ("vert uni", "أخضر سادة"),
              ("bleu ciel uni", "سماوي سادة")],
}


def r3(x):
    return round(x, 3)


def nice(prix):
    return r3(round(prix) - 0.1) if prix >= 5 else r3(max(0.3, round(prix * 20) / 20))


def make(base, n, gamme, genre, desc, desc_ar, k):
    lab, lab_ar, mult, marge = GAMME[gamme]
    prix = nice(base["prix_vente"] * mult * k)
    marge = marge if marge is not None else (base["prix_vente"] - base["prix_achat"]) / base["prix_vente"]
    achat = r3(prix * (1 - marge))
    nom = f"{base['nom']} — {desc}" + (f" — {lab}" if lab else "")
    nom_ar = f"{base['nom_ar']} — {desc_ar}" + (f" — {lab_ar}" if lab_ar else "")
    return {**base, "id": f"DZV-{n:04d}", "nom": nom, "nom_ar": nom_ar, "prix_vente": prix, "prix_achat": achat,
            "marge_pct": round((prix - achat) / prix * 100, 1), "stock": random.choice([12, 24, 40, 80, 150, 300]),
            "famille": base["id"], "gamme": gamme, "genre": genre}


def main():
    cat = json.loads(P.read_text(encoding="utf-8"))
    base = [p for p in cat["produits"] if p["id"].startswith("DZ-0")]
    out, n = [], 0
    for p in base:
        p.update(famille=p["id"], gamme="standard", genre="mixte", choix="enfant" if p["id"] in GENRE else "parent")
        out.append(p)
        if p["rubrique"] != "papeterie":
            continue
        ks = [0.9, 0.95, 1.0, 1.05, 1.1]
        for gamme in ("eco", "standard", "premium"):
            if p["id"] in GENRE:
                plan = [("garcon", MOTIFS["garcon"][i]) for i in range(3)] + [("fille", MOTIFS["fille"][i]) for i in range(3)] + \
                       [("mixte", MOTIFS["mixte"][i]) for i in range(2)]
                if gamme == "standard" and p["stock"] > 0:   # le produit de base (s'il est en stock) compte comme un modèle mixte
                    plan = plan[:-1]
            else:
                plan = [("mixte", d) for d in DESC.get(p["categorie"], DESC["Classement & papeterie"])][:2]   # parents : 2 modèles
                if gamme == "standard" and p["stock"] > 0:   # le produit de base (s'il est en stock) compte comme un modèle
                    plan = plan[1:]
            for i, (genre, (d, d_ar)) in enumerate(plan):
                n += 1
                out.append(make(p, n, gamme, genre, d, d_ar, ks[i % 5]))
    cat["produits"] = out
    P.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    write_csv(cat)
    print(f"{len(base)} produits de base, {n} modèles ajoutés, {len(out)} références au total")


def write_csv(cat):
    """Fichier d'import WooCommerce (alternative au script d'import)."""
    rub = {r["id"]: r["nom"] for r in cat["rubriques"]}
    with P.with_name("woocommerce_import.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["SKU", "Name", "Type", "Published", "Categories", "Regular price", "Stock", "In stock?", "Meta: _cout_achat",
                    "Meta: _fournisseur", "Meta: _nom_ar", "Meta: _famille", "Meta: _gamme", "Meta: _genre", "Meta: _choix", "Short description"])
        for p in cat["produits"]:
            w.writerow([p["id"], p["nom"], "simple", 0 if p["bientot"] else 1, f"{rub[p['rubrique']]} > {p['categorie']}",
                        f"{p['prix_vente']:.3f}", p["stock"], int(p["stock"] > 0), f"{p['prix_achat']:.3f}", p["fournisseur"],
                        p["nom_ar"], p["famille"], p["gamme"], p["genre"], p.get("choix", "parent"), f"{p['nom']} (DONNÉES FICTIVES)"])


if __name__ == "__main__":
    main()
