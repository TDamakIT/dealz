/* Filtres « Fille / Garçon » et « gamme » du bloc « Choisis ton modèle » (fiche produit). */
(function () {
  document.querySelectorAll('[data-dealz-modeles]').forEach(function (box) {
    var etat = { genre: '', gamme: '' };
    var items = box.querySelectorAll('.dealz-modeles-grille > li');
    var vide = box.querySelector('.dealz-modeles-vide');
    function appliquer() {
      var visibles = 0;
      items.forEach(function (li) {
        var g = li.getAttribute('data-genre'), gm = li.getAttribute('data-gamme');
        // « Garçon » montre les modèles garçon ET mixtes (même règle que la liste scolaire)
        var ok = (!etat.genre || g === etat.genre || g === 'mixte') && (!etat.gamme || gm === etat.gamme);
        li.hidden = !ok;
        if (ok) visibles++;
      });
      if (vide) vide.hidden = visibles > 0;
    }
    box.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-f]');
      if (!b) return;
      var f = b.getAttribute('data-f');
      etat[f] = b.getAttribute('data-v');
      box.querySelectorAll('button[data-f="' + f + '"]').forEach(function (x) {
        x.setAttribute('aria-pressed', String(x === b));
      });
      appliquer();
    });
  });
})();
