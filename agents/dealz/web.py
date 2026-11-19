"""API et tableau de bord local du service d'agents (http://localhost:8000)."""
import base64
import hmac
import html
import json

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse

from . import db, llm
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
    return f"""<!doctype html><html lang=fr><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Dealz — agents</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>body{{font:15px system-ui,sans-serif;margin:0;background:#f4f6fb;color:#131a33}}main{{max-width:1100px;margin:auto;padding:20px;display:grid;gap:18px}}
.c{{background:#fff;border:1px solid #dce1ec;border-radius:14px;padding:16px;overflow-x:auto}}h1{{margin:0;font-size:26px}}h2{{margin:0 0 10px;font-size:18px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{padding:7px;border-bottom:1px solid #e6e9f2;text-align:left}}.r{{text-align:right;font-variant-numeric:tabular-nums}}
.k{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}.k div{{background:#fff;border:1px solid #dce1ec;border-radius:14px;padding:14px}}.k b{{display:block;font-size:22px}}
.m{{color:#59627f}}pre{{white-space:pre-wrap;font:14px system-ui}}.lv{{padding:2px 8px;border-radius:99px;font-size:12px;background:#e3e9fa}}.critique{{background:#fbe3e1}}.important{{background:#fdf0d4}}.opportunite{{background:#dff3e8}}</style></head>
<body><main><h1>Dealz — agents</h1>
<div class=k><div>IA<b>{'active' if llm.available() else 'simulation'}</b></div><div>Budget du mois<b>{db.month_cost():.2f} / {settings.budget_usd:.0f} $</b></div>
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
</main><script>
const S={json.dumps(series, ensure_ascii=False)};const C=['#1b3a8c','#f2b10a','#d6453b'];
new Chart(document.getElementById('ch'),{{type:'line',data:{{datasets:Object.entries(S).map(([k,v],i)=>({{label:k,data:v,borderColor:C[i%3],backgroundColor:C[i%3],tension:0}}))}},
options:{{parsing:{{xAxisKey:'x',yAxisKey:'y'}},scales:{{x:{{type:'category'}}}},plugins:{{legend:{{position:'bottom'}}}}}}}});
</script></body></html>"""
