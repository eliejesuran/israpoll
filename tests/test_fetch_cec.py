"""Tests du collecteur CEC (données synthétiques, aucune requête réseau).  python3 -I -m unittest discover tests"""
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import fetch_cec  # noqa: E402

CSV = (
    "﻿סמל ועדה,שם ישוב,סמל ישוב,בזב,מצביעים,פסולים,כשרים,אמת,מחל,רק,דרך,\n"
    "1,עיר א,10,1000,700,10,690,50,300,140,200,\n"
    "2,עיר ב,20,500,300,0,300,20,100,80,100,\n"
)
HTML_2022_STYLE = """<table><tr><th>a</th></tr>
<tr><td>1,500</td><td>1,000</td><td>66.67%</td><td>990</td><td>10</td></tr></table>
<table>
<tr><td>הליכוד</td><td>מחל</td><td>40</td><td>40.40%</td><td>400</td></tr>
<tr><td>ביחד</td><td>רק</td><td>30</td><td>22.22%</td><td>220</td></tr>
<tr><td>ישר</td><td>דרך</td><td>30</td><td>30.30%</td><td>300</td></tr>
<tr><td>הדמוקרטים</td><td>אמת</td><td>20</td><td>7.07%</td><td>70</td></tr>
</table>"""


class FetchCec(unittest.TestCase):
    def test_csv_sums_localities(self):
        votes, totals, n = fetch_cec.parse_csv(CSV)
        self.assertEqual(n, 2)
        self.assertEqual(votes["מחל"], 400)
        self.assertEqual(votes["אמת"], 70)
        self.assertEqual(totals, {"eligible": 1500, "voters": 1000, "invalid": 10, "valid": 990})

    def test_csv_before_counting_is_empty_not_an_error(self):
        votes, totals, n = fetch_cec.parse_csv("סמל ועדה,שם ישוב,סמל ישוב,בזב,מצביעים,פסולים,כשרים,אמת,מחל,\n")
        self.assertEqual(n, 0)
        self.assertEqual(totals["valid"], 0)

    def test_csv_rejects_foreign_content(self):
        with self.assertRaises(ValueError):
            fetch_cec.parse_csv("<html>erreur</html>")

    def test_html_seats_only_if_they_total_120(self):
        votes, totals, names, seats, waiting = fetch_cec.parse_html(HTML_2022_STYLE)
        self.assertEqual(sum(seats.values()), 120)
        self.assertEqual(seats["מחל"], 40)
        self.assertEqual(totals["eligible"], 1500)
        bad = HTML_2022_STYLE.replace("<td>40</td>", "<td>41</td>")
        self.assertEqual(fetch_cec.parse_html(bad)[3], {})

    def test_html_waiting_page(self):
        page = "<html><body><p>ממתינים לספירת הקולות</p></body></html>"
        votes, totals, names, seats, waiting = fetch_cec.parse_html(page)
        self.assertTrue(waiting)
        self.assertEqual(votes, {})

    def test_only_cec_hosts_are_fetched(self):
        with self.assertRaises(ValueError):
            fetch_cec.get("https://example.com/x.csv", 1)


def csv_res(valid, voters=None, rows=3, votes=None):
    votes = votes or {"מחל": valid // 2, "רק": valid - valid // 2}
    return {"votes": votes, "totals": {"eligible": valid * 2, "voters": voters or valid + 10, "invalid": 10, "valid": valid}, "rows": rows}


class Build(unittest.TestCase):
    def run_cycle(self, prev, csv, html=None):
        return fetch_cec.build(prev, {}, csv, html, {})

    def test_waiting_before_counting(self):
        out = self.run_cycle({}, csv_res(0, voters=0, votes={"מחל": 0, "רק": 0}))
        self.assertEqual(out["status"], "waiting")
        self.assertIsNone(out["votes"])

    def test_counting_then_transient_failure_keeps_last_good_numbers(self):
        a = self.run_cycle({}, csv_res(1000))
        self.assertEqual(a["status"], "counting")
        b = self.run_cycle(a, None)                       # panne réseau
        self.assertEqual(b["votes"], a["votes"])
        self.assertFalse(b["stale"])                      # 1 échec : on ne s'alarme pas encore
        for _ in range(2):
            b = self.run_cycle(b, None)
        self.assertTrue(b["stale"])                       # 3 échecs de suite : signalé
        c = self.run_cycle(b, csv_res(1200))
        self.assertFalse(c["stale"])
        self.assertEqual(c["fails"], 0)

    def test_truncated_file_is_rejected_then_accepted_if_persistent(self):
        a = self.run_cycle({}, csv_res(100000))
        cur = a
        for i in range(2):
            cur = self.run_cycle(cur, csv_res(20000))     # chute de 80 % = fichier tronqué
            self.assertEqual(cur["totals"]["valid"], 100000)
        cur = self.run_cycle(cur, csv_res(20000))         # 3e fois : c'est une vraie correction
        self.assertEqual(cur["totals"]["valid"], 20000)
        self.assertTrue(cur["suspect"])

    def test_inconsistent_party_sum_is_rejected(self):
        a = self.run_cycle({}, csv_res(1000))
        bad = csv_res(2000, votes={"מחל": 10, "רק": 10})
        self.assertEqual(self.run_cycle(a, bad)["totals"]["valid"], 1000)

    def test_never_goes_back_to_empty(self):
        a = self.run_cycle({}, csv_res(1000))
        empty = self.run_cycle(a, csv_res(0, voters=0, votes={"מחל": 0, "רק": 0}))
        self.assertEqual(empty["status"], "counting")

    def test_official_seats_need_a_matching_page(self):
        a = self.run_cycle({}, csv_res(1000))
        seats = {"מחל": 60, "רק": 60}
        ok = {"votes": {"מחל": 500, "רק": 500}, "totals": None, "names": {}, "seats": seats, "waiting": False}
        self.assertEqual(self.run_cycle(a, csv_res(1000), ok)["official_seats"], seats)
        stale_page = dict(ok, votes={"מחל": 50, "רק": 50})
        self.assertIsNone(self.run_cycle(a, csv_res(1000), stale_page)["official_seats"])

    def test_final_flag_comes_from_manual_file(self):
        out = fetch_cec.build({}, {"final": True}, csv_res(1000), None, {})
        self.assertEqual(out["status"], "final")


class Sane(unittest.TestCase):
    def test_voters_cannot_be_below_valid(self):
        ok, why = fetch_cec.sane({"a": 100}, {"eligible": 500, "voters": 50, "invalid": 0, "valid": 100}, None)
        self.assertFalse(ok)


def blog(*updates):
    """Page de live-blog minimale : un LiveBlogPosting en JSON-LD, comme sur nbcnews.com (entrées les plus récentes d'abord)."""
    doc = {"@type": "LiveBlogPosting", "liveBlogUpdate": [{"headline": h, "articleBody": f"<p>{b}</p>", "datePublished": "2026-10-27T17:00:00Z"} for h, b in updates]}
    return f'<html><script type="application/ld+json">{json.dumps({"@type": "Dataset"})}</script><script type="application/ld+json">{json.dumps(doc)}</script></html>'


# textes relevés sur le live-blog NBC le 27 octobre 2026
E18 = ("Voter turnout reaches 66.7%, Central Elections Committee says",
       "Voter turnout had reached 66.7% as of 6 p.m. local time (noon ET), according to Israel's Central Elections Committee, the highest turnout "
       "seen in decades. This is a 9% increase from the 2022 election, when 57.7% of all eligible voters had cast their ballots by that time.")
E14 = ("Turnout soars to 44.9% in latest update; polling stations could stay open late",
       "As of 2 p.m. local time (8 a.m. ET), turnout in the election stands at 44.9%, according to Israel's Central Elections Committee, the highest "
       "turnout recorded at this hour since 1973. Turnout among Israel Defense Forces service members was even higher at 48% an hour earlier, "
       "according to the IDF. In 2022 the list ran long.")
E12 = ("Turnout surges to highest in decades as of midday in Israel",
       "Five hours into Israel’s highly contentious elections, voter turnout is beating historic records. Some 31.5% of the voting public had cast "
       "their ballots up to noon today local time, according to Israel’s Central Elections Committee, the highest since 1977. At the same time "
       "during the last election in 2022, only 28.4% of voters had cast their ballots, the CEC said.")
E10 = ("Early signs point to high turnout",
       "Voter turnout stood at 16.7% as of 10 a.m. local time (4 a.m. ET), Israel’s Central Elections Committee has said. That's higher than the "
       "15.9% reported at the same time during the last election, in 2022.")
NOISE = [("No extension to voting hours amid high turnout, elections committee says",
          "There will be no formal extension to voting hours, Israel's Central Elections Committee has said, after high turnout led to long lines."),
         ("Counting begins", "As of 10 p.m. local time, 5% of ballots had been counted, according to Israel's Central Elections Committee."),
         ("Night shift", "As of 1 a.m. local time, turnout among overnight workers was 3%, the Central Elections Committee said."),
         ("Netanyahu cites high Arab turnout", "Netanyahu said that as of 3 p.m. local time, 80% of Arab towns reported long lines.")]   # une heure et un %, mais pas un relevé de la CEC
# variantes de rédaction possibles : le « +6 % » est plus près de l'heure (ou de « 2022 ») que le vrai chiffre
E20 = ("Turnout update", "As of 8 p.m. local time, up 6% on last time, voter turnout reached 70.1%, according to Israel's Central Elections Committee. "
       "That is a 6% increase over 2022, when turnout stood at 64.1% at the same hour.")


class Turnout(unittest.TestCase):
    def test_reads_every_cec_reading_with_its_hour(self):
        rows = fetch_cec.parse_turnout(blog(NOISE[0], E18, NOISE[1], E14, E12, E10))
        self.assertEqual([(r["time"], r["pct"], r["prev2022"]) for r in rows],
                         [("10:00", 16.7, 15.9), ("12:00", 31.5, 28.4), ("14:00", 44.9, None), ("18:00", 66.7, 57.7)])
        self.assertTrue(all(r["auto"] and r["url"] == fetch_cec.TURNOUT_URL for r in rows))

    def test_army_turnout_and_increase_are_not_mistaken_for_2022(self):
        rows = fetch_cec.parse_turnout(blog(E14, E18))
        self.assertIsNone(rows[0]["prev2022"])            # « 48 % chez les soldats » n'est pas la participation 2022
        self.assertEqual(rows[1]["prev2022"], 57.7)        # « +9 % » non plus

    def test_an_increase_is_neither_the_reading_nor_the_2022_figure(self):
        (row,) = fetch_cec.parse_turnout(blog(E20))
        self.assertEqual((row["time"], row["pct"], row["prev2022"]), ("20:00", 70.1, 64.1))

    def test_a_page_that_is_not_a_liveblog_is_an_error_not_an_empty_list(self):
        with self.assertRaises(ValueError):
            fetch_cec.parse_turnout("<html>404</html>")
        self.assertEqual(fetch_cec.parse_turnout(blog(*NOISE)), [])      # un blog sans relevé : liste vide, pas une panne

    def test_hand_entry_wins_for_the_same_hour(self):
        hand = [{"time": "18:00", "pct": 66.9, "source": "CEC"}]
        merged = fetch_cec.merge_turnout(hand, fetch_cec.parse_turnout(blog(E18)))
        self.assertEqual([(r["time"], r["pct"]) for r in merged], [("18:00", 66.9)])

    def test_auto_reading_that_goes_backwards_is_dropped_but_never_a_hand_entry(self):
        auto = fetch_cec.parse_turnout(blog(E18, E12))
        self.assertEqual([r["time"] for r in fetch_cec.merge_turnout([{"time": "14:00", "pct": 70.0}], auto)], ["12:00", "14:00"])
        self.assertEqual([r["time"] for r in fetch_cec.merge_turnout([{"time": "20:00", "pct": 60.0}], auto)], ["12:00", "18:00", "20:00"])

    def test_cycle_end_to_end_keeps_readings_when_the_relay_goes_down(self):
        tmp = tempfile.mkdtemp()
        try:
            out, prev, man = (os.path.join(tmp, n) for n in ("live.json", "prev.json", "manual.json"))
            with open(man, "w") as f:
                json.dump({"turnout": [{"time": "10:00", "pct": 16.7, "prev2022": 15.9}]}, f)

            def run(nbc, *extra):
                def fake_get(url, timeout, tries=3, ok=None, opener=None):
                    if url == fetch_cec.TURNOUT_URL:
                        if nbc is None:
                            raise OSError("réseau coupé")
                        return nbc
                    return "<html></html>" if "nationalresults" in url else "סמל ועדה,שם ישוב,סמל ישוב,בזב,מצביעים,פסולים,כשרים,מחל,\n"
                argv = ["fetch_cec.py", "--out", out, "--manual", man, "--prev", prev, *extra]
                with mock.patch.object(fetch_cec, "get", fake_get), mock.patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()):
                    os.path.exists(out) and os.remove(out)       # un fichier périmé ne doit pas masquer un échec
                    fetch_cec.main()
                with open(out) as f:
                    return json.load(f)

            a = run(blog(E18, E10))
            self.assertEqual([r["time"] for r in a["manual"]["turnout"]], ["10:00", "18:00"])
            self.assertTrue(a["source"]["fetch"]["turnout"].startswith("ok"))
            shutil.copy(out, prev)
            b = run(None)                                  # NBC injoignable : on garde 18:00 et on le dit
            self.assertEqual([r["time"] for r in b["manual"]["turnout"]], ["10:00", "18:00"])
            self.assertTrue(b["source"]["fetch"]["turnout"].startswith("indisponible"))
            shutil.copy(out, prev)
            c = run(None, "--skip-html")                   # cycle rapide : pas de requête, mêmes relevés
            self.assertEqual([r["time"] for r in c["manual"]["turnout"]], ["10:00", "18:00"])
            self.assertEqual(c["digest"], b["digest"])     # rien n'a changé : pas de republication inutile
        finally:
            shutil.rmtree(tmp)


def cec(valid=1000, **over):
    """Saisie de secours cohérente : 98 % des voix réparties entre deux listes."""
    m = {"as_of": "23:40", "totals": {"eligible": valid * 2, "voters": valid + 10, "valid": valid, "invalid": 10},
         "votes": {"likud": valid // 2, "together": valid * 48 // 100}}
    m.update(over)
    return m


class ManualCec(unittest.TestCase):
    """Le site de la CEC filtre les scripts (défi anti-bot) : les totaux nationaux peuvent être recopiés à la main."""

    def cycle(self, prev, manual_cec, csv=None):
        return fetch_cec.build(prev, {"cec": manual_cec}, csv, None, {})

    def test_ids_and_letters_both_accepted(self):
        r = fetch_cec.parse_manual_cec(cec(votes={"likud": 500, "ני": 20, "together": 480}))
        self.assertEqual(r["votes"], {"מחל": 500, "ני": 20, "רק": 480})
        self.assertEqual(r["totals"]["invalid"], 10)
        self.assertEqual(fetch_cec.parse_manual_cec(cec(totals={"eligible": 2000, "voters": 1010, "valid": 1000}))["totals"]["invalid"], 10)

    def test_a_typo_is_refused_not_published(self):
        bad = [cec(votes={"likudd": 500, "together": 480}), cec(votes={"likud": 5, "מחל": 500, "together": 480}),             # même liste sous deux noms : la somme resterait plausible
               cec(votes={"likud": "500", "together": 480}), cec(votes={"likud": 500.5, "together": 480}), cec(votes={"likud": True, "together": 480}),
               cec(votes={"likud": 100, "together": 480}), cec(votes={"likud": 1200, "together": 480}),       # somme trop basse / trop haute
               cec(totals={"eligible": 2000, "voters": 900, "valid": 1000}), cec(totals={"eligible": 2000, "voters": 1010, "valid": 0}),
               cec(totals={"eligible": 1000, "voters": 1010, "valid": 1000}), cec(totals={"eligible": 2000, "voters": 1010, "valid": 1000, "invalid": 400}),
               {}, {"votes": {}}]
        for m in bad:
            with self.assertRaises(ValueError, msg=str(m)):
                fetch_cec.parse_manual_cec(m)
            self.assertEqual(self.cycle({}, m)["status"], "waiting", str(m))

    def test_used_while_the_collector_is_blocked_and_never_goes_stale(self):
        cur = self.cycle({}, cec())
        self.assertEqual((cur["status"], cur["totals"]["valid"], cur["stale"]), ("counting", 1000, False))
        self.assertEqual(cur["votes"], {"מחל": 500, "רק": 480})
        self.assertEqual(cur["source"]["manual_cec"], {"as_of": "23:40", "url": fetch_cec.HTML_URL})
        for _ in range(6):                                                    # le collecteur reste bloqué : la saisie vaut toujours
            cur = self.cycle(dict(cur, fails=cur["fails"]), cec())
            cur["fails"] = cur["fails"] + 1
        self.assertFalse(cur["stale"])
        self.assertEqual(cur["status"], "counting")

    def test_beats_an_empty_csv_but_not_a_more_advanced_automatic_feed(self):
        self.assertEqual(self.cycle({}, cec(), csv_res(0, voters=0, votes={"מחל": 0, "רק": 0}))["totals"]["valid"], 1000)
        auto = self.cycle({}, cec(1000), csv_res(2000))
        self.assertEqual(auto["totals"]["valid"], 2000)
        self.assertIsNone(auto["source"]["manual_cec"])

    def test_never_older_than_the_last_reading_except_to_correct_itself(self):
        old = fetch_cec.build({}, {}, csv_res(5000), None, {})
        stale_hand = self.cycle(old, cec(1000))                               # saisie plus ancienne que le dernier relevé automatique
        self.assertEqual(stale_hand["totals"]["valid"], 5000)
        self.assertIsNone(stale_hand["source"]["manual_cec"])
        a = self.cycle({}, cec(5000))
        self.assertEqual(self.cycle(a, cec(4000))["totals"]["valid"], 4000)   # correction d'une saisie par une autre

    def test_cycle_end_to_end_through_the_manual_file(self):
        tmp = tempfile.mkdtemp()
        try:
            out, man = os.path.join(tmp, "live.json"), os.path.join(tmp, "manual.json")
            with open(man, "w") as f:
                json.dump({"cec": cec()}, f)

            def fake_get(url, timeout, tries=3, ok=None, opener=None):
                raise OSError("HTTP 202 : défi anti-bot")
            argv = ["fetch_cec.py", "--out", out, "--manual", man, "--skip-html"]
            with mock.patch.object(fetch_cec, "get", fake_get), mock.patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()):
                fetch_cec.main()
            with open(out) as f:
                live = json.load(f)
            self.assertEqual((live["status"], live["totals"]["valid"]), ("counting", 1000))
            self.assertTrue(live["source"]["fetch"]["cec_manual"].startswith("utilisée"))
        finally:
            shutil.rmtree(tmp)

    def test_party_letters_match_the_page(self):
        with open(os.path.join(ManualFile.ROOT, "js", "common.js"), encoding="utf-8") as f:     # PARTIES vit dans js/common.js
            page = dict(re.findall(r'\{ id: "(\w+)",[^\n]*?letters: "([^"]+)"', f.read()))
        self.assertEqual(fetch_cec.PARTY_LETTERS, page)
        self.assertLessEqual(set(page.values()), fetch_cec.KNOWN_LETTERS)

    def test_helper_replaces_and_clears_without_touching_the_rest_of_the_file(self):
        import cec_manual
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "manual.json")
            shutil.copy(os.path.join(ManualFile.ROOT, "data", "manual.json"), path)
            cec_manual.write(path, None)                  # le vrai fichier peut déjà porter une saisie : on part du fichier sans
            with open(path, encoding="utf-8") as f:
                original = f.read()
            for valid in (1000, 2000):
                cec_manual.write(path, cec(valid))
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertEqual(json.loads(text)["cec"]["totals"]["valid"], 2000)
            self.assertEqual(text.count('"cec"'), 1)
            self.assertTrue(text.startswith(original.rstrip()[:-1].rstrip()))
            cec_manual.write(path, None)
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), original)
        finally:
            shutil.rmtree(tmp)


class ManualFile(unittest.TestCase):
    """data/manual.json est saisi à la main, souvent dans l'urgence : la page écarte en silence un identifiant de parti inconnu."""
    ROOT = os.path.join(os.path.dirname(__file__), "..")

    def test_exit_polls_use_known_parties_and_total_120(self):
        with open(os.path.join(self.ROOT, "js", "common.js"), encoding="utf-8") as f:
            ids = set(re.findall(r'\{ id: "(\w+)",\s+fr:', f.read()))
        with open(os.path.join(self.ROOT, "data", "manual.json"), encoding="utf-8") as f:
            manual = json.load(f)
        self.assertGreater(len(ids), 10)
        for e in manual["exit_polls"]:
            self.assertFalse(set(e["seats"]) - ids, f"{e['channel']} : parti inconnu {set(e['seats']) - ids}")
            self.assertEqual(sum(e["seats"].values()), 120, e["channel"])


import http.server
import threading
import urllib.request


class _Challenge(http.server.BaseHTTPRequestHandler):
    hits = 0

    def do_GET(self):
        type(self).hits += 1
        self.send_response(202)
        self.send_header("x-amzn-waf-action", "challenge")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *a):
        pass


class AntiBot(unittest.TestCase):
    def test_challenge_is_not_retried(self):
        srv = http.server.HTTPServer(("127.0.0.1", 0), _Challenge)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        _Challenge.hits = 0
        try:
            with self.assertRaises(fetch_cec.Blocked):
                fetch_cec.get(f"http://127.0.0.1:{srv.server_port}/x.csv", 3, ok=lambda u: True, opener=urllib.request.build_opener())
        finally:
            srv.shutdown()
        self.assertEqual(_Challenge.hits, 1)          # une seule requête : on n'insiste pas

    def run_main(self, tmp, *args, env=None, now=None):
        out = os.path.join(tmp, "out.json")
        argv = ["fetch_cec.py", "--out", out, "--skip-html", *args]
        with mock.patch.object(sys, "argv", argv), mock.patch.dict(os.environ, env or {"COLLECTOR_ID": "jetson"}), \
             mock.patch.object(fetch_cec.time, "time", return_value=now or 1_000_000.0):
            fetch_cec.main()
        with open(out, encoding="utf-8") as f:
            return json.load(f)

    def test_backoff_grows_and_pauses_requests(self):
        calls = []

        def blocked(*a, **k):
            calls.append(1)
            raise fetch_cec.Blocked("défi")

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(fetch_cec, "get", blocked):
            prev = os.path.join(tmp, "prev.json")
            first = self.run_main(tmp, now=1_000_000.0)
            self.assertTrue(first["challenge"])
            self.assertEqual(first["blocked"], {"strikes": 1, "until": 1_000_045.0})
            self.assertEqual(first["status"], "waiting")
            json.dump(first, open(prev, "w"))
            # pendant la pause : aucune requête
            paused = self.run_main(tmp, "--prev", prev, now=1_000_020.0)
            self.assertEqual(len(calls), 1)
            self.assertTrue(paused["challenge"])
            self.assertIn("pause anti-bot", paused["source"]["fetch"]["csv"])
            # la pause terminée : un nouvel essai, pause doublée
            json.dump(paused, open(prev, "w"))
            again = self.run_main(tmp, "--prev", prev, now=1_000_100.0)
            self.assertEqual(len(calls), 2)
            self.assertEqual(again["blocked"], {"strikes": 2, "until": 1_000_190.0})

    def test_local_csv_file_overrides_and_clears_the_block(self):
        csv_text = "סמל ועדה,שם ישוב,סמל ישוב,בזב,מצביעים,פסולים,כשרים,מחל,רק,\n1,א,1,1000,700,0,700,400,300,\n"
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, "expc.csv")
            open(f, "w", encoding="utf-8").write(csv_text)
            prev = os.path.join(tmp, "prev.json")
            json.dump({"blocked": {"strikes": 4, "until": 9e12}, "challenge": True}, open(prev, "w"))
            out = self.run_main(tmp, "--prev", prev, "--csv-file", f)
        self.assertEqual(out["status"], "counting")
        self.assertEqual(out["votes"], {"מחל": 400, "רק": 300})
        self.assertFalse(out["challenge"])
        self.assertIsNone(out["blocked"])

    def test_peer_with_more_votes_is_adopted_only_when_we_read_nothing(self):
        peer = {"collector": "local", "votes": {"מחל": 400, "רק": 300}, "totals": {"eligible": 2000, "voters": 750, "invalid": 0, "valid": 700}}

        def blocked(*a, **k):
            raise fetch_cec.Blocked("défi")

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(fetch_cec, "get", blocked):
            p = os.path.join(tmp, "peer.json")
            json.dump(peer, open(p, "w"))
            out = self.run_main(tmp, "--peer", p)
            self.assertEqual(out["status"], "counting")
            self.assertEqual(out["totals"]["valid"], 700)
            self.assertIn("adopté", out["source"]["fetch"]["peer"])
            # son propre relevé n'est jamais « adopté »
            mine = self.run_main(tmp, "--peer", p, env={"COLLECTOR_ID": "local"})
            self.assertEqual(mine["status"], "waiting")


PRESS_PAGE = """<html><head><script>var x = "Projected seats from the count so far, by party : Fake 999 ."</script></head><body>
<p>With 76.89% of ballots counted at 10:58, the Netanyahu bloc leads the Change bloc 54 to 47, with 19 for the Arab parties.</p>
<p>Projected seats from the count so far, by party : <b>Yashar</b> 20, B&#x27;Yachad 11, The Democrats 8, Yisrael Beiteinu 8,
The Joint List 13, Ra&#x27;am 6, Likud 27, Otzma Yehudit 7, Shas 7, United Torah Judaism 7, Religious Zionism &amp; Zehut 6 . 47 seats for the opposition bloc.</p>
<dl><dd>4,006,695</dd><dt>valid votes counted</dt></dl>
</body></html>"""


class Press(unittest.TestCase):
    def test_parse_real_looking_page(self):
        r = fetch_cec.parse_press(PRESS_PAGE.replace("</dd><dt>valid votes counted</dt>", "</dd>").replace("<dd>4,006,695", "valid votes counted <dd>4,006,695"))
        self.assertEqual(r["as_of"], "10:58")
        self.assertEqual(r["counted_pct"], 76.89)
        self.assertEqual(r["valid"], 4006695)
        self.assertEqual(r["seats"]["together"], 11)
        self.assertEqual(r["seats"]["rzp"], 6)
        self.assertEqual(sum(r["seats"].values()), 120)         # le script de la page (« Fake 999 ») est ignoré

    def page(self, **kw):
        t = PRESS_PAGE.replace("</dd><dt>valid votes counted</dt>", "</dd>").replace("<dd>4,006,695", "valid votes counted <dd>4,006,695")
        for old, new in kw.items():
            t = t.replace(old.replace("_", " "), new)
        return t

    def test_strict_on_unknown_party_wrong_total_or_layout_change(self):
        with self.assertRaises(ValueError):
            fetch_cec.parse_press(self.page(Likud_27="Parti inconnu 27"))
        with self.assertRaises(ValueError):
            fetch_cec.parse_press(self.page(Likud_27="Likud 28"))              # 121 sièges
        with self.assertRaises(ValueError):
            fetch_cec.parse_press("<html>autre mise en page</html>")

    def run_main(self, tmp, *args):
        out = os.path.join(tmp, "out.json")
        with mock.patch.object(sys, "argv", ["fetch_cec.py", "--out", out, *args]), mock.patch.dict(os.environ, {"COLLECTOR_ID": "jetson"}):
            fetch_cec.main()
        with open(out, encoding="utf-8") as f:
            return json.load(f)

    def test_press_is_kept_when_the_source_fails_and_never_goes_backwards(self):
        good = self.page()
        fewer = good.replace("4,006,695", "3,000,000")
        with tempfile.TemporaryDirectory() as tmp:
            prev = os.path.join(tmp, "prev.json")

            def fake(page_or_exc):
                def _get(url, *a, **k):
                    if url.startswith("https://www.thepetek.com"):
                        if isinstance(page_or_exc, Exception):
                            raise page_or_exc
                        return page_or_exc
                    raise fetch_cec.Blocked("défi")
                return _get

            with mock.patch.object(fetch_cec, "get", fake(good)):
                first = self.run_main(tmp)
            self.assertEqual(first["press"]["valid"], 4006695)
            self.assertIn("ok", first["source"]["fetch"]["press"])
            json.dump(first, open(prev, "w"))
            with mock.patch.object(fetch_cec, "get", fake(OSError("réseau coupé"))):
                down = self.run_main(tmp, "--prev", prev)
            self.assertEqual(down["press"]["valid"], 4006695)                   # le dernier relevé reste
            self.assertIn("indisponible", down["source"]["fetch"]["press"])
            with mock.patch.object(fetch_cec, "get", fake(fewer)):
                back = self.run_main(tmp, "--prev", prev)
            self.assertEqual(back["press"]["valid"], 4006695)                   # un relevé en recul est ignoré
            self.assertIn("recul", back["source"]["fetch"]["press"])
            self.assertEqual(back["status"], "waiting")                         # le relais ne devient jamais un résultat officiel


if __name__ == "__main__":
    unittest.main()
