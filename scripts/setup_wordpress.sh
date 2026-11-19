#!/usr/bin/env bash
# Dealz — installation de WordPress + WooCommerce en local, en une commande.
# À lancer depuis la racine du projet, après "docker compose up -d".
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "Fichier .env manquant : cp .env.example .env puis remplis-le."; exit 1; }
set -a; . ./.env; set +a

wp() { docker compose run --rm -T wpcli wp "$@"; }

echo "==> Attente de WordPress…"
for i in $(seq 1 60); do
  if docker compose run --rm -T wpcli sh -c 'test -f /var/www/html/wp-config.php' >/dev/null 2>&1; then break; fi
  sleep 3
  [ "$i" = 60 ] && { echo "WordPress ne répond pas. Vérifie : docker compose ps / docker compose logs wordpress"; exit 1; }
done

if ! wp core is-installed >/dev/null 2>&1; then
  echo "==> Installation de WordPress"
  wp core install --url="$WP_PUBLIC_URL" --title="Dealz" \
    --admin_user="$WP_ADMIN_USER" --admin_password="$WP_ADMIN_PASSWORD" \
    --admin_email="$WP_ADMIN_EMAIL" --skip-email
else
  echo "==> WordPress déjà installé"
fi

echo "==> Langue française"
wp language core install fr_FR --activate || true

echo "==> Permaliens propres (nécessaires à l'API)"
wp rewrite structure '/%postname%/' --hard || true

echo "==> WooCommerce + thème Storefront + extension Dealz"
wp plugin install woocommerce --activate
wp language plugin install woocommerce fr_FR || true
wp theme install storefront --activate || true
wp plugin activate dealz-liste
wp plugin install seo-by-rank-math --activate   # champs SEO (titre, méta-description) et plan du site utilisés par l'agent SEO

echo "==> Réglages boutique (Tunisie, dinar, 3 décimales)"
wp option update woocommerce_default_country "TN"
wp option update woocommerce_store_city "Sfax"
wp option update woocommerce_currency "TND"
wp option update woocommerce_currency_pos "right_space"
wp option update woocommerce_price_num_decimals 3
wp option update woocommerce_price_decimal_sep ","
wp option update woocommerce_price_thousand_sep " "
wp option update woocommerce_calc_taxes "no"
wp option update woocommerce_allowed_countries "specific"
wp option update woocommerce_specific_allowed_countries '["TN"]' --format=json
wp option update woocommerce_ship_to_countries ""
wp option update woocommerce_enable_guest_checkout "yes"
wp option update woocommerce_task_list_hidden "yes"
wp option update woocommerce_onboarding_profile '{"skipped":true}' --format=json
wp option update woocommerce_coming_soon "no" || true

echo "==> Paiement à la livraison"
wp option update woocommerce_cod_settings '{"enabled":"yes","title":"Paiement à la livraison","description":"Vous payez en espèces au livreur. Nous vous confirmons la commande sur WhatsApp avant l envoi.","instructions":"Nous vous contactons sur WhatsApp pour confirmer la commande.","enable_for_methods":[],"enable_for_virtual":"yes"}' --format=json

echo "==> Page « Ma liste scolaire »"
if ! wp post list --post_type=page --name=liste-scolaire --field=ID | grep -q .; then
  wp post create --post_type=page --post_status=publish --post_title="Ma liste scolaire" \
    --post_name=liste-scolaire --post_content='[dealz_liste]'
fi

echo "==> Mot de passe d'application pour les agents"
if [ -z "${WOO_APP_PASSWORD:-}" ]; then
  APP_PW=$(wp user application-password create "$WP_ADMIN_USER" dealz-agents --porcelain)
  if grep -q '^WOO_APP_PASSWORD=' .env; then
    sed -i "s|^WOO_APP_PASSWORD=.*|WOO_APP_PASSWORD=${APP_PW}|" .env
  else
    echo "WOO_APP_PASSWORD=${APP_PW}" >> .env
  fi
  echo "    Enregistré dans .env"
else
  echo "    Déjà présent dans .env"
fi

echo "==> Redémarrage du service d'agents avec les nouveaux accès"
docker compose up -d --build --force-recreate agents

echo "==> Import du catalogue (zone de livraison, catégories, produits, packs)"
sleep 5
docker compose exec -T agents python -m dealz.tools.import_catalog

echo
echo "Terminé."
echo "  Boutique       : $WP_PUBLIC_URL"
echo "  Admin          : $WP_PUBLIC_URL/wp-admin  (utilisateur $WP_ADMIN_USER)"
echo "  Liste scolaire : $WP_PUBLIC_URL/liste-scolaire/"
echo "  Agents         : http://localhost:${AGENTS_PORT:-8000}/  (tableau de bord)"
