#!/usr/bin/env python3
"""Récupère les résultats officiels de la Commission électorale centrale (CEC) et les écrit en JSON.

Le site de la CEC n'envoie pas d'en-tête CORS : un navigateur ne peut donc pas le lire directement.
Ce script (lancé toutes les ~30 s par scripts/live.sh le soir du scrutin) fait le relais.

Sources, par ordre de priorité (même structure qu'en 2022, vérifiée sur les résultats 2022) :
  CSV  par commune  : https://media26.bechirot.gov.il/files/expc.csv   (somme = résultat national)
  HTML national     : https://votes26.bechirot.gov.il/nationalresults  (sièges attribués par la CEC)

Robustesse : un relevé incohérent (fichier tronqué, page d'erreur, total qui s'effondre) ou une panne réseau
ne remplace jamais les derniers bons chiffres ; ils sont conservés et signalés `stale` après 3 échecs de suite.

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


class _SameSiteOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise urllib.error.URLError(f"redirection vers un hôte non autorisé : {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SameSiteOnly)


def get(url, timeout, tries=3):
    """GET avec quelques essais : le site de la CEC répond parfois 202 + corps vide (filtre anti-bot) ou coupe
    la poignée de main TLS. Seuls les hôtes *.bechirot.gov.il sont autorisés, redirections comprises."""
    if not allowed(url):
        raise ValueError(f"hôte non autorisé : {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    last = None
    for i in range(tries):
        try:
            with _opener.open(req, timeout=timeout) as r:
                raw = r.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError("réponse trop volumineuse")
                body = raw.decode("utf-8-sig", errors="replace")
                if r.status == 200 and body.strip():
                    return body
                last = ValueError(f"réponse vide (HTTP {r.status}, probablement le filtre anti-bot du site)")
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
def build(prev, manual, csv_res, html_res, log):
    """prev : dernier live.json ; csv_res / html_res : dict ou None (échec) ; renvoie le nouveau dict (sans digest)."""
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
    else:
        fails += 1

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
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--skip-html", action="store_true", help="ne lit que le CSV (reprend les sièges du --prev)")
    a = ap.parse_args()

    prev = load_json(a.prev) or {}
    manual = load_json(a.manual)
    log = {}
    if manual is None:                      # fichier absent ou JSON cassé : on garde la dernière version valide
        manual = prev.get("manual") or {}
        log["manual"] = "illisible : dernière version valide conservée" if a.manual else "absent"

    csv_res = html_res = None
    try:
        votes, totals, rows = parse_csv(get(a.csv_url, a.timeout))
        csv_res = {"votes": votes, "totals": totals, "rows": rows}
        log["csv"] = f"ok ({rows} communes)"
    except (urllib.error.URLError, ValueError, OSError) as e:
        log["csv"] = f"indisponible : {e}"

    if a.skip_html:
        log["html"] = "non relu (cycle rapide)"
    else:
        try:
            h_votes, h_totals, names, seats, waiting = parse_html(get(a.html_url, a.timeout), set(csv_res["votes"]) if csv_res else None)
            html_res = {"votes": h_votes, "totals": h_totals, "names": names, "seats": seats, "waiting": waiting}
            log["html"] = "ok (en attente du dépouillement)" if waiting and not h_votes else "ok"
        except (urllib.error.URLError, ValueError, OSError) as e:
            log["html"] = f"indisponible : {e}"

    body = build(prev, manual, csv_res, html_res, log)
    stable = {k: v for k, v in body.items() if k not in ("fails", "source")}   # ce qui compte pour « les données ont changé »
    digest = hashlib.sha1(json.dumps(stable, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    body["digest"] = digest
    body["updated_at"] = prev.get("updated_at") if prev.get("digest") == digest and prev.get("updated_at") else now_iso()
    body["checked_at"] = now_iso()
    body["collector"] = os.environ.get("COLLECTOR_ID", "local")     # étiquette neutre : d'où vient ce relevé

    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, a.out)                  # écriture atomique : un lecteur ne voit jamais un fichier à moitié écrit
    print(f"[{body['checked_at']}] statut={body['status']}{' STALE' if body['stale'] else ''} csv={log.get('csv')} html={log.get('html')}", file=sys.stderr)


if __name__ == "__main__":
    main()
