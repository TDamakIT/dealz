<?php
/**
 * Thème Dealz (thème enfant de Storefront).
 *
 * - polices et couleurs de la marque (les mêmes que les vidéos) ;
 * - en-tête : bandeau de réassurance, logo texte « Dealz · ديلز » ;
 * - page d'accueil dédiée (front-page.php) ;
 * - fiche produit : bloc « Choisis ton modèle » qui regroupe les modèles d'une même famille
 *   (les modèles sont masqués de la boutique pour ne pas l'inonder) ;
 * - pied de page Dealz, image par défaut aux couleurs de la marque.
 */

if (!defined('ABSPATH')) exit;

define('DEALZ_THEME_VERSION', '0.1.0');

/* ---------- Styles et polices ---------- */
add_action('wp_enqueue_scripts', function () {
    wp_enqueue_style('storefront-style', get_template_directory_uri() . '/style.css', [], null);
    wp_enqueue_style('dealz-style', get_stylesheet_uri(), ['storefront-style', 'storefront-woocommerce-style'], DEALZ_THEME_VERSION);
    wp_enqueue_script('dealz-modeles', get_stylesheet_directory_uri() . '/assets/js/modeles.js', [], DEALZ_THEME_VERSION, true);
}, 20);

// Pas de polices Google : on sert les nôtres (plus rapide, pas de traçage).
add_filter('storefront_google_font_families', '__return_empty_array');

add_action('wp_head', function () {
    $f = get_stylesheet_directory_uri() . '/assets/fonts/';
    foreach (['rubik-latin-500-normal', 'baloo-bhaijaan-2-latin-800-normal'] as $font) {
        printf('<link rel="preload" href="%s%s.woff2" as="font" type="font/woff2" crossorigin>' . "\n", esc_url($f), $font);
    }
}, 1);

// Accueil et page liste scolaire en pleine largeur (pas de barre latérale)
add_filter('body_class', function ($classes) {
    if (is_front_page() || is_page('liste-scolaire') || is_page('espace-pro') || is_product()) {
        $classes[] = 'storefront-full-width-content';
    }
    return $classes;
});

/* ---------- Image par défaut aux couleurs de Dealz ---------- */
add_filter('woocommerce_placeholder_img_src', function () {
    return get_stylesheet_directory_uri() . '/assets/img/placeholder.png';
});

/* ---------- En-tête ---------- */
add_action('storefront_before_header', function () { ?>
    <div class="dealz-topbar"><div class="col-full">
        <span>Livraison partout en Tunisie</span>
        <span>Paiement à la livraison</span>
        <span>Confirmation sur WhatsApp</span>
        <span class="dealz-topbar-hide-sm">Livraison offerte dès 150 DT</span>
    </div></div>
<?php });

add_action('init', function () {
    remove_action('storefront_header', 'storefront_site_branding', 20);
    remove_action('storefront_header', 'storefront_secondary_navigation', 30);
    remove_action('storefront_footer', 'storefront_credit', 20);
    remove_action('storefront_homepage', 'storefront_homepage_header', 10);
    remove_action('woocommerce_after_single_product_summary', 'storefront_single_product_pagination', 30);
});

add_action('storefront_header', function () { ?>
    <div class="site-branding dealz-branding">
        <a href="<?php echo esc_url(home_url('/')); ?>" class="dealz-logo" rel="home" aria-label="Dealz, accueil">
            <span class="dealz-logo-fr">Dealz</span><span class="dealz-logo-ar" lang="ar">ديلز</span>
        </a>
        <span class="dealz-tagline">L'école, le bureau, la maison. Livrés chez vous.</span>
    </div>
<?php }, 20);

/* ---------- Boutique : on n'affiche que le produit principal de chaque famille ---------- */
// Les modèles (fille, garçon, petit prix, haut de gamme…) sont importés avec la visibilité « cachée » ;
// on les retrouve sur la fiche du produit principal et dans la page liste scolaire.

/* ---------- Fiche produit : « Choisis ton modèle » ---------- */
function dealz_famille_modeles($product) {
    $famille = $product->get_meta('_famille') ?: $product->get_sku();
    if (!$famille) return [];
    $q = new WP_Query([
        'post_type' => 'product', 'post_status' => 'publish', 'posts_per_page' => 60, 'fields' => 'ids',
        'meta_query' => [['key' => '_famille', 'value' => $famille]],
        'orderby' => 'meta_value_num', 'meta_key' => '_price', 'order' => 'ASC',
    ]);
    return array_values(array_filter(array_map('wc_get_product', $q->posts)));
}

add_action('woocommerce_after_single_product_summary', function () {
    global $product;
    if (!$product) return;
    $modeles = dealz_famille_modeles($product);
    if (count($modeles) < 2) return;
    $gammes = ['eco' => 'Petit prix', 'standard' => 'Moyenne gamme', 'premium' => 'Haut de gamme'];
    $genres_presents = array_unique(array_map(fn($m) => $m->get_meta('_genre') ?: 'mixte', $modeles));
    $avec_genre = (bool) array_intersect(['fille', 'garcon'], $genres_presents);
    $gammes_presentes = array_unique(array_map(fn($m) => $m->get_meta('_gamme') ?: 'standard', $modeles));
    ?>
    <section class="dealz-modeles" data-dealz-modeles>
        <h2>Choisis ton modèle <small><?php echo count($modeles); ?> modèles</small></h2>
        <div class="dealz-filtres">
            <?php if ($avec_genre): ?>
            <div class="dealz-filtre" role="group" aria-label="Pour qui">
                <button type="button" data-f="genre" data-v="" aria-pressed="true">Tous</button>
                <button type="button" data-f="genre" data-v="fille" aria-pressed="false">Fille</button>
                <button type="button" data-f="genre" data-v="garcon" aria-pressed="false">Garçon</button>
            </div>
            <?php endif; ?>
            <?php if (count($gammes_presentes) > 1): ?>
            <div class="dealz-filtre" role="group" aria-label="Gamme">
                <button type="button" data-f="gamme" data-v="" aria-pressed="true">Toutes gammes</button>
                <?php foreach ($gammes as $k => $lib): if (in_array($k, $gammes_presentes, true)): ?>
                <button type="button" data-f="gamme" data-v="<?php echo esc_attr($k); ?>" aria-pressed="false"><?php echo esc_html($lib); ?></button>
                <?php endif; endforeach; ?>
            </div>
            <?php endif; ?>
        </div>
        <ul class="dealz-modeles-grille">
            <?php foreach ($modeles as $m):
                $g = $m->get_meta('_genre') ?: 'mixte'; $gm = $m->get_meta('_gamme') ?: 'standard'; ?>
            <li data-genre="<?php echo esc_attr($g); ?>" data-gamme="<?php echo esc_attr($gm); ?>" class="<?php echo $m->get_id() === $product->get_id() ? 'is-current' : ''; ?>">
                <a href="<?php echo esc_url($m->get_permalink()); ?>">
                    <?php echo $m->get_image('woocommerce_thumbnail'); ?>
                    <span class="dealz-modele-nom"><?php echo esc_html(dealz_nom_court($m->get_name(), $product)); ?></span>
                </a>
                <span class="dealz-badges">
                    <span class="dealz-badge dealz-badge-<?php echo esc_attr($gm); ?>"><?php echo esc_html($gammes[$gm] ?? $gm); ?></span>
                    <?php if ($g !== 'mixte'): ?><span class="dealz-badge"><?php echo $g === 'fille' ? 'Fille' : 'Garçon'; ?></span><?php endif; ?>
                </span>
                <span class="price"><?php echo $m->get_price_html(); ?></span>
                <?php if ($m->is_in_stock()): ?>
                <a href="<?php echo esc_url($m->add_to_cart_url()); ?>" data-quantity="1" data-product_id="<?php echo esc_attr($m->get_id()); ?>"
                   class="button add_to_cart_button ajax_add_to_cart" rel="nofollow">Ajouter</a>
                <?php else: ?><span class="dealz-rupture">En rupture</span><?php endif; ?>
            </li>
            <?php endforeach; ?>
        </ul>
        <p class="dealz-modeles-vide" hidden>Aucun modèle pour ce choix.</p>
    </section>
    <?php
}, 5);

// « Cartable primaire classique — garçon, bleu motif foot — haut de gamme » → « garçon, bleu motif foot — haut de gamme »
function dealz_nom_court($nom, $principal) {
    $base = explode(' — ', $principal->get_name())[0];
    $court = trim(preg_replace('/^' . preg_quote($base, '/') . '\s*—\s*/u', '', $nom));
    return $court === $nom ? 'Modèle classique' : $court;
}

/* ---------- Pied de page ---------- */
add_action('storefront_footer', function () { ?>
    <div class="dealz-footer">
        <div class="dealz-footer-col">
            <span class="dealz-logo"><span class="dealz-logo-fr">Dealz</span><span class="dealz-logo-ar" lang="ar">ديلز</span></span>
            <p>Fournitures scolaires, informatique et bureau, livrées partout en Tunisie. Une entreprise familiale basée à Sfax.</p>
        </div>
        <div class="dealz-footer-col">
            <h3>Commander</h3>
            <ul>
                <li><a href="<?php echo esc_url(home_url('/liste-scolaire/')); ?>">Envoyer ma liste scolaire</a></li>
                <li><a href="<?php echo esc_url(wc_get_page_permalink('shop')); ?>">La boutique</a></li>
                <li><a href="<?php echo esc_url(home_url('/espace-pro/')); ?>">Espace pro (écoles, entreprises)</a></li>
            </ul>
        </div>
        <div class="dealz-footer-col">
            <h3>Nos engagements</h3>
            <ul>
                <li>Livraison partout en Tunisie</li>
                <li>Paiement à la livraison</li>
                <li>Commande confirmée sur WhatsApp</li>
                <li>Livraison offerte dès 150 DT</li>
            </ul>
        </div>
    </div>
    <div class="dealz-footer-bas">© <?php echo esc_html(date('Y')); ?> Dealz · Site de démonstration : produits et prix fictifs.</div>
<?php }, 20);

/* ---------- Commande : adresse adaptée à la Tunisie ---------- */
// Les 24 gouvernorats en liste déroulante (WooCommerce n'en propose pas pour la Tunisie).
add_filter('woocommerce_states', function ($states) {
    $states['TN'] = [
        'ARI' => 'Ariana', 'BEJ' => 'Béja', 'BEN' => 'Ben Arous', 'BIZ' => 'Bizerte', 'GAB' => 'Gabès', 'GAF' => 'Gafsa',
        'JEN' => 'Jendouba', 'KAI' => 'Kairouan', 'KAS' => 'Kasserine', 'KEB' => 'Kébili', 'KEF' => 'Le Kef', 'MAH' => 'Mahdia',
        'MAN' => 'La Manouba', 'MED' => 'Médenine', 'MON' => 'Monastir', 'NAB' => 'Nabeul', 'SFA' => 'Sfax', 'SBZ' => 'Sidi Bouzid',
        'SIL' => 'Siliana', 'SOU' => 'Sousse', 'TAT' => 'Tataouine', 'TOZ' => 'Tozeur', 'TUN' => 'Tunis', 'ZAG' => 'Zaghouan',
    ];
    return $states;
});
// Code postal facultatif (beaucoup de clients ne le connaissent pas) ; gouvernorat obligatoire, utile au livreur.
add_filter('woocommerce_get_country_locale', function ($locale) {
    $locale['TN']['postcode'] = ['required' => false, 'label' => 'Code postal'];
    $locale['TN']['state'] = ['required' => true, 'label' => 'Gouvernorat'];
    return $locale;
});
