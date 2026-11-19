<?php
/**
 * Plugin Name: Dealz – Liste scolaire
 * Description: Shortcode [dealz_liste] : le parent envoie la photo ou le texte de la liste, l'agent prépare le panier.
 * Version: 0.3.0
 * Author: Dealz
 * Requires Plugins: woocommerce
 */
if (!defined('ABSPATH')) exit;

add_shortcode('dealz_liste', function () {
    wp_enqueue_script('dealz-liste', plugins_url('dealz-liste.js', __FILE__), [], '0.3.0', true);
    wp_localize_script('dealz-liste', 'DEALZ_LISTE', [
        'ajax'  => admin_url('admin-ajax.php'),
        'nonce' => wp_create_nonce('dealz_liste'),
        'cart'  => function_exists('wc_get_cart_url') ? wc_get_cart_url() : '/panier/',
    ]);
    ob_start(); ?>
    <div id="dealz-liste" style="max-width:720px">
      <p><strong>Envoyez la liste de l'école, on prépare le cartable.</strong><br>Photo ou texte, en français ou en arabe. Un cartable par enfant, une seule commande.</p>
      <form id="dealz-liste-form">
        <div class="dealz-enfants"></div>
        <p><button type="button" class="button dealz-ajout-enfant">+ Ajouter un enfant</button></p>
        <p><button type="submit" class="button alt">Préparer mon panier</button> <span class="dealz-statut" aria-live="polite"></span></p>
      </form>
      <div class="dealz-resultat"></div>
    </div>
    <style>
      #dealz-liste fieldset{border:1px solid #dcdcdc;border-radius:10px;padding:12px 14px;margin:0 0 14px}
      #dealz-liste .dz-choix{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 10px}
      #dealz-liste .dz-choix label{border:1px solid #ccc;border-radius:99px;padding:5px 12px;cursor:pointer}
      #dealz-liste .dz-choix input{margin-right:5px}
      #dealz-liste .dz-enfant-res{margin:18px 0}
      #dealz-liste select{max-width:100%}
      #dealz-liste .dz-gammes{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}
      #dealz-liste .dz-gammes button{border:1px solid #bbb;background:#fff;border-radius:99px;padding:3px 10px;font-size:.85em;cursor:pointer}
      #dealz-liste .dz-gammes button[aria-pressed=true]{background:#132a66;color:#fff;border-color:#132a66}
    </style>
    <?php return ob_get_clean();
});

/** 1) Lecture de la liste : relaie vers le service d'agents (le jeton reste côté serveur). */
function dealz_liste_lire() {
    check_ajax_referer('dealz_liste', 'nonce');
    $texte = isset($_POST['texte']) ? sanitize_textarea_field(wp_unslash($_POST['texte'])) : '';
    $genre = in_array($_POST['genre'] ?? '', ['fille', 'garcon'], true) ? $_POST['genre'] : 'garcon';
    $body = ['texte' => $texte, 'genre' => $genre];   // la gamme se filtre ligne par ligne sur la page
    $boundary = wp_generate_password(24, false);
    $payload = '';
    foreach ($body as $k => $v) {
        $payload .= "--$boundary\r\nContent-Disposition: form-data; name=\"$k\"\r\n\r\n$v\r\n";
    }
    if (!empty($_FILES['photo']['tmp_name']) && is_uploaded_file($_FILES['photo']['tmp_name'])) {
        $type = wp_check_filetype($_FILES['photo']['name'])['type'] ?: 'image/jpeg';
        if (strpos($type, 'image/') !== 0) wp_send_json_error(['message' => 'Le fichier doit être une image.'], 400);
        $payload .= "--$boundary\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"liste\"\r\nContent-Type: $type\r\n\r\n"
                  . file_get_contents($_FILES['photo']['tmp_name']) . "\r\n";
    }
    $payload .= "--$boundary--\r\n";
    $res = wp_remote_post(DEALZ_AGENTS_URL . '/api/liste', [
        'timeout' => 60,
        'headers' => ['Content-Type' => "multipart/form-data; boundary=$boundary", 'X-Dealz-Token' => DEALZ_AGENTS_TOKEN],
        'body'    => $payload,
    ]);
    if (is_wp_error($res) || wp_remote_retrieve_response_code($res) !== 200) {
        wp_send_json_error(['message' => "Le service de lecture ne répond pas. Réessayez dans un instant."], 502);
    }
    $data = json_decode(wp_remote_retrieve_body($res), true);
    $lignes = [];
    foreach (($data['lignes'] ?? []) as $l) {
        $options = [];
        foreach (($l['options'] ?? []) as $o) {   // prix et stock relus dans WooCommerce : c'est la boutique qui fait foi
            $pid = wc_get_product_id_by_sku($o['sku'] ?? '');
            $p = $pid ? wc_get_product($pid) : null;
            if (!$p || !$p->is_purchasable() || !$p->is_in_stock()) continue;
            $options[] = ['product_id' => $pid, 'nom' => $p->get_name(), 'prix' => (float)$p->get_price(),
                          'gamme' => $o['gamme'] ?? 'standard', 'genre' => $o['genre'] ?? 'mixte'];
        }
        $lignes[] = [
            'ligne' => $l['ligne'] ?? '', 'qte' => max(1, (int)($l['qte'] ?? 1)), 'note' => $l['note'] ?? '',
            'options' => $options, 'product_id' => $options ? $options[0]['product_id'] : 0,
            'gammes' => array_values(array_unique(array_column($options, 'gamme'))),
        ];
    }
    wp_send_json_success(['lignes' => $lignes, 'mode' => $data['mode'] ?? '']);
}
add_action('wp_ajax_dealz_liste_lire', 'dealz_liste_lire');
add_action('wp_ajax_nopriv_dealz_liste_lire', 'dealz_liste_lire');

/** 2) Ajout de la sélection au panier WooCommerce. */
function dealz_liste_panier() {
    check_ajax_referer('dealz_liste', 'nonce');
    $items = json_decode(wp_unslash($_POST['items'] ?? '[]'), true);
    if (!is_array($items) || !function_exists('WC')) wp_send_json_error(['message' => 'Panier indisponible.'], 400);
    if (null === WC()->cart) wc_load_cart();
    $n = 0;
    foreach (array_slice($items, 0, 80) as $it) {
        $pid = absint($it['product_id'] ?? 0);
        $qte = min(50, max(1, absint($it['qte'] ?? 1)));
        $enfant = mb_substr(sanitize_text_field($it['enfant'] ?? ''), 0, 30);
        $data = $enfant !== '' ? ['dealz_enfant' => $enfant] : [];
        if ($pid && WC()->cart->add_to_cart($pid, $qte, 0, [], $data)) $n++;
    }
    wp_send_json_success(['ajoutes' => $n, 'panier' => wc_get_cart_url()]);
}
add_action('wp_ajax_dealz_liste_panier', 'dealz_liste_panier');
add_action('wp_ajax_nopriv_dealz_liste_panier', 'dealz_liste_panier');

/** 3) « Pour : Yassine » visible dans le panier et gardé sur chaque ligne de la commande (préparation par enfant). */
add_filter('woocommerce_get_item_data', function ($item_data, $cart_item) {
    if (!empty($cart_item['dealz_enfant'])) {
        $item_data[] = ['key' => 'Pour', 'value' => esc_html($cart_item['dealz_enfant'])];
    }
    return $item_data;
}, 10, 2);
add_action('woocommerce_checkout_create_order_line_item', function ($item, $cart_item_key, $values) {
    if (!empty($values['dealz_enfant'])) {
        $item->add_meta_data('Pour', $values['dealz_enfant'], true);
    }
}, 10, 3);
