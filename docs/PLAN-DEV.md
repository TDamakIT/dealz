# Plan de développement Dealz — du draft local au lancement

## Étape 0 — demain (toi, ≈ 45 min)
Suivre le README : VM → Docker → boutique → Telegram → Claude → tests.
**Critère de réussite** : tu passes une commande sur la boutique et tu reçois l'alerte sur Telegram avec le lien WhatsApp ; `/veille` remplit le tableau de bord.

## Étape 1 — semaine 1 : un draft présentable à la famille
| # | Tâche | Qui | Durée |
|---|---|---|---|
| 1 | Faire tourner le draft, noter tout ce qui coince | Tarek | ½ j |
| 2 | Logo et couleurs Dealz dans Storefront (Apparence → Personnaliser) ou thème enfant | Frère | ½ j |
| 3 | Pages obligatoires : CGV, mentions légales, livraison, retours (brouillons à faire valider) | Sœur + agent Stratège | ½ j |
| 4 | **Vrai fichier produits Office House** (référence, nom, prix d'achat, stock) → remplacer `data/catalog.json` et relancer l'import | Père + Sœur | 1 j |
| 5 | Photos produits : 30 best-sellers sur fond blanc au téléphone | Sœur | 1 j |
| 6 | Version arabe du site (extension de traduction, ex. TranslatePress ou Polylang) | Frère | 1 j |
| 7 | Démo à la famille, retours, décisions | Tous | 1 h |

## Étape 2 — semaines 2 à 4 : fonctions qui font la différence (frère)
| Priorité | Fonction | Détail technique |
|---|---|---|
| 1 | **Packs avec stock des composants** | à la commande d'un pack, décrémenter les produits listés dans `_pack_items` (hook `woocommerce_reduce_order_stock`) |
| 2 | **Confirmation WhatsApp semi-automatique** | bouton dans l'admin commande qui ouvre le lien `wa.me` prérempli ; statut « Confirmée » personnalisé |
| 3 | **Liste scolaire v2** | page de résultat plus belle (mobile d'abord), photos produits, choix entre produits équivalents, sauvegarde de la liste |
| 4 | **Espace pro** | formulaire de devis → commande en brouillon + tarifs par quantité (extension « tiered pricing » ou code maison) |
| 5 | Transporteur | choisir un livreur tunisien qui fait le paiement à la livraison ; intégrer son API ou un export CSV quotidien |
| 6 | Paiement en ligne | Konnect ou ClicToPay en mode test (extensions WooCommerce existantes) — **après** la création de la société |

## Étape 3 — avant de vendre pour de vrai
- Société créée, identifiant fiscal, compte bancaire pro (bloquant).
- Hébergement réel : un VPS (≈ 5 à 10 €/mois) plutôt qu'une offre gratuite pour un site qui encaisse ; HTTPS ; sauvegardes quotidiennes de la base.
- Nom de domaine (`dealz.tn` à vérifier, sinon `.com`) ; vérifier que la marque « Dealz » est disponible en Tunisie (INNORPI).
- WhatsApp Business API avec un numéro dédié.
- Vrais prix, vraies photos, CGV validées.

## Étape 4 — les agents, version suivante (Tarek)
- **Veille élargie** : papeterie et fournitures (Spacenet, Tunisianet) en plus des PC ; alertes par produit suivi.
- **Prévision de réassort** : ventes par semaine × saisonnalité (rentrée) → commande fournisseur proposée chaque lundi.
- **Agent B2B** : relances automatiques des devis non répondus après 3 jours (message proposé, envoi validé).
- **Agent service client** : réponses proposées aux messages WhatsApp/Messenger, validées par un humain.
- **Agent Facebook** : génération de visuels et vidéos à partir des idées validées (le script de vidéo est prêt, la voix reste à régler).
- Passer le service d'agents sur le même VPS que la boutique.

## Ce qui ne doit pas être codé maintenant
- Un site sur mesure (Next.js…) : WooCommerce suffit jusqu'à plusieurs centaines de commandes par jour.
- L'électroménager et les meubles : pas de fournisseur, pas de code.
- Une application mobile : le site mobile + WhatsApp suffisent.
