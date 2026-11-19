"""Relevé des PC sur Tunisianet (pages catégories publiques).

Bonnes pratiques : un seul passage par jour, une pause entre chaque page, un User-Agent qui dit qui on est.
Avant un usage régulier, vérifier les conditions d'utilisation du site. Mytek n'est pas relevé :
il bloque les robots par une vérification anti-robot, qu'on ne contourne pas.
"""
import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from .config import settings

log = logging.getLogger("dealz.scraper")

SOURCE = "Tunisianet"
CATEGORIES = [
    ("P", "https://www.tunisianet.com.tn/301-pc-portable-tunisie"),
    ("G", "https://www.tunisianet.com.tn/682-pc-de-bureau-gamer"),
    ("T", "https://www.tunisianet.com.tn/686-pc-tout-en-un"),
    ("B", "https://www.tunisianet.com.tn/373-pc-de-bureau"),
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DealzVeilleBot/0.1; veille prix quotidienne)",
           "Accept-Language": "fr-FR,fr;q=0.9"}


def parse_price(txt: str):
    """'1 099,000 DT' → 1099.0"""
    if not txt:
        return None
    t = re.sub(r"[^\d,\.]", "", txt.replace("\xa0", "").replace(" ", ""))
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def parse_listing(html_text: str, cat: str):
    """Renvoie (articles, total_annoncé) pour une page de catégorie."""
    soup = BeautifulSoup(html_text, "html.parser")
    items = []
    for a in soup.select("article.product-miniature"):
        title = a.select_one(".product-title")
        price = a.select_one(".price")
        nom = re.sub(r"\s+", " ", title.get_text(" ", strip=True)) if title else None
        prix = parse_price(price.get_text(" ", strip=True)) if price else None
        if not nom or prix is None:
            continue
        txt = a.get_text(" ", strip=True)
        items.append({"id": a.get("data-id-product"), "cat": cat, "nom": nom, "prix": prix,
                      "en_stock": bool(re.search(r"En stock", txt, re.I))})
    m = re.search(r"Il y a (\d+) produits", soup.get_text(" ", strip=True))
    return items, (int(m.group(1)) if m else None)


def scrape(client: httpx.Client = None, max_pages=60):
    """Parcourt les catégories. Renvoie la liste des PC (dédoublonnés par identifiant produit)."""
    own = client is None
    client = client or httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True)
    seen, out = set(), []
    try:
        for cat, url in CATEGORIES:
            for page in range(1, max_pages + 1):
                r = client.get(url, params={"page": page})
                if r.status_code != 200:
                    log.warning("%s page %s → HTTP %s", url, page, r.status_code)
                    break
                items, _ = parse_listing(r.text, cat)
                if not items:
                    break
                for it in items:
                    key = it["id"] or it["nom"]
                    if key not in seen:
                        seen.add(key)
                        out.append(it)
                if len(items) < 24:
                    break
                time.sleep(settings.veille_delai)
    finally:
        if own:
            client.close()
    return out


# --- Tendances : meilleures ventes des concurrents ---------------------------
SALES_ORDER = "product.sales.desc"


def sales_sort_available(html_text: str) -> bool:
    """La boutique (PrestaShop) propose-t-elle le tri « Meilleures ventes » sur cette page ?"""
    return SALES_ORDER in (html_text or "")


def fetch_ranked(url: str, client: httpx.Client, cat: str = "", top: int = 24):
    """Première page d'une catégorie, triée par meilleures ventes si la boutique le permet.

    Renvoie (articles avec leur rang, tri) où tri vaut 'ventes' (vrai classement des ventes du site)
    ou 'defaut' (ordre du site : ne dit rien des ventes, seuls les passages en rupture comptent).
    """
    r = client.get(url)
    r.raise_for_status()
    tri, html_text = "defaut", r.text
    if sales_sort_available(html_text):
        time.sleep(settings.veille_delai)
        r2 = client.get(url, params={"order": SALES_ORDER})
        if r2.status_code == 200:
            tri, html_text = "ventes", r2.text
    items, _ = parse_listing(html_text, cat)
    for i, it in enumerate(items[:top], 1):
        it["rang"] = i
    return items[:top], tri


def new_client():
    return httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True)
