# CLAUDE.md — IsraPoll

Résultats des élections israéliennes du **27 octobre 2026** (26ᵉ Knesset) : un site statique en trois pages, alimenté par un
collecteur Python/bash. Projet **indépendant et open source** (MIT), non affilié à la Commission électorale centrale (CEC).
Dépôt : <https://github.com/eliejesuran/israpoll> · site : <https://eliejesuran.github.io/israpoll/> (GitHub Pages, branche `main`).

Ce fichier est la mémoire du projet pour les sessions Claude : règles, architecture, exploitation, pièges rencontrés et
**défauts mineurs connus** (section 9). Le `README.md` s'adresse aux visiteurs et contributeurs ; ici, tout ce qu'il faut savoir
avant de toucher au code.

---

## 1. Règles de travail (à respecter à chaque session)

**Intégrité des chiffres**
- **Jamais de chiffre inventé ni d'« à peu près ».** La page n'affiche que des chiffres de la CEC (sièges attribués, ou estimation
  Bader-Ofer sur les voix de la CEC). Le seul repli accepté est le **relais presse** (The Petek), toujours étiqueté « non officiel ».
- **Aucun sondage n'est affiché** (ni d'avant-scrutin, ni sorties des urnes) : décision du propriétaire du projet. Les sorties des urnes ont
  été retirées de `data/manual.json` (28/10).
- Les rattachements de listes à un camp (`PARTIES.bloc`, `GROUPS` de `js/compare.js`) sont une **lecture éditoriale** : toujours
  dire « lecture éditoriale » quand on les affiche. Les verbes de l'analyse restent factuels (« progresse », « recule »), sans
  jugement ni couleur « bon/mauvais » (voir `.delta`).

**Défi anti-bot de la CEC : on ne le contourne pas, et on n'interroge plus son site** (le propriétaire a fait arrêter la lecture le 28/10 ;
`--poll-cec` / `CEC_POLL=1` la réactive). Depuis la fermeture des bureaux, `media26.bechirot.gov.il` et
`votes26.bechirot.gov.il` répondent HTTP 202 à corps vide avec `x-amzn-waf-action: challenge` (AWS WAF) à tout client non-navigateur.
Interdits : usurper un User-Agent de navigateur, résoudre/rejouer le défi, passer par un proxy pour l'éviter. Autorisés : en-tête
honnête, pause croissante (45 s → 10 min, `fetch_cec.py --poll-cec`), import d'un CSV téléchargé **à la main** par un humain, saisie manuelle
des totaux (`scripts/cec_manual.py`), relais presse étiqueté.

**Fuseaux horaires** : toujours préciser. Israël = UTC+2 depuis le 25/10/2026 (heure d'hiver) ; Bruxelles/Paris = UTC+1.
Clôture des bureaux : **22:00 en Israël = 21:00 à Bruxelles = 20:00Z**. Les heures de `manual.json` (`as_of`, participation) sont en
heure d'Israël ; les `*_at` de `live.json` sont en UTC.

**Collaboration**
- **Plusieurs sessions Claude (et le propriétaire) poussent sur `main` en parallèle.** Avant tout `git push` : `git fetch`, lire
  `git log HEAD..origin/main`, `git pull --rebase`. Ne jamais écraser ni `--force` sur `main`. Un commit « fantôme » d'une autre session
  est normal ; le lire (`git show`) avant de réagir.
- Messages de commit en français, descriptifs (le « pourquoi »). Le trailer `Co-Authored-By` suit les consignes de l'environnement de la session ;
  le propriétaire ne le souhaite pas dans certains de ses autres dépôts — en cas de doute, le lui demander.
- **Demander avant d'agir sur le Jetson** (voir §4) : machine de production d'un autre projet de l'utilisateur. Ne jamais toucher à ce que
  cet autre projet y exécute (dossiers, conteneurs).
- Les actions qui publient (push, Pages, déploiement distant) doivent correspondre à une demande explicite.

**Site** : la page ne parle jamais de « blocage », de « défi » ni de ce que le collecteur tente. Elle dit seulement **d'où vient** chaque chiffre
(totaux de la CEC recopiés, fichier de la CEC, relais The Petek « non officiel »).

**Style** : HTML/CSS/JS **sans build ni dépendance** (le propriétaire tient à un site « assez simple »). Textes en français. Pas de
framework, pas de bibliothèque. Scripts classiques (pas de modules ES) : les pages partagent l'espace global.

---

## 2. Architecture

```
CEC ─(totaux recopiés par un humain, ou CSV téléchargé et importé)─┐   (le site de la CEC n'est pas interrogé)
NBC live-blog (participation) ─────────────────────────────────────┤  scripts/fetch_cec.py  ──►  live.json
The Petek (projection de sièges, relais NON officiel) ─────────────┤        ▲ data/manual.json (lu sur `main` à chaque tour)
saisie manuelle des totaux CEC (data/manual.json, clé `cec`) ──────┘        │
                                                                            ▼
scripts/live.sh (boucle) ──push force──► branche orpheline `data` : live.json ──► pages (API GitHub ~1 min, raw 5 min)
flux RSS presse ──► scripts/fetch_news.py ──push force──► branche orpheline `news` : news.json ──► « À lire »
```

| Fichier | Rôle |
|---|---|
| `index.html` | Accueil : hémicycle, simulateur, « À lire », duel Yashar vs BB, sources (les annexes sont dans le menu) |
| `resultats.html` | Annexe : résultat brut de la CEC (chiffres clés, participation, tableau voix/%/sièges) |
| `analyse.html` | 2026 contre 2022 par famille politique |
| `css/site.css` | Tous les styles (thèmes clair/sombre par variables CSS) |
| `js/common.js` | **Cœur partagé** : constantes (`PARTIES`, `BLOCS`, `PACTS`, `CEC`, `PRESS`), `sanitizeLive`, `loadLive`, `derive`, pastille « page actualisée », menu/pied de page injectés (`mountChrome`), thème, `render()`/`refresh()`/`App.start()` |
| `js/seats.js` | Seuil 3,25 % + quotient + Bader-Ofer avec accords de surplus (UMD : navigateur et Node) |
| `js/compare.js` | Comparaison 2022 → 2026 (`GROUPS` = familles et correspondances ; pur, testé) |
| `js/data2022.js` | Résultats officiels 2022 (CEC), somme exacte du fichier par localité |
| `scripts/fetch_cec.py` | Collecteur : participation NBC, relais presse, totaux saisis ou CSV importé, adoption des relevés des autres collecteurs ; avec `--poll-cec` seulement : CSV et HTML de la CEC (sièges), pause anti-bot |
| `scripts/live.sh` | Boucle de collecte + publication `data` et `news` + mise à jour automatique du clone supervisé |
| `scripts/fetch_news.py` | Titres de presse FR (RSS) → `news.json` (titre, média, lien, date uniquement) |
| `scripts/cec_manual.py` | Assistant de saisie manuelle des totaux CEC (clé `cec` de `manual.json`) |
| `deploy/jetson/` | Superviseur (`run.sh`, flock + cron) et installeur du collecteur pour le Jetson |
| `data/manual.json` | Saisies à la main : participation, totaux de la CEC (`cec`), `final`, `final_turnout_est` |
| `data/live.json`, `data/news.json` | **Instantanés statiques périmés**, derniers recours de la page (voir B1) |
| `tests/` | `*.test.mjs` (Node, sans dépendance) et `test_*.py` (unittest) |

### Modèle de la page (`derive()` dans `js/common.js`)
Sources de sièges, par priorité : **`official`** (sièges attribués par la CEC) > **`cec`** (Bader-Ofer sur les voix CEC, y compris saisies à
la main) > **`press`** (relais non officiel) > **`none`** (hémicycle vide). Le relais ne passe devant `cec` que si `press.valid >
totals.valid` (plus de bulletins comptés). Le choix manuel (`state.seatSource`) est respecté tant que la source existe.
`model` = `{ live, manual, totals, lists, sources, chosen, seats, active }` ; `model.seats` = `{ idParti: sièges }` de la source active.

### Pages et rendu
Chaque page déclare `App.start({ id, sections: [[nom, fonction], …], start?() })`. `render()` exécute chaque section dans un
`try/catch` : si l'une échoue, les autres restent affichées et un bandeau (`#appError`) le dit. Le menu et le pied de page sont
**injectés** par `mountChrome` dans `<header id="siteHeader">` / `<footer id="siteFooter">` (le `header` doit rester un enfant direct de
`<body>` pour que `position: sticky` fonctionne).
Toute chaîne dynamique passe par `esc()` ; les URL par `safeUrl()` (http/https seulement) ; le JSON externe par `sanitizeLive` /
`sanitizeNews` (types, bornes, identifiants connus, somme des sièges = 120).

### Données publiées
`live.json` (branche `data`) : `status` (`waiting|counting|final`), `totals`, `votes` (par lettre de vote de la CEC), `official_seats`,
`manual` (copie de `manual.json` + participation automatique), `press`, `stale` (seulement avec `--poll-cec`), `source.fetch` (journal par source),
`collector` (`jetson`/`local`), `checked_at` (dernière vérif) / `updated_at` (dernier changement), `digest`.
La page lit **API GitHub** (`api.github.com/.../contents/live.json?ref=data`, ~1 min, 60 req/h/IP) **et** `raw.githubusercontent.com`
(5 min de cache) et garde la plus récente (`checked_at`) ; une source en retard ne fait jamais reculer la page.

---

## 3. Calculs et choix éditoriaux

- **Sièges** : seuil 3,25 % des bulletins valides ; quotient national ; restes par plus forte moyenne (Bader-Ofer) ; accords de surplus
  déclarés (`PACTS`) : Ensemble–Israël Beiteinou, Yashar–Démocrates, Liste commune–Ra'am, Likoud–Sionisme religieux, Shas–UTJ. Reproduit
  exactement les 120 sièges de 2022 avec l'accord Likoud–RZ (`tests/seats.test.mjs`).
- **Camps** (`PARTIES.bloc`) : Netanyahou = Likoud, Shas, UTJ, Otzma, Sionisme religieux–Zehut, Noam ; Eisenkot = Yashar, Ensemble, Démocrates,
  Israël Beiteinou, Réservistes ; arabes = Liste commune, Ra'am ; autres = Amcha, Public haredi, le reste.
- **Comparaison 2022** (`GROUPS`, `js/compare.js`) : chaque ligne additionne les listes de 2022 qui correspondent à une ou plusieurs
  listes de 2026 (Yesh Atid → Ensemble ; Union nationale → Yashar ; Travaillistes + Meretz → Démocrates ; Hadash–Ta'al + Balad → Liste
  commune ; liste commune RZ–Otzma–Noam → trois listes). Les notes de chaque ligne expliquent les fusions/scissions. Les parts de voix 2026
  sont celles des bulletins **déjà comptés** (partiel) face au résultat final de 2022.
- **Participation** : relevés de la CEC (toutes les ~2 h), lus sur le live-blog NBC (JSON-LD) puis saisis/corrigés dans `manual.json`.
  La comparaison avec 2022 se fait à la **même heure** (`prev2022`), ou avec le total 2022 pour le seul relevé de clôture (22:00).
- **« Dépouillement ≈ X % »** (accueil) : `votants / (inscrits × participation finale estimée)` ; ce n'est **pas** le pourcentage d'urnes
  dépouillées annoncé par la presse (voir B6).

---

## 4. Exploitation

### Où tourne quoi
- **Collecteur de production : le Jetson** de l'utilisateur (réseau interne, IP privée : joignable seulement depuis le même réseau local, pas
  depuis un autre réseau). L'adresse et l'identifiant SSH ne figurent volontairement **pas** dans ce dépôt public : ils sont dans la documentation
  privée de l'utilisateur. Dossier `~/israpoll-collector/` : `run.sh` (superviseur), `deploy_key` (clé de déploiement, **écriture limitée au dépôt
  israpoll**), `known_hosts`, `work/` (clone du dépôt, journal `live.log`, temporaires). Cron : `@reboot` et chaque minute ; `flock` ⇒ un seul
  superviseur. Le superviseur relance `live.sh` chaque heure ; `live.sh` se met à jour seul (`git reset --hard` de `main` toutes les ~5 min, se
  relance si lui-même a changé) : **pousser sur `main` suffit à déployer**.
- La SSH vers le Jetson utilise la clé de l'utilisateur, protégée par une passphrase : elle doit être chargée dans l'agent par **l'utilisateur**
  (`ssh-add`). Claude ne saisit jamais de mot de passe ni de passphrase.
- Le Jetson sert aussi un autre projet : le collecteur est léger (python3 + curl toutes les 30 s, `nice`), sans sudo, et n'écrit presque rien sur la
  carte SD (quelques Ko par relevé).
- Le Mac de l'utilisateur peut lancer la même boucle (`scripts/live.sh`) ; il se met en veille (coupures de session constatées) : préférer le Jetson.

### Commandes utiles
```bash
# état de publication (depuis n'importe où)
gh api "repos/eliejesuran/israpoll/contents/live.json?ref=data" --jq .content | base64 -d | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['collector'],d['status'],d['checked_at'],d['source']['fetch'])"
# sur le Jetson (lecture seule)
ssh <utilisateur>@<ip-du-jetson> 'tail -20 ~/israpoll-collector/work/live.log; ps -eo pid,etimes,cmd | grep "[i]srapoll"; crontab -l'
# arrêter proprement : retirer les 2 lignes `israpoll-collector` du crontab PUIS tuer les PID (pas de `pkill -f` : il se tue lui-même via la commande ssh)
# un relevé à la main / tester sans publier (le site de la CEC n'est interrogé qu'avec --poll-cec)
python3 -I scripts/fetch_cec.py --out /tmp/live.json --manual data/manual.json
# import humain du fichier téléchargé sur le site de la CEC (résumé + confirmation ; --dry pour ne rien publier)
scripts/import_csv.sh
# saisie manuelle des totaux CEC (voir README) puis commit/push
python3 -I scripts/cec_manual.py --as-of 12:30 --eligible … --voters … --valid … likud=… yashar=…
```

### Chiffres de la CEC (le site bloque depuis le soir du scrutin ; lecture arrêtée le 28/10)
1. Le collecteur n'interroge pas le site de la CEC (`source.fetch.csv` : « site de la CEC non interrogé »). Pour essayer quand même : `CEC_POLL=1 scripts/live.sh`
   (journal `pause anti-bot jusqu'à …`, pause 45 s → 10 min).
2. Voie officielle : un humain lit le tableau national dans un navigateur et saisit les totaux (`cec_manual.py`), ou télécharge le CSV (`scripts/import_csv.sh`).
3. Voie non officielle : relais presse (`press`), toujours étiqueté ; la page le préfère aux totaux CEC seulement s'il est plus avancé.
4. Conséquence : **les sièges attribués par la CEC ne sont pas lus** (`parse_html` ne tourne qu'avec `--poll-cec`) ; la page affiche l'estimation Bader-Ofer jusqu'à ce que
   quelqu'un réactive la lecture ou que le site redevienne lisible.

---

## 5. Pièges rencontrés (ne pas les refaire)

- **CORS** : ni la CEC, ni les RSS de presse ne l'autorisent ⇒ un relais est obligatoire. `raw.githubusercontent.com` et `api.github.com` l'autorisent.
- **GitHub Actions** : depuis ses serveurs la CEC répond au défi anti-bot ; et les **exécutions planifiées (`schedule`) sont très irrégulières**
  sur ce dépôt (une seule exécution de `news.yml` en ~20 h, le 28/10 à 12:58Z) ⇒ tout est fait par le collecteur du Jetson, le workflow n'est qu'un filet.
- **Caches** : `raw.githubusercontent.com` = 5 min (la chaîne `?t=` n'y change rien) ; l'API GitHub = 60 s + ETag, **60 requêtes/h/IP** (la page
  s'en détache sous 5 restantes) ; **jsDelivr** : l'API de purge répond `throttled: true` après quelques dizaines d'appels ⇒ abandonné ; GitHub Pages = 10 min (voir B3).
- **systemd-logind `RemoveIPC=yes`** (Ubuntu) : vide `/dev/shm` et `/run/user/…` à la fermeture de la dernière session SSH ⇒ **ne jamais** mettre
  clone, verrous ou logs du collecteur dans `/dev/shm` (c'était la cause de superviseurs en double). Tout vit sous `~/israpoll-collector/work`.
- **`pkill -f` via `ssh`** : la ligne de commande contient le motif ⇒ le shell distant se tue lui-même. Tuer par PID.
- **macOS** : pas de `timeout` (déjà géré), bash 3.2 (tableaux vides sous `set -u` : idiome `${a[@]+"${a[@]}"}`), pas de `sha1sum` (le bloc de mise à
  jour automatique ne s'exécute que sur le clone supervisé du Jetson).
- **Hébergement mutualisé Infomaniak (offre de base, un seul nom d'hôte)** : seuls le FTP **en clair** (21) et HTTPS (443) répondent ; `AUTH TLS` est refusé et le
  port 22 est fermé. **Ne pas retenter un déploiement FTP/FTPS vers cet hébergement** (un déploiement qui enverrait le mot de passe en clair est exclu). Alternatives étudiées,
  non retenues : sous-domaine servi par GitHub Pages (enregistrement DNS `CNAME`), récepteur PHP signé en HTTPS, FTP en clair.
- **`force-push` sur les branches `data` et `news`** : branches orphelines à un seul commit, volontairement (l'historique ne grossit pas) ;
  ne jamais y mettre autre chose que `live.json` / `news.json`.
- **Veille du Mac** : peut couper une session en plein travail ; `caffeinate -i -w <pid>` retient la machine tant que le processus tourne.
- **Heure** : les relevés de la CEC et The Petek sont en heure d'Israël ; The Petek affiche « 27 Oct » même après minuit (libellé erroné de la source).
- **Les listes 2022 et 2026 partagent des lettres de vote** (`ב` = Foyer juif en 2022, Otzma Yehudit en 2026) : `data2022.js` est indexé par lettre
  **de 2022** seulement pour documenter la source ; la logique n'utilise que les identifiants (`likud22`, `likud`…).

---

## 6. Tests

```bash
node tests/seats.test.mjs        # Bader-Ofer : 120 sièges de 2022 reproduits, entrées dégradées
node tests/compare.test.mjs      # camps 2022 (64/46/10), fusions, écarts, pas de double compte
node tests/common.test.mjs       # sanitizeLive + choix de la source des sièges (vm, sans DOM)
python3 -I -m unittest discover tests   # collecteur CEC (site non interrogé par défaut, pause anti-bot avec --poll-cec, pairs, saisie manuelle), relais presse, actualités
python3 -m pyflakes scripts/*.py tests/*.py
```
Pas de test automatisé du rendu : vérifier à la main dans le navigateur (`.claude/launch.json` lance `python3 -m http.server 8765`, dossier
ignoré par git). Modes de démonstration : `?demo=1` (dépouillement partiel simulé), `?demo=final`. Vérifier toujours les **trois pages**, en clair et
en sombre, au format mobile (375 px : pas de défilement horizontal de la page).

---

## 7. Conventions de code

- Tokens CSS dans `:root` (+ variante sombre) ; jamais de couleur « bon/mauvais » pour un parti (`.delta`).
- Nombres en `fr-FR` (`fmt`, `pc`), heures via `Intl` (`hhmmss`, `tz`).
- Chaque section d'une page reçoit son conteneur ; ne pas écrire hors de son propre conteneur.
- Nouveau parti : `PARTIES` (`js/common.js`) **et** `PARTY_LETTERS` (`scripts/fetch_cec.py`) **et**, si besoin, `PRESS_PARTIES` ; un test garde les tables
  alignées. Nouvelle ligne de comparaison : `GROUPS` (`js/compare.js`) + test.
- Les scripts Python n'utilisent que la bibliothèque standard ; hôtes réseau en liste blanche (`allowed*`), redirections comprises, tailles bornées.
- Publier = `git push` sur `main` : Pages se reconstruit en ~1 min ; le Jetson récupère le code en ≤ 5 min.

---

## 8. Idées non réalisées

- Relais sans cache (Worker Cloudflare avec R2) pour passer sous la seconde et lever la limite de 60 req/h de l'API GitHub.
- Test de rendu automatisé (jsdom/Playwright) ; vérification visuelle mobile en intégration continue.
- Résultats par localité (carte), évolution du comptage dans le temps (historique `live.json` dans une branche dédiée).
- Une fois les résultats définitifs publiés (Reshumot, d'ici le 4 novembre 2026) : `manual.final = true`, figer le site, archiver `live.json`.

---

## 9. Défauts mineurs connus (documentés, non corrigés)

Relecture complète du 28/10/2026. **Corrigés** : (1) le fil « À lire » restait figé (le cron de GitHub Actions ne part jamais) — le collecteur
le rafraîchit maintenant lui-même, et la page affiche l'âge du relevé avec un avertissement au-delà de 45 min ; (2) la comparaison de participation
confrontait un relevé de 14:00 au total final de 2022 — elle utilise la même heure de 2022 (`turnoutRef`) ; (3) débordement horizontal de l'accueil
sur mobile (`<code>` long) ; (4) CSS mort de la section supprimée, variables et imports inutilisés ; (5) preset « Union nationale » ambigu avec la liste
de 2022 (renommé) ; (6) tests de cohérence page/collecteur repointés sur `js/common.js`. **Restent** (aucun n'empêche d'afficher des chiffres justes) :

| # | Où | Défaut | Impact / piste |
|---|---|---|---|
| B1 | `data/live.json`, `data/news.json` | Instantanés statiques périmés (27/10 16:26Z et 28/10 06:11Z) servis en **dernier recours** si l'API GitHub **et** `raw` échouent | La page afficherait un état ancien (le chip « dernier relevé » le montre en orange). Piste : un job qui recopie `data`/`news` dans `main` à chaque heure, ou supprimer ces replis |
| B2 | `.github/workflows/news.yml` | Le déclencheur `schedule` ne part que très rarement (voir §5) et double le travail du collecteur (deux force-push sur `news`) | Inoffensif : filet de secours. Piste : retirer `schedule`, garder `workflow_dispatch` |
| B3 | `index.html`, `resultats.html`, `analyse.html` | Pas de version dans les URL de `css/site.css` et `js/*.js` ; GitHub Pages met 10 min en cache | Quelques minutes de décalage HTML/JS après un déploiement. Piste : `?v=<date>` à chaque modification |
| B4 | menu (`.nav`) | Sur écran étroit le menu défile horizontalement ; « Sources » est partiellement coupé | Cosmétique ; piste : menu repliable sous 700 px |
| B5 | `index.html` | Le simulateur ne propose que les partis qui ont ≥ 1 siège dans la source active ; un parti à 0 siège ne peut pas être coché | Voulu, mais un lien partagé contenant un parti à 0 siège l'ignore sans message |
| B6 | `common.js` (`derive`) | `cec.share` (« ≈ X % du vote attendu ») vient de la participation finale estimée, pas des urnes dépouillées | Écart avec le « 76,89 % des urnes » de la presse ; libellé à clarifier ou remplacer par `press.counted_pct` quand disponible |
| B7 | `fetch_cec.py` (`parse_html`) | Écrit pour la mise en page 2022 et une heuristique 2026 **jamais vue en conditions réelles** ; ne tourne plus qu'avec `--poll-cec` | Les sièges officiels de la CEC ne sont lus que si la lecture est réactivée et la page conforme ; sinon estimation Bader-Ofer (pas de saisie manuelle des sièges officiels) |
| B8 | `fetch_cec.py` (`parse_turnout`) | Dépend de la structure JSON-LD du live-blog NBC ; la dernière mise à jour de ce live-blog précède la clôture | En cas d'échec : saisie manuelle de la participation (`manual.json`) |
| B9 | `fetch_cec.py` (`parse_press`) | Lit le **texte** de la page The Petek (aucune API) ; un changement de mise en page rejette le relevé | Le dernier relevé reste affiché ; la source est facultative |
| B10 | `fetch_news.py` | Liste blanche `MEDIA` tenue à la main : un média absent est écarté sans message | Ajouter son nom tel qu'il apparaît dans Google Actualités |
| B11 | `live.sh` | Le relevé des actualités (≈ 5–20 s) s'exécute dans la boucle principale, une fois par ~10 min | Un tour de collecte CEC est retardé d'autant ; piste : sous-processus en arrière-plan |
| B12 | `js/compare.js` | La note « fusion annoncée avec le Likoud » (Nouvel Espoir) s'appuie sur une source secondaire (Wikipédia, juillet 2026) | À revérifier avec la liste officielle des 38 listes |
| B13 | `analyse.html` | Les parts de voix 2026 sont partielles (urnes déjà comptées) face au résultat final 2022 ; les urnes restantes (soldats, diplomates…) peuvent déplacer quelques sièges | Signalé par un bandeau ; pas de correction statistique |
| B14 | rendu | Aucun test automatisé des fonctions `render*` (seulement `derive`, `sanitizeLive`, `Compare`) | Vérification manuelle des trois pages à chaque changement |
| B15 | `deploy/jetson/run.sh` | La clé de déploiement donne l'écriture sur **tout** le dépôt (pas seulement les branches `data`/`news`) | Limite de GitHub (une clé de déploiement = un dépôt) ; à révoquer après le scrutin (*Settings → Deploy keys*) |

---

## 10. Journal des décisions (extraits)

- 27/10 : collecteur sur GitHub Actions abandonné (défi anti-bot) ; jsDelivr abandonné (purge throttlée) ; API GitHub + `raw` retenus.
- 27/10 soir : défi anti-bot sur tous les clients ⇒ pause croissante, import humain, saisie manuelle, relais presse étiqueté (accord du propriétaire).
- 28/10 matin : sondages et sorties des urnes retirés de la page (décision du propriétaire) ; fil « À lire » ajouté.
- 28/10 : lecture automatique du site de la CEC **arrêtée** à la demande du propriétaire (`--poll-cec` / `CEC_POLL=1` pour la réactiver) ; la page ne mentionne plus
  de blocage, elle indique seulement la source de chaque chiffre ; `exit_polls` supprimé de `manual.json`.
- 28/10 : hébergement sur le domaine personnel de l'utilisateur (déploiement par Action GitHub) **abandonné** : l'offre Infomaniak de base n'expose que le FTP
  en clair (port 21) et HTTPS (443) — ni FTPS (`AUTH TLS` → « 500 not implemented »), ni SFTP/SSH (port 22 fermé). Le site reste sur GitHub Pages ; l'utilisateur gère
  lui-même le `.htaccess` de son domaine. Voir §5.
- 28/10 : section « Blocs pressentis » supprimée ; « Résultat brut » déplacé en annexe ; page « 2026 contre 2022 » ; code commun extrait
  (`css/site.css`, `js/common.js`) ; relevé des actualités transféré au collecteur (le cron de GitHub Actions ne part pas).
