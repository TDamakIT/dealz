# Dealz — draft local (boutique + agents)

Ce dossier contient tout ce qu'il faut pour faire tourner **en local, sur ta VM Ubuntu** :

- la **boutique** WordPress + WooCommerce, réglée pour la Tunisie (dinar, 3 décimales, paiement à la livraison, livraison 7 DT, offerte dès 150 DT), avec le catalogue fictif importé (718 références, 7 packs et coffrets) ;
- la page **« Ma liste scolaire »** : le parent envoie la photo ou le texte de la liste et son panier se remplit ;
- le **service d'agents** : ils tournent seuls selon un planning, réfléchissent avec Claude, t'alertent sur **Telegram** et alimentent un **tableau de bord** local.

Tout est en données fictives. Rien n'est publié ni vendu pour de vrai.

---

## Demain matin : les étapes, dans l'ordre (≈ 45 min)

### 1. Préparer la VM (10 min)
```bash
# Copier le dossier dealz-draft dans la VM (dossier partagé, scp ou clé USB), puis :
cd dealz-draft
chmod +x scripts/*.sh
./scripts/install_docker_ubuntu.sh      # si Docker n'est pas déjà installé
newgrp docker                            # ou déconnecte/reconnecte-toi
```
Prévoir 4 Go de RAM et 10 Go de disque pour la VM.

### 2. Configurer (5 min)
```bash
cp .env.example .env
nano .env        # change au minimum DB_PASSWORD, DB_ROOT_PASSWORD, WP_ADMIN_PASSWORD, AGENTS_API_TOKEN
```
Si tu ouvres la boutique depuis Windows et pas depuis la VM, mets dans `WP_PUBLIC_URL` l'adresse IP de la VM (`ip -4 a` dans la VM), par exemple `http://192.168.56.10:8080`, et vérifie que la VM est en réseau « pont » ou « réseau privé hôte ».

### 3. Lancer la boutique (10 min)
```bash
docker compose up -d
./scripts/setup_wordpress.sh
```
Le script installe WordPress en français, WooCommerce, le thème Storefront et le **thème Dealz** (couleurs et polices de la marque, page d'accueil, menu, pages en français), l'extension Dealz, Rank Math (SEO), règle la boutique, crée la page liste scolaire, crée l'accès des agents et importe le catalogue avec les images de démo (une image par modèle : 612 images, environ 1 minute). Dans la boutique, seul le produit principal de chaque famille apparaît ; ses modèles (fille, garçon, petit prix, haut de gamme…) sont sur sa fiche, dans le bloc « Choisis ton modèle ».
Pour ne réappliquer que le thème, les pages et le menu : `WP="docker compose run --rm -T wpcli wp" ./scripts/setup_theme.sh`
À la fin : boutique sur `http://localhost:8080`, administration sur `/wp-admin`.

### 4. Brancher Telegram (5 min)
1. Sur Telegram, écris à **@BotFather** → `/newbot` → nom « Dealz Alertes » → copie le jeton.
2. Colle-le dans `.env` : `TELEGRAM_BOT_TOKEN=...`
3. Envoie `/start` à ton bot (et ajoute-le au groupe famille si tu veux, puis écris `/start` dans le groupe).
4. `python3 scripts/telegram_chat_id.py` → copie les identifiants dans `TELEGRAM_CHAT_IDS=` (séparés par des virgules).
5. `docker compose up -d agents` → tu dois recevoir « Agents Dealz démarrés ».

### 5. Brancher Claude (5 min) — facultatif pour les premiers tests
1. Sur https://console.anthropic.com : crée une clé API, et **règle une limite de dépense mensuelle à 20 $** (sécurité en plus de celle du code).
2. Dans la console, autorise la **recherche web** (réglages de l'organisation) : l'agent Prospection en a besoin.
3. Colle la clé dans `.env` : `ANTHROPIC_API_KEY=...`
4. `docker compose up -d agents`

Sans clé, tout fonctionne en **mode simulation** : les agents appliquent leurs règles (ruptures, marges, commandes à risque, variations de prix) mais n'écrivent pas d'analyse.

### 6. Tester (10 min)
Sur Telegram :
| Commande | Ce qui doit se passer |
|---|---|
| `/aide` | la liste des commandes |
| `/veille` | 1 à 3 min plus tard : le relevé Tunisianet (~1 700 PC) et le tableau de bord se remplit |
| `/stock` | les ruptures et marges faibles du catalogue fictif, et une proposition de réassort |
| `/commandes` | rien au début. Passe une commande sur la boutique (paiement à la livraison), relance : alerte avec score de risque et lien WhatsApp |
| `/confirme 12` | la commande n°12 passe « confirmée » (note ajoutée dans WooCommerce) |
| `/rapport` | le rapport hebdo du Stratège (Sonnet) |
| `/radar` | le Stratège cherche un signal à traiter aujourd'hui |
| `/marketing` | 3 idées de publications en derja, à valider |
| `/ask quelle est notre marge moyenne ?` | réponse à partir des vraies données |
| `/seo` | l'agent SEO optimise 10 fiches maintenant ; le message donne la commande pour annuler |
| `/seo_annuler abc123` | remet les fiches du passage abc123 comme avant |
| `/prospection` | 1 à 3 min plus tard : le rapport de prospection (nécessite la clé Claude et la recherche web activée) |
| `/prospects` | les 10 dernières cibles ; `/prospect 12 contacte` pour suivre |
| `/import 6.5 500 petit_electro 189` | sans IA : coût de revient d'un import Chine (6,5 $ FOB, 500 pièces, vendu 189 DT) |
| `/tendances` | 1 à 2 min : l'expert Tendances analyse les meilleures ventes des concurrents et propose des opportunités |
| `/opportunites` puis `/sourcing 4` | l'expert Sourcing Chine chiffre l'opportunité n°4 (offres, coût rendu, marge, verdict) |
| `/signal` + capture d'écran | un signal du terrain (groupe Facebook…) : l'IA lit la capture, retire noms et numéros, le rattache à une opportunité |
| `/opportunite 4 go` | valide une opportunité : Prospection, SEO (fiche brouillon) et Marketing se mettent en route |
| `/tableau` · `/priorites` | ce que les agents se sont transmis · les 3 priorités de la semaine |
| `/budget` | ce que l'IA a coûté ce mois-ci |

Puis :
- tableau de bord des agents : `http://localhost:8000`
- liste scolaire : `http://localhost:8080/liste-scolaire/` : un bloc par enfant (fille ou garçon), texte ou photo de la liste (photo si la clé Claude est branchée), sur chaque ligne un filtre de gamme (petit prix / moyenne / haut de gamme) et le choix du modèle exact, une seule commande avec « Pour : prénom » sur chaque article
- catalogue de démo : 718 références fictives. Règle « qui choisit ? » : quand c'est l'enfant (cartable, trousse, gourde, agenda…), au moins 5 modèles par genre et par gamme ; quand ce sont les parents (stylos, cahiers, règles…), 2 modèles par gamme. Champ `choix` = enfant | parent. Pour régénérer : `python3 data/gen_variantes.py`

Avant de croire les experts, deux réglages à faire toi-même :
- `docker compose exec agents python -m dealz.tools.check_sources` : vérifie que les pages concurrentes sont lues et si le tri « meilleures ventes » existe. Si une page affiche « AUCUN PRODUIT LU », son thème est différent : retire-la de `data/tendances_sources.json` ou adapte les sélecteurs dans `agents/dealz/scraper.py`.
- `data/import_params.json` : mets le vrai taux de change et, dès que tu as un devis transitaire, le vrai fret et les vrais droits par catégorie. Tant que ce n'est pas fait, les verdicts d'import sont des ordres de grandeur.

### 7. Voir les agents travailler ensemble (5 min, données fictives)
```bash
docker compose exec agents python -m dealz.tools.scenarios tous    # puis /tableau sur Telegram et http://localhost:8000
docker compose exec agents python -m dealz.tools.scenarios reset   # efface tout ce qui est « démo »
```
Le détail des scénarios et ce que tu dois voir : `docs/SCENARIOS.md`.

### Après un `git pull`
- Code des agents modifié (`agents/`) : il est copié dans l'image Docker, donc **`docker compose up -d --build agents`** (sinon l'ancien code continue de tourner).
- Thème (`wp-theme/`) ou extension (`wp-plugin/`) modifiés : montés directement dans WordPress, un rechargement de la page suffit (Ctrl+F5).
- Catalogue ou images (`data/`) modifiés : `docker compose exec -T agents python -m dealz.tools.import_catalog`.

### En cas de souci
```bash
docker compose ps                    # tout doit être "running"
docker compose logs -f agents        # journaux des agents
docker compose logs -f wordpress
docker compose exec agents python -m pytest -q tests   # tests hors ligne (37)
docker compose down                  # arrêter (les données restent)
docker compose down -v               # tout effacer et repartir de zéro
```

---

## Ce qui tourne tout seul

| Agent | Quand | Modèle | Ce qu'il fait | Alerte quand… |
|---|---|---|---|---|
| Veille prix | tous les jours 06:30 | Haiku | relève les PC de Tunisianet, calcule les prix par gamme, compare à la veille et à nos prix | une médiane bouge de ±5 %, un de nos PC est > 8 % au-dessus du marché, le relevé échoue |
| Achats & stock | tous les jours 07:15 | Haiku | ruptures, stocks bas, marges sous 25 %, couverture des ventes | rupture d'un produit qui se vend |
| Vente & commandes | toutes les 10 min | aucun (règles) | score de risque, message WhatsApp de confirmation prêt | chaque nouvelle commande ; commande non confirmée après 24 h |
| Stratège — radar | tous les jours 08:00 | Sonnet | cherche LE signal qui demande une décision (ventes, stock, veille, temps forts) | seulement s'il trouve quelque chose |
| Stratège — hebdo | lundi 08:30 | Sonnet + outils | rapport : faits, risques, 3 opportunités chiffrées, décisions avec responsable | toujours (rapport) |
| Marketing | dimanche 18:00 | Haiku | 3 publications de la semaine en derja selon les temps forts et les produits à bonne marge | toujours (à valider) |
| SEO | tous les jours 03:00 | Haiku | **modifie lui-même** jusqu'à 10 fiches par nuit : titre SEO, méta-description, mot-clé, descriptions FR + AR, texte des images ; descriptions des catégories. Jamais les prix, stocks, noms ni adresses de pages. Tout est sauvegardé et annulable | à chaque passage, avec la liste des fiches et la commande d'annulation |
| Expert Tendances | relevé tous les jours 06:45 (sans IA) ; analyse le mercredi 08:30 | règles, puis Sonnet + 3 recherches web | lit la 1re page des catégories concurrentes triée par « meilleures ventes » (Tunisianet, Spacenet…), détecte best-sellers stables, nouveaux entrants, ruptures, baisses de prix ; le mercredi, transforme ça en 3 à 6 opportunités avec un canal (fournisseur local / import Chine / pas maintenant) | alerte si un produit entre dans le top 3 ; rapport hebdo |
| Expert Sourcing Chine | jeudi 09:30 (2 opportunités) ou `/sourcing` | Haiku + 5 recherches web, puis calcul sans IA | offres fournisseurs chinois et prix tunisiens, chaque chiffre avec sa source ; coût rendu (fret, droits, FODEC, TVA, transitaire), trésorerie, marge, verdict ; signale la liste BCT et le contrôle technique | rapport par produit |
| Prospection | tous les jours 09:00 | Haiku + recherche web | cherche 1 segment de clients B2B et 1 segment de fournisseurs (en rotation : écoles, crèches, cabinets, PME… / fabricants, grossistes, livreurs…), relève les coordonnées publiques avec leur source, propose une accroche | rapport quotidien sur Telegram |
| Liste scolaire | à la demande | Haiku (vision) | photo/texte → panier | — |
| Assistant `/ask` | à la demande | Haiku + outils | répond avec les vraies données | — |

Budget : le code coupe l'IA à 20 $ par mois (`LLM_BUDGET_USD`) et repasse en simulation. Estimation à l'usage prévu : **environ 6 à 7 $ par mois**, dont 3 à 4 $ pour la prospection (recherche web) (détail dans `docs/AGENTS.md`).

## Arborescence
```
docker-compose.yml        WordPress, MariaDB, service d'agents
.env.example              tous les réglages
scripts/                  installation Docker, installation WordPress, identifiant Telegram
data/                     catalogue fictif (JSON + CSV WooCommerce), instructions des agents
wp-plugin/dealz-liste/    extension WordPress « Ma liste scolaire » (shortcode [dealz_liste])
wp-theme/dealz/           thème Dealz (thème enfant de Storefront) : en-tête, accueil, fiche produit, pied de page
agents/dealz/             service Python : agents, planning, bot Telegram, API, tableau de bord
agents/tests/             tests hors ligne (boutique et Telegram simulés)
docs/                     plan de dev, agents et coûts, questions ouvertes
data/photos/              images FICTIVES des produits (une par modèle) + index.json ; régénérer : python3 data/photos/gen_photos.py
```
