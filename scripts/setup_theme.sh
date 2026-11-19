#!/usr/bin/env bash
# Habillage de la boutique : thème Dealz, pages, menu, page d'accueil. Relançable sans doublons.
# Appelé par setup_wordpress.sh (qui définit la fonction `wp`). Seul :  WP="wp --path=..." ./scripts/setup_theme.sh
set -euo pipefail
if ! declare -F wp >/dev/null; then
  wp() { ${WP:?définir WP, ex. WP="docker compose run --rm -T wpcli wp"} "$@"; }
fi
id_of() { wp post list --post_type="$1" --name="$2" --field=ID --posts_per_page=1 2>/dev/null | tr -d '\r' | head -1; }

echo "==> Thème Dealz"
wp theme is-installed storefront || wp theme install storefront
wp theme activate dealz

echo "==> Ménage : pages et articles d'exemple"
for slug in sample-page exemple-de-page; do p=$(id_of page "$slug"); [ -n "$p" ] && wp post delete "$p" --force >/dev/null && echo "    page $slug supprimée"; done
for slug in hello-world bonjour-tout-le-monde; do p=$(id_of post "$slug"); [ -n "$p" ] && wp post delete "$p" --force >/dev/null && echo "    article $slug supprimé"; done

echo "==> Pages de la boutique en français"
for kv in shop:Boutique cart:Panier checkout:Commande myaccount:"Mon compte"; do
  k=${kv%%:*}; t=${kv#*:}; p=$(wp option get "woocommerce_${k}_page_id" 2>/dev/null | tr -d '\r' || true)
  [ -n "$p" ] && [ "$p" != "0" ] && wp post update "$p" --post_title="$t" >/dev/null && echo "    $k → $t"
done

echo "==> Page d'accueil"
home=$(id_of page accueil)
[ -z "$home" ] && home=$(wp post create --post_type=page --post_status=publish --post_title="Accueil" --post_name=accueil --porcelain | tr -d '\r')
wp option update show_on_front page >/dev/null
wp option update page_on_front "$home" >/dev/null

echo "==> Page Espace pro"
pro=$(id_of page espace-pro)
PRO_CONTENT='<!-- wp:paragraph --><p><strong>Écoles, crèches, entreprises, administrations :</strong> vos fournitures scolaires et de bureau, vos consommables informatiques, livrés partout en Tunisie.</p><!-- /wp:paragraph -->
<!-- wp:list --><ul><li>Prix au volume et devis sous 24 h</li><li>Facture pour votre comptabilité</li><li>Commandes récurrentes (rentrée, trimestre, réassort)</li><li>Un interlocuteur à Sfax</li></ul><!-- /wp:list -->
<!-- wp:paragraph --><p>Envoyez votre liste ou votre besoin par e-mail à <a href="mailto:pro@dealz.tn">pro@dealz.tn</a> (adresse de démonstration) : nous revenons vers vous avec un devis.</p><!-- /wp:paragraph -->'
if [ -z "$pro" ]; then
  pro=$(wp post create --post_type=page --post_status=publish --post_title="Espace pro" --post_name=espace-pro --post_content="$PRO_CONTENT" --porcelain | tr -d '\r')
fi

echo "==> Menu principal"
wp menu delete "Principal" >/dev/null 2>&1 || true
wp menu create "Principal" >/dev/null
liste=$(id_of page liste-scolaire)
[ -n "$liste" ] && wp menu item add-post Principal "$liste" --title="Ma liste scolaire" --classes="dealz-menu-liste" >/dev/null
for nom in "Papeterie & scolaire" "Informatique & bureau" "Idées cadeaux"; do
  t=$(wp term list product_cat --name="$nom" --field=term_id 2>/dev/null | tr -d '\r' | head -1)
  [ -n "$t" ] && wp menu item add-term Principal product_cat "$t" >/dev/null
done
wp menu item add-post Principal "$pro" --title="Espace pro" >/dev/null
wp menu location assign Principal primary >/dev/null
wp menu location assign Principal handheld >/dev/null 2>&1 || true

echo "==> Réglages d'affichage"
wp option update woocommerce_catalog_columns 4 >/dev/null 2>&1 || true
wp option update blogdescription "L'école, le bureau, la maison. Livrés chez vous." >/dev/null
wp rewrite flush >/dev/null 2>&1 || true
echo "    Thème prêt"
