"""Client minimal de l'API REST WooCommerce (authentification par mot de passe d'application WordPress)."""
import logging
from datetime import datetime, timedelta, timezone

import httpx

from .config import settings

log = logging.getLogger("dealz.woo")


class Woo:
    def __init__(self, base_url=None, user=None, app_password=None, client=None):
        self.base = (base_url or settings.woo_url).rstrip("/") + "/wp-json/wc/v3"
        self.http = client or httpx.Client(auth=(user or settings.woo_user, app_password or settings.woo_app_password),
                                           timeout=30, headers={"User-Agent": "Dealz-Agents/0.1"})

    def _req(self, method, path, **kw):
        r = self.http.request(method, f"{self.base}/{path.lstrip('/')}", **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"WooCommerce {method} {path} → {r.status_code} : {r.text[:300]}")
        return r

    def get(self, path, **params):
        return self._req("GET", path, params=params).json()

    def get_all(self, path, **params):
        params.setdefault("per_page", 100)
        page, out = 1, []
        while True:
            r = self._req("GET", path, params={**params, "page": page})
            data = r.json()
            out.extend(data)
            if page >= int(r.headers.get("X-WP-TotalPages", 1) or 1) or not data:
                return out
            page += 1

    def post(self, path, data):
        return self._req("POST", path, json=data).json()

    def put(self, path, data):
        return self._req("PUT", path, json=data).json()

    def delete(self, path, force=True):
        return self._req("DELETE", path, params={"force": str(force).lower()}).json()

    # Raccourcis métier
    def products(self, **params):
        return self.get_all("products", **params)

    def orders_since(self, dt: datetime, **params):
        return self.get_all("orders", after=dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"), **params)

    def orders_last_days(self, days: int):
        return self.orders_since(datetime.now(timezone.utc) - timedelta(days=days))


def meta(product: dict, key: str, default=None):
    for m in product.get("meta_data", []):
        if m.get("key") == key:
            return m.get("value")
    return default


def to_float(x, default=0.0):
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return default
