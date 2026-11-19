# Dealz — contexte pour Claude Code

## Le projet
Dealz : boutique en ligne familiale en Tunisie (entrepôt à Sfax, livraison dans tout le pays, paiement à la livraison dominant).
Site généraliste en rayons : Papeterie & scolaire, Informatique & bureau, Idées cadeaux, Espace pro (B2B). Maison & petit électroménager « bientôt » (pas de fournisseur).
La **rentrée scolaire est le déclencheur marketing** (acquisition), pas la cible unique du site.
Fournisseurs : Office House (grossiste fournitures scolaires) et Dartech (informatique), sociétés du père. Dealz est une société distincte.

## Équipe
- Tarek : DevOps, infra et agents (France)
- Frère : développeur, site WooCommerce (France)
- Sœur : opérations et marketing sur place (ex-stagiaire Amazon/Rakuten)
- Conjoints : finance et comptabilité ; Père : sourcing et réseau à Sfax

## Stack
- WordPress 7 + WooCommerce 11, thème enfant Storefront `wp-theme/dealz`, extension `wp-plugin/dealz-liste` — en Docker (`docker-compose.yml`), plugin et thème montés en volume.
- Service d'agents Python `agents/` (FastAPI, APScheduler, SQLite, Telegram, SDK anthropic). Le code est **copié dans l'image** : après un `git pull`, `docker compose up -d --build agents`.
- Tableau de bord des agents : `http://localhost:8000`. Bot Telegram : `/commandes`, `/veille`, `/tableau`, `/signal`…
- Bus d'événements partagé entre agents (`bus.py`, `links.py`) ; `LIENS_VENTES=0` tant qu'il n'y a pas de vraies ventes.
- Tests : `docker compose exec agents pytest` ; scénarios de mock : `python -m dealz.tools.scenarios tous` (voir `docs/SCENARIOS.md`).

## Liste scolaire (fonction phare)
- Un bloc par enfant : prénom + **Fille ou Garçon** (pas de choix « mixte »). Garçon voit garçon + mixte, jamais fille ; idem pour fille.
- Plusieurs enfants = **une seule commande**, chaque ligne porte « Pour : prénom ».
- La **gamme se choisit par produit** (Petit prix / Moyenne gamme / Haut de gamme) + bouton « Tout » qui montre tous les modèles du genre.
- Catalogue : beaucoup de modèles quand l'enfant choisit (cartable, trousse, stylos…), peu quand les parents choisissent (2 par gamme). Variantes masquées du catalogue (`catalog_visibility hidden`), meta `_famille`, `_gamme`, `_genre`, `_choix`.
- Checkout : 24 gouvernorats, code postal facultatif.

## Règles à respecter
- Données **fictives** tant que le vrai fichier Office House n'est pas là ; ne jamais inventer de prix ou de contacts réels.
- Prospection : organisations uniquement, contacts publiés avec leur source, **aucun envoi automatique** (un humain valide).
- Pas de scraping Facebook ; `/signal` reçoit des captures et retire noms, numéros et emails ; jamais de données de mineurs.
- WhatsApp : l'agent prépare le message et le lien `wa.me`, l'envoi reste manuel.
- Pas de photos de marques réelles (droits).
- Ne jamais committer `.env`. Travailler sur des branches, pas directement sur `main`.
- Langue : français ; textes clients en français + derja/arabe (« مكتبات », pas « ليبريريات »).

## Docs utiles
`docs/PLAN-DEV.md` (feuille de route), `docs/AGENTS.md` et `docs/AGENTS-INSTRUCTIONS.md` (agents), `docs/SCENARIOS.md` (tests à la main), `docs/QUESTIONS.md` (questions ouvertes).

## Prochaine tâche identifiée
Section « Commandes à confirmer » sur le tableau de bord (`agents/dealz/web.py`) : client, gouvernorat, montant, score de risque (`agents/commandes.py`), bouton WhatsApp (`wa_link`), boutons Confirmée / Annulée qui mettent à jour la commande WooCommerce, en rouge si non confirmée après 24 h.
