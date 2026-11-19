"""Socle commun des agents : alertes dédoublonnées, rapports, accès boutique."""
import logging

from .. import db, telegram
from ..config import settings
from ..woo import Woo

_woo = None


def get_woo():
    """Client WooCommerce, ou None tant que l'accès n'est pas configuré."""
    global _woo
    if _woo is None and settings.woo_enabled:
        _woo = Woo()
    return _woo


def set_woo(client):  # utilisé par les tests
    global _woo
    _woo = client


class Agent:
    name = "agent"
    label = "Agent"
    model = None  # None = modèle rapide

    def __init__(self):
        self.log = logging.getLogger(f"dealz.{self.name}")

    def alert(self, level, title, body, key=None) -> bool:
        """Crée une alerte et l'envoie sur Telegram. Une même `key` n'est envoyée qu'une fois."""
        aid = db.add_alert(self.label, level, title, body, key)
        if aid is None:
            return False
        if telegram.send(telegram.format_alert(level, self.label, title, body)):
            db.mark_sent(aid)
        return True

    def report(self, title, body, notify=True):
        db.add_report(self.label, title, body)
        if notify:
            telegram.send(f"{telegram.ICON['rapport']} <b>{telegram.esc(title)}</b>\n\n{telegram.esc(body)}")

    def run(self):
        raise NotImplementedError

    def safe_run(self):
        try:
            return self.run()
        except Exception as e:
            self.log.exception("échec")
            self.alert("important", f"{self.label} : échec de l'exécution", str(e)[:500],
                       key=f"echec:{self.name}:{type(e).__name__}:{str(e)[:80]}")
            return None
