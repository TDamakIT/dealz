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

    def upload_media(self, path, filename, mime="image/png"):
        """Envoie une image dans la médiathèque WordPress (API wp/v2). Renvoie l'élément créé."""
        root = self.base.rsplit("/wc/v3", 1)[0]
        with open(path, "rb") as f:
            r = self.http.post(f"{root}/wp/v2/media", content=f.read(),
                               headers={"Content-Disposition": f'attachment; filename="{filename}"', "Content-Type": mime})
        if r.status_code >= 400:
            raise RuntimeError(f"WordPress POST media → {r.status_code} : {r.text[:300]}")
        return r.json()

    def media_slugs(self, prefix):
        """{slug: id} de toutes les images dont le slug commence par prefix (une seule série d'appels)."""
        root = self.base.rsplit("/wc/v3", 1)[0]
        out, page = {}, 1
        while True:
            r = self.http.get(f"{root}/wp/v2/media", params={"search": prefix, "per_page": 100, "page": page, "orderby": "id", "order": "asc", "_fields": "id,slug"})
            if r.status_code != 200:
                break
            batch = r.json()
            out.update({m["slug"]: m["id"] for m in batch if m["slug"].startswith(prefix)})
            if len(batch) < 100:
                break
            page += 1
        return out

    def find_media(self, search):
        root = self.base.rsplit("/wc/v3", 1)[0]
        r = self.http.get(f"{root}/wp/v2/media", params={"search": search, "per_page": 20})
        return r.json() if r.status_code == 200 else []

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
