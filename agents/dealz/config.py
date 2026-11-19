"""Réglages lus dans les variables d'environnement (.env)."""
import os
from dataclasses import dataclass, field
from pathlib import Path


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", "./var")))
    catalog_path: Path = field(default_factory=lambda: Path(os.getenv("CATALOG_PATH", "../data/catalog.json")))
    tz: str = field(default_factory=lambda: os.getenv("TZ", "Africa/Tunis"))

    woo_url: str = field(default_factory=lambda: os.getenv("WOO_URL", "http://localhost:8080").rstrip("/"))
    woo_user: str = field(default_factory=lambda: os.getenv("WOO_USER", "admin"))
    woo_app_password: str = field(default_factory=lambda: os.getenv("WOO_APP_PASSWORD", ""))
    public_url: str = field(default_factory=lambda: os.getenv("WP_PUBLIC_URL", "http://localhost:8080").rstrip("/"))

    api_token: str = field(default_factory=lambda: os.getenv("AGENTS_API_TOKEN", ""))

    anthropic_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    budget_usd: float = field(default_factory=lambda: _f("LLM_BUDGET_USD", 20))
    model_fast: str = field(default_factory=lambda: os.getenv("MODEL_FAST", "claude-haiku-5-5"))
    model_smart: str = field(default_factory=lambda: os.getenv("MODEL_SMART", "claude-sonnet-5-5"))

    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_ids: list = field(default_factory=lambda: [c.strip() for c in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if c.strip()])

    veille_heure: str = field(default_factory=lambda: os.getenv("VEILLE_HEURE", "06:30"))
    veille_delai: float = field(default_factory=lambda: _f("VEILLE_DELAI_SECONDES", 1.5))
    seuil_prix_pct: float = field(default_factory=lambda: _f("SEUIL_PRIX_ALERTE_PCT", 8))
    seuil_marge_pct: float = field(default_factory=lambda: _f("SEUIL_MARGE_PCT", 25))
    seuil_stock_bas: int = field(default_factory=lambda: int(_f("SEUIL_STOCK_BAS", 20)))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_key)

    @property
    def woo_enabled(self) -> bool:
        return bool(self.woo_app_password)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat_ids)


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)

# Temps forts commerciaux (dates approximatives : Ramadan et Aïd dépendent de la lune, à confirmer chaque année)
TEMPS_FORTS = [
    {"nom": "Ramadan", "debut": "2027-02-08", "fin": "2027-03-09", "approx": True},
    {"nom": "Aïd el-Fitr", "debut": "2027-03-10", "fin": "2027-03-12", "approx": True},
    {"nom": "Aïd el-Adha", "debut": "2027-05-16", "fin": "2027-05-18", "approx": True},
    {"nom": "Soldes d'été", "debut": "2027-07-01", "fin": "2027-08-15", "approx": True},
    {"nom": "Rentrée scolaire", "debut": "2027-07-15", "fin": "2027-09-20", "approx": False},
    {"nom": "Black Friday", "debut": "2027-11-26", "fin": "2027-11-29", "approx": False},
    {"nom": "Fin d'année", "debut": "2027-12-01", "fin": "2027-12-31", "approx": False},
    {"nom": "Black Friday", "debut": "2026-11-27", "fin": "2026-11-30", "approx": False},
    {"nom": "Fin d'année", "debut": "2026-12-01", "fin": "2026-12-31", "approx": False},
]
