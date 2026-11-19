"""Agent SEO — tous les jours à 03:00 (et à la demande avec /seo).

Il MODIFIE la boutique lui-même, dans un périmètre limité :
  - fiches produits : titre SEO, méta-description, mot-clé principal (champs Rank Math),
    description courte et description longue (français + arabe), texte alternatif des images ;
  - catégories : description.
Il ne touche JAMAIS : prix, stock, nom du produit, adresse (slug) des pages, statut de publication.

Sécurité :
  - chaque valeur remplacée est sauvegardée ; /seo_annuler <n° de passage> remet tout comme avant ;
  - au plus SEO_MAX_PAR_PASSAGE fiches par passage (10 par défaut) ;
  - les textes générés sont contrôlés (longueurs, aucun prix ni chiffre inventé) avant d'être appliqués ;
  - SEO_AUTO=0 : l'agent propose sans appliquer.
Sans clé Claude, il applique seulement des modèles simples (titre, méta-description, texte alternatif).
"""
import html
import json
import os
import re
import uuid

import httpx

from .. import db, llm
from ..config import settings
from ..woo import meta
from .base import Agent, get_woo

MAX_PAR_PASSAGE = int(os.getenv("SEO_MAX_PAR_PASSAGE", "10"))
AUTO = os.getenv("SEO_AUTO", "1") == "1"
MARQUE = "Dealz"

SYSTEM = f"""Tu es l'expert SEO e-commerce de {MARQUE}, boutique en ligne tunisienne (Sfax, livraison dans les 24 gouvernorats, paiement à la livraison).
Les clients cherchent sur Google en français ET en arabe/derja, souvent sur mobile, avec des requêtes comme « cahier 96 pages prix tunisie », « cartable roulettes tunisie », « clé usb 64go prix ».
Pour la fiche produit fournie, réponds UNIQUEMENT avec un objet JSON :
{{"focus_keyword": "requête principale en français, 2 à 5 mots, avec « tunisie » si naturel",
 "meta_title": "≤ 60 caractères, mot-clé au début, finit par | {MARQUE}",
 "meta_description": "120 à 155 caractères, bénéfice + livraison partout en Tunisie + paiement à la livraison, sans prix",
 "short_description_fr": "1 à 2 phrases, 200 caractères max",
 "short_description_ar": "1 phrase en arabe (registre simple, compréhensible en Tunisie)",
 "description_fr": "150 à 250 mots en HTML simple (<p>, <ul><li>, <h2>) : usage, pour qui (niveau scolaire, bureau…), points forts, conseils",
 "description_ar": "60 à 120 mots en HTML simple, en arabe",
 "image_alt": "≤ 110 caractères, décrit le produit"}}
Règles strictes : n'invente AUCUNE caractéristique technique, marque, dimension ou prix absente des données ; pas de superlatifs mensongers ; pas de chiffre qui n'est pas dans le nom du produit."""

CAT_SYSTEM = f"""Tu es l'expert SEO de {MARQUE} (boutique en ligne tunisienne). Écris la description d'une catégorie de produits :
80 à 150 mots en HTML simple (<p>), français puis une phrase en arabe, avec la requête principale (ex. « fournitures scolaires en Tunisie »),
les types de produits listés, la livraison partout en Tunisie et le paiement à la livraison. Aucun prix, aucune promesse inventée.
Réponds UNIQUEMENT avec le HTML."""


def _strip(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", html.unescape(s or "")).strip()


def _numbers(s: str) -> set:
    return set(re.findall(r"\d+(?:[.,]\d+)?", s or ""))


def audit_product(p: dict) -> dict:
    """Problèmes SEO d'une fiche, avec un score (plus il est haut, plus c'est urgent)."""
    issues = []
    if len(_strip(p.get("description"))) < 300:
        issues.append("description trop courte")
    if len(_strip(p.get("short_description"))) < 60:
        issues.append("description courte absente")
    if not meta(p, "rank_math_description"):
        issues.append("méta-description absente")
    if not meta(p, "rank_math_title"):
        issues.append("titre SEO absent")
    if not meta(p, "rank_math_focus_keyword"):
        issues.append("mot-clé principal absent")
    imgs = p.get("images") or []
    if not imgs:
        issues.append("pas de photo")
    elif any(not (i.get("alt") or "").strip() for i in imgs):
        issues.append("texte alternatif d'image manquant")
    if not re.search(r"[؀-ۿ]", (p.get("description") or "") + (p.get("short_description") or "")):
        issues.append("pas de texte en arabe")
    return {"id": p["id"], "nom": p["name"], "problemes": issues, "score": len(issues)}


def validate(gen: dict, product: dict) -> list:
    """Renvoie la liste des erreurs ; vide si le texte peut être appliqué."""
    err = []
    allowed = _numbers(product["name"]) | {"24", "48", "72"}
    if not gen.get("meta_title") or len(gen["meta_title"]) > 65:
        err.append("meta_title")
    if not gen.get("meta_description") or not (90 <= len(gen["meta_description"]) <= 165):
        err.append("meta_description")
    for k in ("description_fr", "description_ar", "short_description_fr", "meta_description", "meta_title"):
        txt = _strip(gen.get(k, ""))
        if re.search(r"\b(DT|TND|dinars?)\b|د\.ت", txt, re.I):
            err.append(f"{k}: prix")
        extra = _numbers(txt) - allowed
        if extra:
            err.append(f"{k}: chiffres non fournis {sorted(extra)[:3]}")
    if gen.get("description_fr") and len(_strip(gen["description_fr"]).split()) < 80:
        err.append("description_fr trop courte")
    if re.search(r"<\s*(script|iframe|style)", json.dumps(gen), re.I):
        err.append("html interdit")
    return err


def template(p: dict, cat: str) -> dict:
    """Version sans IA : seulement des champs sûrs."""
    name = p["name"]
    mt = f"{name} | {MARQUE}"
    if len(mt) > 60:
        mt = name[: 57 - len(MARQUE)].rstrip() + f"… | {MARQUE}"
    md = f"{name} : commandez en ligne chez {MARQUE}, livraison partout en Tunisie, paiement à la livraison."
    return {"focus_keyword": f"{name.lower()} tunisie"[:60], "meta_title": mt, "meta_description": md[:160], "image_alt": name[:110]}


class SeoAgent(Agent):
    name = "seo"
    label = "SEO"

    def run(self, auto: bool = AUTO):
        woo = get_woo()
        if not woo:
            return None
        run_id = uuid.uuid4().hex[:6]
        products = woo.products(status="publish")
        cats = {c["id"]: c for c in woo.get_all("products/categories", hide_empty=False)}
        audits = sorted((audit_product(p) for p in products), key=lambda a: -a["score"])
        todo = [a for a in audits if a["score"] > 0][:MAX_PAR_PASSAGE]
        by_id = {p["id"]: p for p in products}
        done, skipped = [], []
        for a in todo:
            p = by_id[a["id"]]
            cat = cats.get((p.get("categories") or [{}])[0].get("id"), {}).get("name", "")
            gen, mode = self._generate(p, cat)
            errors = validate(gen, p) if mode == "ia" else []
            if errors:
                skipped.append(f"{p['name']} ({', '.join(errors[:2])})")
                gen, mode = template(p, cat), "modele"
            if auto:
                self._apply_product(woo, p, gen, run_id)
            done.append(f"{p['name']} [{mode}]")

        cat_done = self._categories(woo, cats, run_id, auto)
        site = self.check_pages()
        remaining = sum(1 for a in audits if a["score"] > 0) - len(done)

        verb = "optimisée(s)" if auto else "proposée(s) (mode sans application)"
        body = f"{len(done)} fiche(s) {verb}, {cat_done} catégorie(s). Encore {max(remaining, 0)} fiche(s) à traiter."
        if done:
            body += "\n\n• " + "\n• ".join(done)
        if skipped:
            body += "\n\nTexte IA refusé par le contrôle (modèle simple appliqué à la place) :\n• " + "\n• ".join(skipped)
        if site:
            body += "\n\nPoints techniques à corriger à la main :\n• " + "\n• ".join(site)
        if auto and (done or cat_done):
            body += f"\n\nPour tout annuler : /seo_annuler {run_id}"
        self.report(f"SEO — passage {run_id}", body)
        db.set_state("seo_last_run", run_id)
        return {"run_id": run_id, "fiches": len(done), "categories": cat_done, "refus": len(skipped), "restant": max(remaining, 0)}

    # --- génération ---------------------------------------------------------
    def _generate(self, p, cat):
        if not llm.available():
            return template(p, cat), "modele"
        data = {"nom": p["name"], "categorie": cat, "description_actuelle": _strip(p.get("description"))[:600],
                "nom_arabe": meta(p, "_nom_ar", ""), "fournisseur": meta(p, "_fournisseur", "")}
        raw = llm.ask("seo", SYSTEM, json.dumps(data, ensure_ascii=False), max_tokens=1400)
        m = re.search(r"\{[\s\S]*\}", raw or "")
        try:
            return json.loads(m.group(0)), "ia"
        except Exception:
            return template(p, cat), "modele"

    # --- application avec sauvegarde -----------------------------------------
    def _apply_product(self, woo, p, gen, run_id):
        changes = []  # (champ, ancien, nouveau)
        upd = {"meta_data": []}
        for key, field in (("rank_math_title", "meta_title"), ("rank_math_description", "meta_description"),
                           ("rank_math_focus_keyword", "focus_keyword")):
            if gen.get(field):
                changes.append((f"meta:{key}", meta(p, key, ""), gen[field]))
                upd["meta_data"].append({"key": key, "value": gen[field]})
        if gen.get("short_description_fr"):
            new = f"<p>{html.escape(gen['short_description_fr'])}</p>"
            if gen.get("short_description_ar"):
                new += f"<p dir=\"rtl\">{html.escape(gen['short_description_ar'])}</p>"
            changes.append(("short_description", p.get("short_description", ""), new))
            upd["short_description"] = new
        if gen.get("description_fr"):
            new = gen["description_fr"] + (f'<div dir="rtl" lang="ar">{gen["description_ar"]}</div>' if gen.get("description_ar") else "")
            changes.append(("description", p.get("description", ""), new))
            upd["description"] = new
        if gen.get("image_alt") and p.get("images"):
            old = [{"id": i["id"], "alt": i.get("alt", "")} for i in p["images"]]
            new = [{"id": i["id"], "alt": i.get("alt") or gen["image_alt"]} for i in p["images"]]
            if old != new:
                changes.append(("images_alt", json.dumps(old), json.dumps(new)))
                upd["images"] = new
        if not upd["meta_data"]:
            upd.pop("meta_data")
        if len(upd) == 0:
            return
        db.save_seo_changes(run_id, "product", p["id"], changes)
        woo.put(f"products/{p['id']}", upd)

    def _categories(self, woo, cats, run_id, auto, limit=5):
        n = 0
        for c in cats.values():
            if n >= limit or c.get("count", 0) == 0 or len(_strip(c.get("description"))) >= 80:
                continue
            if llm.available():
                txt = llm.ask("seo", CAT_SYSTEM, f"Catégorie : {c['name']}", max_tokens=500).strip()
                if re.search(r"\b(DT|TND)\b|<\s*script", txt, re.I) or len(_strip(txt)) < 60:
                    continue
            else:
                txt = (f"<p>{html.escape(c['name'])} : commandez en ligne chez {MARQUE}. "
                       f"Livraison partout en Tunisie et paiement à la livraison.</p>")
            if auto:
                db.save_seo_changes(run_id, "category", c["id"], [("description", c.get("description", ""), txt)])
                woo.put(f"products/categories/{c['id']}", {"description": txt})
            n += 1
        return n

    # --- contrôles techniques des pages --------------------------------------
    def check_pages(self) -> list:
        out = []
        base = settings.woo_url
        try:
            with httpx.Client(timeout=20, follow_redirects=True, headers={"Host": settings.public_url.split("//")[-1]}) as c:
                home = c.get(base + "/")
                t = home.text
                if not re.search(r"<title>[^<]{10,}</title>", t):
                    out.append("page d'accueil : titre absent ou trop court")
                if 'name="description"' not in t:
                    out.append("page d'accueil : méta-description absente (Rank Math → Titres et métas)")
                if "hreflang" not in t:
                    out.append("pas de balises hreflang : la version arabe n'est pas encore déclarée (extension de traduction à installer)")
                r = c.get(base + "/robots.txt")
                if r.status_code != 200 or "Disallow: /" in r.text.replace("Disallow: /wp-admin", ""):
                    out.append("robots.txt bloque l'exploration : à vérifier avant la mise en ligne")
                sm = c.get(base + "/sitemap_index.xml")
                if sm.status_code != 200:
                    out.append("plan du site (sitemap) introuvable : activer le module Sitemap de Rank Math")
        except Exception as e:
            out.append(f"pages non vérifiables : {e}")
        return out


def rollback(run_id: str) -> str:
    woo = get_woo()
    if not woo:
        return "WooCommerce n'est pas configuré."
    rows = db.seo_changes(run_id)
    if not rows:
        return f"Aucune modification enregistrée pour le passage {run_id}."
    by_obj = {}
    for r in rows:
        by_obj.setdefault((r["kind"], r["obj_id"]), []).append(r)
    for (kind, oid), changes in by_obj.items():
        if kind == "category":
            woo.put(f"products/categories/{oid}", {"description": changes[0]["old"]})
            continue
        upd, metas = {}, []
        for ch in changes:
            if ch["field"].startswith("meta:"):
                metas.append({"key": ch["field"][5:], "value": ch["old"]})
            elif ch["field"] == "images_alt":
                upd["images"] = json.loads(ch["old"])
            else:
                upd[ch["field"]] = ch["old"]
        if metas:
            upd["meta_data"] = metas
        woo.put(f"products/{oid}", upd)
    db.mark_seo_rolled_back(run_id)
    return f"Passage {run_id} annulé : {len(by_obj)} fiche(s) ou catégorie(s) remises comme avant ✅"
