"""scripts/import_csv.sh en mode --dry : résumé et garde-fous, sans jamais rien publier."""
import os
import subprocess
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "import_csv.sh")
CSV = ("סמל ועדה,שם ישוב,סמל ישוב,בזב,מצביעים,פסולים,כשרים,מחל,רק,דרך,\n"
       "1,עיר א,10,1000,700,10,690,300,140,250,\n2,עיר ב,20,500,300,0,300,100,80,120,\n")


class ImportCsv(unittest.TestCase):
    def run_script(self, *args, downloads=None):
        env = {**os.environ, "DOWNLOADS": downloads or tempfile.mkdtemp()}
        return subprocess.run(["bash", SCRIPT, *args], capture_output=True, text=True, cwd=ROOT, env=env, input="")

    def test_summary_of_a_cec_file_and_nothing_is_published_in_dry_mode(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "expc.csv")
            open(f, "w", encoding="utf-8").write(CSV)
            r = self.run_script(f, "--dry")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("communes : 2", r.stdout)
        self.assertIn("bulletins valides : 990", r.stdout)
        self.assertIn("rien n'est publié", r.stdout)

    def test_finds_the_latest_cec_file_in_downloads_and_ignores_other_csv(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "autre.csv"), "w").write("a,b\n1,2\n")
            good = os.path.join(d, "expc (3).csv")
            open(good, "w", encoding="utf-8").write(CSV)
            r = self.run_script("--dry", downloads=d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("expc (3).csv", r.stdout)

    def test_a_file_that_is_not_from_the_cec_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "x.csv")
            open(f, "w").write("a,b\n1,2\n")
            r = self.run_script(f, "--dry")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("refusé", r.stderr)

    def test_no_file_found_explains_what_to_do(self):
        r = self.run_script("--dry")
        self.assertEqual(r.returncode, 1)
        self.assertIn("télécharge-le", r.stderr)

    def test_an_empty_count_is_not_published(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "expc.csv")
            open(f, "w", encoding="utf-8").write("סמל ועדה,שם ישוב,סמל ישוב,בזב,מצביעים,פסולים,כשרים,מחל,\n")
            r = self.run_script(f, "--dry")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("aucun bulletin dépouillé", r.stderr)


if __name__ == "__main__":
    unittest.main()
