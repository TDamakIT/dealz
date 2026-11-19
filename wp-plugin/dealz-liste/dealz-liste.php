<?php
/**
 * Plugin Name: Dealz – Liste scolaire
 * Description: Shortcode [dealz_liste] : le parent envoie la photo ou le texte de la liste, l'agent prépare le panier.
 * Version: 0.4.0
 * Author: Dealz
 * Requires Plugins: woocommerce
 */
if (!defined('ABSPATH')) exit;

add_shortcode('dealz_liste', function () {
    wp_enqueue_script('dealz-liste', plugins_url('dealz-liste.js', __FILE__), [], '0.4.0', true);
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
      #dealz-liste .dz-ligne{display:grid;grid-template-columns:28px 76px 1fr auto auto;gap:6px 14px;align-items:center;padding:14px 0;border-bottom:1px solid #eee}
      #dealz-liste .dz-ligne.off{opacity:.45}
      #dealz-liste .dz-thumb{width:76px;height:76px;object-fit:cover;border-radius:12px;background:#f6f1e4}
      #dealz-liste .dz-titre{font-weight:700;line-height:1.25}
      #dealz-liste .dz-modele{font-size:.92em;color:#333;margin-top:2px}
      #dealz-liste .dz-tag{display:inline-block;font-size:.75em;border-radius:99px;padding:1px 8px;background:#eef1f8;color:#132a66;margin-left:4px}
      #dealz-liste .dz-tag.eco{background:#e7f6ec;color:#16653f}#dealz-liste .dz-tag.premium{background:#2a2140;color:#ffd979}
      #dealz-liste .dz-source{font-size:.78em;color:#6b7280;margin-top:3px}
      #dealz-liste .dz-actions{grid-column:2 / -1;display:flex;flex-wrap:wrap;gap:6px}
      #dealz-liste .dz-actions button{background:#fff;color:#132a66;border:1px solid #cfd5e3;border-radius:99px;padding:4px 12px;font-size:.82em;font-weight:500;cursor:pointer;line-height:1.4}
      #dealz-liste .dz-actions button[aria-pressed=true]{background:#132a66;color:#fff;border-color:#132a66}
      #dealz-liste .dz-actions .dz-voir{border-style:dashed}
      #dealz-liste .dz-qte{display:flex;align-items:center;border:1px solid #cfd5e3;border-radius:99px;overflow:hidden}
      #dealz-liste .dz-qte button{background:#fff;color:#132a66;border:0;width:32px;height:34px;padding:0;font-size:1.1em;cursor:pointer;border-radius:0}
      #dealz-liste .dz-qte input{width:38px;height:34px;border:0;text-align:center;padding:0;-moz-appearance:textfield;border-radius:0;background:#fff}
      #dealz-liste .dz-qte input::-webkit-inner-spin-button{-webkit-appearance:none}
      #dealz-liste .dz-prix{font-weight:700;white-space:nowrap;min-width:78px;text-align:right}
      #dealz-liste .dz-modeles{grid-column:2 / -1;display:flex;gap:10px;overflow-x:auto;padding:6px 2px 10px;scroll-snap-type:x mandatory}
      #dealz-liste .dz-carte{flex:0 0 132px;scroll-snap-align:start;background:#fff;border:2px solid #e6e2d6;border-radius:14px;padding:6px;text-align:left;cursor:pointer;color:#1b2238}
      #dealz-liste .dz-carte img{width:100%;height:110px;object-fit:cover;border-radius:10px;background:#f6f1e4;display:block}
      #dealz-liste .dz-carte span{display:block;font-size:.76em;line-height:1.25;margin-top:5px;min-height:2.5em}
      #dealz-liste .dz-carte b{font-size:.85em}
      #dealz-liste .dz-carte[aria-pressed=true]{border-color:#f2b10a;box-shadow:0 0 0 2px #f2b10a}
      #dealz-liste .dz-manque{grid-column:2 / -1;color:#b42318;font-weight:500}
      #dealz-liste .dz-total{display:flex;justify-content:space-between;align-items:center;gap:1em;flex-wrap:wrap;margin-top:16px;font-size:1.15em}
      @media (max-width:640px){
        #dealz-liste .dz-ligne{grid-template-columns:24px 64px 1fr;}
        #dealz-liste .dz-thumb{width:64px;height:64px}
        #dealz-liste .dz-qte{grid-column:2 / 3}
        #dealz-liste .dz-prix{grid-column:3 / 4}
        #dealz-liste .dz-actions button{font-size:.74em;padding:3px 9px}
      }
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
            $nom = $p->get_name();
            $parts = explode(' — ', $nom, 2);
            $img = $p->get_image_id() ? wp_get_attachment_image_url($p->get_image_id(), 'woocommerce_thumbnail') : '';
            $options[] = ['product_id' => $pid, 'nom' => $nom, 'base' => $parts[0], 'court' => $parts[1] ?? 'Modèle classique',
                          'prix' => (float)$p->get_price(), 'image' => $img ?: wc_placeholder_img_src('woocommerce_thumbnail'),
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
