#!/usr/bin/env python3
"""Titres de presse en français sur les élections israéliennes -> news.json.

Les flux RSS des médias n'envoient pas d'en-tête CORS : un navigateur ne peut pas les lire. Ce script (lancé toutes les
~10 min par .github/workflows/news.yml) fait le relais et ne retient que quatre champs par article : titre, média, lien, date.
Aucun texte d'article n'est copié ; chaque titre renvoie vers l'article du média.

Sources :
  Google Actualités   recherche en français (élections israéliennes, Knesset…) : agrège la presse francophone
  Le Monde, France 24, RFI   flux « Moyen-Orient », gardés seulement si le titre parle d'Israël ET d'un scrutin

Robustesse : une source en panne ne retire rien (les articles déjà recueillis restent jusqu'à leur péremption) ; si aucune
source ne répond et qu'il n'y a rien en réserve, rien n'est écrit (code de sortie 1) : le dernier bon fichier reste publié.

Usage :
  fetch_news.py --out news.json [--prev news.json]
"""
import argparse
import html
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlparse

UA = "Mozilla/5.0 (compatible; israpoll/1.0; +https://github.com/eliejesuran/israpoll)"
MAX_BYTES = 5 * 1024 * 1024
MAX_AGE = timedelta(days=4)       # un titre plus vieux n'est plus de l'actualité du scrutin
MAX_ITEMS = 20
PER_SOURCE = 3                    # au plus 3 titres par média : pas de page tapissée par un seul direct
MAX_TITLE = 220

GOOGLE_QUERY = 'élections israéliennes OR "législatives en Israël" OR Knesset when:3d'
GOOGLE_URL = f"https://news.google.com/rss/search?q={quote(GOOGLE_QUERY)}&hl=fr&gl=FR&ceid=FR:fr"
# (nom du flux, URL, média imposé ou None = lu dans <source>, titre filtré par les deux listes de mots-clés)
FEEDS = [
    ("Google Actualités", GOOGLE_URL, None, False),
    ("Le Monde", "https://www.lemonde.fr/proche-orient/rss_full.xml", "Le Monde", True),
    ("France 24", "https://www.france24.com/fr/moyen-orient/rss", "France 24", True),
    ("RFI", "https://www.rfi.fr/fr/moyen-orient/rss", "RFI", True),
]
HOSTS = {"news.google.com", "www.lemonde.fr", "www.france24.com", "www.rfi.fr"}

# Google agrège tout et n'importe qui : on ne garde que la presse d'information généraliste (agences, audiovisuel public,
# quotidiens nationaux et régionaux, chaînes d'info). Ni sites d'opinion ou confessionnels, ni médias d'État étrangers.
# Pour ajouter un média : son nom tel qu'il apparaît dans Google Actualités (casse, accents et ponctuation ignorés).
MEDIA = {
    "AFP", "Reuters", "Le Monde", "Le Monde.fr", "Le Figaro", "Libération", "L'Express", "Le Point", "L'Obs", "Les Echos",
    "La Croix", "Le Parisien", "Le HuffPost", "Challenges", "Marianne", "Slate.fr", "Mediapart", "20 Minutes", "Ouest-France",
    "Sud Ouest", "Midi Libre", "La Dépêche", "Le Télégramme", "La Voix du Nord", "Le Dauphiné Libéré", "Courrier international",
    "France 24", "RFI", "franceinfo", "France Info", "France Inter", "France Culture", "TV5monde", "Euronews", "TF1 Info",
    "BFM", "BFMTV", "LCI", "i24NEWS", "RTBF", "RTBF Info", "La Libre.be", "La Libre", "Le Soir", "RTS", "Le Temps",
    "Le Devoir", "La Presse", "Radio-Canada", "ICI Radio-Canada", "Le Journal de Montréal",
}
ALIASES = {"Le Monde.fr": "Le Monde", "tv5monde": "TV5Monde", "BFM": "BFMTV", "France Info": "franceinfo"}   # un média, un seul nom
MEDIA_KEYS = None                 # clés repliées, calculées au premier usage

ISRAEL = re.compile(r"isra[eë]l|knesset|n[eé]tanyahou|netanyahu|eisenkot|eizenkot|likoud|likud|bennett|lapid|ben[ -]gvir|smotrich|liberman", re.I)
ELECTION = re.compile(r"[eé]lection|l[eé]gislative|scrutin|\bvot(?:e|er|ent|ants?)\b|\burnes?\b|d[eé]pouillement|knesset|coalition|majorit[eé]|sondage|participation", re.I)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- réseau
def get(url, timeout=20):
    """GET d'un flux RSS : hôtes de FEEDS uniquement (redirections comprises), taille bornée, XML sans entités déclarées."""
    if (urlparse(url).hostname or "") not in HOSTS:
        raise ValueError(f"hôte non autorisé : {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.5"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if (urlparse(r.geturl()).hostname or "") not in HOSTS:
            raise ValueError(f"redirection vers un hôte non autorisé : {r.geturl()}")
        raw = r.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("réponse trop volumineuse")
    if b"<!ENTITY" in raw[:4096]:                       # flux piégé (entités XML) : on n'y touche pas
        raise ValueError("flux refusé : entités XML déclarées")
    return raw


# ---------------------------------------------------------------- analyse (pure, testable)
def clean(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def fold(text):
    """Clé de comparaison : sans accents, minuscules, lettres et chiffres seulement."""
    text = unicodedata.normalize("NFKD", text)
    return re.sub(r"[^a-z0-9]+", "", "".join(c for c in text if not unicodedata.combining(c)).lower())


def allowed_media(source):
    global MEDIA_KEYS
    if MEDIA_KEYS is None:
        MEDIA_KEYS = {fold(m) for m in MEDIA}
    return fold(source) in MEDIA_KEYS


def safe_url(url):
    u = urlparse((url or "").strip())
    return u.geturl() if u.scheme == "https" and u.hostname and len(u.geturl()) <= 700 else ""


def parse_feed(raw, media=None):
    """Articles d'un flux RSS : [{title, source, url, published}] ; ValueError si ce n'est pas du RSS."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise ValueError(f"XML illisible : {e}")
    out = []
    for it in root.iter("item"):
        source = clean(media or it.findtext("source") or "")
        raw_source = source
        source = ALIASES.get(source, source)
        title = clean(it.findtext("title"))
        if raw_source and title.lower().endswith(" - " + raw_source.lower()):   # Google ajoute « - Média » à chaque titre
            title = title[: -len(raw_source) - 3].rstrip()
        url = safe_url(it.findtext("link"))
        try:
            when = parsedate_to_datetime(it.findtext("pubDate") or "")
            when = (when if when.tzinfo else when.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue                                                         # sans date fiable, impossible de le classer
        if title and url and source:
            out.append({"title": title[:MAX_TITLE], "source": source[:60], "url": url, "published": when.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return out


def relevant(title, strict):
    """Strict (flux généralistes) : Israël ET un mot de scrutin. Sinon la requête de recherche a déjà filtré : Israël suffit."""
    return bool(ISRAEL.search(title)) and (not strict or bool(ELECTION.search(title)))


def merge(batches, now, limit=MAX_ITEMS):
    """Fusionne, retire les doublons (même lien ou même titre) et les articles périmés ; le plus récent d'abord."""
    seen_url, seen_title, per_source, out = set(), set(), {}, []
    for it in sorted((i for b in batches for i in b), key=lambda i: i["published"], reverse=True):
        try:
            age = now - datetime.strptime(it["published"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        key = fold(it["title"])
        if age > MAX_AGE or age < timedelta(hours=-1) or it["url"] in seen_url or key in seen_title:
            continue                                                         # trop vieux, daté du futur, ou déjà vu
        src = fold(it["source"])
        if per_source.get(src, 0) >= PER_SOURCE:
            continue
        per_source[src] = per_source.get(src, 0) + 1
        seen_url.add(it["url"]); seen_title.add(key); out.append(it)
    return out[:limit]


def load_items(path):
    if not path:
        return []
    try:
        with open(path, encoding="utf-8") as f:
            items = json.load(f).get("items", [])
    except (OSError, ValueError, AttributeError):
        return []
    return [i for i in items if isinstance(i, dict) and all(isinstance(i.get(k), str) for k in ("title", "source", "url", "published")) and safe_url(i["url"])]


def collect(fetch=get, now=None):
    """Lit tous les flux ; renvoie (articles, journal par flux). `fetch` est injectable pour les tests."""
    now = now or datetime.now(timezone.utc)
    batches, log = [], {}
    for name, url, media, strict in FEEDS:
        try:
            items = [i for i in parse_feed(fetch(url), media) if allowed_media(i["source"]) and relevant(i["title"], strict)]
            batches.append(items)
            log[name] = f"ok ({len(items)})"
        except (urllib.error.URLError, OSError, ValueError) as e:
            log[name] = f"indisponible : {e}"
    return batches, log


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--prev", help="news.json précédent : ses articles encore récents sont conservés")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    batches, log = collect(now=now)
    items = merge(batches + [load_items(a.prev)], now)
    for k, v in log.items():
        print(f"[{now_iso()}] {k}: {v}", file=sys.stderr)
    if not items:
        print("aucun article : rien n'est écrit", file=sys.stderr)
        return 1
    body = {"schema": 1, "updated_at": now_iso(), "query": GOOGLE_QUERY, "feeds": log, "items": items}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{len(items)} articles, le plus récent : {items[0]['published']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
