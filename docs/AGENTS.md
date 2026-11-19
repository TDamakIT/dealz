# Agents Dealz : rôles, modèles, coûts, réglages

## Principe
Chaque agent fait d'abord le travail **avec des règles** (calculs, seuils, comparaisons). C'est gratuit, fiable et testable.
Claude n'intervient que pour **lire, relier et proposer** : expliquer ce qui bouge, trouver l'opportunité, rédiger la commande fournisseur ou les posts.
Les agents **proposent et alertent** ; un humain valide. Deux exceptions : `/confirme`, que tu déclenches toi-même, et l'**agent SEO**, qui modifie seul les champs SEO des fiches (jamais prix, stock, nom ni adresse), avec sauvegarde de chaque valeur et annulation par `/seo_annuler`. Pour qu'il propose sans appliquer : `SEO_AUTO=0`.

## Choix des modèles (budget 20 $/mois)
| Usage | Modèle | Pourquoi |
|---|---|---|
| Volume et tâches cadrées (veille, stock, marketing, liste scolaire, `/ask`) | **Haiku 5.5** (`MODEL_FAST`) | 0,10 $ / 0,50 $ par million de tokens, sait lire une photo |
| Raisonnement (radar quotidien, rapport hebdo) | **Sonnet 5.5** (`MODEL_SMART`) | 2 $ / 10 $ par million de tokens ; seul endroit où la qualité du jugement compte vraiment |
| Opus | non utilisé | inutile à ce stade |

## Estimation de coût (usage de test)
| Agent | Fréquence | Coût unitaire estimé | Par mois |
|---|---|---|---|
| Veille | 1/jour | ≈ 0,0004 $ | ≈ 0,01 $ |
| Stock | 1/jour | ≈ 0,001 $ | ≈ 0,03 $ |
| Radar (Sonnet) | 1/jour | ≈ 0,009 $ | ≈ 0,27 $ |
| Rapport hebdo (Sonnet + outils) | 1/semaine | ≈ 0,08 $ | ≈ 0,32 $ |
| Marketing | 1/semaine | ≈ 0,001 $ | < 0,01 $ |
| SEO | 10 fiches/nuit | ≈ 0,0007 $ par fiche | ≈ 0,20 $ |
| Liste scolaire | 500 listes | ≈ 0,001 $ | ≈ 0,55 $ |
| `/ask` | 300 questions | ≈ 0,001 $ | ≈ 0,33 $ |
| Prospection (Haiku + recherche web) | 2 segments/jour | ≈ 0,05 à 0,15 $ par jour (recherches à 0,01 $ + pages lues) | ≈ 2 à 4 $ |
| Tendances (relevé quotidien) | 1/jour | 0 $ (sans IA) | 0 $ |
| Tendances (analyse Sonnet + 3 recherches) | 1/semaine | ≈ 0,10 $ | ≈ 0,40 $ |
| Sourcing Chine (Haiku + 5 recherches) | ≈ 3 produits/semaine | ≈ 0,06 à 0,10 $ par produit | ≈ 1 $ |
| **Total** | | | **≈ 5,5 à 7,5 $** |

Ordres de grandeur calculés sur des tailles de messages estimées. La vraie consommation s'affiche avec `/budget` et sur le tableau de bord.
Avec cette marge, tu peux passer le Marketing ou l'assistant `/ask` sur Sonnet sans dépasser 20 $ (dans `agents/dealz/agents/marketing.py`, ajouter `model=settings.model_smart`).

## Planning (fuseau Africa/Tunis, modifiable dans `agents/dealz/main.py`)
- toutes les 5 min : liens du tableau partagé · 03:00 SEO · 06:30 veille prix · 06:45 relevé tendances · 09:00 prospection · 07:15 stock · 08:00 radar · toutes les 10 min commandes
- lundi 08:30 rapport hebdo · mercredi 08:30 analyse Tendances · jeudi 09:30 Sourcing Chine · dimanche 18:00 marketing

## Réglages utiles (`.env`)
- `SEUIL_PRIX_ALERTE_PCT=8` : écart au-dessus de la médiane du marché qui déclenche « trop cher »
- `SEUIL_MARGE_PCT=25` : marge minimale avant alerte
- `SEUIL_STOCK_BAS=20` : stock bas
- `LLM_BUDGET_USD=20` : coupure automatique de l'IA
- `VEILLE_DELAI_SECONDES=1.5` : pause entre deux pages du site concurrent

## Modifier un agent
- Les consignes données à Claude sont en tête de chaque fichier `agents/dealz/agents/*.py` (variables `SYSTEM`, `RADAR`, `HEBDO`).
- Les dates des temps forts sont dans `agents/dealz/config.py` (`TEMPS_FORTS`) : Ramadan et Aïd sont **approximatifs**, à corriger chaque année.
- Après une modification : `docker compose up -d --build agents`.

## Limites connues (honnêtement)
- **Veille** : seulement Tunisianet. Mytek bloque les robots (vérification anti-robot) et on ne la contourne pas. Si Tunisianet change sa page, le relevé tombe à zéro et tu reçois l'alerte « relevé incomplet ». Vérifie aussi leurs conditions d'utilisation avant un usage régulier ; le relevé est volontairement lent (1 passage par jour, une pause entre les pages).
- **Si le relevé échoue depuis la VM** (blocage par le site) : la veille peut être faite depuis le navigateur, comme le premier relevé, mais pas de façon automatique.
- **Packs** : un pack est un produit à part ; vendre un pack ne décrémente pas encore le stock de ses composants (à coder, voir le plan de dev).
- **WhatsApp** : l'agent prépare le message et le lien ; l'envoi reste manuel tant que l'API WhatsApp Business n'est pas branchée.
- **Pas de vrai paiement par carte** pour l'instant : paiement à la livraison seulement.

## Prospection : règles et limites
- Seulement des **organisations** (écoles, entreprises, grossistes…), jamais des particuliers.
- Seulement des coordonnées **publiées** par l'organisation ou un annuaire professionnel, avec la page source. Un email ou un numéro deviné est rejeté ; les numéros sont vérifiés (format tunisien) et les doublons écartés.
- L'agent **ne contacte personne** : il trouve et prépare l'accroche, un humain appelle ou écrit.
- Prospection B2B : se présenter clairement, ne pas envoyer d'emails en masse, et retirer tout contact qui le demande (statut `refus`). À valider avec le cadre tunisien sur les données personnelles (INPDP) avant de démarrer à grande échelle.
- La qualité dépend de ce qui est publié en ligne : beaucoup d'écoles et de PME tunisiennes n'ont qu'une page Facebook. Attends-toi à des fiches incomplètes ; c'est à la sœur et au père de compléter par le terrain.
- Le nom de l'outil de recherche web (`WEB_SEARCH_TOOL`) peut changer de version : si l'agent renvoie une erreur d'outil, essaie `web_search_20250305`.


## Experts Tendances et Sourcing Chine : règles et limites
- **Aucun concurrent ne publie ses ventes.** Le meilleur indice public est le tri « meilleures ventes » des boutiques PrestaShop (paramètre `order=product.sales.desc`), détecté automatiquement. Sans lui, seules les ruptures de stock comptent ; l'expert le sait et le dit.
- **Les prix ne viennent jamais du modèle.** Prix marché : nos relevés d'abord, sinon des pages web citées. Prix Chine : seulement avec l'URL de l'annonce ; les fourchettes absurdes sont jetées.
- **Le coût d'import est calculé par du code**, pas par l'IA (`agents/dealz/import_calc.py`) : FOB → fret → assurance → valeur en douane → droits + redevance + FODEC → TVA ; avance d'impôt et TVA comptent dans la trésorerie mais pas dans le coût (récupérables). Les taux par catégorie sont des **valeurs par défaut à confirmer avec un transitaire** selon le code SH.
- **Liste BCT** : depuis la circulaire BCT n°2026-04 (mars 2026), l'électroménager, les jouets, la déco et les gadgets sont des importations « non prioritaires » : pas de financement bancaire, 100 % sur fonds propres déposés avant. Les catégories concernées sont marquées dans `import_params.json` ; à vérifier sur la liste officielle par code SH.
- L'expert Sourcing **ne contacte aucun fournisseur et ne commande rien**. Prochaine étape humaine : échantillon, vérification du fournisseur, devis transitaire.


## Tableau partagé : comment les agents travaillent ensemble
Les agents ne discutent pas entre eux (coût, erreurs qui s'amplifient, boucles). Ils publient des événements sur un
**tableau partagé** (`agents/dealz/bus.py`) et des **liens** écrits en règles simples (`agents/dealz/links.py`) les font réagir.
Chaque réaction est notée : `/tableau` sur Telegram, section « Tableau partagé » du tableau de bord.

| Événement | Publié par | Réactions |
|---|---|---|
| `signal_terrain` | l'équipe (`/signal`) | Tendances : rattache à une opportunité (+1 au score) ou garde pour le mercredi |
| `opportunite_go` | l'équipe (`/opportunite N go`) | Prospection : fournisseurs du produit en tête de file · SEO : fiche brouillon sans prix · Marketing : 3 publications de lancement |
| `prix_concurrent` | Veille (nous > marché + seuil) | Stock : s'aligner ou tenir le prix selon la marge ; angle « service » pour le Marketing |
| `priorites` | Stratège (lundi) ou l'équipe (`/priorites A ; B ; C`) | Prospection : segments prioritaires en file · Marketing : publications centrées dessus |
| `rupture_proche` | Stock (< 15 jours de ventes) | **après lancement** (`LIENS_VENTES=1`) : Prospection cherche un 2e fournisseur · Marketing arrête de pousser le produit |

Garde-fous : rien n'est publié, commandé ou envoyé à un tiers sans décision humaine (`go`) ; une fiche créée par un lien
reste en brouillon et sans prix ; les signaux terrain sont nettoyés des noms, numéros et emails ; un lien en erreur n'arrête pas les autres.
Coût : les liens sont des règles (0 $). Seuls la lecture d'une capture (≈ 0,001 $) et les publications de lancement (≈ 0,001 $) appellent l'IA.
