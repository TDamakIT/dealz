#!/usr/bin/env python3
"""Affiche les identifiants de discussion Telegram qui ont écrit à ton bot.

1. Crée le bot avec @BotFather sur Telegram, copie le jeton dans .env (TELEGRAM_BOT_TOKEN=...).
2. Envoie « /start » à ton bot (et dans le groupe famille si tu l'y as ajouté).
3. Lance : python3 scripts/telegram_chat_id.py
4. Copie les identifiants dans .env : TELEGRAM_CHAT_IDS=123456,-100987654
"""
import json
import pathlib
import urllib.request

env = {}
for line in pathlib.Path(__file__).resolve().parents[1].joinpath(".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
token = env.get("TELEGRAM_BOT_TOKEN")
if not token:
    raise SystemExit("TELEGRAM_BOT_TOKEN est vide dans .env")
with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20) as r:
    data = json.load(r)
seen = {}
for u in data.get("result", []):
    chat = (u.get("message") or u.get("my_chat_member") or {}).get("chat")
    if chat:
        seen[chat["id"]] = chat.get("title") or chat.get("username") or chat.get("first_name")
if not seen:
    print("Aucun message reçu. Envoie /start à ton bot puis relance ce script.")
for cid, name in seen.items():
    print(f"{cid}\t{name}")
