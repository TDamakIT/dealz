"""Point d'entrée : planificateur des agents + bot Telegram + API/tableau de bord."""
import logging
import threading

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler

from . import bot, bus, db, telegram, web
from .agents.commandes import CommandesAgent
from .agents.marketing import MarketingAgent
from .agents.prospection import ProspectionAgent
from .agents.seo import SeoAgent
from .agents.sourcing import SourcingAgent
from .agents.stock import StockAgent
from .agents.tendances import TendancesAgent
from .agents.strategie import StrategieAgent
from .agents.veille import VeilleAgent
from .config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("dealz")


def build_agents():
    return {a.name: a for a in (VeilleAgent(), StockAgent(), CommandesAgent(), StrategieAgent(), MarketingAgent(), SeoAgent(), ProspectionAgent(),
                                    TendancesAgent(), SourcingAgent())}


def schedule(agents):
    s = BackgroundScheduler(timezone=settings.tz)
    h, m = (int(x) for x in settings.veille_heure.split(":"))
    s.add_job(agents["veille"].safe_run, "cron", hour=h, minute=m, id="veille")                      # tous les jours 06:30
    s.add_job(agents["stock"].safe_run, "cron", hour=7, minute=15, id="stock")                       # tous les jours
    s.add_job(agents["commandes"].safe_run, "interval", minutes=10, id="commandes")                  # toutes les 10 min
    s.add_job(agents["strategie"].radar, "cron", hour=8, minute=0, id="radar")                       # tous les jours
    s.add_job(agents["strategie"].safe_run, "cron", day_of_week="mon", hour=8, minute=30, id="hebdo")  # lundi
    s.add_job(agents["marketing"].safe_run, "cron", day_of_week="sun", hour=18, minute=0, id="marketing")  # dimanche
    s.add_job(agents["prospection"].safe_run, "cron", hour=9, minute=0, id="prospection")          # tous les jours 09:00
    s.add_job(agents["seo"].safe_run, "cron", hour=3, minute=0, id="seo")                          # tous les jours 03:00
    s.add_job(agents["tendances"].safe_run, "cron", hour=6, minute=45, id="tendances")              # relevé quotidien, sans IA
    s.add_job(agents["tendances"].analyse, "cron", day_of_week="wed", hour=8, minute=30, id="tendances_hebdo")  # mercredi
    s.add_job(agents["sourcing"].safe_run, "cron", day_of_week="thu", hour=9, minute=30, id="sourcing")   # jeudi
    s.add_job(bus.dispatch, "interval", minutes=5, id="tableau")                                  # liens entre agents
    s.start()
    return s


def main():
    db.init()
    agents = build_agents()
    web.AGENTS.update(agents)
    schedule(agents)
    threading.Thread(target=bot.poll_forever, args=(agents,), daemon=True).start()
    telegram.send("✅ Agents Dealz démarrés. /aide pour les commandes.")
    log.info("IA : %s | WooCommerce : %s | Telegram : %s",
             "active" if settings.llm_enabled else "simulation", settings.woo_enabled, settings.telegram_enabled)
    uvicorn.run(web.app, host="0.0.0.0", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
