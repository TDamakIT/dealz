"""Envoi d'alertes et lecture des commandes du bot Telegram (API HTTP, sans bibliothèque dédiée)."""
import html
import logging

import httpx

from .config import settings

log = logging.getLogger("dealz.telegram")
API = "https://api.telegram.org/bot{token}/{method}"
ICON = {"critique": "🔴", "important": "🟠", "info": "🔵", "opportunite": "🟢", "rapport": "📋"}


def esc(s) -> str:
    return html.escape(str(s), quote=False)


def _call(method, **data):
    r = httpx.post(API.format(token=settings.telegram_token, method=method), json=data, timeout=40)
    r.raise_for_status()
    return r.json()


def send(text: str, chat_ids=None, html_mode=True) -> bool:
    """Envoie un message (découpé si > 4000 caractères). Renvoie False si Telegram n'est pas configuré."""
    if not settings.telegram_enabled:
        log.info("[telegram désactivé] %s", text[:200])
        return False
    ok = True
    for cid in chat_ids or settings.telegram_chat_ids:
        for i in range(0, len(text), 4000):
            try:
                _call("sendMessage", chat_id=cid, text=text[i:i + 4000],
                      parse_mode="HTML" if html_mode else None, disable_web_page_preview=True)
            except Exception as e:
                log.warning("Telegram : échec d'envoi à %s : %s", cid, e)
                ok = False
    return ok


def format_alert(level, agent, title, body) -> str:
    return f"{ICON.get(level, '•')} <b>{esc(title)}</b>\n<i>{esc(agent)}</i>\n\n{esc(body)}"


def get_updates(offset=None, timeout=30):
    data = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset is not None:
        data["offset"] = offset
    return _call("getUpdates", **data).get("result", [])


def download_photo(photos: list):
    """Télécharge la plus grande version d'une photo Telegram. Renvoie (media_type, base64) ou None."""
    import base64
    if not photos:
        return None
    file_id = max(photos, key=lambda ph: ph.get("file_size", 0))["file_id"]
    path = _call("getFile", file_id=file_id)["result"]["file_path"]
    r = httpx.get(f"https://api.telegram.org/file/bot{settings.telegram_token}/{path}", timeout=40)
    r.raise_for_status()
    if len(r.content) > 8 * 1024 * 1024:
        return None
    return ("image/png" if path.lower().endswith(".png") else "image/jpeg", base64.b64encode(r.content).decode())
