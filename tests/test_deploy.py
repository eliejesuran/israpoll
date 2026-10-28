"""Tests du déploiement FTPS (scripts/deploy_ftp.sh) avec un faux `curl` : aucun réseau, aucun vrai serveur."""
import glob
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "deploy_ftp.sh")

SHIM = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CURL_LOG"
prev=""
for a in "$@"; do
  [ "$prev" = "-K" ] && cat "$a" >> "$CURL_CFG_LOG"
  prev="$a"
done
last="${@: -1}"
case "$last" in
  https://example.test/israpoll/*)
    path="${last#https://example.test/israpoll/}"; path="${path%%\?*}"
    if [ -n "${SHIM_STALE:-}" ]; then echo "version périmée"; else cat "$REPO/$path"; fi ;;
esac
exit "${SHIM_EXIT:-0}"
"""


class DeployFtp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.mkdir(os.path.join(self.tmp, "bin"))
        shim = os.path.join(self.tmp, "bin", "curl")
        with open(shim, "w", encoding="utf-8") as f:
            f.write(SHIM)
        os.chmod(shim, os.stat(shim).st_mode | stat.S_IEXEC)
        self.log, self.cfglog = os.path.join(self.tmp, "curl.log"), os.path.join(self.tmp, "cfg.log")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_script(self, **extra):
        env = {"PATH": os.path.join(self.tmp, "bin") + os.pathsep + os.environ["PATH"], "CURL_LOG": self.log, "CURL_CFG_LOG": self.cfglog,
               "REPO": ROOT, "FTP_HOST": "ftp.example.test", "FTP_USER": "elie", "FTP_PASSWORD": "s3cr3t",
               "FTP_PATH": "/sites/eliejesuran.be/israpoll/", "VERIFY_RETRIES": "1", "VERIFY_DELAY": "0"}
        env.update(extra)
        return subprocess.run(["bash", SCRIPT], env=env, capture_output=True, text=True, cwd=ROOT)

    def calls(self):
        with open(self.log, encoding="utf-8") as f:
            return f.read().splitlines()

    def test_missing_variable_is_refused_before_any_request(self):
        r = self.run_script(FTP_PASSWORD="")
        self.assertEqual(r.returncode, 2)
        self.assertIn("FTP_PASSWORD", r.stderr)
        self.assertFalse(os.path.exists(self.log))

    def test_host_is_cleaned_and_hostile_values_are_refused(self):
        # un « ftp://hôte/dossier » ou une valeur collée avec des espaces/retours à la ligne est ramené(e) à l'hôte seul
        r = self.run_script(FTP_HOST="ftp://ftp.example.test/israpoll\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("seul le nom d'hôte est utilisé", r.stderr)
        ups = [c for c in self.calls() if " -T " in c]
        self.assertTrue(all("ftp://ftp.example.test/sites/eliejesuran.be/israpoll/" in c for c in ups))
        os.remove(self.log)
        self.assertEqual(self.run_script(FTP_HOST="ftp.example.test:21").returncode, 0)          # port explicite accepté
        os.remove(self.log)
        for bad in ("ftp.example.test;rm -rf", "$(id).example.test", "ftp.example.test|x", "ftp.example.test:99999999"):
            self.assertEqual(self.run_script(FTP_HOST=bad).returncode, 2, bad)
            self.assertFalse(os.path.exists(self.log))

    def test_uploads_are_encrypted_ordered_and_keep_the_password_off_the_command_line(self):
        r = self.run_script(SITE_URL="https://example.test/israpoll")
        self.assertEqual(r.returncode, 0, r.stderr)
        ups = [c for c in self.calls() if " -T " in c]
        self.assertTrue(all("--ssl-reqd" in c for c in ups))                       # FTPS obligatoire
        self.assertTrue(all("ftp://ftp.example.test/sites/eliejesuran.be/israpoll/" in c for c in ups))
        self.assertFalse(any("s3cr3t" in c for c in self.calls()))                  # le mot de passe n'est jamais un argument
        names = [re.search(r"-T (\S+)", c).group(1) for c in ups]
        self.assertEqual(names[0], "deploy/eliejesuran/.htaccess")
        self.assertEqual(names[-1], "index.html")                                    # les pages HTML partent en dernier
        self.assertLess(names.index("js/common.js"), names.index("index.html"))
        self.assertIn("css/site.css", names)
        with open(self.cfglog, encoding="utf-8") as f:
            self.assertIn('user = "elie:s3cr3t"', f.read())
        self.assertIn("vérifié : https://example.test/israpoll/index.html", r.stdout)

    def test_special_characters_in_the_password_are_escaped(self):
        r = self.run_script(FTP_PASSWORD='a"b\\c')
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.cfglog, encoding="utf-8") as f:
            self.assertIn('user = "elie:a\\"b\\\\c"', f.read())

    def test_a_failed_upload_stops_with_curls_code_and_a_plain_explanation(self):
        r = self.run_script(SHIM_EXIT="64")
        self.assertEqual(r.returncode, 64)
        self.assertIn("TLS explicite", r.stderr)                 # code 64 : le serveur refuse le FTP chiffré
        self.assertEqual(len(self.calls()), 1)                   # on s'arrête au premier échec
        self.assertNotIn("s3cr3t", r.stderr + r.stdout)
        self.assertEqual(self.run_script(SHIM_EXIT="67").returncode, 67)

    def test_tls_can_only_be_switched_off_explicitly(self):
        self.run_script(FTP_TLS="off")
        self.assertFalse(any("--ssl-reqd" in c for c in self.calls() if " -T " in c))

    def test_a_stale_or_different_published_site_fails_the_job(self):
        r = self.run_script(SITE_URL="https://example.test/israpoll", SHIM_STALE="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("vérification échouée", r.stderr)

    def test_every_local_reference_of_the_pages_is_deployed(self):
        """Ajouter un script à une page sans l'ajouter à la liste du déploiement casserait le site publié."""
        with open(SCRIPT, encoding="utf-8") as f:
            text = f.read()
        listed = set(re.findall(r"([\w./-]+\.(?:css|js|html))", re.search(r"ASSETS=\((.*?)\)", text).group(1) + " " + re.search(r"PAGES=\((.*?)\)", text).group(1)))
        pages = {os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "*.html"))}
        refs = set(pages)
        for page in pages:
            with open(os.path.join(ROOT, page), encoding="utf-8") as f:
                html = f.read()
            refs |= set(re.findall(r'(?:src|href)="((?:js|css)/[^"?#]+)"', html))
        self.assertEqual(refs, listed, "écart entre les fichiers référencés par les pages et la liste du déploiement")
        for f in listed:
            self.assertTrue(os.path.exists(os.path.join(ROOT, f)), f)

    def test_workflow_runs_when_site_files_change_and_skips_when_secrets_are_missing(self):
        with open(os.path.join(ROOT, ".github", "workflows", "deploy-eliejesuran.yml"), encoding="utf-8") as f:
            wf = f.read()
        for path in ('"index.html"', '"resultats.html"', '"analyse.html"', '"css/**"', '"js/**"', '"scripts/deploy_ftp.sh"', '"scripts/ftp_diagnose.sh"'):
            self.assertIn(path, wf)
        self.assertIn("ready=false", wf)                      # sans secrets : rien n'est déployé, rien n'échoue
        self.assertIn("contents: read", wf)                   # jeton en lecture seule


if __name__ == "__main__":
    unittest.main()
