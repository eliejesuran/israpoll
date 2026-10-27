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


class ManualFile(unittest.TestCase):
    """data/manual.json est saisi à la main, souvent dans l'urgence : la page écarte en silence un identifiant de parti inconnu."""
    ROOT = os.path.join(os.path.dirname(__file__), "..")

    def test_exit_polls_use_known_parties_and_total_120(self):
        with open(os.path.join(self.ROOT, "index.html"), encoding="utf-8") as f:
            ids = set(re.findall(r'\{ id: "(\w+)",\s+fr:', f.read()))
        with open(os.path.join(self.ROOT, "data", "manual.json"), encoding="utf-8") as f:
            manual = json.load(f)
        self.assertGreater(len(ids), 10)
        for e in manual["exit_polls"]:
            self.assertFalse(set(e["seats"]) - ids, f"{e['channel']} : parti inconnu {set(e['seats']) - ids}")
            self.assertEqual(sum(e["seats"].values()), 120, e["channel"])


if __name__ == "__main__":
    unittest.main()
