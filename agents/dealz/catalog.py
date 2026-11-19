"""Catalogue local (data/catalog.json) : source de l'import WooCommerce et repli de l'agent liste scolaire."""
import json
from functools import lru_cache

from .config import settings


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    with open(settings.catalog_path, encoding="utf-8") as f:
        return json.load(f)
