"""Tableau partagé entre agents.

Un agent PUBLIE un événement (sujet + résumé + données). Les liens (links.py) le LISENT et réagissent
avec des règles simples, sans IA sauf exception. Chaque réaction est notée : on voit sur /tableau
et sur le tableau de bord qui a fait quoi, à partir de quoi.

Sujets :
  signal_terrain   — capture ou texte envoyé avec /signal (groupes Facebook, boutique, client…)
  opportunite_go   — l'équipe a validé une opportunité (/opportunite 4 go)
  prix_concurrent  — un concurrent est nettement moins cher que nous (agent Veille)
  rupture_proche   — un produit qui se vend va manquer (agent Stock) — lien actif après lancement
  priorites        — les 3 priorités de la semaine (Stratège ou équipe)
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from . import db

log = logging.getLogger("dealz.bus")
TOPICS = ("signal_terrain", "opportunite_go", "prix_concurrent", "rupture_proche", "priorites")


def publish(topic: str, agent: str, resume: str, payload: dict = None, key: str = None, mock: bool = False):
    """Publie un événement. Renvoie son id, ou None si la même clé a déjà été publiée."""
    assert topic in TOPICS, topic
    with db.conn() as c:
        try:
            cur = c.execute("INSERT INTO bus_events(ts,topic,agent,resume,payload,mock,dedupe) VALUES(?,?,?,?,?,?,?)",
                            (db.now_iso(), topic, agent, resume[:300], json.dumps(payload or {}, ensure_ascii=False, default=str),
                             int(mock), key))
            return cur.lastrowid
        except Exception:  # clé déjà publiée
            return None


def _row(r):
    d = dict(r)
    d["payload"] = json.loads(d.get("payload") or "{}")
    return d


def events(topic=None, days=30, limit=100):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    q, args = "SELECT * FROM bus_events WHERE ts>=?", [since]
    if topic:
        q += " AND topic=?"; args.append(topic)
    q += " ORDER BY id DESC LIMIT ?"; args.append(limit)
    with db.conn() as c:
        return [_row(r) for r in c.execute(q, args)]


def reactions(event_id):
    with db.conn() as c:
        return [dict(r) for r in c.execute("SELECT subscriber, result, ts FROM bus_handled WHERE event_id=? ORDER BY ts", (event_id,))]


def pending(subscriber, topics, days=14):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    marks = ",".join("?" * len(topics))
    with db.conn() as c:
        return [_row(r) for r in c.execute(
            f"""SELECT * FROM bus_events e WHERE topic IN ({marks}) AND ts>=? AND NOT EXISTS
                (SELECT 1 FROM bus_handled h WHERE h.event_id=e.id AND h.subscriber=?) ORDER BY id""",
            (*topics, since, subscriber))]


def mark(event_id, subscriber, result):
    with db.conn() as c:
        c.execute("INSERT OR REPLACE INTO bus_handled VALUES(?,?,?,?)", (event_id, subscriber, db.now_iso(), str(result)[:300]))


def dispatch() -> int:
    """Fait réagir tous les liens aux événements qu'ils n'ont pas encore traités. Renvoie le nombre de réactions."""
    from .links import LINKS, sales_links_enabled
    n = 0
    for link in LINKS:
        for ev in pending(link["nom"], link["sujets"]):
            if link.get("apres_lancement") and not sales_links_enabled():
                mark(ev["id"], link["nom"], "en veille (LIENS_VENTES=0, s'active après le lancement)")
                continue
            try:
                res = link["reagir"](ev)
            except Exception as e:  # un lien en panne ne bloque pas les autres
                log.exception("lien %s", link["nom"])
                res = f"erreur : {e}"
            mark(ev["id"], link["nom"], res or "rien à faire")
            n += 1
    return n


def clear_mock():
    with db.conn() as c:
        ids = [r[0] for r in c.execute("SELECT id FROM bus_events WHERE mock=1")]
        c.executemany("DELETE FROM bus_handled WHERE event_id=?", [(i,) for i in ids])
        c.execute("DELETE FROM bus_events WHERE mock=1")
    return len(ids)
