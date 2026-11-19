import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="dealz-test-")
_cat = ROOT.parent / "data" / "catalog.json"
os.environ["CATALOG_PATH"] = str(_cat if _cat.exists() else ROOT / "data" / "catalog.json")
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["AGENTS_API_TOKEN"] = "test-token"

from dealz import db  # noqa: E402

db.init()


class FakeWoo:
    """Boutique factice pour tester les agents sans WordPress."""

    def __init__(self, products=None, orders=None, categories=None):
        self._categories = categories or []
        self._products = products or []
        self._orders = orders or []
        self.calls = []

    def products(self, **params):
        st = params.get("status")
        return [p for p in self._products if st in (None, "any") or p.get("status", "publish") == st]

    def orders_since(self, dt, **params):
        return list(self._orders)

    def orders_last_days(self, days):
        return list(self._orders)

    def get_all(self, path, **params):
        if path == "products/categories":
            return self._categories
        return self.get(path, **params)

    def get(self, path, **params):
        self.calls.append(("GET", path, params))
        if path == "orders":
            return self._orders
        if path == "products":
            if "sku" in params:
                return [p for p in self._products if p.get("sku") == params["sku"]]
            return self._products
        return []

    def put(self, path, data):
        self.calls.append(("PUT", path, data))
        if path.startswith("products/categories/"):
            cid = int(path.rsplit("/", 1)[1])
            for cat in self._categories:
                if cat["id"] == cid:
                    cat.update(data)
            return {}
        if path.startswith("products/"):
            pid = int(path.rsplit("/", 1)[1])
            for p in self._products:
                if p["id"] == pid:
                    for k, v in data.items():
                        if k == "meta_data":
                            for m in v:
                                p.setdefault("meta_data", [])
                                p["meta_data"] = [x for x in p["meta_data"] if x["key"] != m["key"]] + [m]
                        else:
                            p[k] = v
        return {}

    def post(self, path, data):
        self.calls.append(("POST", path, data))
        if path == "products":
            p = {"id": 900 + len(self._products), **data}
            self._products.append(p)
            return p
        return {}
