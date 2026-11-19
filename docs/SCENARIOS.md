# Scénarios à simuler (mock)

But : voir les agents travailler ensemble **avant** d'avoir de vraies ventes, avec des données fictives
marquées « (démo) », puis tout effacer en une commande.

Prérequis : la stack tourne (`docker compose up -d`), Telegram branché. La clé Claude est facultative :
sans elle, tout marche sauf les textes rédigés par l'IA (remplacés par une trame).

Raccourci utilisé ci-dessous :
```bash
alias dz='docker compose exec agents python -m dealz.tools.scenarios'
```

---

## Partie A — Scénarios automatiques (5 minutes)

### A1. De la rumeur au produit en rayon — `dz airfryer`
Ce qui est injecté : 7 jours de relevés où une friteuse à air 5 L est n°2 des ventes chez Tunisianet,
une opportunité proposée par l'expert Tendances (score 3), un signal terrain « demande dans un groupe de Sfax ».

Ce que tu dois voir :
| Étape | Où | Résultat attendu |
|---|---|---|
| Signal terrain | terminal + `/tableau` | « rattaché à l'opportunité #N : score 3 → 4 » |
| GO automatique | terminal | 3 réactions : Prospection, SEO, Marketing |
| Prospection | `/tableau` | segment « fournisseurs de friteuse à air 5 L » en tête de file |
| SEO | WordPress → Produits → Brouillons | fiche « Friteuse à air 5 L (démo) », **sans prix**, SKU OPP-N |
| Marketing | Telegram | rapport « Lancement : … publications à valider », avec [PRIX] à la place du prix |
| Tableau de bord | http://localhost:8000 | sections Priorités, Tableau partagé, Opportunités remplies |

Pour aller plus loin : `/prospection` (vérifie que le premier segment fournisseurs est bien la friteuse),
puis `/sourcing N` pour comparer avec l'import (clé Claude + recherche web nécessaires, ≈ 0,10 $).

### A2. Un concurrent casse les prix — `dz prix`
Deux cas fictifs :
- PC portable i5 : nous 2 499 DT, marché 2 190 DT, achat 2 050 DT → **« Ne pas s'aligner »** (marge 6 %), angle service enregistré pour le Marketing ;
- Imprimante laser : nous 459 DT, marché 399 DT, achat 250 DT → **« S'aligner est possible »** (marge 37 %).

Attendu : 2 alertes Telegram de « Achats & stock (lien Veille) ». Puis `/marketing` : une publication doit parler de service sur le PC, pas de prix.

### A3. Rupture proche — `dz rupture` puis `dz rupture --ventes`
- Sans `--ventes` : les deux liens répondent « en veille (LIENS_VENTES=0) ». C'est voulu : avant le lancement, notre stock est fictif.
- Avec `--ventes` : la Prospection met « autres fournisseurs de cartables » en file, le Marketing arrête de pousser le cartable 14 jours.

### A4. Les priorités de la semaine — `dz priorites`
3 priorités fictives (fournisseur électroménager, packs rentrée, 3 écoles privées).
Attendu : `/priorites` les affiche, 2 segments ajoutés à la file de prospection, `/marketing` centre ses idées dessus.

### Tout d'un coup, puis nettoyage
```bash
dz tous
dz reset      # efface événements, opportunités, relevés, alertes, rapports et fiches brouillon « démo »
```

---

## Partie B — Scénarios à la main sur Telegram (avec la clé Claude)

| # | Ce que tu fais | Ce qui doit se passer | Ce que tu vérifies |
|---|---|---|---|
| B1 | Capture d'un vrai post de groupe Facebook (une demande de produit) envoyée avec la légende `/signal` | Réponse « 📡 Signal #… [demande] produit · intérêt … » | **aucun nom ni numéro** dans la réponse ni dans `/tableau` |
| B2 | `/signal` sur une capture de pub d'un concurrent | type `pub`, prix lu si visible | le prix lu correspond à l'image |
| B3 | `/signal une cliente demande des cartables Barbie pour 6 ans` (texte) | signal enregistré | rattaché à une opportunité si un mot correspond |
| B4 | `/tendances` (après 2-3 jours de relevés réels) | rapport avec 3-6 opportunités ; les signaux terrain y sont cités | aucun prix qui ne vient pas des relevés |
| B5 | `/opportunite N go` sur une vraie opportunité | message avec les 3 réactions | fiche brouillon dans WordPress, à compléter puis publier |
| B6 | `/priorites Trouver un fournisseur de mixeurs ; Signer 2 crèches` | « Priorités enregistrées » | le dimanche, `/marketing` en tient compte |
| B7 | `/rapport` (lundi) | rapport + message « 🎯 Priorités de la semaine » | les priorités sont concrètes et ont un responsable |
| B8 | `/import 6.5 500 petit_electro 189` | coût de revient, trésorerie, marge, alerte BCT | refais le calcul à la main une fois pour valider la formule |

---

## Partie C — Scénarios « boutique » à jouer dans WordPress (mock de commandes)

| # | Mise en place | Attendu |
|---|---|---|
| C1 | Passe une commande test avec un nom bidon et un numéro invalide | agent Commandes (10 min) : alerte risque + lien WhatsApp de confirmation |
| C2 | Laisse-la non confirmée 24 h (ou change sa date en base) | relance « commande non confirmée » |
| C3 | Mets le stock d'un cahier à 3 et crée 5 commandes de ce cahier | `/stock` : stock bas, réassort proposé ; avec `LIENS_VENTES=1`, un événement `rupture_proche` sur `/tableau` |
| C4 | Mets le prix d'un PC 15 % au-dessus du marché (méta `_veille_gamme` renseignée) | `/veille` : alerte « Trop cher » + décision du lien Stock (s'aligner ou non) |
| C5 | `/seo` puis `/seo_annuler <id>` | fiches optimisées, puis remises comme avant |
| C6 | Page liste-scolaire : colle une liste en arabe | panier rempli avec les bons articles |
| C7 | Page liste-scolaire : enfant 1 « Garçon », + Ajouter un enfant, enfant 2 « Fille », une liste chacun | sur chaque ligne : modèles du genre choisi + mixtes (jamais l'autre genre), moyenne gamme proposée par défaut, filtres « Tout / Petit prix / Moyenne gamme / Haut de gamme » quand l'article existe en plusieurs gammes ; un total par enfant + un total général |
| C8 | Change un modèle dans la liste déroulante, décoche une ligne, puis « Tout ajouter au panier » | une seule commande ; dans le panier et dans la commande, chaque ligne porte « Pour : prénom » |
| C9 | Liste avec un article en rupture (« cahier de dessin » dans la démo) | ligne « en rupture : l'équipe vous propose une alternative », pas de produit au hasard |

Ce qui doit t'alerter pendant les tests : un chiffre que tu ne retrouves nulle part dans les données,
une donnée personnelle dans `/tableau`, un agent qui réagit deux fois au même événement, une fiche publiée sans que vous l'ayez décidé.
