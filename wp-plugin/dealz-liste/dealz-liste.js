(function () {
  const root = document.getElementById('dealz-liste');
  if (!root || !window.DEALZ_LISTE) return;
  const form = root.querySelector('#dealz-liste-form');
  const box = root.querySelector('.dealz-enfants');
  const statut = root.querySelector('.dealz-statut');
  const out = root.querySelector('.dealz-resultat');
  const fmt = (n) => n.toLocaleString('fr-FR', { minimumFractionDigits: 3, maximumFractionDigits: 3 }) + ' DT';
  const GAMMES = [['eco', 'Petit prix'], ['standard', 'Moyenne gamme'], ['premium', 'Haut de gamme']];
  const GENRES = [['fille', 'Fille'], ['garcon', 'Garçon']];
  const LIB = { eco: 'petit prix', standard: 'moyenne gamme', premium: 'haut de gamme', fille: 'fille', garcon: 'garçon', mixte: 'mixte' };
  let enfants = []; // [{label, genre, lignes}] ; chaque ligne : options, product_id, filtre (gamme choisie ou null)
  let seq = 0;

  const el = (tag, attrs = {}, text) => {
    const e = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
    if (text !== undefined) e.textContent = text;
    return e;
  };

  function radios(name, choices, checked) {
    const wrap = el('div', { class: 'dz-choix', role: 'radiogroup' });
    choices.forEach(([v, t]) => {
      const lab = el('label');
      const r = el('input', { type: 'radio', name, value: v, required: 'required' });
      if (v === checked) r.checked = true;
      lab.append(r, document.createTextNode(t));
      wrap.append(lab);
    });
    return wrap;
  }

  function addChild() {
    seq += 1;
    const n = box.children.length + 1;
    const fs = el('fieldset', { 'data-id': String(seq) });
    fs.append(el('legend', {}, `Enfant ${n}`));
    const lab = el('label', {}, 'Prénom (facultatif, pour préparer son cartable à part)');
    lab.append(el('br'), el('input', { type: 'text', name: 'label', maxlength: '30', placeholder: `Enfant ${n}` }));
    fs.append(lab, el('div', {}, 'C\u2019est pour'), radios(`genre-${seq}`, GENRES, null));
    const ph = el('label', {}, 'Photo de la liste');
    ph.append(el('br'), el('input', { type: 'file', name: 'photo', accept: 'image/*' }));
    const tx = el('label', {}, 'Ou collez le texte de la liste');
    tx.append(el('br'), el('textarea', { name: 'texte', rows: '6', style: 'width:100%' }));
    fs.append(ph, el('br'), tx);
    if (n > 1) {
      const rm = el('button', { type: 'button', class: 'button' }, 'Retirer cet enfant');
      rm.addEventListener('click', () => { fs.remove(); renumber(); });
      fs.append(el('p'), rm);
    }
    box.append(fs);
  }

  function renumber() {
    [...box.children].forEach((fs, i) => {
      fs.querySelector('legend').textContent = `Enfant ${i + 1}`;
      fs.querySelector('input[name=label]').placeholder = `Enfant ${i + 1}`;
    });
  }

  root.querySelector('.dealz-ajout-enfant').addEventListener('click', addChild);
  addChild();

  function selected(l) { return l.options.find((o) => o.product_id === l.product_id); }

  const GLIB = { eco: 'Petit prix', standard: 'Moyenne gamme', premium: 'Haut de gamme' };

  function ligneCarte(l, ei, li) {
    const row = el('div', { class: 'dz-ligne' + (l.keep === false ? ' off' : '') });
    const cur = l.product_id ? selected(l) : null;
    const cb = el('input', { type: 'checkbox', 'data-act': 'keep', 'data-e': ei, 'data-l': li, 'aria-label': 'Garder cet article' });
    cb.checked = l.keep !== false;
    if (!cur) cb.disabled = true;
    row.append(el('label', { class: 'dz-garder' }), el('img', { class: 'dz-thumb', alt: '', src: cur ? cur.image : '' }));
    row.firstChild.append(cb);
    const info = el('div', { class: 'dz-info' });
    if (cur) {
      info.append(el('div', { class: 'dz-titre' }, cur.base));
      const m = el('div', { class: 'dz-modele' }, cur.court);
      m.append(el('span', { class: 'dz-tag ' + cur.gamme }, GLIB[cur.gamme] || cur.gamme));
      info.append(m);
    } else {
      info.append(el('div', { class: 'dz-titre' }, l.ligne));
    }
    info.append(el('div', { class: 'dz-source' }, `Sur la liste : « ${l.ligne} »${l.note ? ' · ' + l.note : ''}`));
    let act = null;
    if (cur && l.options.length > 1) {
      act = el('div', { class: 'dz-actions' });
      const dispo = GAMMES.filter(([g]) => l.options.some((o) => o.gamme === g));
      if (dispo.length > 1) dispo.forEach(([g, t]) => act.append(el('button', { type: 'button', 'data-act': 'gamme', 'data-g': g, 'data-e': ei, 'data-l': li, 'aria-pressed': String(l.open && l.filtre === g) }, t)));
      const n = l.options.length;
      act.append(el('button', { type: 'button', class: 'dz-voir', 'data-act': 'voir', 'data-e': ei, 'data-l': li, 'aria-expanded': String(!!l.open) },
        l.open ? 'Fermer' : `Voir les ${n} modèles`));
    }
    row.append(info);
    if (cur) {
      const q = el('div', { class: 'dz-qte' });
      q.append(el('button', { type: 'button', 'data-act': 'moins', 'data-e': ei, 'data-l': li, 'aria-label': 'Moins' }, '−'),
        el('input', { type: 'number', min: '1', max: '50', value: String(l.qte), 'data-act': 'qte', 'data-e': ei, 'data-l': li, 'aria-label': 'Quantité' }),
        el('button', { type: 'button', 'data-act': 'plus', 'data-e': ei, 'data-l': li, 'aria-label': 'Plus' }, '+'));
      row.append(q, el('div', { class: 'dz-prix' }, fmt(cur.prix * l.qte)));
      if (act) row.append(act);
      if (l.open) {
        const strip = el('div', { class: 'dz-modeles', role: 'listbox', 'aria-label': 'Modèles' });
        l.options.filter((o) => !l.filtre || o.gamme === l.filtre).forEach((o) => {
          const c = el('button', { type: 'button', class: 'dz-carte', 'data-act': 'pick', 'data-p': String(o.product_id), 'data-e': ei, 'data-l': li, 'aria-pressed': String(o.product_id === l.product_id) });
          c.append(el('img', { src: o.image, alt: '' }), el('span', {}, o.court), el('b', {}, fmt(o.prix)));
          strip.append(c);
        });
        row.append(strip);
      }
    } else {
      row.append(el('div', { class: 'dz-manque' }, 'Pas trouvé dans le catalogue : l’équipe vous propose une solution.'));
    }
    return row;
  }

  function render() {
    out.replaceChildren();
    let total = 0;
    enfants.forEach((enf, ei) => {
      const sec = el('div', { class: 'dz-enfant-res' });
      const ok = enf.lignes.filter((l) => l.product_id && l.keep !== false);
      const sous = ok.reduce((a, l) => a + selected(l).prix * l.qte, 0);
      total += sous;
      sec.append(el('h3', {}, `${enf.label} · ${LIB[enf.genre]} · ${fmt(sous)}`));
      const manque = enf.lignes.filter((l) => !l.product_id).length;
      sec.append(el('p', { class: 'dz-source' }, `${ok.length} article(s) dans le panier${manque ? `, ${manque} à vérifier par l'équipe` : ''}. Le modèle proposé est en moyenne gamme : change la gamme ou le modèle sur chaque ligne.`));
      enf.lignes.forEach((l, li) => sec.append(ligneCarte(l, ei, li)));
      out.append(sec);
    });
    if (enfants.length) {
      const tp = el('div', { class: 'dz-total' });
      tp.append(el('strong', {}, `Total${enfants.length > 1 ? ' pour les ' + enfants.length + ' enfants' : ''} : ${fmt(total)}`));
      const b = el('button', { type: 'button', class: 'button alt' }, 'Tout ajouter au panier (une seule commande)');
      b.addEventListener('click', addToCart);
      tp.append(b);
      out.append(tp);
    }
  }

  out.addEventListener('click', (e) => {
    const t = e.target.closest('[data-act]');
    if (!t || t.tagName === 'INPUT') return;
    const l = enfants[+t.getAttribute('data-e')].lignes[+t.getAttribute('data-l')];
    const act = t.getAttribute('data-act');
    if (act === 'gamme') {
      const g = t.getAttribute('data-g');
      if (l.open && l.filtre === g) { l.open = false; } else {
        l.open = true; l.filtre = g;
        if (selected(l).gamme !== g) { const first = l.options.find((o) => o.gamme === g); if (first) l.product_id = first.product_id; }
      }
    } else if (act === 'voir') {
      l.open = !l.open; l.filtre = l.open ? null : l.filtre;
    } else if (act === 'pick') {
      l.product_id = parseInt(t.getAttribute('data-p'), 10);
    } else if (act === 'moins') {
      l.qte = Math.max(1, l.qte - 1);
    } else if (act === 'plus') {
      l.qte = Math.min(50, l.qte + 1);
    } else return;
    render();
  });

  out.addEventListener('change', (e) => {
    const t = e.target, act = t.getAttribute('data-act');
    if (!act) return;
    const l = enfants[+t.getAttribute('data-e')].lignes[+t.getAttribute('data-l')];
    if (act === 'qte') l.qte = Math.min(50, Math.max(1, parseInt(t.value, 10) || 1));
    else if (act === 'keep') l.keep = t.checked;
    else return;
    render();
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const blocks = [...box.children];
    enfants = [];
    try {
      for (let i = 0; i < blocks.length; i++) {
        const fs = blocks[i];
        const genre = (fs.querySelector('input[type=radio][name^=genre]:checked') || {}).value;
        const label = fs.querySelector('input[name=label]').value.trim() || `Enfant ${i + 1}`;
        const photo = fs.querySelector('input[name=photo]').files[0];
        const texte = fs.querySelector('textarea[name=texte]').value;
        if (!genre) throw new Error(`${label} : choisissez Fille ou Garçon.`);
        if (!photo && !texte.trim()) throw new Error(`${label} : ajoutez la photo ou le texte de la liste.`);
        const fd = new FormData();
        fd.append('action', 'dealz_liste_lire');
        fd.append('nonce', DEALZ_LISTE.nonce);
        fd.append('genre', genre); fd.append('texte', texte);
        if (photo) fd.append('photo', photo);
        statut.textContent = `Lecture de la liste de ${label}…`;
        const r = await fetch(DEALZ_LISTE.ajax, { method: 'POST', body: fd, credentials: 'same-origin' });
        const j = await r.json();
        if (!j.success) throw new Error((j.data && j.data.message) || 'Erreur');
        // avec 5 modèles ou plus par gamme, on ouvre chaque ligne sur la gamme du modèle proposé (moyenne gamme)
        j.data.lignes.forEach((l) => { l.open = false; l.filtre = null; });
        enfants.push({ label, genre, lignes: j.data.lignes });
      }
      statut.textContent = enfants.length > 1 ? `${enfants.length} listes lues.` : 'Liste lue.';
      render();
    } catch (err) {
      statut.textContent = err.message;
    }
  });

  async function addToCart() {
    const items = [];
    enfants.forEach((enf) => enf.lignes.forEach((l) => {
      if (l.product_id && l.keep !== false) items.push({ product_id: l.product_id, qte: l.qte, enfant: enf.label });
    }));
    const fd = new FormData();
    fd.append('action', 'dealz_liste_panier');
    fd.append('nonce', DEALZ_LISTE.nonce);
    fd.append('items', JSON.stringify(items));
    statut.textContent = 'Ajout au panier…';
    const r = await fetch(DEALZ_LISTE.ajax, { method: 'POST', body: fd, credentials: 'same-origin' });
    const j = await r.json();
    if (j.success) window.location.href = j.data.panier;
    else statut.textContent = 'Impossible d’ajouter au panier.';
  }
})();
