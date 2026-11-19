"""Stockage local SQLite : historique veille, alertes, rapports, consommation IA, état."""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import settings

_lock = threading.Lock()
DB_PATH = settings.data_dir / "dealz.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_usage (
  ts TEXT, agent TEXT, model TEXT, input_tokens INT, output_tokens INT,
  cache_read INT, cache_write INT, cost_usd REAL);
CREATE TABLE IF NOT EXISTS veille_items (
  date TEXT, source TEXT, cat TEXT, nom TEXT, prix REAL, en_stock INT);
CREATE INDEX IF NOT EXISTS ix_vi_date ON veille_items(date);
CREATE TABLE IF NOT EXISTS veille_segments (
  date TEXT, source TEXT, type TEXT, gamme TEXT, modeles INT,
  prix_min REAL, prix_median REAL, prix_max REAL,
  PRIMARY KEY (date, source, type, gamme));
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, agent TEXT, level TEXT,
  title TEXT, body TEXT, dedupe_key TEXT UNIQUE, sent INT DEFAULT 0);
CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, agent TEXT, title TEXT, body TEXT);
CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS prospects (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, segment TEXT, nom TEXT, type TEXT, ville TEXT,
  telephone TEXT, email TEXT, site TEXT, adresse TEXT, source_url TEXT, pertinence INT, pourquoi TEXT,
  accroche TEXT, statut TEXT DEFAULT 'nouveau', dedupe TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS tendances_snap (
  date TEXT, site TEXT, categorie TEXT, page TEXT, tri TEXT, rang INT, pid TEXT, nom TEXT, prix REAL, en_stock INT);
CREATE INDEX IF NOT EXISTS ix_ts_date ON tendances_snap(date);
CREATE TABLE IF NOT EXISTS opportunites (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, agent TEXT, produit TEXT, categorie TEXT, canal TEXT,
  score INT, pourquoi TEXT, preuves TEXT, prix_marche REAL, analyse TEXT, statut TEXT DEFAULT 'nouveau', dedupe TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS bus_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, topic TEXT, agent TEXT, resume TEXT, payload TEXT,
  mock INT DEFAULT 0, dedupe TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS bus_handled (
  event_id INT, subscriber TEXT, ts TEXT, result TEXT, PRIMARY KEY (event_id, subscriber));
CREATE TABLE IF NOT EXISTS seo_changes (
  ts TEXT, run_id TEXT, kind TEXT, obj_id INT, field TEXT, old TEXT, new TEXT, rolled_back INT DEFAULT 0);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def conn():
    with _lock:
        c = sqlite3.connect(DB_PATH)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)


def get_state(key, default=None):
    with conn() as c:
        r = c.execute("SELECT v FROM state WHERE k=?", (key,)).fetchone()
    return json.loads(r["v"]) if r else default


def set_state(key, value):
    with conn() as c:
        c.execute("INSERT INTO state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                  (key, json.dumps(value, ensure_ascii=False)))


def add_alert(agent, level, title, body, dedupe_key=None):
    """Enregistre une alerte. Renvoie son id, ou None si la même alerte existe déjà (dédoublonnage)."""
    with conn() as c:
        try:
            cur = c.execute("INSERT INTO alerts(ts,agent,level,title,body,dedupe_key) VALUES(?,?,?,?,?,?)",
                            (now_iso(), agent, level, title, body, dedupe_key))
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None


def mark_sent(alert_id):
    with conn() as c:
        c.execute("UPDATE alerts SET sent=1 WHERE id=?", (alert_id,))


def recent_alerts(limit=30):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))]


def add_report(agent, title, body):
    with conn() as c:
        c.execute("INSERT INTO reports(ts,agent,title,body) VALUES(?,?,?,?)", (now_iso(), agent, title, body))


def recent_reports(limit=10):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM reports ORDER BY id DESC LIMIT ?", (limit,))]


def log_usage(agent, model, inp, out, cread, cwrite, cost):
    with conn() as c:
        c.execute("INSERT INTO llm_usage VALUES(?,?,?,?,?,?,?,?)", (now_iso(), agent, model, inp, out, cread, cwrite, cost))


def month_cost(month_prefix=None) -> float:
    month_prefix = month_prefix or datetime.now(timezone.utc).strftime("%Y-%m")
    with conn() as c:
        r = c.execute("SELECT COALESCE(SUM(cost_usd),0) s FROM llm_usage WHERE ts LIKE ?", (month_prefix + "%",)).fetchone()
    return float(r["s"])


def usage_by_agent(month_prefix=None):
    month_prefix = month_prefix or datetime.now(timezone.utc).strftime("%Y-%m")
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT agent, model, COUNT(*) appels, SUM(cost_usd) cout FROM llm_usage WHERE ts LIKE ? GROUP BY agent, model ORDER BY cout DESC",
            (month_prefix + "%",))]


def save_veille(date, source, items, segments):
    with conn() as c:
        c.execute("DELETE FROM veille_items WHERE date=? AND source=?", (date, source))
        c.executemany("INSERT INTO veille_items VALUES(?,?,?,?,?,?)",
                      [(date, source, i["cat"], i["nom"], i["prix"], int(i["en_stock"])) for i in items])
        c.execute("DELETE FROM veille_segments WHERE date=? AND source=?", (date, source))
        c.executemany("INSERT INTO veille_segments VALUES(?,?,?,?,?,?,?,?)",
                      [(date, source, s["type"], s["gamme"], s["modeles"], s["min"], s["median"], s["max"]) for s in segments])


def veille_dates(source="Tunisianet"):
    with conn() as c:
        return [r["date"] for r in c.execute("SELECT DISTINCT date FROM veille_segments WHERE source=? ORDER BY date", (source,))]


def veille_segments(date, source="Tunisianet"):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM veille_segments WHERE date=? AND source=? ORDER BY type, gamme", (date, source))]


def veille_history(source="Tunisianet", days=60):
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT date, type, gamme, prix_median, modeles FROM veille_segments WHERE source=? AND date >= date('now', ?) ORDER BY date",
            (source, f"-{days} days"))]


def veille_cheapest(date, source="Tunisianet", cat="P", n=10):
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT nom, prix FROM veille_items WHERE date=? AND source=? AND cat=? ORDER BY prix LIMIT ?", (date, source, cat, n))]


def save_seo_changes(run_id, kind, obj_id, changes):
    with conn() as c:
        c.executemany("INSERT INTO seo_changes(ts,run_id,kind,obj_id,field,old,new) VALUES(?,?,?,?,?,?,?)",
                      [(now_iso(), run_id, kind, obj_id, f, "" if o is None else str(o), str(n)) for f, o, n in changes])


def seo_changes(run_id):
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM seo_changes WHERE run_id=? AND rolled_back=0 ORDER BY rowid", (run_id,))]


def mark_seo_rolled_back(run_id):
    with conn() as c:
        c.execute("UPDATE seo_changes SET rolled_back=1 WHERE run_id=?", (run_id,))


def seo_runs(limit=10):
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT run_id, MIN(ts) ts, COUNT(DISTINCT kind||obj_id) objets, MAX(rolled_back) annule FROM seo_changes GROUP BY run_id ORDER BY ts DESC LIMIT ?",
            (limit,))]


def add_prospect(p: dict):
    """Ajoute un prospect ; renvoie son id, ou None s'il est déjà connu."""
    with conn() as c:
        try:
            cur = c.execute("""INSERT INTO prospects(ts,kind,segment,nom,type,ville,telephone,email,site,adresse,source_url,
                               pertinence,pourquoi,accroche,dedupe) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (now_iso(), p["kind"], p["segment"], p["nom"], p.get("type", ""), p.get("ville", ""),
                             p.get("telephone", ""), p.get("email", ""), p.get("site", ""), p.get("adresse", ""),
                             p["source_url"], int(p.get("pertinence") or 0), p.get("pourquoi", ""), p.get("accroche", ""),
                             p["dedupe"]))
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None


def prospects(kind=None, statut=None, limit=200):
    q, args = "SELECT * FROM prospects WHERE 1=1", []
    if kind:
        q += " AND kind=?"; args.append(kind)
    if statut:
        q += " AND statut=?"; args.append(statut)
    q += " ORDER BY id DESC LIMIT ?"; args.append(limit)
    with conn() as c:
        return [dict(r) for r in c.execute(q, args)]


def set_prospect_status(pid: int, statut: str) -> bool:
    with conn() as c:
        return c.execute("UPDATE prospects SET statut=? WHERE id=?", (statut, pid)).rowcount > 0


def known_prospect_names(kind):
    with conn() as c:
        return [r["nom"] for r in c.execute("SELECT nom FROM prospects WHERE kind=? ORDER BY id DESC LIMIT 300", (kind,))]


# --- Tendances concurrents & opportunités ---------------------------------

def save_tendances(day, rows):
    with conn() as c:
        c.execute("DELETE FROM tendances_snap WHERE date=?", (day,))
        c.executemany("INSERT INTO tendances_snap VALUES(?,?,?,?,?,?,?,?,?,?)",
                      [(day, r["site"], r["categorie"], r["page"], r["tri"], r["rang"], r.get("pid") or r["nom"],
                        r["nom"], r["prix"], int(bool(r.get("en_stock")))) for r in rows])


def tendances_dates(limit=30):
    with conn() as c:
        return [r[0] for r in c.execute("SELECT DISTINCT date FROM tendances_snap ORDER BY date DESC LIMIT ?", (limit,))]


def tendances_snapshot(day):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM tendances_snap WHERE date=? ORDER BY site, page, rang", (day,))]


def add_opportunite(o: dict):
    """Ajoute une opportunité ; si elle existe déjà (même produit), met à jour l'analyse. Renvoie l'id."""
    with conn() as c:
        row = c.execute("SELECT id FROM opportunites WHERE dedupe=?", (o["dedupe"],)).fetchone()
        if row:
            c.execute("UPDATE opportunites SET ts=?, score=?, pourquoi=?, preuves=?, prix_marche=COALESCE(?, prix_marche), "
                      "analyse=COALESCE(?, analyse), canal=? WHERE id=?",
                      (now_iso(), o.get("score", 0), o.get("pourquoi", ""), json.dumps(o.get("preuves", []), ensure_ascii=False),
                       o.get("prix_marche"), json.dumps(o["analyse"], ensure_ascii=False) if o.get("analyse") else None,
                       o.get("canal", ""), row["id"]))
            return row["id"]
        cur = c.execute("""INSERT INTO opportunites(ts,agent,produit,categorie,canal,score,pourquoi,preuves,prix_marche,analyse,statut,dedupe)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (now_iso(), o["agent"], o["produit"], o.get("categorie", "autre"), o.get("canal", ""), o.get("score", 0),
                         o.get("pourquoi", ""), json.dumps(o.get("preuves", []), ensure_ascii=False), o.get("prix_marche"),
                         json.dumps(o["analyse"], ensure_ascii=False) if o.get("analyse") else None,
                         o.get("statut", "nouveau"), o["dedupe"]))
        return cur.lastrowid


def opportunites(statut=None, limit=50):
    q, args = "SELECT * FROM opportunites WHERE 1=1", []
    if statut:
        q += " AND statut=?"; args.append(statut)
    q += " ORDER BY ts DESC LIMIT ?"; args.append(limit)
    with conn() as c:
        return [dict(r) for r in c.execute(q, args)]


def opportunite(oid: int):
    with conn() as c:
        r = c.execute("SELECT * FROM opportunites WHERE id=?", (oid,)).fetchone()
        return dict(r) if r else None


def set_opportunite_status(oid: int, statut: str) -> bool:
    with conn() as c:
        return c.execute("UPDATE opportunites SET statut=? WHERE id=?", (statut, oid)).rowcount > 0
