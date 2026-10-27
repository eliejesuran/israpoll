#!/usr/bin/env python3
"""Récupère les résultats officiels de la Commission électorale centrale (CEC) et les écrit en JSON.

Le site de la CEC n'envoie pas d'en-tête CORS : un navigateur ne peut donc pas le lire directement.
Ce script (lancé par GitHub Actions toutes les ~30 s le soir du scrutin) fait le relais.

Sources, par ordre de priorité (même structure qu'en 2022, vérifiée sur les résultats 2022) :
  CSV  par commune  : https://media26.bechirot.gov.il/files/expc.csv   (somme = résultat national)
  HTML national     : https://votes26.bechirot.gov.il/nationalresults  (sièges attribués par la CEC)

Usage :
  fetch_cec.py --out live.json [--manual manual.json] [--prev live.json]
  fetch_cec.py --csv-url URL --html-url URL ...        # pour tester sur un autre scrutin
"""
import argparse
import csv
import hashlib
import html
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

CSV_URL = "https://media26.bechirot.gov.il/files/expc.csv"
HTML_URL = "https://votes26.bechirot.gov.il/nationalresults"
UA = "Mozilla/5.0 (compatible; israpoll/1.0; +https://github.com/eliejesuran/israpoll)"
META_COLS = {"סמל ועדה", "שם ישוב", "סמל ישוב", "בזב", "מצביעים", "פסולים", "כשרים"}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url, timeout, tries=3):
    """GET avec quelques essais : le site de la CEC répond parfois 202 + corps vide le temps de se réveiller."""
    if not (urlparse(url).hostname or "").endswith(".bechirot.gov.il"):
        raise ValueError(f"hôte non autorisé : {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8-sig", errors="replace")
                if r.status == 200 and body.strip():
                    return body, r.headers.get("Content-Type", "")
                last = ValueError(f"réponse vide (HTTP {r.status}, probablement le filtre anti-bot du site)")
        except (urllib.error.URLError, OSError) as e:
            last = e
        time.sleep(2)
    raise last


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
    out = []
    for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.S):
        out.append(html.unescape(re.sub(r"<[^>]+>", "", c)).strip())
    return out


# Lettres de vote des 38 listes de 2026 (en-tête du CSV officiel) ; sert à reconnaître les lignes du tableau HTML.
KNOWN_LETTERS = set(
    "אמת ב בד בי בקר ג ד די דרך ה ודם ז זך זץ ט י יק ך כן ל מחל ני נף נץ נקי נר עם פה צבי צדק צף ק קה קך קץ רץ רק שס".split()
)
WAITING_MARK = "ממתינים לספירת הקולות"


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


def load_json(path):
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--manual")
    ap.add_argument("--prev")
    ap.add_argument("--csv-url", default=CSV_URL)
    ap.add_argument("--html-url", default=HTML_URL)
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--skip-html", action="store_true", help="ne lit que le CSV (reprend les sièges du --prev)")
    a = ap.parse_args()

    prev = load_json(a.prev) or {}
    manual = load_json(a.manual) or {}
    log = {}
    votes = totals = None
    names, seats = {}, {}
    n_rows = 0
    cec_waiting = False

    try:
        txt, _ = get(a.csv_url, a.timeout)
        votes, totals, n_rows = parse_csv(txt)
        log["csv"] = f"ok ({n_rows} communes)"
    except (urllib.error.URLError, ValueError, OSError) as e:
        log["csv"] = f"indisponible : {e}"

    if a.skip_html:
        names, seats = prev.get("names", {}), prev.get("official_seats") or {}
        cec_waiting = bool(prev.get("cec_waiting"))
        log["html"] = "non relu (cycle rapide)"
    else:
      try:
        txt, _ = get(a.html_url, a.timeout)
        h_votes, h_totals, names, seats, cec_waiting = parse_html(txt, set(votes) if votes else None)
        log["html"] = "ok (en attente du dépouillement)" if cec_waiting and not h_votes else "ok"
        if votes is None and h_votes and h_totals:
            votes, totals = h_votes, h_totals
      except (urllib.error.URLError, ValueError, OSError) as e:
        log["html"] = f"indisponible : {e}"

    stale = False
    if votes is None or not totals or not totals.get("valid"):
        if prev.get("votes"):
            votes, totals, names, seats = prev["votes"], prev["totals"], prev.get("names", {}), prev.get("official_seats") or {}
            stale = True
        else:
            votes = totals = None

    official = bool(seats) and sum(seats.values()) > 0
    if votes is None:
        status = "waiting"
    elif manual.get("final"):
        status = "final"
    else:
        status = "counting"

    body = {
        "schema": 1,
        "status": status,
        "stale": stale,
        "source": {
            "name": "Commission électorale centrale d'Israël (ועדת הבחירות המרכזית)",
            "page": "https://votes26.bechirot.gov.il/nationalresults",
            "csv": a.csv_url,
            "fetch": log,
        },
        "totals": totals,
        "votes": votes,
        "names": names,
        "official_seats": seats if official else None,
        "cec_waiting": bool(cec_waiting),
        "manual": manual,
    }
    digest = hashlib.sha1(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    body["digest"] = digest
    body["updated_at"] = prev.get("updated_at") if prev.get("digest") == digest else now_iso()
    body["checked_at"] = now_iso()

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print(f"[{body['checked_at']}] statut={status} csv={log.get('csv')} html={log.get('html')}", file=sys.stderr)


if __name__ == "__main__":
    main()
