"""Classement des PC par type et gamme de processeur, et statistiques de prix."""
import re
from statistics import median

TYPES = {"P": "Portable", "B": "Bureau", "G": "Bureau gamer", "T": "Tout-en-un"}


def gamme(nom: str) -> str:
    n = nom.lower()
    if re.search(r"apple|macbook|imac", n):
        return "Apple"
    if re.search(r"celeron|\bn4\d{3}|\bn5\d{3}|\bn100|\bn150|\bn200|\bn95\b|pentium|athlon|3200g", n):
        return "Entrée"
    if re.search(r"\bi3[- ]|core 3|ryzen 3|ultra 3", n):
        return "i3 / Core 3 / Ryzen 3"
    if re.search(r"\bi5[- ]|core 5|ryzen 5|ultra 5|ryzen ai 5", n):
        return "i5 / Core 5 / Ultra 5 / Ryzen 5"
    if re.search(r"\bi7[- ]|core 7|ryzen 7|ultra 7|ryzen ai 7", n):
        return "i7 / Core 7 / Ultra 7 / Ryzen 7"
    if re.search(r"\bi9[- ]|ultra 9|ryzen 9|ryzen ai 9", n):
        return "i9 / Ultra 9 / Ryzen 9"
    return "Autre"


def is_gamer(nom: str) -> bool:
    return bool(re.search(r"rtx|gamer|gaming", nom, re.I))


def segment_key(item) -> tuple:
    t = TYPES.get(item["cat"], item["cat"])
    g = gamme(item["nom"])
    if item["cat"] == "P" and is_gamer(item["nom"]) and g not in ("Apple",):
        g += " gamer"
    return t, g


def aggregate(items):
    groups = {}
    for it in items:
        groups.setdefault(segment_key(it), []).append(it["prix"])
    out = []
    for (t, g), prices in sorted(groups.items()):
        out.append({"type": t, "gamme": g, "modeles": len(prices), "min": min(prices),
                    "median": float(median(prices)), "max": max(prices)})
    return out
