"""Tests du relais d'actualités (flux RSS synthétiques, aucune requête réseau).  python3 -I -m unittest discover tests"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import fetch_news  # noqa: E402

NOW = datetime(2026, 10, 28, 6, 0, tzinfo=timezone.utc)


def rss(*items):
    body = "".join(
        f"<item><title>{t}</title><link>{u}</link><pubDate>{d}</pubDate>" + (f"<source url='https://x.fr'>{s}</source>" if s else "") + "</item>"
        for t, u, d, s in items
    )
    return f"<?xml version='1.0'?><rss><channel>{body}</channel></rss>".encode()


def ago(**kw):
    return (NOW - timedelta(**kw)).strftime("%a, %d %b %Y %H:%M:%S GMT")


class Parse(unittest.TestCase):
    def test_google_title_loses_its_media_suffix_and_entities_are_decoded(self):
        raw = rss(("Législatives en Israël : l&amp;#39;égalité - Le Monde.fr", "https://news.google.com/a", ago(hours=1), "Le Monde.fr"))
        (it,) = fetch_news.parse_feed(raw)
        self.assertEqual(it["title"], "Législatives en Israël : l'égalité")
        self.assertEqual(it["source"], "Le Monde")                      # alias : « Le Monde.fr » et « Le Monde » ne font qu'un
        self.assertEqual(it["published"], (NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))

    def test_imposed_media_and_unsafe_or_undated_items_are_dropped(self):
        raw = rss(("Knesset : vote", "https://www.rfi.fr/a", ago(hours=1), None),
                  ("Sans date", "https://www.rfi.fr/b", "n'importe quoi", None),
                  ("Lien http", "http://www.rfi.fr/c", ago(hours=1), None),
                  ("Lien piégé", "javascript:alert(1)", ago(hours=1), None))
        out = fetch_news.parse_feed(raw, media="RFI")
        self.assertEqual([i["title"] for i in out], ["Knesset : vote"])
        self.assertEqual(out[0]["source"], "RFI")

    def test_not_xml_is_an_error(self):
        with self.assertRaises(ValueError):
            fetch_news.parse_feed(b"<html><body>Acces refuse")

    def test_relevance(self):
        self.assertTrue(fetch_news.relevant("Législatives en Israël : égalité", True))
        self.assertFalse(fetch_news.relevant("Gaza : nouvelles frappes israéliennes", True))     # Israël sans scrutin : écarté des flux généralistes
        self.assertTrue(fetch_news.relevant("Eisenkot veut former un gouvernement", False))      # la requête de recherche a déjà filtré
        self.assertFalse(fetch_news.relevant("Élections municipales à Lyon", True))


class Merge(unittest.TestCase):
    def item(self, title, url, **age):
        return {"title": title, "source": "Média", "url": url, "published": (NOW - timedelta(**age)).strftime("%Y-%m-%dT%H:%M:%SZ")}

    def test_newest_first_without_duplicates_or_stale_items(self):
        a = [self.item("Même titre accentué : élection", "https://a/1", hours=3), self.item("Vieux", "https://a/2", days=9)]
        b = [self.item("MEME TITRE ACCENTUE : ELECTION", "https://b/1", hours=2), self.item("Récent", "https://a/3", minutes=5),
             self.item("Même lien", "https://a/3", minutes=10), self.item("Futur", "https://a/4", hours=-5)]
        out = fetch_news.merge([a, b], NOW)
        self.assertEqual([i["title"] for i in out], ["Récent", "MEME TITRE ACCENTUE : ELECTION"])

    def test_one_media_cannot_fill_the_page(self):
        items = [self.item(f"Titre {n}", f"https://a/{n}", minutes=n) for n in range(10)]
        self.assertEqual(len(fetch_news.merge([items], NOW)), fetch_news.PER_SOURCE)


class Collect(unittest.TestCase):
    def test_unknown_media_are_ignored_and_a_failing_feed_does_not_stop_the_others(self):
        google = rss(("Élections en Israël : tractations - Le Figaro", "https://news.google.com/1", ago(hours=1), "Le Figaro"),
                     ("Élections en Israël : un site d'opinion - Site Inconnu", "https://news.google.com/2", ago(hours=1), "Site Inconnu"))

        def fetch(url):
            if "news.google.com" in url:
                return google
            raise OSError("panne")
        batches, log = fetch_news.collect(fetch=fetch, now=NOW)
        titles = [i["title"] for b in batches for i in b]
        self.assertEqual(titles, ["Élections en Israël : tractations"])
        self.assertTrue(log["Google Actualités"].startswith("ok"))
        self.assertTrue(log["RFI"].startswith("indisponible"))

    def test_get_refuses_foreign_hosts_and_entity_bombs(self):
        with self.assertRaises(ValueError):
            fetch_news.get("https://exemple.org/rss")


class Main(unittest.TestCase):
    def run_main(self, prev_items=None, feeds=None):
        tmp = tempfile.mkdtemp()
        out, prev = os.path.join(tmp, "news.json"), os.path.join(tmp, "prev.json")
        if prev_items is not None:
            with open(prev, "w", encoding="utf-8") as f:
                json.dump({"items": prev_items}, f)
        real = fetch_news.collect
        fetch_news.collect = lambda now=None: (feeds or [], {"Google Actualités": "ok"})
        old = sys.argv
        sys.argv = ["fetch_news.py", "--out", out] + (["--prev", prev] if prev_items is not None else [])
        try:
            code = fetch_news.main()
        finally:
            fetch_news.collect, sys.argv = real, old
        return code, out

    def test_nothing_anywhere_writes_nothing(self):
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(out))

    def test_previous_items_survive_an_outage(self):
        fresh = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        prev = [{"title": "Déjà publié : élection", "source": "Le Monde", "url": "https://www.lemonde.fr/a", "published": fresh}]
        code, out = self.run_main(prev_items=prev)
        self.assertEqual(code, 0)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["items"], prev)


if __name__ == "__main__":
    unittest.main()
