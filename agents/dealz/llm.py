"""Appels à Claude avec garde-fou de budget, cache de prompt et mode simulation.

- Sans ANTHROPIC_API_KEY, ou une fois le budget mensuel atteint, aucun appel n'est fait :
  la fonction renvoie un texte de simulation et les agents continuent avec leurs règles.
- Le coût est calculé à partir des tokens renvoyés par l'API et des tarifs ci-dessous.
"""
import json
import logging

from . import db
from .config import settings

log = logging.getLogger("dealz.llm")

# Tarifs en $ par million de tokens (vérifiés le 18/11/2026 : Haiku 5.5 sous 100k tokens, Sonnet 5.5).
PRICES = {
    "claude-haiku-5-5": {"in": 0.10, "out": 0.50, "cache_read": 0.01, "cache_write": 0.125},
    "claude-sonnet-5-5": {"in": 2.00, "out": 10.00, "cache_read": 0.10, "cache_write": 2.50},
    "claude-opus-5-5": {"in": 4.00, "out": 20.00, "cache_read": 0.20, "cache_write": 5.00},
}
DEFAULT_PRICE = {"in": 2.00, "out": 10.00, "cache_read": 0.20, "cache_write": 2.50}

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=settings.anthropic_key)
    return _client


WEB_SEARCH_PRICE = 0.01  # $ par recherche web (10 $ les 1 000)


def cost_of(model, usage) -> float:
    p = PRICES.get(model, DEFAULT_PRICE)
    stu = getattr(usage, "server_tool_use", None)
    searches = (getattr(stu, "web_search_requests", 0) or 0) if stu else 0
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    cr = getattr(usage, "cache_read_input_tokens", 0) or 0
    cw = getattr(usage, "cache_creation_input_tokens", 0) or 0
    return (inp * p["in"] + out * p["out"] + cr * p["cache_read"] + cw * p["cache_write"]) / 1_000_000 + searches * WEB_SEARCH_PRICE


def budget_left() -> float:
    return settings.budget_usd - db.month_cost()


def available() -> bool:
    return settings.llm_enabled and budget_left() > 0


class Simulated(str):
    """Texte renvoyé quand l'IA n'est pas appelée (pas de clé ou budget atteint)."""
    simulated = True


def ask(agent: str, system: str, user, model: str = None, max_tokens: int = 1200,
        tools: list = None, tool_impl: dict = None, images: list = None, max_turns: int = 6) -> str:
    """Envoie une demande à Claude et renvoie le texte final.

    - `user` : texte ou liste de blocs.
    - `tools`/`tool_impl` : outils que Claude peut appeler (définition + fonction Python).
    - `images` : liste de (media_type, base64) pour la lecture de photos.
    """
    model = model or settings.model_fast
    if not settings.llm_enabled:
        return Simulated(f"[simulation : pas de clé API, l'agent {agent} a utilisé ses règles seules]")
    if budget_left() <= 0:
        return Simulated(f"[simulation : budget IA du mois atteint ({settings.budget_usd:.0f} $)]")

    content = []
    for media_type, b64 in images or []:
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}})
    content.append({"type": "text", "text": user if isinstance(user, str) else json.dumps(user, ensure_ascii=False)})
    messages = [{"role": "user", "content": content}]
    system_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    client = _get_client()
    for _ in range(max_turns):
        kwargs = dict(model=model, max_tokens=max_tokens, system=system_blocks, messages=messages)
        if tools:
            kwargs["tools"] = tools
        resp = client.messages.create(**kwargs)
        cost = cost_of(model, resp.usage)
        db.log_usage(agent, model, resp.usage.input_tokens, resp.usage.output_tokens,
                     getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
                     getattr(resp.usage, "cache_creation_input_tokens", 0) or 0, cost)
        if resp.stop_reason == "pause_turn":  # outil serveur (recherche web) encore en cours : on relance
            messages.append({"role": "assistant", "content": resp.content})
            continue
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text").strip()
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for b in resp.content:
            if b.type != "tool_use":
                continue
            try:
                out = tool_impl[b.name](**(b.input or {}))
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": json.dumps(out, ensure_ascii=False, default=str)[:20000]})
            except Exception as e:  # l'erreur est renvoyée à Claude, qui peut corriger sa demande
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": f"Erreur : {e}", "is_error": True})
        messages.append({"role": "user", "content": results})
        if budget_left() <= 0:
            return Simulated("[arrêt : budget IA du mois atteint pendant la réponse]")
    return "Je n'ai pas pu terminer en un nombre raisonnable d'étapes."
