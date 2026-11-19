"""Agent Vente & commandes — toutes les 10 minutes, sans IA (règles seules, donc gratuit).

- Chaque nouvelle commande : alerte Telegram avec un score de risque et un lien WhatsApp prêt
  à envoyer au client pour confirmer (levier n°1 contre les colis refusés).
- Commande en paiement à la livraison non confirmée depuis plus de 24 h : relance.
- On marque une commande confirmée depuis Telegram avec /confirme <numéro>.
"""
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from .. import db
from ..woo import meta, to_float
from .base import Agent, get_woo

GOUV_LOIN = {"tataouine", "kebili", "kébili", "tozeur", "gafsa", "medenine", "médenine", "kasserine", "jendouba", "le kef", "siliana"}


def normalize_phone(p: str) -> str:
    d = re.sub(r"\D", "", p or "")
    if d.startswith("00"):
        d = d[2:]
    if len(d) == 8:
        d = "216" + d
    return d


def risk(order: dict, previous_orders_by_phone: int) -> tuple:
    """Score de 0 à 100 et raisons. Plus c'est haut, plus il faut confirmer avant d'envoyer."""
    score, why = 0, []
    total = to_float(order.get("total"))
    cod = order.get("payment_method") == "cod"
    phone = normalize_phone(order.get("billing", {}).get("phone", ""))
    city = (order.get("billing", {}).get("state") or order.get("billing", {}).get("city") or "").lower()
    if cod:
        score += 20; why.append("paiement à la livraison")
    if cod and total > 300:
        score += 25; why.append(f"gros montant ({total:.0f} DT)")
    if previous_orders_by_phone == 0:
        score += 20; why.append("premier achat")
    if not re.fullmatch(r"216[2-9]\d{7}", phone):
        score += 25; why.append("numéro de téléphone douteux")
    if any(g in city for g in GOUV_LOIN):
        score += 10; why.append("livraison lointaine")
    return min(score, 100), why


def confirmation_message(order: dict) -> str:
    first = (order.get("billing", {}).get("first_name") or "").strip() or "Bonjour"
    items = order.get("line_items", [])
    lines = "\n".join(f"• {li.get('quantity')} × {li.get('name')}" for li in items[:5])
    if len(items) > 5:
        lines += f"\n• … et {len(items) - 5} autre(s) article(s)"
    total = to_float(order.get("total"))
    pay = "à payer à la livraison" if order.get("payment_method") == "cod" else "déjà payé"
    return (f"Ahla {first} 👋\nMa3ak Dealz. Wsoltna commande mte3ek n°{order.get('number')} :\n\n{lines}\n\n"
            f"Total : {total:.3f} DT ({pay}).\nLivraison 48 à 72 h.\n\nAbe3thelna OK bech nconfirmiw, wala 9olelna chnowa nbadlou. Merci !")


def wa_link(order: dict) -> str:
    return f"https://wa.me/{normalize_phone(order.get('billing', {}).get('phone', ''))}?text={quote(confirmation_message(order))}"


class CommandesAgent(Agent):
    name = "commandes"
    label = "Vente & commandes"

    def run(self):
        woo = get_woo()
        if not woo:
            return None
        now = datetime.now(timezone.utc)
        last = db.get_state("commandes_last_check")
        since = datetime.fromisoformat(last) if last else now - timedelta(hours=2)
        new = woo.orders_since(since)
        recent = woo.orders_last_days(180)
        phones = {}
        for o in recent:
            ph = normalize_phone(o.get("billing", {}).get("phone", ""))
            phones.setdefault(ph, []).append(o["id"])

        for o in new:
            ph = normalize_phone(o.get("billing", {}).get("phone", ""))
            prev = len([i for i in phones.get(ph, []) if i != o["id"]])
            score, why = risk(o, prev)
            level = "important" if score >= 50 else "info"
            b = o.get("billing", {})
            body = (f"{b.get('first_name', '')} {b.get('last_name', '')} — {b.get('city', '')} {b.get('state', '')}\n"
                    f"Total : {to_float(o.get('total')):.3f} DT — {o.get('payment_method_title', '')}\n"
                    f"Risque : {score}/100 ({', '.join(why) or 'faible'})\n\n"
                    f"Confirmer sur WhatsApp : {wa_link(o)}\n"
                    f"Puis : /confirme {o.get('number')}")
            self.alert(level, f"Nouvelle commande n°{o.get('number')}", body, key=f"cmd-new:{o['id']}")

        # Relance des commandes non confirmées depuis 24 h
        for o in recent:
            if o.get("status") not in ("processing", "on-hold", "pending"):
                continue
            if meta(o, "_dealz_confirmee") == "oui":
                continue
            created = datetime.fromisoformat(o["date_created_gmt"]).replace(tzinfo=timezone.utc)
            if now - created > timedelta(hours=24):
                self.alert("important", f"Commande n°{o.get('number')} non confirmée depuis 24 h",
                           f"Rappeler le client ou l'annuler avant d'expédier.\nWhatsApp : {wa_link(o)}",
                           key=f"cmd-relance:{o['id']}")
        db.set_state("commandes_last_check", now.isoformat())
        return {"nouvelles": len(new)}


def confirm_order(number: str) -> str:
    woo = get_woo()
    if not woo:
        return "WooCommerce n'est pas configuré."
    found = woo.get("orders", search=str(number))
    order = next((o for o in found if str(o.get("number")) == str(number)), None)
    if not order:
        return f"Commande {number} introuvable."
    woo.put(f"orders/{order['id']}", {"meta_data": [{"key": "_dealz_confirmee", "value": "oui"}]})
    woo.post(f"orders/{order['id']}/notes", {"note": "Confirmée par le client sur WhatsApp (via Telegram).", "customer_note": False})
    return f"Commande {number} marquée confirmée ✅"
