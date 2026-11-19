"""API et tableau de bord local du service d'agents (http://localhost:8000)."""
import base64
import hmac
import html
import json

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse

from . import db, llm, suivi
from .agents import liste
from .config import settings
from .scraper import SOURCE

app = FastAPI(title="Dealz agents")
db.init()   # tables prêtes même si l'API est lancée seule (sans le planificateur)
AGENTS = {}  # rempli par main.py


def _check(token):
    if not settings.api_token or not hmac.compare_digest(token or "", settings.api_token):
        raise HTTPException(401, "Jeton invalide")


@app.get("/api/health")
def health():
    return {"ok": True, "ia": llm.available(), "budget_restant_usd": round(llm.budget_left(), 2),
            "woocommerce": settings.woo_enabled, "telegram": settings.telegram_enabled}


@app.post("/api/liste")
async def api_liste(texte: str = Form(""), genre: str = Form("garcon"), gamme: str = Form("standard"),
                    photo: UploadFile = File(None), x_dealz_token: str = Header(None)):
    _check(x_dealz_token)
    image = None
    if photo is not None:
        raw = await photo.read()
        if len(raw) > 8_000_000:
            raise HTTPException(413, "Photo trop lourde (8 Mo max)")
        image = (photo.content_type or "image/jpeg", base64.b64encode(raw).decode())
    return liste.match(texte, image, genre=genre, gamme=gamme)


@app.post("/api/run/{name}")
def run_agent(name: str, x_dealz_token: str = Header(None)):
    _check(x_dealz_token)
    if name not in AGENTS:
        raise HTTPException(404, "Agent inconnu")
    return {"resultat": AGENTS[name].safe_run()}


@app.get("/prospects.csv", response_class=PlainTextResponse)
def prospects_csv(token: str = ""):
    _check(token)
    import csv, io
    buf = io.StringIO()
    cols = ["id", "ts", "kind", "segment", "nom", "type", "ville", "telephone", "email", "site", "adresse",
            "source_url", "pertinence", "pourquoi", "accroche", "statut"]
    wr = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    wr.writeheader()
    for r in db.prospects(limit=5000):
        wr.writerow(r)
    return PlainTextResponse(buf.getvalue(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=prospects-dealz.csv"})


def _prix(o):
    return f"{o['prix_marche']:.3f}" if o.get("prix_marche") else "—"


def _verdict(o):
    try:
        return json.loads(o["analyse"])["verdict"] if o.get("analyse") else "—"
    except (ValueError, KeyError, TypeError):
        return "—"


@app.get("/", response_class=HTMLResponse)
def dashboard():
    e = html.escape
    dates = db.veille_dates(SOURCE)
    last = dates[-1] if dates else None
    segs = db.veille_segments(last, SOURCE) if last else []
    hist = db.veille_history(SOURCE, 90)
    portable = [h for h in hist if h["type"] == "Portable" and h["gamme"] in
                ("i3 / Core 3 / Ryzen 3", "i5 / Core 5 / Ultra 5 / Ryzen 5", "i7 / Core 7 / Ultra 7 / Ryzen 7")]
    series = {}
    for h in portable:
        series.setdefault(h["gamme"], []).append({"x": h["date"], "y": h["prix_median"]})
    alerts = db.recent_alerts(25)
    reports = db.recent_reports(6)
    usage = db.usage_by_agent()
    rows_seg = "".join(f"<tr><td>{e(s['type'])}</td><td>{e(s['gamme'])}</td><td class=r>{s['modeles']}</td>"
                       f"<td class=r>{s['prix_min']:.0f}</td><td class=r><b>{s['prix_median']:.0f}</b></td><td class=r>{s['prix_max']:.0f}</td></tr>"
                       for s in segs) or "<tr><td colspan=6>Aucun relevé pour l'instant. Lance /veille sur Telegram.</td></tr>"
    rows_alert = "".join(f"<tr><td>{e(a['ts'][:16].replace('T', ' '))}</td><td><span class='lv {e(a['level'])}'>{e(a['level'])}</span></td>"
                         f"<td>{e(a['agent'])}</td><td>{e(a['title'])}</td></tr>" for a in alerts) or "<tr><td colspan=4>Aucune alerte.</td></tr>"
    rep = "".join(f"<details><summary><b>{e(r['title'])}</b> — {e(r['agent'])}, {e(r['ts'][:10])}</summary><pre>{e(r['body'])}</pre></details>"
                  for r in reports) or "<p class=m>Aucun rapport pour l'instant.</p>"
    pros = db.prospects(limit=40)
    rows_pros = "".join(f"<tr><td>#{p['id']}</td><td>{e(p['kind'])}</td><td><b>{e(p['nom'])}</b><br><small class=m>{e(p['segment'])}</small></td>"
                        f"<td>{e(p['ville'])}</td><td>{e(p['telephone'])}<br>{e(p['email'])}</td><td>{'★' * int(p['pertinence'] or 0)}</td>"
                        f"<td>{e(p['statut'])}</td><td><a href='{e(p['source_url'])}' target=_blank rel=noopener>source</a></td></tr>"
                        for p in pros) or "<tr><td colspan=8>Aucune cible pour l'instant. Lance /prospection sur Telegram.</td></tr>"
    opps = db.opportunites(limit=30)
    rows_opp = "".join(f"<tr><td>#{o['id']}</td><td><b>{e(o['produit'])}</b><br><small class=m>{e((o['pourquoi'] or '')[:160])}</small></td>"
                       f"<td>{e(o['categorie'])}</td><td>{e(o['canal'])}</td><td>{'★' * int(o['score'] or 0)}</td>"
                       f"<td class=r>{_prix(o)}</td>"
                       f"<td>{e(_verdict(o))}</td><td>{e(o['statut'])}</td></tr>"
                       for o in opps) or "<tr><td colspan=8>Aucune opportunité. Lance /tendances sur Telegram.</td></tr>"
    from . import bus
    rows_bus = "".join(f"<tr><td>#{ev['id']}</td><td>{e(ev['ts'][:16].replace('T', ' '))}</td><td>{e(ev['topic'])}</td><td>{e(ev['agent'])}</td>"
                       f"<td>{e(ev['resume'])}{' <small class=m>(démo)</small>' if ev['mock'] else ''}</td><td>"
                       + "<br>".join(f"<b>{e(r['subscriber'])}</b> : {e(r['result'])}" for r in bus.reactions(ev["id"])) + "</td></tr>"
                       for ev in bus.events(days=30, limit=30)) or "<tr><td colspan=6>Tableau vide.</td></tr>"
    prio = (db.get_state("priorites") or {}).get("priorites", [])
    prio_html = "".join(f"<li><b>{e(p['titre'])}</b> — {e(p.get('pourquoi', ''))}</li>" for p in prio) or "<li class=m>Pas encore de priorités.</li>"
    tdays = db.tendances_dates(1)
    tsnap = db.tendances_snapshot(tdays[0]) if tdays else []
    rows_top = "".join(f"<tr><td>{e(r['site'])}</td><td>{e(r['page'])}</td><td>{'ventes' if r['tri'] == 'ventes' else 'ordre du site'}</td>"
                       f"<td class=r>{r['rang']}</td><td>{e(r['nom'][:90])}</td><td class=r>{r['prix']:.3f}</td><td>{'oui' if r['en_stock'] else 'non'}</td></tr>"
                       for r in tsnap if r["rang"] <= 5) or "<tr><td colspan=7>Aucun relevé. Le premier passe à 06:45.</td></tr>"
    use = "".join(f"<tr><td>{e(u['agent'])}</td><td>{e(u['model'])}</td><td class=r>{u['appels']}</td><td class=r>{(u['cout'] or 0):.3f} $</td></tr>" for u in usage)
    body = f"""<div class=k><div>IA<b>{'active' if llm.available() else 'simulation'}</b></div><div>Budget du mois<b>{db.month_cost():.2f} / {settings.budget_usd:.0f} $</b></div>
<div>Boutique<b>{'connectée' if settings.woo_enabled else 'non connectée'}</b></div><div>Telegram<b>{'actif' if settings.telegram_enabled else 'non configuré'}</b></div></div>
<section class=c><h2>Prix médian des portables chez {SOURCE} (DT)</h2><canvas id=ch height=90></canvas></section>
<section class=c><h2>Dernier relevé {SOURCE} {e(last or '')}</h2><table><tr><th>Type</th><th>Gamme</th><th class=r>Modèles</th><th class=r>Min</th><th class=r>Médian</th><th class=r>Max</th></tr>{rows_seg}</table></section>
<section class=c><h2>Alertes</h2><table>{rows_alert}</table></section>
<section class=c><h2>Prospection (40 dernières cibles)</h2><p class=m>Export complet : /prospects.csv?token=… (ton AGENTS_API_TOKEN)</p><table><tr><th>#</th><th>Type</th><th>Organisation</th><th>Ville</th><th>Contact</th><th>Intérêt</th><th>Statut</th><th></th></tr>{rows_pros}</table></section>
<section class=c><h2>Priorités de la semaine</h2><ol>{prio_html}</ol></section>
<section class=c><h2>Tableau partagé des agents (30 jours)</h2><table><tr><th>#</th><th>Quand</th><th>Sujet</th><th>Publié par</th><th>Résumé</th><th>Réactions</th></tr>{rows_bus}</table></section>
<section class=c><h2>Opportunités (experts Tendances et Sourcing)</h2><table><tr><th>#</th><th>Produit</th><th>Catégorie</th><th>Canal</th><th>Score</th><th class=r>Prix marché DT</th><th>Verdict import</th><th>Statut</th></tr>{rows_opp}</table></section>
<section class=c><h2>Top 5 chez les concurrents {e(tdays[0] if tdays else '')}</h2><p class=m>« ventes » = classement des meilleures ventes publié par le site ; « ordre du site » = pas de classement disponible, ne dit rien des ventes.</p><table><tr><th>Site</th><th>Page</th><th>Tri</th><th class=r>Rang</th><th>Produit</th><th class=r>Prix DT</th><th>En stock</th></tr>{rows_top}</table></section>
<section class=c><h2>Rapports</h2>{rep}</section>
<section class=c><h2>Consommation IA du mois</h2><table><tr><th>Agent</th><th>Modèle</th><th class=r>Appels</th><th class=r>Coût</th></tr>{use}</table></section>
"""
    script = f"""
const S={json.dumps(series, ensure_ascii=False)};const C=['#1b3a8c','#f2b10a','#d6453b'];
new Chart(document.getElementById('ch'),{{type:'line',data:{{datasets:Object.entries(S).map(([k,v],i)=>({{label:k,data:v,borderColor:C[i%3],backgroundColor:C[i%3],tension:0}}))}},
options:{{parsing:{{xAxisKey:'x',yAxisKey:'y'}},scales:{{x:{{type:'category'}}}},plugins:{{legend:{{position:'bottom'}}}}}}}});
"""
    return _page("Vue d'ensemble", "/", body, script, chart=True)


# --- Mise en page commune ----------------------------------------------------

CSS = """body{font:15px system-ui,sans-serif;margin:0;background:#f4f6fb;color:#131a33}main{max-width:1100px;margin:auto;padding:20px;display:grid;gap:18px}
.c{background:#fff;border:1px solid #dce1ec;border-radius:14px;padding:16px;overflow-x:auto}h1{margin:0;font-size:26px}h2{margin:0 0 10px;font-size:18px}
table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:7px;border-bottom:1px solid #e6e9f2;text-align:left;vertical-align:top}.r{text-align:right;font-variant-numeric:tabular-nums}
.k{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.k div{background:#fff;border:1px solid #dce1ec;border-radius:14px;padding:14px}.k b{display:block;font-size:22px}
.m{color:#59627f}pre{white-space:pre-wrap;font:14px system-ui}.lv{padding:2px 8px;border-radius:99px;font-size:12px;background:#e3e9fa;white-space:nowrap}.critique{background:#fbe3e1}.important{background:#fdf0d4}.opportunite{background:#dff3e8}
nav{background:#1b3a8c;padding:0 20px}nav div{max-width:1100px;margin:auto;display:flex;gap:4px;flex-wrap:wrap}nav a{color:#dfe6fb;text-decoration:none;padding:12px 14px;font-weight:600}
nav a.on{color:#fff;box-shadow:inset 0 -3px #f2b10a}nav b{color:#f2b10a;padding:12px 14px 12px 0}
tr.retard td{background:#fdecea}.bad{color:#b3261e;font-weight:600}.good{color:#1c7c46}.neutre{color:#59627f}
.btn{display:inline-block;border:1px solid #c8cfe0;background:#fff;border-radius:8px;padding:4px 9px;margin:2px 2px 2px 0;font:13px system-ui;cursor:pointer;color:#131a33;text-decoration:none;white-space:nowrap}
.btn.wa{background:#e3f6ea;border-color:#9ed5b2}.btn.ok{background:#e3e9fa}.btn.no{background:#fbe3e1}
.filtres a{margin-right:6px}form.q{display:flex;gap:8px;flex-wrap:wrap}form.q input,form.q select{font:15px system-ui;padding:7px 10px;border:1px solid #c8cfe0;border-radius:8px}
.bar{height:8px;border-radius:4px;background:#e6e9f2;min-width:80px}.bar i{display:block;height:8px;border-radius:4px;background:#1b3a8c}"""

NAV = [("/", "Vue d'ensemble"), ("/commandes", "Commandes"), ("/prix", "Comparer les prix"), ("/marges", "Marges")]


def _page(title, active, body, script="", chart=False):
    nav = "".join(f"<a href='{u}'{' class=on' if u == active else ''}>{html.escape(t)}</a>" for u, t in NAV)
    lib = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>' if chart else ""
    return f"""<!doctype html><html lang=fr><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Dealz — {html.escape(title)}</title>{lib}<style>{CSS}</style></head>
<body><nav><div><b>Dealz</b>{nav}</div></nav><main><h1>{html.escape(title)}</h1>
{body}</main><script>{script}</script></body></html>"""


def _dt(x, dec=3):
    return "—" if x is None else f"{x:,.{dec}f}".replace(",", " ")


def _pct(x, seuil=None):
    if x is None:
        return "<span class=m>—</span>"
    cls = "bad" if seuil is not None and x < seuil else ""
    return f"<span class='{cls}'>{x:.1f} %</span>"


def _vs(prix, ref):
    if not prix or not ref:
        return "—"
    ecart = (prix - ref) / ref * 100
    return f"<span class='{'bad' if ecart > settings.seuil_prix_pct else 'good' if ecart < 0 else ''}'>{ecart:+.0f} %</span>"


def _erreur(exc):
    return f"<section class=c><p class=bad>La boutique n'a pas répondu : {html.escape(str(exc)[:300])}</p></section>"


# --- Suivi des commandes -----------------------------------------------------

ETAPES = ["à confirmer", "confirmée", "livrée", "annulée"]


@app.post("/api/commandes/{order_id}/{action}")
def commande_action(order_id: int, action: str, x_dealz_token: str = Header(None)):
    _check(x_dealz_token)
    if action not in ("confirmee", "annulee", "livree"):
        raise HTTPException(400, "Action inconnue")
    try:
        note = suivi.changer_etape(order_id, action)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)[:300])
    suivi.clear_cache()
    return {"ok": True, "note": note}


ACTION_JS = """
async function act(id,action,label){
  let t=localStorage.getItem('dealzToken');
  if(!t){t=prompt('Jeton du service d\'agents (AGENTS_API_TOKEN) :');if(!t)return;}
  if(action!=='confirmee'&&!confirm('Commande '+label+' : '+(action==='annulee'?'annuler':'marquer livrée')+' ?'))return;
  const r=await fetch('/api/commandes/'+id+'/'+action,{method:'POST',headers:{'X-Dealz-Token':t}});
  if(r.status===401){localStorage.removeItem('dealzToken');alert('Jeton refusé.');return;}
  if(!r.ok){alert('Erreur : '+await r.text());return;}
  localStorage.setItem('dealzToken',t);location.reload();
}"""


@app.get("/commandes", response_class=HTMLResponse)
def page_commandes(etape: str = "", jours: int = 30):
    e = html.escape
    jours = max(1, min(jours, 180))
    try:
        rows = suivi.commandes(jours)
    except Exception as exc:  # boutique arrêtée, mauvais mot de passe…
        return _page("Suivi des commandes", "/commandes", _erreur(exc))
    if rows is None:
        return _page("Suivi des commandes", "/commandes", "<section class=c><p>La boutique n'est pas connectée "
                     "(WOO_URL, WOO_USER, WOO_APP_PASSWORD dans .env). Le suivi des commandes lit WooCommerce.</p></section>")
    compte = {s: sum(r["etape"] == s for r in rows) for s in ETAPES}
    retard = sum(r["en_retard"] for r in rows)
    actives = [r for r in rows if r["etape"] != "annulée"]
    ca = sum(r["total"] for r in actives)
    vues = [r for r in rows if not etape or r["etape"] == etape]
    vues.sort(key=lambda r: r["date"], reverse=True)   # puis en retard et à confirmer en tête (tri stable)
    vues.sort(key=lambda r: (not r["en_retard"], r["etape"] != "à confirmer"))

    def ligne(r):
        boutons = ""
        if r["wa"] and r["etape"] in ("à confirmer", "confirmée"):
            boutons += f"<a class='btn wa' href='{e(r['wa'])}' target=_blank rel=noopener>WhatsApp</a>"
        if r["etape"] == "à confirmer":
            boutons += f"<button class='btn ok' onclick=\"act({r['id']},'confirmee','n°{r['numero']}')\">Confirmée</button>"
        if r["etape"] == "confirmée":
            boutons += f"<button class='btn ok' onclick=\"act({r['id']},'livree','n°{r['numero']}')\">Livrée</button>"
        if r["etape"] in ("à confirmer", "confirmée"):
            boutons += f"<button class='btn no' onclick=\"act({r['id']},'annulee','n°{r['numero']}')\">Annulée</button>"
        niveau = "critique" if r["score"] >= 70 else "important" if r["score"] >= 50 else ""
        statut = e(r["etape"]) + (f"<br><small class=bad>depuis {r['age_h']} h</small>" if r["en_retard"] else "")
        return (f"<tr class='{'retard' if r['en_retard'] else ''}'><td><b>n°{e(str(r['numero']))}</b><br><small class=m>{e(r['date'])}</small></td>"
                f"<td>{e(r['client'])}<br><small class=m>{e(r['telephone'])}</small></td><td>{e(r['gouvernorat'])}</td>"
                f"<td class=r><b>{_dt(r['total'])}</b><br><small class=m>{r['articles']} art. · {e(r['paiement'])}</small></td>"
                f"<td class=r>{_dt(r['marge'])}</td>"
                f"<td><span class='lv {niveau}'>{r['score']}/100</span><br><small class=m>{e(', '.join(r['raisons']) or 'faible')}</small></td>"
                f"<td>{statut}</td><td>{boutons}</td></tr>")

    filtres = " ".join(f"<a class='btn{' ok' if etape == s else ''}' href='/commandes?jours={jours}&etape={e(s)}'>{e(s)} ({compte[s]})</a>" for s in ETAPES)
    filtres = f"<a class='btn{' ok' if not etape else ''}' href='/commandes?jours={jours}'>toutes ({len(rows)})</a> " + filtres
    body = f"""<div class=k><div>À confirmer<b>{compte['à confirmer']}</b></div><div>En retard (&gt; 24 h)<b class='{'bad' if retard else ''}'>{retard}</b></div>
<div>Commandes ({jours} j, hors annulées)<b>{len(actives)}</b></div><div>Chiffre d'affaires<b>{_dt(ca)} DT</b></div>
<div>Taux d'annulation<b>{(compte['annulée'] / len(rows) * 100 if rows else 0):.0f} %</b></div></div>
<section class=c><p class="filtres">{filtres}</p>
<p class=m>Période : {" ".join(f"<a href='/commandes?jours={j}&etape={e(etape)}'>{j} j</a>" for j in (7, 30, 90))}.
En rouge : non confirmée depuis plus de 24 h. WhatsApp ouvre le message prêt, l'envoi reste manuel. Marge = articles moins prix d'achat (hors livraison).</p>
<table><tr><th>Commande</th><th>Client</th><th>Gouvernorat</th><th class=r>Montant DT</th><th class=r>Marge DT</th><th>Risque</th><th>Étape</th><th></th></tr>
{"".join(ligne(r) for r in vues) or "<tr><td colspan=8>Aucune commande sur la période.</td></tr>"}</table></section>"""
    return _page("Suivi des commandes", "/commandes", body, ACTION_JS)


# --- Comparer les prix -------------------------------------------------------

@app.get("/prix", response_class=HTMLResponse)
def page_prix(q: str = ""):
    e = html.escape
    try:
        day, gammes = suivi.comparer_gammes()
        nous, eux = suivi.rechercher(q)
    except Exception as exc:
        return _page("Comparer les prix", "/prix", _erreur(exc))
    rows_g = "".join(
        f"<tr><td><b>{e(g['nom'])}</b><br><small class=m>{e(g['gamme'])} · {g['modeles']} modèles</small></td>"
        f"<td class=r><b>{_dt(g['prix'])}</b></td><td class=r>{_dt(g['min'], 0)}</td><td class=r>{_dt(g['median'], 0)}</td><td class=r>{_dt(g['max'], 0)}</td>"
        f"<td class=r><span class='{'bad' if g['trop_cher'] else 'good' if g['ecart_pct'] < 0 else ''}'>{g['ecart_pct']:+.1f} %</span></td>"
        f"<td class=r>{_pct(suivi.marge(g['prix'], g['achat'])[1], settings.seuil_marge_pct)}</td></tr>" for g in gammes
    ) or f"<tr><td colspan=7>{'Aucun relevé ' + SOURCE + ' pour l’instant : lance /veille sur Telegram.' if not day else 'Aucun de nos produits n’est rattaché à une gamme de la veille (méta _veille_gamme).'}</td></tr>"

    resultats = ""
    if q.strip():
        bas = min((r["prix"] for r in eux), default=None)
        rows_nous = "".join(f"<tr><td>{e(p['nom'])}<br><small class=m>{e(p['sku'])} · {e(p['categorie'])}</small></td><td class=r><b>{_dt(p['prix'])}</b></td>"
                            f"<td class=r>{_dt(p['achat'])}</td><td class=r>{_pct(suivi.marge(p['prix'], p['achat'])[1], settings.seuil_marge_pct)}</td>"
                            f"<td class=r>{_vs(p['prix'], bas)}</td></tr>" for p in nous
                            ) or "<tr><td colspan=5>Aucun produit Dealz ne correspond.</td></tr>"
        rows_eux = "".join(f"<tr><td>{e(r['site'])}</td><td>{e(r['nom'][:110])}</td><td class=r><b>{_dt(r['prix'])}</b></td>"
                           f"<td>{'oui' if r['en_stock'] else 'non'}</td><td class=m>{e(r['date'])}</td></tr>" for r in eux
                           ) or "<tr><td colspan=5>Rien chez les concurrents dans les derniers relevés (veille PC et pages suivies par l'expert Tendances).</td></tr>"
        resultats = f"""<section class=c><h2>Chez nous ({len(nous)})</h2><table><tr><th>Produit</th><th class=r>Notre prix</th><th class=r>Achat</th><th class=r>Marge</th><th class=r>vs moins cher concurrent</th></tr>{rows_nous}</table></section>
<section class=c><h2>Chez les concurrents ({len(eux)}), du moins cher au plus cher</h2><table><tr><th>Site</th><th>Produit</th><th class=r>Prix DT</th><th>En stock</th><th>Relevé du</th></tr>{rows_eux}</table></section>"""

    body = f"""<section class=c><h2>Rechercher un produit</h2>
<form class=q method=get action=/prix><input name=q value="{e(q)}" placeholder="ex. i5 16go, cartable, bouilloire" size=40><button class='btn ok'>Comparer</button></form>
<p class=m>Cherche dans notre catalogue et dans les derniers relevés concurrents (tous les mots doivent apparaître). Seuls les sites et rayons relevés par les agents sont couverts.</p></section>
{resultats}
<section class=c><h2>Nos PC face au marché ({SOURCE} {e(day or '')})</h2>
<p class=m>Écart = notre prix comparé à la médiane de la gamme. En rouge : plus de {settings.seuil_prix_pct:.0f} % au-dessus.</p>
<table><tr><th>Produit</th><th class=r>Notre prix</th><th class=r>Min marché</th><th class=r>Médiane</th><th class=r>Max</th><th class=r>Écart</th><th class=r>Notre marge</th></tr>{rows_g}</table></section>"""
    return _page("Comparer les prix", "/prix", body)


# --- Marges -----------------------------------------------------------------

@app.get("/marges", response_class=HTMLResponse)
def page_marges(categorie: str = "", tri: str = "marge", tout: int = 0):
    e = html.escape
    try:
        m = suivi.marges()
    except Exception as exc:
        return _page("Marges", "/marges", _erreur(exc))
    seuil = settings.seuil_marge_pct
    rows = [r for r in m["produits"] if (tout or r["principal"]) and (not categorie or r["categorie"] == categorie)]
    cles = {"marge": lambda r: (r["marge_pct"] is None, r["marge_pct"] or 0), "stock": lambda r: -(r["valeur_stock"] or 0),
            "prix": lambda r: -(r["prix"] or 0), "nom": lambda r: r["nom"]}
    rows.sort(key=cles.get(tri, cles["marge"]))
    real = m["realisee"]
    kpi_real = (f"<div>Marge réalisée ({real['jours']} j)<b>{_dt(real['marge'])} DT</b><small class=m>{_pct(real['marge_pct'])} sur {real['commandes']} commandes</small></div>"
                if real else "<div>Marge réalisée<b class=m>—</b><small class=m>boutique non connectée</small></div>")
    src = ("<p class=m>Source : <b>catalogue local fictif</b> (data/catalog.json), la boutique n'est pas connectée.</p>" if m["source"] == "catalogue"
           else "<p class=m>Source : boutique WooCommerce (prix d'achat = méta _cout_achat). Données fictives tant que le fichier Office House n'est pas là.</p>")
    rows_cat = "".join(
        f"<tr><td><a href='/marges?categorie={e(c['categorie'])}'>{e(c['categorie'])}</a></td><td class=r>{c['produits']}</td>"
        f"<td class=r>{_pct(c['marge_pct'], seuil)}</td><td><div class=bar><i style='width:{max(0, min(100, (c['marge_pct'] or 0) * 2)):.0f}%'></i></div></td>"
        f"<td class=r>{'<span class=bad>' + str(c['faibles']) + '</span>' if c['faibles'] else '0'}</td><td class=r>{_dt(c['valeur_stock'], 0)}</td></tr>"
        for c in m["categories"])
    rows_p = "".join(
        f"<tr><td>{e(r['nom'])}<br><small class=m>{e(str(r['sku']))} · {e(r['fournisseur'])}</small></td><td>{e(r['categorie'])}</td>"
        f"<td class=r>{_dt(r['achat'])}</td><td class=r>{_dt(r['prix'])}</td><td class=r>{_dt(r['marge_dt'])}</td><td class=r>{_pct(r['marge_pct'], seuil)}</td>"
        f"<td class=r>{'—' if r['stock'] is None else r['stock']}</td><td class=r>{_dt(r['valeur_stock'], 0)}</td></tr>"
        for r in rows[:300]) or "<tr><td colspan=8>Aucun produit.</td></tr>"
    qs = f"categorie={e(categorie)}&tout={tout}"
    tris = " ".join(f"<a class='btn{' ok' if tri == k else ''}' href='/marges?{qs}&tri={k}'>{t}</a>"
                    for k, t in (("marge", "marge croissante"), ("stock", "valeur de stock"), ("prix", "prix"), ("nom", "nom")))
    body = f"""<div class=k><div>Marge moyenne<b>{_pct(m['moyenne_pct'], seuil)}</b><small class=m>sur le prix de vente TTC</small></div>
<div>Sous {seuil:.0f} %<b class='{'bad' if m['faibles'] else ''}'>{len(m['faibles'])}</b><small class=m>produits</small></div>
<div>Valeur du stock<b>{_dt(m['valeur_stock'], 0)} DT</b><small class=m>au prix d'achat</small></div>{kpi_real}
<div>Sans prix d'achat<b>{m['sans_cout']}</b><small class=m>marge inconnue</small></div></div>
<section class=c><h2>Par catégorie</h2>{src}<table><tr><th>Catégorie</th><th class=r>Produits</th><th class=r>Marge</th><th></th><th class=r>Sous {seuil:.0f} %</th><th class=r>Stock DT</th></tr>{rows_cat}</table></section>
<section class=c><h2>Produits{' — ' + e(categorie) if categorie else ''} ({len(rows)})</h2>
<p class=filtres>{tris} · <a href='/marges?categorie={e(categorie)}&tri={e(tri)}&tout={0 if tout else 1}'>{'produits principaux seulement' if tout else 'inclure tous les modèles'}</a>{" · <a href='/marges'>toutes catégories</a>" if categorie else ''}</p>
<table><tr><th>Produit</th><th>Catégorie</th><th class=r>Achat</th><th class=r>Vente</th><th class=r>Marge DT</th><th class=r>Marge</th><th class=r>Stock</th><th class=r>Stock DT</th></tr>{rows_p}</table>
{'<p class=m>300 premières lignes affichées.</p>' if len(rows) > 300 else ''}</section>"""
    return _page("Marges", "/marges", body)
