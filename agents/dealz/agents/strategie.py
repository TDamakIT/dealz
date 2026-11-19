"""Agent Stratège.

- Radar quotidien (modèle rapide) : cherche les signaux qui méritent une décision (ventes qui décrochent,
  temps fort proche sans stock, prix marché qui bougent) et n'alerte que s'il trouve quelque chose.
- Rapport hebdomadaire (modèle intelligent) : risques, 3 opportunités chiffrées, décisions proposées avec un responsable.
"""
import json

import re

from .. import bus, data, llm
from ..config import settings
from .base import Agent

CONTEXTE = """Dealz est une jeune boutique en ligne familiale tunisienne (entrepôt à Sfax, livraison dans les 24 gouvernorats).
Rayons : Papeterie & scolaire (fournisseur Office House, grossiste), Informatique & bureau (fournisseur Dartech), Maison & petit électroménager (pas encore de fournisseur).
Ventes aussi aux pros (écoles, crèches, entreprises) via devis. Paiement à la livraison dominant en Tunisie, ~30 % de refus estimés sur le marché.
Concurrents : Tunisianet, Mytek, Spacenet. Équipe : Tarek (tech, France), son frère (dev, France), leur sœur (opérations, Tunisie), le père (fournisseurs, réseau Sfax), conjointes en finance et comptabilité.
Temps fort majeur : rentrée scolaire (juillet-septembre)."""

RADAR = CONTEXTE + """
Tu es le radar quotidien. On te donne les chiffres du jour. Ta seule question : y a-t-il un signal qui demande une décision aujourd'hui ?
Si non, réponds exactement : RAS
Si oui, réponds en 3 lignes maximum : le signal, pourquoi il compte, l'action proposée et qui la porte. N'invente aucun chiffre."""

HEBDO = CONTEXTE + """
Tu es le stratège de Dealz. Utilise les outils pour lire les ventes, le stock, la veille et les temps forts, puis écris le rapport de la semaine en français :
### Ce qui s'est passé (3 lignes, chiffres à l'appui)
### Risques (2 maximum)
### Opportunités (3, classées par impact, avec un chiffrage même grossier et ce qu'il faut faire)
### Décisions proposées (responsable + échéance)
Sois direct, challenge l'équipe, ne flatte pas. Signale ce qui manque comme données. N'invente aucun chiffre."""


class StrategieAgent(Agent):
    name = "strategie"
    label = "Stratège"

    def radar(self):
        snap = {"ventes_7j": data.sales_summary(7), "ventes_28j": data.sales_summary(28),
                "stock": data.stock_summary(), "veille": data.veille_summary(), "temps_forts": data.upcoming_events(45)}
        text = llm.ask("strategie-radar", RADAR, json.dumps(snap, ensure_ascii=False, default=str), model=settings.model_smart, max_tokens=300)
        if getattr(text, "simulated", False) or text.strip().upper().startswith("RAS"):
            return None
        self.alert("opportunite", "Radar du Stratège", text, key=f"radar:{hash(text) & 0xffffffff}")
        return text

    def run(self):
        text = llm.ask("strategie-hebdo", HEBDO, "Rédige le rapport de la semaine.", model=settings.model_smart,
                       max_tokens=1800, tools=data.TOOLS, tool_impl=data.TOOL_IMPL, max_turns=8)
        if getattr(text, "simulated", False):
            text = (f"{text}\n\nChiffres bruts : {json.dumps(data.sales_summary(7), ensure_ascii=False, default=str)}\n"
                    f"Temps forts : {', '.join(e['nom'] + ' dans ' + str(e['dans_jours']) + ' j' for e in data.upcoming_events(60))}")
        self.report("Rapport hebdo du Stratège", text)
        if not getattr(text, "simulated", False):
            self.priorities(text)
        return text

    def priorities(self, rapport: str):
        """Tire du rapport les 3 priorités de la semaine et les publie sur le tableau partagé."""
        from ..links import set_priorities
        board = [{"sujet": e["topic"], "resume": e["resume"]} for e in bus.events(days=14, limit=40)]
        raw = llm.ask("strategie-priorites", PRIORITES, json.dumps({"rapport": rapport, "tableau": board}, ensure_ascii=False),
                      model=settings.model_fast, max_tokens=700)
        m = re.search(r"\[[\s\S]*\]", raw or "")
        try:
            items = json.loads(m.group(0)) if m else []
        except json.JSONDecodeError:
            items = []
        items = set_priorities(items, self.label)
        if items:
            from .. import telegram
            telegram.send("🎯 <b>Priorités de la semaine</b>\n" + "\n".join(
                f"{i + 1}. <b>{telegram.esc(p['titre'])}</b> — {telegram.esc(p.get('pourquoi', ''))} ({telegram.esc(p.get('responsable', '?'))})"
                for i, p in enumerate(items)) + "\n\nPour les changer : /priorites A ; B ; C")
        return items

PRIORITES = """À partir du rapport hebdo et du tableau partagé des agents, fixe AU PLUS 3 priorités pour la semaine de Dealz.
Chaque priorité est concrète et vérifiable dans 7 jours. Réponds UNIQUEMENT en JSON :
[{"titre": "verbe + objet, 8 mots max", "pourquoi": "1 phrase", "responsable": "Tarek|frère|sœur|père|équipe",
  "produits": ["..."], "segments_prospection": ["segment de recherche de fournisseurs ou de clients pros, ou vide"]}]"""
