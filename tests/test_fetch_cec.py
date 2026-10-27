"""Tests du collecteur CEC (données synthétiques, aucune requête réseau).  python3 -I -m unittest discover tests"""
import os
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
