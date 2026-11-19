"""Bot Telegram : commandes de l'équipe. Seuls les identifiants de TELEGRAM_CHAT_IDS sont écoutés."""
import logging
import re
import threading
import time

from . import data, db, llm, telegram
from .config import settings

log = logging.getLogger("dealz.bot")

AIDE = """<b>Dealz — commandes</b>
/rapport — rapport hebdo du Stratège maintenant
/radar — le Stratège cherche un signal à traiter aujourd'hui
/veille — relevé des prix concurrents maintenant
/stock — ruptures, stocks bas, marges
/commandes — vérifier les nouvelles commandes
/confirme 1043 — marquer la commande 1043 confirmée
/marketing — idées de publications de la semaine
/seo — l'agent SEO optimise les fiches maintenant
/seo_annuler abc123 — annuler un passage SEO
/prospection — chercher de nouveaux clients et fournisseurs maintenant
/prospects — les 10 dernières cibles (/prospects fournisseur pour les fournisseurs)
/prospect 12 contacte — changer le statut (nouveau, contacte, interesse, refus, client, partenaire)
/tendances — l'expert Tendances analyse ce qui se vend chez les concurrents
/opportunites — les opportunités en cours
/opportunite 4 go — statut (nouveau, a_etudier, chiffree, go, abandon)
/sourcing 4 — l'expert Sourcing chiffre l'import de l'opportunité 4 (ou /sourcing friteuse à air 5L 500)
/import 6.5 500 petit_electro 189 — calcul sans IA : prix FOB $, quantité, catégorie, prix de vente DT
/signal + capture d'écran (ou texte) — un signal du terrain : groupe Facebook, client, boutique…
/tableau — ce que les agents se sont transmis récemment
/priorites — les 3 priorités de la semaine (/priorites A ; B ; C pour les fixer vous-mêmes)
/budget — consommation IA du mois
/ask ta question — poser une question à l'assistant (il lit ventes, stock, veille)"""

ASK_SYSTEM = """Tu es l'assistant de l'équipe Dealz (boutique en ligne tunisienne, Sfax). Tu réponds en français, court et direct.
Utilise les outils pour lire les vraies données avant de répondre. Si une donnée manque, dis-le. N'invente aucun chiffre.
Challenge les idées faibles, propose une action concrète quand c'est utile."""


def handle(text: str, agents: dict, image=None) -> str:
    cmd, _, arg = text.strip().partition(" ")
    cmd = cmd.split("@")[0].lower()
    if cmd in ("/start", "/aide", "/help"):
        return AIDE
    if cmd == "/budget":
        used = db.month_cost()
        lines = [f"Ce mois : {used:.2f} $ sur {settings.budget_usd:.0f} $ ({'IA active' if llm.available() else 'mode simulation'})"]
        lines += [f"• {u['agent']} ({u['model']}) : {u['appels']} appels, {u['cout'] or 0:.3f} $" for u in db.usage_by_agent()]
        return telegram.esc("\n".join(lines))
    if cmd == "/confirme":
        from .agents.commandes import confirm_order
        return telegram.esc(confirm_order(arg.strip()) if arg.strip() else "Indique le numéro : /confirme 1043")
    if cmd == "/seo_annuler":
        from .agents.seo import rollback
        return telegram.esc(rollback(arg.strip()) if arg.strip() else "Indique le n° de passage : /seo_annuler abc123")
    if cmd == "/prospects":
        kind = "fournisseur" if arg.strip().startswith("fourn") else ("client" if arg.strip().startswith("client") else None)
        rows = db.prospects(kind=kind, limit=10)
        if not rows:
            return "Aucune cible pour l'instant. Lance /prospection."
        return "\n\n".join(f"#{r['id']} <b>{telegram.esc(r['nom'])}</b> ({telegram.esc(r['ville'])}) — {telegram.esc(r['statut'])}\n"
                           f"{telegram.esc(' · '.join(x for x in (r['telephone'], r['email'], r['site']) if x))}" for r in rows)
    if cmd == "/prospect":
        parts = arg.split()
        ok_status = {"nouveau", "contacte", "interesse", "refus", "client", "partenaire"}
        if len(parts) != 2 or not parts[0].isdigit() or parts[1] not in ok_status:
            return "Exemple : /prospect 12 contacte (statuts : " + ", ".join(sorted(ok_status)) + ")"
        return "Statut mis à jour ✅" if db.set_prospect_status(int(parts[0]), parts[1]) else "Cible introuvable."
    if cmd == "/opportunites":
        rows = db.opportunites(limit=12)
        if not rows:
            return "Aucune opportunité pour l'instant. Lance /tendances."
        return "\n\n".join(f"#{r['id']} {'★' * (r['score'] or 0)} <b>{telegram.esc(r['produit'])}</b> — {telegram.esc(r['canal'])} "
                           f"[{telegram.esc(r['statut'])}]" + (f" · marché ~{r['prix_marche']:.3f} DT" if r["prix_marche"] else "")
                           for r in rows)
    if cmd == "/opportunite":
        parts = arg.split()
        ok_status = {"nouveau", "a_etudier", "chiffree", "go", "abandon"}
        if len(parts) != 2 or not parts[0].isdigit() or parts[1] not in ok_status:
            return "Exemple : /opportunite 4 go (statuts : " + ", ".join(sorted(ok_status)) + ")"
        if parts[1] == "go":
            from .links import validate_go
            return telegram.esc(validate_go(int(parts[0])))
        return "Statut mis à jour ✅" if db.set_opportunite_status(int(parts[0]), parts[1]) else "Opportunité introuvable."
    if cmd == "/signal":
        from .agents.terrain import record
        if not arg.strip() and not image:
            return "Envoie une capture d'écran avec la légende /signal (ou /signal + texte)."
        eid, sig = record(arg, image)
        if not eid:
            return "Rien à enregistrer."
        from . import bus
        reac = "; ".join(r["result"] for r in bus.reactions(eid)) or "gardé pour l'analyse du mercredi"
        prix = f" · {sig['prix_affiche_tnd']:.0f} DT" if sig["prix_affiche_tnd"] else ""
        return telegram.esc(f"📡 Signal #{eid} : [{sig['type']}] {sig['produit']}{prix} · intérêt {sig['interet']}\n{sig['resume']}\n→ {reac}")
    if cmd == "/tableau":
        from . import bus
        evs = bus.events(days=14, limit=12)
        if not evs:
            return "Tableau vide pour l'instant."
        out = []
        for e in evs:
            reac = bus.reactions(e["id"])
            out.append(f"#{e['id']} <b>{telegram.esc(e['topic'])}</b> ({telegram.esc(e['agent'])}) : {telegram.esc(e['resume'])}"
                       + "".join(f"\n   ↳ {telegram.esc(r['subscriber'])} : {telegram.esc(r['result'])}" for r in reac))
        return "\n\n".join(out)
    if cmd == "/priorites":
        from .links import set_priorities
        if arg.strip():
            items = set_priorities([{"titre": t.strip()[:80], "pourquoi": "fixée par l'équipe", "responsable": "équipe"}
                                    for t in arg.split(";") if t.strip()], "Équipe")
            return "Priorités enregistrées ✅\n" + "\n".join(f"{i + 1}. {telegram.esc(p['titre'])}" for i, p in enumerate(items))
        pr = db.get_state("priorites") or {}
        if not pr.get("priorites"):
            return "Pas encore de priorités. Le Stratège les fixe le lundi, ou : /priorites A ; B ; C"
        return f"🎯 Priorités (par {telegram.esc(pr['par'])}, {telegram.esc(pr['ts'][:10])})\n" + "\n".join(
            f"{i + 1}. <b>{telegram.esc(p['titre'])}</b> — {telegram.esc(p.get('pourquoi', ''))}" for i, p in enumerate(pr["priorites"]))
    if cmd == "/import":
        from . import import_calc
        parts = arg.replace(",", ".").split()
        cats = import_calc.params()["categories"]
        try:
            fob, qte = float(parts[0]), int(parts[1])
            cat = parts[2] if len(parts) > 2 else "autre"
            pv = float(parts[3]) if len(parts) > 3 else None
            if cat not in cats:
                raise ValueError
        except (IndexError, ValueError):
            return telegram.esc("Exemple : /import 6.5 500 petit_electro 189\n(prix FOB en $, quantité, catégorie, prix de vente TTC en DT)\n"
                                "Catégories : " + ", ".join(cats))
        return telegram.esc(import_calc.format_calc(import_calc.landed_cost(fob, qte, cat, pv)))
    if cmd == "/sourcing":
        if not arg.strip():
            return "Exemple : /sourcing 4 (n° d'opportunité) ou /sourcing friteuse à air 5L 500"
        m = re.match(r"^(.*?)(?:\s+(\d{2,5}))?$", arg.strip())
        cible, qte = m.group(1), int(m.group(2) or 0)
        if cible.isdigit() and not qte and len(arg.split()) == 1:
            cible = arg.strip()
        threading.Thread(target=lambda: telegram.send(agents["sourcing"].study(cible, qte or 300)), daemon=True).start()
        return "C'est lancé (Expert Sourcing Chine). Compte 1 à 2 minutes."
    if cmd == "/ask":
        if not arg.strip():
            return "Écris ta question après /ask"
        ans = llm.ask("assistant", ASK_SYSTEM, arg, tools=data.TOOLS, tool_impl=data.TOOL_IMPL, max_tokens=900)
        return telegram.esc(ans)
    mapping = {"/rapport": ("strategie", "run"), "/radar": ("strategie", "radar"), "/veille": ("veille", "run"),
               "/stock": ("stock", "run"), "/commandes": ("commandes", "run"), "/marketing": ("marketing", "run"), "/seo": ("seo", "run"), "/prospection": ("prospection", "run"),
               "/tendances": ("tendances", "analyse")}
    if cmd in mapping:
        name, method = mapping[cmd]
        threading.Thread(target=_run_agent, args=(agents[name], method), daemon=True).start()
        return f"C'est lancé ({agents[name].label}). Le résultat arrive ici."
    return "Commande inconnue. /aide pour la liste."


def _run_agent(agent, method):
    try:
        res = getattr(agent, method)()
        if method == "radar" and not res:
            telegram.send("Radar : rien à signaler aujourd'hui.")
        if method == "run" and res is None and agent.name in ("stock", "commandes", "seo", "prospection"):
            telegram.send(f"{agent.label} : rien de nouveau (ou boutique non configurée).")
    except Exception as e:
        telegram.send(f"Erreur {agent.label} : {telegram.esc(e)}")


def poll_forever(agents: dict):
    if not settings.telegram_token:
        log.info("Bot Telegram désactivé (pas de TELEGRAM_BOT_TOKEN)")
        return
    offset = db.get_state("telegram_offset")
    allowed = set(settings.telegram_chat_ids)
    while True:
        try:
            for u in telegram.get_updates(offset):
                offset = u["update_id"] + 1
                db.set_state("telegram_offset", offset)
                msg = u.get("message") or {}
                cid = str(msg.get("chat", {}).get("id"))
                text = msg.get("text") or msg.get("caption") or ""
                if not text.startswith("/"):
                    continue
                if cid not in allowed:
                    log.warning("Message ignoré d'un chat non autorisé : %s", cid)
                    continue
                image = None
                if msg.get("photo") and text.split()[0].split("@")[0].lower() == "/signal":
                    image = telegram.download_photo(msg["photo"])
                telegram.send(handle(text, agents, image), chat_ids=[cid])
        except Exception as e:
            log.warning("Telegram : %s", e)
            time.sleep(10)
