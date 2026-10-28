#!/usr/bin/env python3
"""Récupère les résultats officiels de la Commission électorale centrale (CEC) et les écrit en JSON.

Le site de la CEC n'envoie pas d'en-tête CORS : un navigateur ne peut donc pas le lire directement.
Ce script (lancé toutes les ~30 s par scripts/live.sh) fait le relais.

Sources, par ordre de priorité (même structure qu'en 2022, vérifiée sur les résultats 2022) :
  CSV  par commune  : https://media26.bechirot.gov.il/files/expc.csv   (somme = résultat national)
  HTML national     : https://votes26.bechirot.gov.il/nationalresults  (sièges attribués par la CEC)
  Participation     : live-blog de NBC News (relevés de la CEC, JSON-LD) ; data/manual.json prévaut pour une même heure
  Relais presse     : projection de The Petek (NON officiel) -> clé « press » de live.json
Le site de la CEC (CSV et HTML) n'est interrogé que si on le demande (--poll-cec) : il répond par un défi anti-bot.

Robustesse : un relevé incohérent (fichier tronqué, page d'erreur, total qui s'effondre) ou une panne réseau
ne remplace jamais les derniers bons chiffres ; ils sont conservés et signalés `stale` après 3 échecs de suite.

Défi anti-bot : le soir du scrutin la CEC a protégé ses fichiers (AWS WAF, HTTP 202 + `x-amzn-waf-action: challenge`).
On ne le contourne pas, et la lecture automatique du site est arrêtée par défaut. Avec --poll-cec le collecteur
s'identifie honnêtement et cesse d'insister (pause croissante de 45 s à 10 min). Sans elle, les chiffres de la CEC
viennent d'un humain : fichier téléchargé sur son site (--csv-file) ou totaux saisis dans manual.json ; ou d'un autre
collecteur qui publie des chiffres plus récents (--peer).

Usage :
  fetch_cec.py --out live.json [--manual manual.json] [--prev live.json] [--peer autre_live.json] [--poll-cec]
  fetch_cec.py --csv-file expc.csv ...                 # fichier téléchargé à la main depuis le site de la CEC
  fetch_cec.py --csv-url URL --html-url URL ...        # pour tester sur un autre scrutin
"""
import argparse
import csv
import hashlib
import html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

CSV_URL = "https://media26.bechirot.gov.il/files/expc.csv"
HTML_URL = "https://votes26.bechirot.gov.il/nationalresults"
# Participation : la CEC publie un relevé toutes les ~2 h sans flux lisible ; le live-blog de NBC News les cite avec
# heure et chiffre dans un JSON structuré (LiveBlogPosting), ~1 h 30 après l'heure de référence.
TURNOUT_URL = "https://www.nbcnews.com/world/israel/live-blog/israel-election-live-updates-netanyahu-eisenkot-voters-war-iran-gaza-rcna604979"
TURNOUT_HOSTS = {"www.nbcnews.com"}
TURNOUT_SOURCE = "CEC, relayé par NBC News"
# Relais presse (NON officiel), repli tant que la CEC bloque les lectures automatiques : The Petek, agrégateur indépendant
# qui reprend le dépouillement de la CEC (« relevé CEC de HH:MM ») et en tire une projection de sièges (Bader-Ofer).
# robots.txt : tout autorisé. Une requête toutes les ~3 min, en-tête honnête, jamais de défi contourné.
PRESS_URL = "https://www.thepetek.com/results"
PRESS_HOSTS = {"www.thepetek.com"}
PRESS_SOURCE = "The Petek"
PRESS_MAX_DROP = 0.02          # le relais corrige parfois son total de quelques milliers de voix ; une chute plus forte est écartée
PRESS_PARTIES = {       # nom affiché par la source (minuscules) -> identifiant de parti (PARTIES dans index.html)
    "yashar": "yashar", "b'yachad": "together", "beyachad": "together", "together": "together",
    "the democrats": "democrats", "democrats": "democrats", "yisrael beiteinu": "yb",
    "the joint list": "joint", "joint list": "joint", "ra'am": "raam", "raam": "raam",
    "likud": "likud", "otzma yehudit": "otzma", "shas": "shas", "united torah judaism": "utj",
    "religious zionism & zehut": "rzp", "religious zionism": "rzp", "noam": "noam",
    "the reservists and the economic party": "reservists", "reservists and the economic party": "reservists",
    "amcha israel": "amcha",
}
UA = "Mozilla/5.0 (compatible; israpoll/1.0; +https://github.com/eliejesuran/israpoll)"
META_COLS = {"סמל ועדה", "שם ישוב", "סמל ישוב", "בזב", "מצביעים", "פסולים", "כשרים"}
MAX_BYTES = 20 * 1024 * 1024
FAILS_BEFORE_STALE = 3          # ~90 s à raison d'un relevé toutes les 30 s
SUM_TOLERANCE = 0.005           # écart toléré entre la somme des listes et les bulletins valides
WAITING_MARK = "ממתינים לספירת הקולות"
# Lettres de vote des 38 listes de 2026 (en-tête du CSV officiel) ; sert à reconnaître les lignes du tableau HTML.
KNOWN_LETTERS = set(
    "אמת ב בד בי בקר ג ד די דרך ה ודם ז זך זץ ט י יק ך כן ל מחל ני נף נץ נקי נר עם פה צבי צדק צף ק קה קך קץ רץ רק שס".split()
)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- réseau
def allowed(url):
    return (urlparse(url).hostname or "").endswith(".bechirot.gov.il")


def allowed_turnout(url):
    return (urlparse(url).hostname or "") in TURNOUT_HOSTS


def allowed_press(url):
    return (urlparse(url).hostname or "") in PRESS_HOSTS


class Blocked(ValueError):
    """Le site répond par un défi anti-bot (JavaScript) : inutile de réessayer tout de suite."""


class _SameSiteOnly(urllib.request.HTTPRedirectHandler):
    def __init__(self, ok):
        self.ok = ok

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not self.ok(newurl):
            raise urllib.error.URLError(f"redirection vers un hôte non autorisé : {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SameSiteOnly(allowed))
_turnout_opener = urllib.request.build_opener(_SameSiteOnly(allowed_turnout))
_press_opener = urllib.request.build_opener(_SameSiteOnly(allowed_press))


def get(url, timeout, tries=3, ok=allowed, opener=_opener):
    """GET avec quelques essais : le site de la CEC répond parfois 202 + corps vide (filtre anti-bot) ou coupe
    la poignée de main TLS. Seuls les hôtes *.bechirot.gov.il sont autorisés (ou ceux de `ok`), redirections comprises."""
    if not ok(url):
        raise ValueError(f"hôte non autorisé : {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    last = None
    for i in range(tries):
        try:
            with opener.open(req, timeout=timeout) as r:
                raw = r.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError("réponse trop volumineuse")
                body = raw.decode("utf-8-sig", errors="replace")
                if r.status == 200 and body.strip():
                    return body
                if r.status == 202 and (r.headers.get("x-amzn-waf-action") == "challenge" or not body.strip()):
                    raise Blocked("défi anti-bot de la CEC (HTTP 202) : accès automatique refusé")
                last = ValueError(f"réponse vide (HTTP {r.status})")
        except Blocked:
            raise
        except (urllib.error.URLError, OSError, ValueError) as e:
            last = e
        if i < tries - 1:
            time.sleep(2)
    raise last


# ---------------------------------------------------------------- analyse
def to_int(s):
    s = re.sub(r"[^\d]", "", s or "")
    return int(s) if s else 0


def parse_csv(text):
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or "כשרים" not in rows[0]:
        raise ValueError("CSV inattendu (pas d'en-tête CEC)")
    head = rows[0]
    idx = {k: i for i, k in enumerate(head)}
    letters = [k for k in head if k not in META_COLS and k]
    body = [r for r in rows[1:] if len(r) >= len(head)]
    votes = {k: sum(to_int(r[idx[k]]) for r in body) for k in letters}
    totals = {
        "eligible": sum(to_int(r[idx["בזב"]]) for r in body),
        "voters": sum(to_int(r[idx["מצביעים"]]) for r in body),
        "invalid": sum(to_int(r[idx["פסולים"]]) for r in body),
        "valid": sum(to_int(r[idx["כשרים"]]) for r in body),
    }
    return votes, totals, len(body)


def cells(row_html):
    return [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.S)]


def parse_html(text, known=None):
    """Lit le tableau national de la CEC. Renvoie (voix, totaux, noms, sièges, message_d_attente).

    La mise en page de 2026 n'est pas la même qu'en 2022 : on reconnaît donc les lignes par leurs lettres de
    vote plutôt que par leur position, et on n'accepte des sièges que s'ils totalisent exactement 120.
    """
    known = set(known or KNOWN_LETTERS)
    text = re.sub(r"<(script|style).*?</\1>", "", text, flags=re.S)
    waiting = WAITING_MARK in text
    rows = [cells(r) for r in re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.S)]
    totals, names, seats, votes = None, {}, {}, {}
    for r in rows:
        if len(r) == 5 and all(re.fullmatch(r"[\d,]+", c or "x") for c in (r[0], r[1])) and r[2].endswith("%"):
            totals = {"eligible": to_int(r[0]), "voters": to_int(r[1]), "valid": to_int(r[3]), "invalid": to_int(r[4])}
            continue
        letters = next((c.strip() for c in r if c.strip() in known), None)
        if not letters:
            continue
        nums = [to_int(c) for c in r if re.fullmatch(r"[\d,]+", c.strip() or "x")]
        if len(nums) < 2:
            continue
        v = max(nums)
        small = [n for n in nums if n <= 120 and n != v]
        votes[letters] = v
        seats[letters] = small[0] if small else 0
        names[letters] = r[0]
    if sum(seats.values()) != 120:
        seats = {}
    if not votes and not waiting:
        raise ValueError("tableau national introuvable")
    return votes, totals, names, seats, waiting


# ---------------------------------------------------------------- participation
_LOCAL_TIME = re.compile(r"(?:as of|up to|until|by)\s+(?:(\d{1,2})(?::(\d{2}))?\s*([ap])\.m\.|(noon))(?:\s+today)?\s+local time", re.I)
_PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s?%")


def _nearest_pct(text, pos, span, skip=lambda m: False):
    """Le pourcentage le plus proche de `pos` (à moins de `span` signes), ou None."""
    best = None
    for m in _PCT.finditer(text):
        if skip(m) or abs(m.start() - pos) > span:
            continue
        if best is None or abs(m.start() - pos) < abs(best.start() - pos):
            best = m
    return float(best.group(1)) if best else None


def _is_delta(text, p):
    """« +9 % », « up 6 % », « 6 % increase », « 3 points » : un écart avec 2022, pas un niveau de participation."""
    return bool(re.search(r"(?:\bup|\bdown|\bby|\bplus|\+|\b(?:increase|rise|jump|gain) of)\s*$", text[max(0, p.start() - 16):p.start()], re.I)
                or re.match(r"\s*(?:increase|rise|jump|points?\b|pts?\b|higher|lower|up (?:from|on)|compared)", text[p.end():p.end() + 24], re.I))


def turnout_entry(update):
    """Une entrée du live-blog -> {time, pct, prev2022, auto} si elle annonce un relevé de la CEC, sinon None."""
    raw = f"{update.get('headline') or ''}. {update.get('articleBody') or ''}"
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    m = _LOCAL_TIME.search(text)
    if not m or "Central Elections Committee" not in text or not re.search(r"turnout|cast (?:their )?ballots", text, re.I):
        return None                                   # pas un relevé de participation (ex. avancement du dépouillement)
    hour = 12 if m.group(4) else int(m.group(1)) % 12 + (12 if m.group(3).lower() == "p" else 0)
    minute = int(m.group(2) or 0)
    pct = _nearest_pct(text, m.start(), 90, skip=lambda p: _is_delta(text, p))
    if pct is None or not (7 <= hour <= 22) or not (0 < pct <= 100):
        return None
    # « 2022 » : le pourcentage cité à côté (hors écarts, hors armée : « 48 % chez les soldats »)
    year = re.search(r"\b2022\b|last election", text)
    prev = None
    if year:
        def not_prev(p):
            return float(p.group(1)) == pct or _is_delta(text, p) or re.search(r"IDF|Defense Forces|service members", text[max(0, p.start() - 60):p.start()])
        prev = _nearest_pct(text, year.start(), 60, skip=not_prev)
    return {"time": f"{hour:02d}:{minute:02d}", "pct": pct, "prev2022": prev, "source": TURNOUT_SOURCE, "url": TURNOUT_URL, "auto": True}


def parse_turnout(page):
    """Relevés de participation du live-blog (JSON-LD LiveBlogPosting), un par heure, triés. ValueError si la page n'en est pas un."""
    rows, seen_blog = {}, False
    for block in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, flags=re.S):
        try:
            doc = json.loads(block)
        except ValueError:
            continue
        for x in doc if isinstance(doc, list) else [doc]:
            if isinstance(x, dict) and x.get("@type") == "LiveBlogPosting":
                seen_blog = True
                for u in x.get("liveBlogUpdate") or []:
                    if isinstance(u, dict) and (r := turnout_entry(u)):
                        rows.setdefault(r["time"], r)       # le plus récent d'abord dans le flux : on garde le plus récent
    if not seen_blog:
        raise ValueError("live-blog introuvable (structure de la page changée ?)")
    return sorted(rows.values(), key=lambda r: r["time"])


def merge_turnout(manual_rows, auto_rows):
    """Relevés saisis à la main + relevés du relais. Pour une même heure la saisie à la main prévaut ; la participation
    cumulée ne peut que croître : un relevé du relais qui recule est écarté (jamais un relevé saisi à la main)."""
    manual_rows = [r for r in manual_rows or [] if isinstance(r, dict)]
    by_time = {r["time"]: r for r in manual_rows if r.get("auto") and r.get("time")}
    by_time.update({r["time"]: r for r in auto_rows if r.get("time")})
    hand = {str(r.get("time")): r for r in manual_rows if not r.get("auto")}
    out, top = [], 0.0
    for t in sorted(set(hand) | set(by_time)):
        r = hand.get(t) or by_time[t]
        try:
            pct = float(r["pct"])
        except (KeyError, TypeError, ValueError):
            continue
        if not r.get("auto") or pct >= top:
            out.append(r)
            top = max(top, pct)
    return out


# ---------------------------------------------------------------- relais presse (non officiel)
def parse_press(page):
    """Projection de The Petek -> {source, url, as_of, counted_pct, valid, stations, seats{id: n}, fetched_at}.

    Texte de la page : « With 76.89% of ballots counted at 10:58, … », « Projected seats from the count so far, by
    party : Yashar 20, B'Yachad 11, … . », « valid votes counted 4,006,695 », « polling stations counted 9,224 ».
    Strict : liste inconnue, sièges ≠ 120 ou pourcentage absurde -> ValueError (mieux vaut ne rien montrer qu'un faux chiffre).
    """
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text)).replace("\u2019", "'")
    text = re.sub(r"\s+", " ", text)
    m = re.search(r"With (\d{1,3}(?:\.\d+)?)% of ballots counted at (\d{1,2}):(\d{2})", text)
    block = re.search(r"Projected seats from the count so far, by party\s*:\s*(.+?)\s\.(?:\s|$)", text)
    valid = re.search(r"valid votes counted\s*([\d,]+)", text)
    if not (m and block and valid):
        raise ValueError("relevé du relais introuvable (structure de la page changée ?)")
    pct = float(m.group(1))
    seats = {}
    for item in block.group(1).split(","):
        im = re.fullmatch(r"\s*(.+?)\s+(\d{1,3})\s*", item)
        if not im:
            raise ValueError(f"entrée illisible dans la projection : {item.strip()!r}")
        pid = PRESS_PARTIES.get(im.group(1).strip().lower())
        if pid is None:
            raise ValueError(f"liste inconnue dans la projection : {im.group(1).strip()!r}")
        seats[pid] = seats.get(pid, 0) + int(im.group(2))
    stations = re.search(r"polling stations counted\s*([\d,]+)", text)
    if sum(seats.values()) != 120 or not (0 < pct <= 100) or not to_int(valid.group(1)):
        raise ValueError("projection incohérente (120 sièges, pourcentage et bulletins attendus)")
    return {"source": PRESS_SOURCE, "url": PRESS_URL, "as_of": f"{int(m.group(2)):02d}:{m.group(3)}", "counted_pct": pct,
            "valid": to_int(valid.group(1)), "stations": to_int(stations.group(1)) if stations else None,
            "seats": seats, "fetched_at": now_iso()}


# ---------------------------------------------------------------- saisie de secours
# Identifiant de parti (PARTIES dans index.html ; un test garde les deux tables identiques) -> lettre de vote de la CEC.
PARTY_LETTERS = {
    "democrats": "אמת", "together": "רק", "yashar": "דרך", "yb": "ל", "reservists": "די", "joint": "ודם", "raam": "עם", "amcha": "ך",
    "haredi": "זך", "noam": "ני", "rzp": "ט", "otzma": "ב", "utj": "ג", "shas": "שס", "likud": "מחל",
}


def parse_manual_cec(m):
    """Totaux nationaux de la CEC saisis à la main (data/manual.json, clé « cec ») quand le collecteur est bloqué par le
    défi anti-bot du site. Renvoie {votes, totals, rows, as_of, url} ; ValueError au moindre doute (faute de frappe,
    liste inconnue, total incohérent) : mieux vaut ne rien publier qu'un chiffre faux.

    m = {"as_of": "23:40", "url": "...", "totals": {"eligible": n, "voters": n, "valid": n, "invalid": n (facultatif)},
         "votes": {"likud": n, "yashar": n, ...}}   (clés : identifiants de parti, ou lettres de vote pour les petites listes)
    """
    if not isinstance(m, dict) or not isinstance(m.get("votes"), dict) or not isinstance(m.get("totals"), dict):
        raise ValueError("saisie « cec » incomplète (totals et votes attendus)")

    def count(v, what):
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise ValueError(f"{what} : entier positif attendu, pas {v!r}")
        return v

    votes = {}
    for key, v in m["votes"].items():
        letters = PARTY_LETTERS.get(key, key)
        if letters not in KNOWN_LETTERS:
            raise ValueError(f"liste inconnue : {key!r}")
        if letters in votes:
            raise ValueError(f"liste saisie deux fois : {key!r}")
        votes[letters] = count(v, key)
    t = m["totals"]
    valid, voters, eligible = count(t.get("valid"), "valid"), count(t.get("voters"), "voters"), count(t.get("eligible"), "eligible")
    invalid = count(t["invalid"], "invalid") if t.get("invalid") is not None else voters - valid
    if not valid or voters < valid or abs(voters - valid - invalid) > max(5, 0.001 * voters) or eligible < voters:
        raise ValueError("totaux incohérents (électeurs ≥ votants ≥ bulletins valides, votants = valides + nuls)")
    listed = sum(votes.values())
    if listed > valid * (1 + SUM_TOLERANCE) or listed < 0.85 * valid:
        raise ValueError(f"somme des listes saisies ({listed}) incompatible avec les bulletins valides ({valid})")
    return {"votes": votes, "totals": {"eligible": eligible, "voters": voters, "invalid": invalid, "valid": valid},
            "rows": 0, "as_of": str(m.get("as_of") or "")[:20], "url": str(m.get("url") or HTML_URL)}


# ---------------------------------------------------------------- cohérence
def sane(votes, totals, prev_totals):
    """Un relevé n'est accepté que s'il est cohérent avec lui-même et avec le précédent.

    Renvoie (ok, raison). Un fichier vide avant le dépouillement est légitime ; un fichier qui redevient vide
    ou perd plus de 10 % des bulletins valides en cours de route ne l'est pas (fichier tronqué, page d'erreur).
    """
    valid = totals["valid"]
    pv = (prev_totals or {}).get("valid", 0)
    if pv and valid < 0.9 * pv:
        return False, f"bulletins valides en chute ({pv} -> {valid})"
    if valid <= 0:
        return True, ""
    if abs(sum(votes.values()) - valid) > max(5, SUM_TOLERANCE * valid):
        return False, f"somme des listes ({sum(votes.values())}) ≠ bulletins valides ({valid})"
    if totals["voters"] < valid:
        return False, "moins de votants que de bulletins valides"
    return True, ""


def seats_match_votes(html_votes, csv_totals):
    """Les sièges lus sur la page HTML ne servent que si la page est à peu près au même stade que le CSV."""
    if not csv_totals or not csv_totals["valid"]:
        return True
    return abs(sum(html_votes.values()) - csv_totals["valid"]) <= 0.1 * csv_totals["valid"]


def load_json(path):
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- assemblage (pur, testable)
def build(prev, manual, csv_res, html_res, log, polled=True):
    """prev : dernier live.json ; csv_res / html_res : dict ou None (échec) ; polled : le site de la CEC a-t-il été interrogé ?
    Renvoie le nouveau dict (sans digest)."""
    prev = prev or {}
    fails = int(prev.get("fails", 0))
    votes = totals = None
    n_rows = 0
    suspect = False

    if csv_res:
        ok, why = sane(csv_res["votes"], csv_res["totals"], prev.get("totals"))
        if ok:
            votes, totals, n_rows, fails = csv_res["votes"], csv_res["totals"], csv_res["rows"], 0
        else:
            fails += 1
            log["csv"] = f"relevé rejeté : {why} (échec {fails})"
            if fails >= FAILS_BEFORE_STALE:        # une vraie correction de la CEC finit par passer
                votes, totals, n_rows, suspect = csv_res["votes"], csv_res["totals"], csv_res["rows"], True
    elif polled:
        fails += 1
    else:
        fails = 0                                  # site non interrogé : pas d'échec à signaler, les derniers chiffres restent

    fresh_valid = totals["valid"] if votes is not None and totals else 0     # ce que le flux automatique vient de donner

    # repli : derniers bons chiffres
    stale = False
    if votes is None and prev.get("votes") and prev.get("totals"):
        votes, totals = prev["votes"], prev["totals"]
        stale = fails >= FAILS_BEFORE_STALE

    names, seats, waiting = prev.get("names", {}), prev.get("official_seats") or {}, bool(prev.get("cec_waiting"))
    if html_res is not None:
        waiting = html_res["waiting"]
        names = html_res["names"] or names
        if html_res["seats"] and seats_match_votes(html_res["votes"], totals):
            seats = html_res["seats"]
        elif not html_res["seats"]:
            seats = {}
        if votes is None and html_res["votes"] and html_res["totals"] and html_res["totals"]["valid"] > 0:
            votes, totals = html_res["votes"], html_res["totals"]
            fresh_valid = totals["valid"]

    # saisie de secours (le site de la CEC filtre les scripts) : prise si elle est plus avancée que le flux automatique,
    # et jamais plus ancienne que le dernier relevé — sauf pour corriger une saisie précédente
    manual_cec = None
    if manual.get("cec"):
        try:
            m = parse_manual_cec(manual["cec"])
            prev_valid = (prev.get("totals") or {}).get("valid", 0)
            from_manual = bool((prev.get("source") or {}).get("manual_cec"))
            if m["totals"]["valid"] <= fresh_valid:
                log["cec_manual"] = "ignorée : le flux automatique est plus avancé"
            elif m["totals"]["valid"] < prev_valid and not from_manual:
                log["cec_manual"] = f"ignorée : antérieure au dernier relevé ({m['totals']['valid']} < {prev_valid} bulletins valides)"
            else:
                votes, totals, n_rows, stale = m["votes"], m["totals"], 0, False
                manual_cec = {"as_of": m["as_of"], "url": m["url"]}
                log["cec_manual"] = f"utilisée ({m['totals']['valid']} bulletins valides, relevé de {m['as_of'] or '?'})"
        except (ValueError, TypeError) as e:
            log["cec_manual"] = f"rejetée : {e}"

    has_votes = bool(votes) and bool(totals) and totals["valid"] > 0
    official = bool(seats) and sum(seats.values()) == 120 and has_votes
    if not has_votes:
        status, votes, totals = "waiting", None, None
    elif manual.get("final"):
        status = "final"
    else:
        status = "counting"

    return {
        "schema": 1,
        "status": status,
        "stale": stale,
        "suspect": suspect,
        "source": {
            "name": "Commission électorale centrale d'Israël (ועדת הבחירות המרכזית)",
            "page": HTML_URL,
            "csv": CSV_URL,
            "fetch": log,
            "rows": n_rows,
            "manual_cec": manual_cec,        # non nul : les voix viennent d'une saisie à la main d'après le site de la CEC
        },
        "totals": totals,
        "votes": votes,
        "names": names,
        "official_seats": seats if official else None,
        "cec_waiting": waiting,
        "manual": manual,
        "fails": fails,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--manual")
    ap.add_argument("--prev")
    ap.add_argument("--csv-url", default=CSV_URL)
    ap.add_argument("--html-url", default=HTML_URL)
    ap.add_argument("--turnout-url", default=TURNOUT_URL)
    ap.add_argument("--press-url", default=PRESS_URL)
    ap.add_argument("--poll-cec", action="store_true",
                    help="interroge le site de la CEC (CSV + HTML), arrêté par défaut : il répond par un défi anti-bot")
    ap.add_argument("--csv-file", help="fichier expc.csv téléchargé à la main sur le site de la CEC (remplace la lecture réseau)")
    ap.add_argument("--peer", help="live.json publié par un autre collecteur : adopté s'il a des chiffres plus avancés que les nôtres")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--skip-html", action="store_true", help="ne lit que le CSV (reprend les sièges et la participation du --prev)")
    a = ap.parse_args()

    prev = load_json(a.prev) or {}
    manual = load_json(a.manual)
    log = {}
    if manual is None:                      # fichier absent ou JSON cassé : on garde la dernière version valide
        manual = prev.get("manual") or {}
        log["manual"] = "illisible : dernière version valide conservée" if a.manual else "absent"

    me = os.environ.get("COLLECTOR_ID", "local")
    now = time.time()
    blk = prev.get("blocked") or {}
    strikes, until = int(blk.get("strikes", 0)), float(blk.get("until", 0))
    polling = a.poll_cec and not a.csv_file
    if not polling:
        strikes, until = 0, 0
    blocked_now = False

    csv_res = html_res = None
    paused = polling and until > now
    if a.csv_file:
        try:
            with open(a.csv_file, encoding="utf-8-sig") as f:
                votes, totals, rows = parse_csv(f.read())
            csv_res = {"votes": votes, "totals": totals, "rows": rows}
            log["csv"] = f"fichier local téléchargé sur le site de la CEC ({rows} communes)"
            strikes, until = 0, 0
        except (OSError, ValueError) as e:
            log["csv"] = f"fichier local illisible : {e}"
    elif not polling:
        log["csv"] = "site de la CEC non interrogé (totaux saisis à la main, fichier importé, relais presse)"
    elif paused:
        blocked_now = True
        log["csv"] = f"pause anti-bot jusqu'à {datetime.fromtimestamp(until, timezone.utc).strftime('%H:%M:%SZ')} (tentative {strikes})"
    else:
        try:
            votes, totals, rows = parse_csv(get(a.csv_url, a.timeout))
            csv_res = {"votes": votes, "totals": totals, "rows": rows}
            log["csv"] = f"ok ({rows} communes)"
            strikes, until = 0, 0
        except Blocked as e:
            strikes += 1
            until = now + min(600, 45 * 2 ** (strikes - 1))
            blocked_now = True
            log["csv"] = f"indisponible : {e}"
        except (urllib.error.URLError, ValueError, OSError) as e:
            log["csv"] = f"indisponible : {e}"

    # Un autre collecteur (ou un import manuel) a-t-il des chiffres plus avancés que les nôtres ? Seulement si nous n'avons rien lu.
    peer = load_json(a.peer)
    if csv_res is None and peer and peer.get("collector") != me and isinstance(peer.get("votes"), dict) and isinstance(peer.get("totals"), dict):
        pv = (prev.get("totals") or {}).get("valid", 0)
        if peer["totals"].get("valid", 0) > pv and sane(peer["votes"], peer["totals"], prev.get("totals"))[0]:
            prev = {**prev, "votes": peer["votes"], "totals": peer["totals"], "names": peer.get("names") or prev.get("names"),
                    "official_seats": peer.get("official_seats"), "fails": 0}
            log["peer"] = f"relevé de « {peer.get('collector')} » adopté ({peer['totals']['valid']} bulletins valides)"

    if a.skip_html or not polling or paused or blocked_now:
        log["html"] = "non relu (cycle rapide)" if a.skip_html else "non relu (site de la CEC non interrogé ou bloqué)"
    else:
        try:
            h_votes, h_totals, names, seats, waiting = parse_html(get(a.html_url, a.timeout), set(csv_res["votes"]) if csv_res else None)
            html_res = {"votes": h_votes, "totals": h_totals, "names": names, "seats": seats, "waiting": waiting}
            log["html"] = "ok (en attente du dépouillement)" if waiting and not h_votes else "ok"
        except Blocked as e:
            blocked_now = True
            log["html"] = f"indisponible : {e}"
        except (urllib.error.URLError, ValueError, OSError) as e:
            log["html"] = f"indisponible : {e}"

    # participation : relevés du relais + ceux déjà recueillis (une panne ne les efface pas) + saisie à la main (prioritaire)
    auto = {r["time"]: r for r in (prev.get("manual") or {}).get("turnout", []) if isinstance(r, dict) and r.get("auto") and r.get("time")}
    if a.skip_html:
        log["turnout"] = "non relu (cycle rapide)"
    else:
        try:
            fresh = parse_turnout(get(a.turnout_url, a.timeout, tries=2, ok=allowed_turnout, opener=_turnout_opener))
            auto.update({r["time"]: r for r in fresh})
            log["turnout"] = f"ok ({len(fresh)} relevés, dernier {fresh[-1]['time']})" if fresh else "ok (aucun relevé publié)"
        except (urllib.error.URLError, ValueError, OSError) as e:
            log["turnout"] = f"indisponible : {e}"
    manual = {**manual, "turnout": merge_turnout(manual.get("turnout"), list(auto.values()))}

    # relais presse (non officiel) : le dernier relevé reste affiché si la source tombe ; un net recul du dépouillement est écarté
    press = prev.get("press") if isinstance(prev.get("press"), dict) else None
    if a.skip_html:
        log["press"] = "non relu (cycle rapide)"
    else:
        try:
            fresh = parse_press(get(a.press_url, a.timeout, tries=2, ok=allowed_press, opener=_press_opener))
            if press and fresh["valid"] < press.get("valid", 0) * (1 - PRESS_MAX_DROP):
                log["press"] = f"ignoré : recul du dépouillement ({fresh['valid']} < {press.get('valid')})"
            else:
                press = fresh
                log["press"] = f"ok ({fresh['counted_pct']} % dépouillés, relevé de {fresh['as_of']})"
        except (urllib.error.URLError, ValueError, OSError) as e:
            log["press"] = f"indisponible : {e}"

    body = build(prev, manual, csv_res, html_res, log, polled=a.poll_cec or bool(a.csv_file))
    body["press"] = press
    body["blocked"] = {"strikes": strikes, "until": until} if strikes else None
    stable = {k: v for k, v in body.items() if k not in ("fails", "source", "blocked")}   # ce qui compte pour « les données ont changé »
    if isinstance(stable.get("press"), dict):
        stable["press"] = {k: v for k, v in stable["press"].items() if k != "fetched_at"}
    digest = hashlib.sha1(json.dumps(stable, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    body["digest"] = digest
    body["updated_at"] = prev.get("updated_at") if prev.get("digest") == digest and prev.get("updated_at") else now_iso()
    body["checked_at"] = now_iso()
    body["collector"] = me                  # étiquette neutre : d'où vient ce relevé

    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, a.out)                  # écriture atomique : un lecteur ne voit jamais un fichier à moitié écrit
    print(f"[{body['checked_at']}] statut={body['status']}{' STALE' if body['stale'] else ''} csv={log.get('csv')} html={log.get('html')} participation={log.get('turnout')} relais={log.get('press')}{' | ' + log['peer'] if 'peer' in log else ''}", file=sys.stderr)


if __name__ == "__main__":
    main()
