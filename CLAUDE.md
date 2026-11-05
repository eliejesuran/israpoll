# CLAUDE.md — IsraPoll, gabarit de suivi des résultats d'une élection

Site statique (hémicycle, simulateur de coalition, résultat brut, comparaison avec l'élection précédente, fil de presse) alimenté par un
collecteur Python/bash. **Première instance : les élections israéliennes du 27 octobre 2026** (26ᵉ Knesset, scrutin terminé).
Projet **indépendant et open source** (MIT), non affilié à l'autorité électorale.
Dépôt : <https://github.com/eliejesuran/israpoll> · site : <https://eliejesuran.github.io/israpoll/> (GitHub Pages, branche `main`).

**Comment lire ce fichier**
- *Adapter l'outil à une autre élection ou un autre pays* → lis §1 (règles, valables pour toute instance), puis **§3, ton point d'entrée**.
- *Intervenir sur l'instance Israël 2026* → §2, §4 à §9 et l'annexe A.
- Le `README.md` s'adresse aux visiteurs et contributeurs ; ici : règles, architecture, mode d'emploi de l'adaptation, pièges, défauts connus.

**Vocabulaire** — *instance* : un dépôt configuré pour un scrutin. *Autorité* : l'organisme qui publie les résultats officiels (Israël : la
Commission électorale centrale, « CEC », ועדת הבחירות המרכזית). *Clé de bulletin* : l'identifiant que la source officielle donne à une liste
(Israël : les lettres de vote hébraïques, champ `letters`). Le code garde le vocabulaire israélien (`cec`, `letters`, `prev2022`, `official_seats`,
`Bader-Ofer`) : ces noms sont un **contrat interne**, pas une vérité sur la nouvelle instance (voir §3.4, phase 1).

---

## 1. Règles permanentes (toute instance)

**Intégrité des chiffres**
- **Jamais de chiffre inventé ni d'« à peu près ».** La page n'affiche que : (a) des chiffres de l'autorité ; (b) des calculs reproductibles faits sur
  ses voix (sièges estimés, étiquetés « calcul »/« est. ») ; (c) une source **non officielle** explicitement étiquetée « non officiel » et citée (lien,
  plus la révision pour un wiki). Israël 2026 : Wikipédia (base par défaut depuis le 28/10) et le relais presse The Petek. Pour une autre instance,
  la liste des sources non officielles se valide avec le propriétaire (§3.1).
- **Mieux vaut ne rien afficher qu'un chiffre faux.** Tout parseur est strict : liste inconnue, somme des listes ≠ bulletins valides (> 0,5 %), sièges
  ≠ total, pourcentage absurde ⇒ relevé rejeté, le dernier bon relevé reste. On ne desserre jamais un contrôle pour « faire passer » un relevé : on
  corrige la cause. Un relevé en retard ne fait jamais reculer la page ; une chute de bulletins valides (> 2 % pour les sources non officielles, > 10 %
  pour l'autorité) est écartée.
- **Test de référence** : le calcul des sièges doit reproduire *exactement* les sièges officiels de l'élection précédente avant toute mise en ligne
  (Israël : les 120 sièges de 2022, `tests/seats.test.mjs`). Un parseur se teste sur des **fichiers réels enregistrés** de cette élection.
- **Aucun sondage affiché** (ni d'avant-scrutin, ni sorties des urnes) : décision du propriétaire (Israël, 28/10/2026). Valeur par défaut des nouvelles
  instances ; ne la lever que sur sa demande explicite.
- Les rattachements de listes à un camp ou une famille (`PARTIES.bloc`, `GROUPS` de `js/compare.js`) sont une **lecture éditoriale** : toujours dire
  « lecture éditoriale » quand on les affiche. Verbes factuels (« progresse », « recule »), jamais de couleur « bon/mauvais » (voir `.delta`).
- La page ne parle jamais de « blocage », de « défi » ni de ce que le collecteur tente. Elle dit seulement **d'où vient** chaque chiffre.
- **Indépendance** : ne jamais se faire passer pour l'autorité (nom, logo, domaine) ; le pied de page dit « non affilié ». Vérifier la licence de
  chaque source (Wikipédia : CC BY-SA 4.0 ⇒ attribuer + permalien de la révision).

**Respect des sources (anti-bot, robots.txt, conditions d'usage)**
- Un défi anti-bot (WAF, CAPTCHA, JavaScript obligatoire) **ne se contourne pas**. Interdits : usurper un User-Agent de navigateur, résoudre ou rejouer le
  défi, passer par un proxy pour l'éviter. Autorisés : en-tête honnête (nom du projet + URL du dépôt, **jamais d'adresse e-mail personnelle**), pause
  croissante (45 s → 10 min), import d'un fichier téléchargé **à la main** par un humain, saisie manuelle des totaux, relais presse étiqueté.
- Respecter `robots.txt` et les conditions d'utilisation ; requêtes espacées ; hôtes en liste blanche (redirections comprises) ; tailles bornées.
- Lire automatiquement le site d'une autorité est **une décision à prendre avec le propriétaire** (§3.1). Si l'autorité offre une API ou des données
  ouvertes, c'est la voie normale. Israël 2026 : depuis la fermeture des bureaux, `media26.bechirot.gov.il` et `votes26.bechirot.gov.il` répondent HTTP
  202 à corps vide avec `x-amzn-waf-action: challenge` (AWS WAF) ; le propriétaire a fait arrêter la lecture le 28/10 (`--poll-cec` / `CEC_POLL=1` la réactive).

**Fuseaux horaires** : toujours préciser le fuseau quand on écrit une heure (heure locale du pays + équivalent UTC ou Bruxelles/Paris). Les heures de
`manual.json` (`as_of`, participation) sont en **heure locale du pays** ; les `*_at` de `live.json` sont en **UTC**. Vérifier les changements d'heure
autour du scrutin. Israël 2026 : UTC+2 depuis le 25/10 ; Bruxelles/Paris UTC+1 ; clôture **22:00 en Israël = 21:00 à Bruxelles = 20:00Z**.

**Collaboration**
- **Plusieurs sessions Claude (et le propriétaire) poussent sur `main` en parallèle.** Avant tout `git push` : `git fetch`, lire `git log HEAD..origin/main`,
  `git pull --rebase`. Jamais de `--force` sur `main`. Un commit « fantôme » d'une autre session est normal : le lire (`git show`) avant de réagir.
- Messages de commit en français, descriptifs (le « pourquoi »). Le trailer `Co-Authored-By` suit les consignes de l'environnement de la session ; le
  propriétaire ne le souhaite pas dans certains de ses autres dépôts — en cas de doute, le lui demander.
- **Demander avant d'agir sur le Jetson** (§A.3) : machine de production d'un autre projet de l'utilisateur. Ne jamais toucher à ce que cet autre projet y exécute.
- Les actions qui publient (push, Pages, déploiement distant, création de dépôt, clé de déploiement) doivent correspondre à une demande explicite.
- Claude ne saisit jamais de mot de passe ni de passphrase (la clé SSH du propriétaire est chargée par **lui** dans l'agent, `ssh-add`).

**Style** : HTML/CSS/JS **sans build ni dépendance** (le propriétaire tient à un site « assez simple »). Textes en français par défaut. Pas de framework,
pas de bibliothèque. Scripts classiques (pas de modules ES) : les pages partagent l'espace global.

---

## 2. Architecture et contrat de données

```
Autorité (totaux recopiés par un humain, fichier téléchargé puis importé ; API/données ouvertes si autorisé) ─┐
Wikipédia (API MediaWiki : voix par liste, non officiel) ────────────────────────────────────────────────────┤
Participation (live-blog de presse relayant les relevés de l'autorité) ──────────────────────────────────────┤  scripts/fetch_cec.py ──► live.json
Relais presse (projection de sièges, NON officiel) ──────────────────────────────────────────────────────────┤        ▲ data/manual.json (lu sur `main` à chaque tour)
saisie manuelle des totaux (data/manual.json, clé `cec`) ────────────────────────────────────────────────────┘        │
                                                                                                                      ▼
scripts/live.sh (boucle) ──push force──► branche orpheline `data` : live.json ──► pages (API GitHub ~1 min, raw 5 min)
flux RSS presse ──► scripts/fetch_news.py ──push force──► branche orpheline `news` : news.json ──► « À lire »
```

La colonne **Adaptation** dit l'ampleur du travail pour une nouvelle instance (détail ligne par ligne : §3.3).

| Fichier | Rôle | Adaptation |
|---|---|---|
| `index.html` | Accueil : hémicycle, simulateur, « À lire », duel, sources (annexes dans le menu) | forte (textes, duel, presets) |
| `resultats.html` | Annexe : résultat brut (chiffres clés, participation, tableau voix/%/sièges) | moyenne (textes, seuil) |
| `analyse.html` | Élection courante contre la précédente, par famille politique | forte (ou à supprimer) |
| `css/site.css` | Tous les styles (thèmes clair/sombre par variables CSS) | faible (couleurs, polices) |
| `js/common.js` | **Cœur partagé** : constantes, `sanitizeLive`, `loadLive`, `derive`, pastille « page actualisée », `mountChrome`, thème, `render()`/`refresh()`/`App.start()` | forte (constantes), le reste est à garder |
| `js/seats.js` | Seuil + quotient + plus forte moyenne avec accords de surplus (UMD : navigateur et Node) | selon le système électoral |
| `js/compare.js` | Comparaison avec l'élection précédente (`GROUPS` = familles et correspondances ; pur, testé) | forte (`GROUPS`) |
| `js/data2022.js` | Résultats officiels de l'élection précédente (somme exacte du fichier par localité) | totale (nouvelles données) |
| `scripts/fetch_cec.py` | Collecteur : un adaptateur par source (`parse_*`), validations (`sane`), assemblage pur (`build`) | forte (adaptateurs), `build` à garder |
| `scripts/live.sh` | Boucle de collecte + publication `data` et `news` + mise à jour automatique du clone supervisé | faible (noms) |
| `scripts/fetch_news.py` | Titres de presse (RSS) → `news.json` (titre, média, lien, date uniquement) | moyenne (langue, pays, médias) |
| `scripts/cec_manual.py`, `scripts/import_csv.sh` | Saisie manuelle des totaux ; import d'un fichier téléchargé à la main | moyenne (clés, en-tête) |
| `deploy/jetson/` | Superviseur (`run.sh`, flock + cron) et installeur du collecteur | faible (noms, dépôt) |
| `data/manual.json` | Saisies à la main : participation, totaux de l'autorité (`cec`), `final`, `final_turnout_est` | à réécrire |
| `data/live.json`, `data/news.json` | **Instantanés statiques périmés**, derniers recours de la page (B1) | à vider |
| `tests/` | `*.test.mjs` (Node, sans dépendance) et `test_*.py` (unittest) | à suivre le code |

### Contrat de données `live.json` (branche `data`) — c'est l'interface collecteur ⇄ pages
`schema`, `status` (`waiting|counting|final`), `totals` (`eligible`, `voters`, `valid`, `invalid`), `votes` (voix par clé de bulletin), `names`,
`official_seats` (seulement si l'autorité a attribué les sièges et que leur somme = total), `manual` (copie de `manual.json` + participation
automatique), `press` (projection non officielle), `wiki` (voix des listes suivies + `others`, `valid`, `invalid`, `eligible`, `counted_pct`, `as_of`,
`revid`), `stale` et `blocked` (seulement avec `--poll-cec`), `source.fetch` (journal par source), `collector`, `checked_at` (dernière vérif, UTC) /
`updated_at` (dernier changement), `digest` (empreinte de ce qui compte ; ne dépend ni de `fetched_at` ni de `revid`).
**En adaptant, on change les adaptateurs, pas le contrat** : `build()`, `sanitizeLive` et `derive()` restent la colonne vertébrale. Un changement de
forme du contrat (ex. voix par circonscription) incrémente `schema` et se fait en dernier recours (§3.2).

La page lit **API GitHub** (`api.github.com/.../contents/live.json?ref=data`, ~1 min, 60 req/h/IP) **et** `raw.githubusercontent.com` (5 min de cache) et
garde la plus récente (`checked_at`) ; une source en retard ne fait jamais reculer la page. `data/live.json` (statique) ne sert que si les deux échouent.

### Modèle de la page (`derive()` dans `js/common.js`)
Sources de sièges, par priorité : **`official`** (sièges attribués par l'autorité) > **`wiki`** (calcul sur les voix de l'article Wikipédia, non officiel ;
**base par défaut** tant que `wiki.valid >= totals.valid` de l'autorité) > **`cec`** (calcul sur les voix de l'autorité, y compris saisies à la main) >
**`press`** (relais non officiel) > **`none`** (hémicycle vide). Le relais ne passe devant la base que s'il a plus de bulletins valides. Chaque source porte
ses `links` (permalien de la révision Wikipédia + autorité) que les pages affichent tels quels. Tableau, chiffres clés et analyse lisent
`model.totals`/`model.lists` (ceux de l'autorité, sauf si `wiki` est choisie ET strictement plus avancée : `model.voteSource`) ; les petites listes de
Wikipédia y sont regroupées en « Autres listes » (`x_others`). Le choix manuel (`state.seatSource`) est respecté tant que la source existe.
`model` = `{ live, manual, totals, lists, sources, chosen, seats, active }` ; `model.seats` = `{ idParti: sièges }` de la source active.

### Pages et rendu
Chaque page déclare `App.start({ id, sections: [[nom, fonction], …], start?() })`. `render()` exécute chaque section dans un `try/catch` : si l'une échoue,
les autres restent affichées et un bandeau (`#appError`) le dit. Menu et pied de page sont **injectés** par `mountChrome` dans `<header id="siteHeader">` /
`<footer id="siteFooter">` (le `header` doit rester un enfant direct de `<body>` pour que `position: sticky` fonctionne). Toute chaîne dynamique passe par
`esc()` ; les URL par `safeUrl()` (http/https seulement) ; le JSON externe par `sanitizeLive` / `sanitizeNews` (types, bornes, identifiants connus, somme des sièges).

---

## 3. Adapter l'outil à une nouvelle élection (point d'entrée)

**Principe** : on remplace les *données* et les *règles du scrutin* (couches basses), on conserve le *pipeline* (collecte → branche `data` → page) et ses
garde-fous, puis on réécrit les *textes*. Ne casse jamais le pipeline pour « simplifier » : c'est ce qui rend les chiffres fiables.

### 3.1 Cadrer avec le propriétaire (avant d'écrire du code)
Poser ces questions (outil de question interactive, une seule salve) ; ne pas demander ce qu'une source ou une convention tranche déjà.
1. **Quel scrutin ?** Pays, type (législatives, présidentielle, référendum…), date, nombre de tours, **système** (§3.2).
2. **Langue et public** du site (français par défaut). Les textes sont en dur dans le HTML/JS : pas de couche i18n, pas de RTL (§3.4, phase 6).
3. **Nouveau dépôt ou même dépôt ?** Par défaut **nouveau dépôt** (copie, nouveau nom, nouvelles Pages) : les branches `data`/`news`, la clé de déploiement
   et le site sont par dépôt, et l'instance Israël reste en archive. Demander le nom du projet et du dépôt.
4. **Lecture automatique du site de l'autorité** : autorisée, ou saisie/import à la main (§1) ?
5. **Sources non officielles** acceptées (Wikipédia ? relais presse ? lesquels ?) ; **aucun sondage** (défaut) ?
6. **Lecture éditoriale** des camps/familles : souhaitée ? Qui la valide ?
7. **Où tourne le collecteur** (machine, clé de déploiement) ?
8. **Élection précédente comparable** (pour `analyse.html`) : laquelle ? Sinon, retirer la page.

### 3.2 Quel type de scrutin ? Ce qui se réutilise
Le code suppose : **une liste nationale unique, un nombre fixe de sièges, un seuil, une formule de répartition, des camps.** Hors de ce cadre, le gros
du travail se déplace des constantes vers le modèle.

| Scrutin | Réutilisable tel quel | À refaire |
|---|---|---|
| **Proportionnelle nationale à liste unique**, seuil, quotient/plus forte moyenne (cas d'Israël) | Tout le pipeline, hémicycle, simulateur (majorité = ⌊total/2⌋ + 1), comparaison, participation, news | Paramètres (`total`, `threshold`), listes, parseurs ; autre formule : option `method` dans `Seats.allocate` (D'Hondt, Sainte-Laguë, plus fort reste) + test de référence |
| **Proportionnelle par circonscriptions** | Pipeline, thème, menu, participation, news | `votes` devient `votes[circonscription][liste]` (⇒ `schema` + 1), répartition par circonscription puis compensation éventuelle ; page de résultats ; gros chantier à faire valider |
| **Uninominal par circonscription** (ex. Royaume-Uni) | Pipeline, hémicycle (alimenté par les sièges proclamés), simulateur (somme de sièges), thème | Pas de formule : `Seats` inutile, les sièges sont des résultats ; `derive` ne calcule plus, il lit `official_seats` ; voix nationales à titre d'information |
| **Présidentielle** (1 ou 2 tours) | Collecteur, `totals`/`votes`, `sanitizeLive`, sources, rafraîchissement, participation, news, thème | Candidats à la place des listes ; plus de sièges ni d'hémicycle (barres, jauge de 50 % + 1 des suffrages exprimés) ; simulateur remplacé par des reports de voix ou supprimé ; 2ᵉ tour : le 1ᵉʳ sert de « précédent » |
| **Référendum** | Idem présidentielle | Deux « listes » (oui/non) |
| **Mixte** (deux votes) | Pipeline | Combine les cas 1 et 3 : hors périmètre sans nouvelle conception |

### 3.3 Inventaire des points d'adaptation (références par symbole : les numéros de ligne dérivent)
| Où | Ce que ça porte | Valeur Israël 2026 |
|---|---|---|
| `js/common.js` · `REPO`, `LIVE_SOURCES` | dépôt qui héberge les branches `data`/`news` | `eliejesuran/israpoll` |
| · `POLLS_CLOSE`, `FINAL_BY` | clôture des bureaux (instant UTC) ; date limite de proclamation | `2026-10-27T20:00:00Z` ; « 4 novembre 2026 » |
| · `CEC`, `PRESS`, `WIKI` | liens fixes vers l'autorité, le relais, l'article (jamais ceux du JSON) | bechirot.gov.il, The Petek, `2026_Israeli_legislative_election` |
| · `BLOCS`, `BLOC_ORDER`, `PARTIES`, `MINOR`, `PACTS` | camps (éditorial) ; listes `{id, fr, he, letters, leader, bloc, color}` dans l'ordre de l'hémicycle ; petites listes nommées ; accords de surplus | 4 camps, 15 listes, 5 accords |
| · `sanitizeLive` | bornes en dur : sièges officiels `=== 120`, presse `<= 120`, `wiki` ≥ 10 listes connues, `final_turnout_est` 20–100 | 120 |
| · `derive` | `turnRef` par défaut (68 %), libellés de sources, règle de la base par défaut | 68 % |
| · `phaseInfo`, `sourceNow`, `renderFoot`, `mountChrome`, `NAV` | libellés d'état, « heure d'Israël », liens du pied de page, marque « IsraPoll » + logo SVG | — |
| · `makeDemo`, `DEMO_SEATS` | mode `?demo=` : clés de bulletin et sièges inventés (toujours étiqueté « DÉMO — chiffres simulés ») | — |
| · `nf`, `pc`, `tz`, `hhmmss` | locale `fr-FR` | — |
| `js/seats.js` | `TOTAL`, `THRESHOLD`, méthode (quotient national + Bader-Ofer), accords de surplus | 120 ; 3,25 % |
| `js/compare.js` | `GROUPS` (familles → lignes → `from`/`to`/`note`), `TOTAL_SEATS`, note « Autres listes » | 3 familles, 11 lignes |
| `js/data2022.js` | `RESULTS_2022` : `election`, `source`, `totals`, `lists` `{id, fr, votes, seats}` par clé de bulletin, `otherVotes` | 25ᵉ Knesset, 1ᵉʳ nov. 2022 |
| `scripts/fetch_cec.py` · constantes | `CSV_URL`, `HTML_URL`, `TURNOUT_URL`, `PRESS_URL`, `WIKI_API/PAGE`, `*_HOSTS`, `*_SOURCE`, `UA`/`WIKI_UA`, `PRESS_PARTIES`, `WIKI_PARTIES`, `WIKI_REQUIRED`, `PARTY_LETTERS`, `KNOWN_LETTERS`, `META_COLS`, `WAITING_MARK` | URLs `*26.bechirot.gov.il`, en-têtes CSV hébreux |
| · parseurs | `parse_csv`, `parse_html`, `parse_turnout` (phrases NBC, « Central Elections Committee », plage 7–22 h, « 2022 »), `parse_press`, `parse_wiki` (modèle `{{Election results}}`, date « October 2026 »), `build` (`== 120`, nom de l'autorité) | un parseur par format de source |
| `scripts/cec_manual.py`, `scripts/import_csv.sh` | assistants de saisie/import ; l'import reconnaît le fichier à l'en-tête CSV `כשרים` | clé `cec` de `manual.json` |
| `scripts/fetch_news.py` | `GOOGLE_QUERY`, `FEEDS`, `HOSTS`, `MEDIA`, `ALIASES`, regex `ISRAEL` et `ELECTION` (pays, langue) | presse francophone |
| `scripts/live.sh`, `deploy/jetson/*`, `.github/workflows/news.yml` | `SUPERVISED` (chemin `*/israpoll-collector/work/repo`), verrou `israpoll-live.lock`, dépôt dans `run.sh`/`install.sh`, nom du workflow | `israpoll-collector` |
| `data/manual.json` | `turnout` (heures locales + `prev2022`), `final_turnout_est`, `cec`, `final` | — |
| `index.html` | `<title>`/méta/og, `lang`, polices (Heebo = hébreu), favicon, `aria-label` de l'hémicycle, `#steps` (déroulé), `PRESETS`, `DUEL` + `renderDuel`, majorité **61** et total **120** en dur, `NEWS_SEARCH`, bloc « Sources et méthode » | duel Yashar–BB |
| `resultats.html`, `analyse.html` | titres, textes, seuil, 61/120 en dur (barres de 120 sièges), « 2026 contre 2022 » | — |
| `tests/` | `fixture-2022.json`, listes de lettres, 120/61, `test_fetch_cec.py` (≈ 150 références à Israël) | — |
| `README.md`, `LICENSE`, `.claude/launch.json` | présentation, nom du serveur de prévisualisation | `israpoll`, port 8765 |

**À garder tel quel** (c'est le gage de fiabilité) : `sanitizeLive`/`sanitizeNews` (structure), `fetchJson`/`loadLive` (deux sources + repli), `render()` avec ses
`try/catch`, `publish()` (branche orpheline, force-push), `sane()`, `merge_turnout`, `get()` + `_SameSiteOnly`, `SUM_TOLERANCE`, `*_MAX_DROP`,
`FAILS_BEFORE_STALE`, le `digest` stable, la règle « un relevé en retard ne fait pas reculer ».

### 3.4 Procédure, phase par phase (chaque phase a un critère d'arrêt)
**Phase 0 — Cadrer et créer le dépôt.** §3.1. Copier le dépôt sous son nouveau nom, adapter `REPO`, activer Pages (*Deploy from a branch → `main` / root*),
ne laisser ni `data/live.json` ni `data/news.json` de l'ancienne instance (`{"status":"waiting"}` et `{"items":[]}` suffisent : `sanitizeLive` et
`sanitizeNews` les acceptent). *Fini quand* : le site vide s'affiche sans erreur (« en attente »).

**Phase 1 — Règles du scrutin.** `Seats` (total, seuil, formule, accords), majorité, bornes de `sanitizeLive`, `compare.js`. Les `120`/`61` sont codés en dur
dans plusieurs fichiers : `grep -nE '\b(120|61)\b' js/*.js *.html scripts/*.py tests/*`. Pas de constante partagée aujourd'hui (§8) : en introduire une
(`ELECTION = { seats, majority, threshold }`) vaut mieux que de multiplier les remplacements. Les noms internes (`cec`, `letters`, `prev2022`,
`official_seats`) restent dans une première passe ; un renommage se fait ensuite, dans un commit dédié, avec les tests. *Fini quand* : le test de
référence reproduit les sièges officiels de l'élection précédente.

**Phase 2 — Listes, camps, clés de bulletin.** `PARTIES` **et** `PARTY_LETTERS` (Python) **et**, si besoin, `PRESS_PARTIES`/`WIKI_PARTIES`/`KNOWN_LETTERS`/`MINOR`.
- `id` : minuscules ASCII et `_` seulement (le lien de partage du simulateur lit `c=([a-z,_]+)`) ; stable, il sert de clé partout (JS, Python, `manual.json`).
- Clé de bulletin (`letters`) : celle de la source officielle (numéro de liste, sigle, code…). **Elle n'est pas stable d'un scrutin à l'autre** (Israël : `ב` =
  Foyer juif en 2022, Otzma Yehudit en 2026) : l'élection précédente s'indexe par ses propres identifiants (`likud22`…).
- Un test compare `PARTY_LETTERS` à la table `PARTIES` en lisant le texte de `js/common.js` à partir de `const PARTIES = [` : garder cette forme.
- Noms, couleurs, chefs : autorité + Wikipédia ; camps : lecture éditoriale validée (§1). *Fini quand* : `tests/test_fetch_cec.py` (alignement des tables) passe.

**Phase 3 — Élection précédente.** Résultats officiels (somme du fichier par localité si possible, vérifiée contre le tableau national publié) dans
`js/data<année>.js` (renommer `RESULTS_2022`), `GROUPS` (fusions/scissions expliquées en `note`), `tests/fixture-<année>.json` (voix + sièges), tests de
`compare`/`seats`. Pas de précédent comparable ⇒ retirer `analyse.html` et son entrée de `NAV` plutôt que la laisser vide. *Fini quand* : `compare.test` et
`seats.test` passent sur ces données.

**Phase 4 — Sources et collecteur.** §3.5. *Fini quand* : `python3 -I scripts/fetch_cec.py --out /tmp/live.json --manual data/manual.json` produit un
`live.json` valide pour les sources actives et que les tests passent sur des fichiers **réels enregistrés** de l'élection précédente.

**Phase 5 — Temps.** `POLLS_CLOSE`, `FINAL_BY`, créneaux de participation (`turnout_entry` : plage horaire, comparaison au précédent ⇒ `prev2022`, `turnRef`),
fuseau dans les libellés (`tz`, « heure d'Israël »), bascule d'heure d'été/hiver.

**Phase 6 — Pages et textes.** Remplacer tout le vocabulaire (grep, §3.6), réécrire le duel et les `PRESETS` (ou les retirer), le déroulé `#steps`, « Sources et
méthode » (décrire le calcul **réel**), titres/méta/og/favicon/marque. Autre langue : `lang`, `Intl` (`nf`, `pc`, `tz`, `hhmmss`), polices du `<head>` des trois pages ;
**l'écriture de droite à gauche n'est pas gérée** (il faudrait `dir="rtl"` et des propriétés logiques dans `site.css`).

**Phase 7 — Actualités.** `fetch_news.py` : requête, flux RSS de la presse du pays dans la langue du site (`FEEDS`, `HOSTS`), `MEDIA` (presse générale, pas de
sites d'opinion ni de médias d'État étrangers), regex pays/scrutin ; `NEWS_SEARCH` dans `index.html`.

**Phase 8 — Infrastructure.** Branches `data`/`news` (créées au premier `live.sh`), machine du collecteur, clé de déploiement limitée au dépôt (la révoquer après le
scrutin, B15), noms `israpoll-collector`, cron.

**Phase 9 — Répétition générale.** `?demo=1` et `?demo=final` (chiffres simulés) ; puis rejouer l'élection précédente avec ses vrais fichiers. **Ne jamais pousser un
essai sur la branche `data` du dépôt public** : la page l'afficherait. En local, un dépôt sans branche `data` fait retomber la page sur `data/live.json` (repli) :
`python3 -I scripts/fetch_cec.py --csv-file <fichier> --out data/live.json --manual data/manual.json`, ou un dépôt d'essai. *Fini quand* : §3.6.

### 3.5 Brancher les sources d'un nouveau pays
1. **Cartographier** : portail de résultats (national, par commune/circonscription, fichier téléchargeable ?), format (CSV/JSON/XML/HTML/PDF), cadence, URL fixes ou
   propres au scrutin (Israël : `votes<N>`/`media<N>.bechirot.gov.il`, N = numéro de Knesset), protections (WAF, CAPTCHA), `robots.txt`, conditions d'usage, licence.
   Presque aucune de ces sources n'envoie d'en-tête **CORS** : un relais (le collecteur) est obligatoire.
2. **Regarder l'élection précédente** : l'autorité reprend souvent la même structure (Israël : « même structure qu'en 2022 », mais la mise en page HTML de 2026 a
   changé : `parse_html` reconnaît les lignes par leurs clés de bulletin, pas par leur position). **Enregistrer des fichiers réels** dans `tests/` et écrire le
   parseur contre eux *avant* le jour J.
3. **Sources non officielles**, toutes facultatives, strictement validées, journalisées dans `source.fetch.<nom>` : article Wikipédia de l'élection (API
   MediaWiki ; ne **jamais** mapper les petites listes par leur nom), agrégateur ou relais de presse (projection de sièges), live-blog pour la participation.
4. **Contrat de sortie** : chaque adaptateur renvoie les mêmes dicts que l'existant (`votes`, `totals`, …) pour que `build()` reste inchangé. Garde-fous à conserver :
   `sane()`, `SUM_TOLERANCE`, `*_MAX_DROP`, `FAILS_BEFORE_STALE`, tailles bornées, redirections limitées au même hôte, liste blanche `allowed*`.
5. **Pas de données lisibles par machine** : saisie manuelle (`cec_manual.py`) ou import (`import_csv.sh`) ; il suffit d'adapter la table des clés et l'en-tête reconnu.
6. Lecture automatique du site de l'autorité : seulement après décision explicite du propriétaire (§1, §3.1).

### 3.6 Checklist de fin d'adaptation
- [ ] Aucun reste de l'ancienne instance hors de l'annexe A :
  `grep -rniE "isra|knesset|\bcec\b|bechirot|likoud|likud|netanyahou|eisenkot|yashar|bader|3,25|hébr|2022|heure d.isra|petek" --exclude-dir=.git --exclude=CLAUDE.md .`
- [ ] `node tests/*.test.mjs`, `python3 -I -m unittest discover tests`, `python3 -m pyflakes scripts/*.py tests/*.py` (§6) passent.
- [ ] Le test de référence reproduit les sièges officiels de l'élection précédente.
- [ ] Les **trois pages** (ou celles qui restent), en clair et en sombre, en 375 px sans défilement horizontal ; `?demo=1` et `?demo=final` ; aucune erreur console.
- [ ] Chaque chiffre affiché a sa source nommée et cliquable ; rien n'est présenté comme officiel s'il ne l'est pas.
- [ ] Le collecteur tourne sur la machine prévue et la pastille « page actualisée » du site dit la même chose que `checked_at` de la branche `data`.
- [ ] `README.md`, `LICENSE`, ce fichier (§A) décrivent la nouvelle instance.

---

## 4. Exploitation

### Jour J, en bref
- **J-7 à J-1** : collecteur installé et supervisé, fichiers réels de l'élection précédente rejoués, sources vérifiées (URL du scrutin en ligne ?), `POLLS_CLOSE` exact
  (fuseau !), `manual.json` prêt, propriétaire joignable pour la saisie/l'import.
- **Clôture des bureaux** : surveiller `source.fetch` (une source facultative en panne ne gêne pas) ; vérifier ce qui bloque (défi anti-bot, §1) avant de bricoler.
- **Dépouillement** : participation relevée ; totaux de l'autorité saisis/importés ; les chiffres non officiels sont étiquetés. Une saisie plus récente corrige la précédente.
- **Proclamation** : `manual.final = true` (statut `final`), figer le site, archiver `live.json`.
- **Après** : arrêter le collecteur (retirer les lignes du crontab **puis** tuer les PID), révoquer la clé de déploiement, mettre à jour README et §A.

### Commandes utiles
```bash
# état de publication (depuis n'importe où)
gh api "repos/<proprietaire>/<depot>/contents/live.json?ref=data" --jq .content | base64 -d | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['collector'],d['status'],d['checked_at'],d['source']['fetch'])"
# un relevé à la main / tester sans publier (le site de l'autorité n'est interrogé qu'avec --poll-cec)
python3 -I scripts/fetch_cec.py --out /tmp/live.json --manual data/manual.json
# import humain du fichier téléchargé sur le site de l'autorité (résumé + confirmation ; --dry pour ne rien publier)
scripts/import_csv.sh
# saisie manuelle des totaux (voir README) puis commit/push
python3 -I scripts/cec_manual.py --as-of 12:30 --eligible … --voters … --valid … likud=… yashar=…
# boucle de collecte (durée en s, intervalle en s) ; CEC_POLL=1 réactive la lecture du site de l'autorité ; CSV_FILE=… un passage sur un fichier local
scripts/live.sh 30000 30
```
`live.sh` publie sur la branche `data` à chaque changement et au moins toutes les ~2 min (le site en déduit que le collecteur est vivant) ; il relit
`data/manual.json` sur `main` à chaque tour : **on peut l'éditer en direct**. Les relevés presse/Wikipédia se font toutes les ~3 min, les actualités toutes les ~10 min.
Plusieurs collecteurs peuvent publier : chacun adopte les chiffres plus avancés des autres (`--peer`).

---

## 5. Pièges rencontrés (ne pas les refaire)

**Génériques**
- **CORS** : ni les autorités, ni les RSS de presse ne l'autorisent ⇒ relais obligatoire. `raw.githubusercontent.com` et `api.github.com` l'autorisent.
- **GitHub Actions** : depuis ses serveurs une autorité peut répondre au défi anti-bot ; les exécutions planifiées (`schedule`) sont **très irrégulières** (Israël : une
  seule exécution de `news.yml` en ~20 h) ⇒ tout est fait par le collecteur, le workflow n'est qu'un filet (B2).
- **Caches** : `raw.githubusercontent.com` = 5 min (la chaîne `?t=` n'y change rien) ; API GitHub = 60 s + ETag, **60 requêtes/h/IP** (la page s'en détache sous 5
  restantes) ; jsDelivr : l'API de purge répond `throttled: true` après quelques dizaines d'appels ⇒ abandonné ; GitHub Pages = 10 min (B3).
- **Branches `data` et `news`** : orphelines à un seul commit, **force-push** volontaire (l'historique ne grossit pas) ; n'y mettre rien d'autre que `live.json` / `news.json`.
- **Une clé de bulletin n'est pas stable d'un scrutin à l'autre** (voir phase 2).
- **Wikipédia** : l'API exige un `User-Agent` qui s'identifie (URL du dépôt), pas d'adresse e-mail personnelle ; les bénévoles recopient le tableau de l'autorité avec ~1 h de
  retard et ont déjà **inversé le nom de deux listes minuscules** (Israël : Hakahal 831 / « Fixing… » 829, alors que la CEC donne HaTikoun 831 et HaKahal 829) ⇒ ne mapper que
  les grandes listes par leur nom, regrouper le reste en « autres listes ». Le tableau n'a pas de sièges (commentaires « spéculatifs »). L'infobox donne `reporting`
  (% d'urnes) et `last_update`.
- **Heure** : les relevés d'une autorité et des relais sont en heure locale du pays ; un relais peut afficher la mauvaise date après minuit (The Petek : « 27 Oct »).
- **Hébergement mutualisé** : vérifier *avant* de promettre un déploiement quels protocoles répondent. Infomaniak (offre de base, un seul nom d'hôte) : seuls FTP **en clair**
  (21) et HTTPS (443) répondent, `AUTH TLS` refusé, port 22 fermé ⇒ **ne pas retenter FTP/FTPS** (un mot de passe en clair est exclu). Écartés : sous-domaine servi par
  GitHub Pages (`CNAME`), récepteur PHP signé en HTTPS.

**Machine du collecteur**
- **systemd-logind `RemoveIPC=yes`** (Ubuntu) vide `/dev/shm` et `/run/user/…` à la fermeture de la dernière session SSH ⇒ **ne jamais** y mettre clone, verrous ou logs
  (cause de superviseurs en double). Tout vit sous `~/<nom>-collector/work`.
- **`pkill -f` via `ssh`** : la ligne de commande contient le motif ⇒ le shell distant se tue lui-même. Tuer par PID.
- **macOS** : pas de `timeout` (déjà géré), bash 3.2 (tableaux vides sous `set -u` : idiome `${a[@]+"${a[@]}"}`), pas de `sha1sum` (le bloc de mise à jour automatique ne tourne
  que sur le clone supervisé du Jetson). Le Mac se met en veille et coupe les sessions : `caffeinate -i -w <pid>` retient la machine tant que le processus tourne.

---

## 6. Tests

```bash
node tests/seats.test.mjs        # répartition des sièges : sièges officiels de l'élection précédente reproduits, entrées dégradées
node tests/compare.test.mjs      # camps de l'élection précédente, fusions, écarts, pas de double compte
node tests/common.test.mjs       # sanitizeLive + choix de la source des sièges (vm, sans DOM)
python3 -I -m unittest discover tests   # collecteur (site non interrogé par défaut, pause anti-bot avec --poll-cec, pairs, saisie manuelle), relais presse, actualités
python3 -m pyflakes scripts/*.py tests/*.py
```
Pas de test automatisé du rendu : vérifier à la main dans le navigateur (`.claude/launch.json` lance `python3 -m http.server 8765`, dossier ignoré par git). Modes de
démonstration : `?demo=1` (dépouillement partiel simulé), `?demo=final`. Vérifier toujours **toutes les pages**, en clair et en sombre, au format mobile (375 px : pas de
défilement horizontal de la page).

---

## 7. Conventions de code

- Tokens CSS dans `:root` (+ variante sombre) ; jamais de couleur « bon/mauvais » pour un parti (`.delta`).
- Nombres en `fr-FR` (`fmt`, `pc`), heures via `Intl` (`hhmmss`, `tz`).
- Chaque section d'une page reçoit son conteneur ; ne pas écrire hors de son propre conteneur.
- Nouveau parti : `PARTIES` (`js/common.js`) **et** `PARTY_LETTERS` (`scripts/fetch_cec.py`) **et**, si besoin, `PRESS_PARTIES` ; un test garde les tables alignées.
  Nouvelle ligne de comparaison : `GROUPS` (`js/compare.js`) + test.
- Les scripts Python n'utilisent que la bibliothèque standard ; hôtes réseau en liste blanche (`allowed*`), redirections comprises, tailles bornées.
- Publier = `git push` sur `main` : Pages se reconstruit en ~1 min ; le collecteur supervisé récupère le code en ≤ 5 min.

---

## 8. Idées non réalisées

- **Extraire la configuration du scrutin** dans un seul fichier (`js/election.js` : total de sièges, majorité, seuil, clôture, liens de l'autorité, textes de la marque ;
  équivalent Python pour le collecteur) : aujourd'hui `120`, `61`, `3,25 %`, les liens et les libellés sont dispersés (§3.3). **Proposer cette étape 0 au propriétaire avant la
  deuxième instance** : elle réduit l'adaptation à un fichier de config + les adaptateurs de sources.
- Couche de textes (i18n) et prise en charge du RTL.
- Relais sans cache (Worker Cloudflare avec R2) pour passer sous la seconde et lever la limite de 60 req/h de l'API GitHub.
- Test de rendu automatisé (jsdom/Playwright) ; vérification visuelle mobile en intégration continue.
- Résultats par localité (carte), évolution du comptage dans le temps (historique `live.json` dans une branche dédiée).

---

## 9. Défauts mineurs connus (documentés, non corrigés)

Relecture complète du 28/10/2026. **Corrigés alors** : fil « À lire » figé (le collecteur le rafraîchit, la page affiche l'âge du relevé et avertit au-delà de 45 min) ;
comparaison de participation à la même heure de 2022 (`turnoutRef`) ; débordement horizontal mobile ; CSS mort ; preset ambigu ; tests de cohérence repointés sur
`js/common.js`. **Restent** (aucun n'empêche d'afficher des chiffres justes). *Structurel* = à traiter en adaptant ; *Israël* = propre à l'instance.

| # | Où | Défaut | Impact / piste |
|---|---|---|---|
| B1 | `data/live.json`, `data/news.json` | Instantanés statiques recopiés à la main le 28/10 (16:28Z), périmés dès le tour suivant, servis en **dernier recours** si l'API GitHub **et** `raw` échouent *(structurel)* | La page afficherait un état ancien (le chip « dernier relevé » le montre en orange). Piste : job qui recopie `data`/`news` dans `main`, ou supprimer ces replis |
| B2 | `.github/workflows/news.yml` | `schedule` rarement déclenché (§5), double le travail du collecteur *(structurel)* | Inoffensif : filet. Piste : retirer `schedule`, garder `workflow_dispatch` |
| B3 | pages HTML | Seul `js/common.js` est versionné (`?v=20261105`, **à changer à chaque modification de ce fichier** : sinon une page HTML neuve qui appelle une fonction ajoutée à `common.js` plante ~10 min, le temps du cache de Pages) ; `css/site.css` et les autres `js/*.js` ne le sont pas *(structurel)* | Décalage HTML/JS possible sur les fichiers non versionnés. Piste : `?v=<date>` partout |
| B4 | menu (`.nav`) | Sur écran étroit le menu défile horizontalement ; « Sources » est partiellement coupé | Cosmétique ; piste : menu repliable sous 700 px |
| B5 | `index.html` | Le simulateur ne propose que les partis à ≥ 1 siège dans la source active ; un lien partagé contenant un parti à 0 siège l'ignore sans message | Voulu, mais sans message |
| B6 | `common.js` (`derive`) | `cec.share` (« ≈ X % du vote attendu ») vient de la participation finale estimée, pas des urnes dépouillées | Écart avec le % d'urnes de la presse ; remplacer par `press.counted_pct`/`wiki.counted_pct` quand disponible |
| B7 | `fetch_cec.py` (`parse_html`) | Écrit pour la mise en page 2022 et une heuristique 2026 **jamais vue en conditions réelles** ; ne tourne qu'avec `--poll-cec` *(Israël)* | Sièges officiels lus seulement si la lecture est réactivée et la page conforme ; sinon estimation, **ou saisie à la main** avec les voix (`cec_manual.py --seats likud=27,…`, clé `cec.seats` de `manual.json` ; validée : 120 sièges, listes connues, au moins 3,25 % des voix saisies) |
| B8 | `fetch_cec.py` (`parse_turnout`) | Dépend de la structure JSON-LD du live-blog NBC ; sa dernière mise à jour précède la clôture *(Israël)* | En cas d'échec : saisie manuelle de la participation |
| B9 | `fetch_cec.py` (`parse_press`, `parse_wiki`) | The Petek : lit le **texte** de la page (aucune API) ; Wikipédia : dépend du modèle `{{Election results}}` et des noms de listes, retard ~1 h *(structurel)* | Un changement de mise en page rejette le relevé ; le dernier reste affiché ; sources facultatives |
| B10 | `fetch_news.py` | Liste blanche `MEDIA` tenue à la main : un média absent est écarté sans message *(structurel)* | Ajouter son nom tel qu'il apparaît dans Google Actualités |
| B11 | `live.sh` | Le relevé des actualités (≈ 5–20 s) s'exécute dans la boucle principale, une fois par ~10 min | Un tour de collecte est retardé d'autant ; piste : sous-processus |
| B12 | `js/compare.js` | Note « fusion annoncée avec le Likoud » (Nouvel Espoir) sourcée par Wikipédia (juillet 2026) *(Israël)* | À revérifier avec la liste officielle des 38 listes |
| B13 | `analyse.html` | Parts de voix 2026 partielles (urnes comptées) face au résultat final 2022 ; les urnes restantes peuvent déplacer quelques sièges | Bandeau d'avertissement ; pas de correction statistique |
| B14 | rendu | Aucun test automatisé des fonctions `render*` | Vérification manuelle de chaque page à chaque changement |
| B15 | `deploy/jetson/run.sh` | La clé de déploiement donne l'écriture sur **tout** le dépôt (pas seulement `data`/`news`) *(structurel)* | Limite de GitHub ; **à révoquer après le scrutin** (*Settings → Deploy keys*) |
| B16 | `fetch_cec.py`, `cec_manual.py` | Commentaires périmés : « PARTIES dans index.html » (la table est dans `js/common.js`) | Cosmétique ; corriger au passage |

---

## Annexe A — Instance Israël 2026 (référence et exemple travaillé)

### A.1 Fiche
- Scrutin : 26ᵉ Knesset, **27 octobre 2026**, proportionnelle nationale à liste unique, 120 sièges, seuil 3,25 %, 38 listes ; précédent : 25ᵉ Knesset, 1ᵉʳ novembre 2022.
- Autorité : CEC — tableau national `votes26.bechirot.gov.il/nationalresults`, fichier par localité `media26.bechirot.gov.il/files/expc.csv` (en-têtes hébreux ; somme = résultat
  national ; vérifié sur 2022). Proclamation au journal officiel (*Reshumot*) au plus tard le 4 novembre 2026.
- Site : français, trois pages (`index`, `resultats`, `analyse`). Sources non officielles : Wikipédia (défaut), The Petek ; participation : live-blog NBC News (JSON-LD).
- **État au dernier commit (`2a6c759`, 28/10/2026)** : `manual.final` valait `false`, lecture du site de la CEC arrêtée, base de calcul par défaut = Wikipédia. Passer `final` à `true` est le
  geste de clôture (§4 « Après »). La suite (gel du site, archivage de `live.json`, arrêt du Jetson, révocation de la clé, B15) **n'est pas vérifiée** : relire `git log` et `data/manual.json`
  avant d'affirmer où en est l'instance.

### A.2 Calculs et choix éditoriaux
- **Sièges** : seuil 3,25 % des bulletins valides ; quotient national ; restes par plus forte moyenne (Bader-Ofer) ; accords de surplus déclarés (`PACTS`) : Ensemble–Israël
  Beiteinou, Yashar–Démocrates, Liste commune–Ra'am, Likoud–Sionisme religieux, Shas–UTJ. Reproduit exactement les 120 sièges de 2022 avec l'accord Likoud–RZ.
- **Camps** (`PARTIES.bloc`, lecture éditoriale) : Netanyahou = Likoud, Shas, UTJ, Otzma, Sionisme religieux–Zehut, Noam ; Eisenkot = Yashar, Ensemble, Démocrates, Israël
  Beiteinou, Réservistes ; arabes = Liste commune, Ra'am ; autres = Amcha, Public haredi, le reste. Majorité : 61.
- **Comparaison 2022** (`GROUPS`) : chaque ligne additionne les listes de 2022 correspondant à une ou plusieurs listes de 2026 (Yesh Atid → Ensemble ; Union nationale → Yashar ;
  Travaillistes + Meretz → Démocrates ; Hadash–Ta'al + Balad → Liste commune ; liste commune RZ–Otzma–Noam → trois listes) ; les notes expliquent fusions et scissions. Parts de
  voix 2026 = bulletins **déjà comptés** face au résultat final de 2022.
- **Participation** : relevés de la CEC toutes les ~2 h, lus sur le live-blog NBC puis saisis/corrigés dans `manual.json`. Comparaison à la **même heure** de 2022 (`prev2022`), ou au
  total 2022 pour le seul relevé de clôture (22:00).
- **« Dépouillement ≈ X % »** (accueil) : `votants / (inscrits × participation finale estimée)` ; ce n'est **pas** le pourcentage d'urnes annoncé par la presse (B6).

### A.3 Exploitation
- **Collecteur de production : le Jetson** de l'utilisateur (réseau interne, IP privée : joignable seulement depuis le même réseau local). L'adresse et l'identifiant SSH ne figurent
  volontairement **pas** dans ce dépôt public (documentation privée de l'utilisateur). Dossier `~/israpoll-collector/` : `run.sh` (superviseur), `deploy_key` (écriture limitée au
  dépôt israpoll), `known_hosts`, `work/` (clone, `live.log`, temporaires). Cron : `@reboot` et chaque minute ; `flock` ⇒ un seul superviseur. Le superviseur relance `live.sh` chaque
  heure ; `live.sh` se met à jour seul (`git reset --hard` de `main` toutes les ~5 min, relance si lui-même a changé) : **pousser sur `main` suffit à déployer**.
- Le Jetson sert aussi un autre projet : le collecteur est léger (python3 + curl toutes les 30 s, `nice`), sans sudo, presque aucune écriture sur la carte SD.
- Lecture seule : `ssh <utilisateur>@<ip-du-jetson> 'tail -20 ~/israpoll-collector/work/live.log; ps -eo pid,etimes,cmd | grep "[i]srapoll"; crontab -l'`. Arrêt propre : retirer
  les 2 lignes `israpoll-collector` du crontab **puis** tuer les PID.
- Le Mac peut lancer la même boucle (`scripts/live.sh`) ; préférer le Jetson.

### A.4 Chiffres de la CEC (le site bloque depuis le soir du scrutin ; lecture arrêtée le 28/10)
1. Le collecteur n'interroge pas le site de la CEC (`source.fetch.csv` : « site de la CEC non interrogé »). Pour essayer : `CEC_POLL=1 scripts/live.sh` (journal
   `pause anti-bot jusqu'à …`, pause 45 s → 10 min).
2. Voie officielle : un humain lit le tableau national dans un navigateur et saisit les totaux (`cec_manual.py`), ou télécharge le CSV (`scripts/import_csv.sh`).
3. Voie non officielle : relais presse (`press`), étiqueté ; la page le préfère aux totaux CEC seulement s'il est plus avancé.
4. Conséquence : **les sièges attribués par la CEC ne sont pas lus** (`parse_html` ne tourne qu'avec `--poll-cec`) ; la page affiche l'estimation jusqu'à ce que quelqu'un réactive
   la lecture ou que le site redevienne lisible.

### A.5 Journal des décisions
- 27/10 : collecteur sur GitHub Actions abandonné (défi anti-bot) ; jsDelivr abandonné (purge throttlée) ; API GitHub + `raw` retenus.
- 27/10 soir : défi anti-bot sur tous les clients ⇒ pause croissante, import humain, saisie manuelle, relais presse étiqueté (accord du propriétaire).
- 28/10 matin : sondages et sorties des urnes retirés de la page et de `manual.json` (décision du propriétaire) ; fil « À lire » ajouté.
- 28/10 : lecture automatique du site de la CEC **arrêtée** à la demande du propriétaire (`--poll-cec` / `CEC_POLL=1`) ; la page ne mentionne plus de blocage, elle indique la source de chaque chiffre.
- 28/10 : **Wikipédia ajoutée comme jeu de données** (comme The Petek), mise **par défaut** à la demande du propriétaire, citée partout ; slogan d'accueil retiré.
- 28/10 : hébergement sur le domaine personnel de l'utilisateur (déploiement par Action GitHub) **abandonné** (voir §5, hébergement mutualisé) ; le site reste sur GitHub Pages, l'utilisateur gère
  lui-même le `.htaccess` de son domaine.
- 28/10 : section « Blocs pressentis » supprimée ; « Résultat brut » déplacé en annexe ; page « 2026 contre 2022 » ; code commun extrait (`css/site.css`, `js/common.js`) ; relevé des
  actualités transféré au collecteur (le cron de GitHub Actions ne part pas).
- 05/11 : `CLAUDE.md` refondu en gabarit réutilisable pour une autre élection ou un autre pays (§3 et annexe A) ; aucun code modifié.
