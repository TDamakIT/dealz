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

  function render() {
    out.replaceChildren();
    let total = 0;
    enfants.forEach((enf, ei) => {
      const sec = el('div', { class: 'dz-enfant-res' });
      const ok = enf.lignes.filter((l) => l.product_id);
      const sous = ok.reduce((a, l) => a + selected(l).prix * l.qte, 0);
      total += sous;
      sec.append(el('h3', {}, `${enf.label} — ${LIB[enf.genre]} : ${fmt(sous)}`));
      sec.append(el('p', {}, `${ok.length} article(s), ${enf.lignes.length - ok.length} à vérifier par l'équipe. Sur chaque ligne : filtrez la gamme si vous voulez, puis choisissez le modèle.`));
      const table = el('table', { class: 'shop_table' });
      enf.lignes.forEach((l, li) => {
        const tr = el('tr');
        const td0 = el('td');
        if (l.product_id) {
          const cb = el('input', { type: 'checkbox', 'data-e': ei, 'data-l': li, 'aria-label': 'Garder cet article' });
          cb.checked = l.keep !== false;
          td0.append(cb);
        }
        const td1 = el('td');
        td1.append(el('small', {}, `Liste : « ${l.ligne} »${l.note ? ' · ' + l.note : ''}`), el('br'));
        if (l.options.length) {
          const dispo = GAMMES.filter(([g]) => l.options.some((o) => o.gamme === g));
          if (dispo.length > 1) {
            const gw = el('div', { class: 'dz-gammes', role: 'group', 'aria-label': 'Gamme' });
            [[null, 'Tout'], ...dispo].forEach(([g, t]) => {
              const b = el('button', { type: 'button', 'data-e': ei, 'data-l': li, 'data-g': g || '', 'aria-pressed': String((l.filtre || null) === g) }, t);
              gw.append(b);
            });
            td1.append(gw);
          }
          const visibles = l.options.filter((o) => !l.filtre || o.gamme === l.filtre);
          const sel = el('select', { 'data-e': ei, 'data-l': li, 'aria-label': 'Modèle' });
          const genre = l.options.some((o) => o.genre !== 'mixte');   // « mixte » n'a de sens que si la ligne a des modèles fille/garçon
          visibles.forEach((o) => {
            const opt = el('option', { value: String(o.product_id) }, `${o.nom}${genre && o.genre === 'mixte' ? ' · mixte' : ''} — ${fmt(o.prix)}`);
            if (o.product_id === l.product_id) opt.selected = true;
            sel.append(opt);
          });
          td1.append(sel);
        } else {
          td1.append(el('strong', {}, 'Non trouvé : l’équipe vous rappelle'));
        }
        const td2 = el('td');
        if (l.product_id) td2.append(el('input', { type: 'number', min: '1', max: '50', value: String(l.qte), 'data-e': ei, 'data-q': li, style: 'width:4em', 'aria-label': 'Quantité' }));
        tr.append(td0, td1, td2, el('td', {}, l.product_id ? fmt(selected(l).prix * l.qte) : ''));
        table.append(tr);
      });
      sec.append(table);
      out.append(sec);
    });
    if (enfants.length) {
      const tp = el('p');
      out.append(tp);
      tp.append(el('strong', {}, `Total ${enfants.length > 1 ? 'pour les ' + enfants.length + ' enfants' : ''} : ${fmt(total)}`));
      const b = el('button', { type: 'button', class: 'button alt' }, 'Tout ajouter au panier (une seule commande)');
      b.addEventListener('click', addToCart);
      out.append(b);
    }
  }

  out.addEventListener('click', (e) => {
    const b = e.target.closest('.dz-gammes button');
    if (!b) return;
    const l = enfants[+b.getAttribute('data-e')].lignes[+b.getAttribute('data-l')];
    l.filtre = b.getAttribute('data-g') || null;
    const first = l.options.find((o) => !l.filtre || o.gamme === l.filtre);
    if (first) l.product_id = first.product_id;
    render();
  });

  out.addEventListener('change', (e) => {
    const t = e.target, ei = t.getAttribute('data-e');
    if (ei === null) return;
    const enf = enfants[+ei];
    if (t.tagName === 'SELECT') enf.lignes[+t.getAttribute('data-l')].product_id = parseInt(t.value, 10);
    else if (t.hasAttribute('data-q')) enf.lignes[+t.getAttribute('data-q')].qte = Math.max(1, parseInt(t.value, 10) || 1);
    else if (t.type === 'checkbox') { enf.lignes[+t.getAttribute('data-l')].keep = t.checked; return; }
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
        j.data.lignes.forEach((l) => { if (l.options && l.options.length > 6) l.filtre = l.options[0].gamme; });
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
