<?php
/**
 * Page d'accueil Dealz.
 */
get_header();
$img = get_stylesheet_directory_uri() . '/assets/img/';
$liste = home_url('/liste-scolaire/');
$cat = function ($name) {
    $t = get_term_by('name', $name, 'product_cat');
    return $t ? get_term_link($t) : wc_get_page_permalink('shop');
};
?>
<div id="primary" class="content-area"><main id="main" class="site-main" role="main">
<div class="dealz-home">

  <section class="dealz-hero">
    <div class="dealz-hero-texte">
      <span class="dealz-pill">Rentrée 2027 · bientôt</span>
      <h1>La rentrée <span class="dealz-surligne">sans stress.</span></h1>
      <p class="dealz-hero-ar" lang="ar" dir="rtl">الرونتري بلا ستراس</p>
      <p class="dealz-hero-sous">Envoie la liste de l'école, on prépare le cartable de chaque enfant. Une seule commande, livrée chez toi partout en Tunisie.</p>
      <div class="dealz-cta">
        <a class="button dealz-btn-primaire" href="<?php echo esc_url($liste); ?>">Envoyer ma liste</a>
        <a class="button dealz-btn-secondaire" href="<?php echo esc_url(wc_get_page_permalink('shop')); ?>">Voir la boutique</a>
      </div>
      <ul class="dealz-hero-plus">
        <li>Simple</li><li>Gain de temps</li><li>Prix doux</li>
      </ul>
    </div>
    <div class="dealz-hero-visuel" aria-hidden="true">
      <img class="v1" src="<?php echo esc_url($img . 'cartable-garcon.jpg'); ?>" alt="">
      <img class="v2" src="<?php echo esc_url($img . 'cartable-fille.jpg'); ?>" alt="">
      <img class="v3" src="<?php echo esc_url($img . 'trousse-fille.jpg'); ?>" alt="">
      <img class="v4" src="<?php echo esc_url($img . 'stylo-premium.jpg'); ?>" alt="">
      <img class="v5" src="<?php echo esc_url($img . 'cahier-standard.jpg'); ?>" alt="">
    </div>
  </section>

  <section class="dealz-etapes">
    <h2>Comment ça marche</h2>
    <ol>
      <li><b>1</b><h3>Envoie la liste</h3><p>Une photo ou le texte de la liste de l'école, en français ou en arabe.</p></li>
      <li><b>2</b><h3>Choisis les modèles</h3><p>Fille ou garçon, puis petit prix, moyenne gamme ou haut de gamme, article par article.</p></li>
      <li><b>3</b><h3>Reçois le cartable</h3><p>On prépare un cartable par enfant, dans un seul colis. Tu paies à la livraison.</p></li>
    </ol>
    <p class="dealz-centre"><a class="button dealz-btn-primaire" href="<?php echo esc_url($liste); ?>">Commencer ma liste</a></p>
  </section>

  <section class="dealz-rayons">
    <h2>Nos rayons</h2>
    <div class="dealz-rayons-grille">
      <a class="dealz-rayon r-scolaire" href="<?php echo esc_url($cat('Papeterie & scolaire')); ?>">
        <img src="<?php echo esc_url($img . 'cartable-premium.jpg'); ?>" alt="">
        <span><b>Papeterie & scolaire</b>Cartables, cahiers, trousses, écriture</span></a>
      <a class="dealz-rayon r-info" href="<?php echo esc_url($cat('Informatique & bureau')); ?>">
        <svg viewBox="0 0 64 64" aria-hidden="true"><rect x="8" y="12" width="48" height="30" rx="4" fill="#132a66"/><rect x="12" y="16" width="40" height="22" rx="2" fill="#8eaaff"/><path d="M4 46h56l-4 6H8z" fill="#132a66"/></svg>
        <span><b>Informatique & bureau</b>PC, accessoires, impression</span></a>
      <a class="dealz-rayon r-cadeaux" href="<?php echo esc_url($cat('Idées cadeaux')); ?>">
        <svg viewBox="0 0 64 64" aria-hidden="true"><rect x="10" y="26" width="44" height="30" rx="4" fill="#e2463b"/><rect x="6" y="18" width="52" height="10" rx="3" fill="#f2b10a"/><rect x="29" y="18" width="6" height="38" fill="#fff"/><path d="M32 18c-6-10-16-6-10 0M32 18c6-10 16-6 10 0" fill="none" stroke="#fff" stroke-width="4"/></svg>
        <span><b>Idées cadeaux</b>Coffrets prêts à offrir</span></a>
      <div class="dealz-rayon r-bientot">
        <svg viewBox="0 0 64 64" aria-hidden="true"><path d="M10 30L32 12l22 18v24H10z" fill="#7a8396"/><rect x="26" y="38" width="12" height="16" fill="#fff"/></svg>
        <span><b>Maison & petit électroménager</b>Bientôt</span></div>
    </div>
  </section>

  <?php
  $packs = get_term_by('name', 'Packs rentrée', 'product_cat');
  if ($packs && $packs->count): ?>
  <section class="dealz-selection">
    <h2>Les packs rentrée</h2>
    <p class="dealz-section-sous">Tout le niveau dans un seul pack, moins cher que l'article par article.</p>
    <?php echo do_shortcode('[products category="' . esc_attr($packs->slug) . '" limit="4" columns="4"]'); ?>
  </section>
  <?php endif; ?>

  <?php
  $sacs = get_term_by('name', 'Sacs à dos & cartables', 'product_cat');
  if ($sacs): ?>
  <section class="dealz-selection">
    <h2>Les cartables</h2>
    <p class="dealz-section-sous">Plus de 5 modèles fille et garçon dans chaque gamme.</p>
    <?php echo do_shortcode('[products category="' . esc_attr($sacs->slug) . '" limit="4" columns="4" visibility="visible"]'); ?>
  </section>
  <?php endif; ?>

  <section class="dealz-pro">
    <div>
      <h2>Écoles, crèches, entreprises</h2>
      <p>Vos fournitures et consommables livrés sur devis, avec des prix au volume et une facture pour votre comptabilité.</p>
    </div>
    <a class="button dealz-btn-primaire" href="<?php echo esc_url(home_url('/espace-pro/')); ?>">Demander un devis</a>
  </section>

</div>
</main></div>
<?php
get_footer();
