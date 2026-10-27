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


if __name__ == "__main__":
    unittest.main()
