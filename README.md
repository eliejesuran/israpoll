# IsraPoll 🇮🇱 — élections israéliennes 2026, en direct

Un site statique (HTML + JS, **sans build ni dépendance**) en trois pages pour les élections à la 26ᵉ Knesset du **27 octobre 2026** :

1. **Accueil** (`index.html`) : l'hémicycle, un **simulateur de coalition** (coche des partis, vois si ta coalition a la majorité, partage-la par lien), le duel Yashar vs BB et **l'actualité du scrutin** (titres de la presse francophone, avec un lien vers chaque article) ;
2. **Résultat brut** (`resultats.html`, annexe) : voix, %, seuil de 3,25 % et sièges de chaque liste tels que publiés par la [Commission électorale centrale](https://votes26.bechirot.gov.il/nationalresults), participation heure par heure, avec la source de chaque chiffre ;
3. **2026 contre 2022** (`analyse.html`) : ce que chaque famille politique (droite et ultra-orthodoxes, centre et gauche, partis arabes) gagne ou perd par rapport aux résultats officiels de 2022, parti par parti.

> English: a dependency-free, open-source live dashboard for Israel's 2026 Knesset election — official CEC results, bloc math and a coalition builder. Independent project, not affiliated with the CEC.

## Comment ça marche

```
totaux de la CEC (recopiés ou fichier importé) + relais presse + participation
        │  toutes les 30 s  (scripts/live.sh → scripts/fetch_cec.py)
        ▼
branche `data` : live.json ──(API GitHub ~1 min · raw 5 min)──►  pages (GitHub Pages) ── recalculent les sièges (js/seats.js)

flux RSS de presse ──(même boucle, toutes les ~10 min)──► branche `news` : news.json ──► « À lire » (accueil)
```

Structure : `index.html`, `resultats.html`, `analyse.html` ; `css/site.css` (styles communs) ; `js/common.js` (données, modèle dérivé, menu, pied de page, thème, pastille « page actualisée ») ; `js/seats.js` (Bader-Ofer) ; `js/compare.js` + `js/data2022.js` (comparaison 2022) ; `scripts/` (collecteurs Python/bash) ; `deploy/jetson/` (collecteur sur un Jetson) ; `tests/`. Voir [`CLAUDE.md`](CLAUDE.md) pour le détail, les décisions et les défauts connus.

- Ni le site de la CEC ni les autres sources n'envoient d'en-tête CORS : un navigateur ne peut pas les lire directement. Le collecteur les relaie vers une branche `data` (l'API GitHub et `raw.githubusercontent.com` autorisent le CORS). La page lit les deux et garde la plus récente : l'API GitHub répond en ~1 min mais est limitée à 60 requêtes/h/IP (la page s'en détache avant d'être bloquée) ; `raw` garde 5 min en cache. Pour du vrai temps réel, il faudrait un petit relais sans cache (Cloudflare Worker).
- **Le site de la CEC n'est pas interrogé automatiquement** : il répond par un défi anti-bot (HTTP 202 à corps vide) que le projet ne contourne pas. Les chiffres de la CEC viennent donc d'une personne (totaux recopiés ou fichier téléchargé, voir plus bas). Le collecteur peut tourner sur n'importe quelle petite machine (un ordinateur, un Jetson, un VPS) ; les actualités (flux RSS publics) n'ont pas ce problème : voir ci-dessous.
- Les **voix** sont la somme du fichier officiel par localité. Vérifié sur 2022 : le total reproduit exactement les résultats nationaux publiés par la CEC.
- Les **sièges** : si la CEC les affiche, on les reprend ; sinon ils sont **estimés** (seuil 3,25 % + quotient + méthode Bader-Ofer + accords de surplus) et marqués « est. ». Le calcul reproduit exactement les 120 sièges de 2022 (`tests/seats.test.mjs`).
- **Aucun sondage n'est affiché** (ni sondages d'avant-scrutin, ni sorties des urnes) : tant que la CEC n'a rien publié, l'hémicycle, le tableau et le simulateur restent vides — sauf le relais presse, explicitement étiqueté « non officiel » (voir plus bas).

### Actualités : titres de presse relevés par le collecteur
Les flux RSS des médias n'envoient pas d'en-tête CORS : la page ne peut pas les lire. Le collecteur (`scripts/live.sh`, toutes les ~10 min) lance `scripts/fetch_news.py` ; [`.github/workflows/news.yml`](.github/workflows/news.yml) fait la même chose, mais GitHub ne déclenche ses exécutions planifiées que très irrégulièrement (une seule en ~20 h sur ce dépôt) : c'est un filet de secours, qu'on peut aussi lancer à la main (*Run workflow*). `fetch_news.py` lit Google Actualités (recherche en français) et les flux « Moyen-Orient » du Monde, de France 24 et de RFI, puis publie `news.json` sur la branche orpheline `news` (force-push : l'historique ne grossit pas). La page le lit via `raw.githubusercontent.com` ; `data/news.json`, un instantané versionné, sert de repli.
- Seuls quatre champs sont repris : **titre, média, lien, date**. Aucun texte d'article.
- Sélection : presse d'information généraliste (constante `MEDIA` dans le script, à compléter au besoin ; ni sites d'opinion ou confessionnels, ni médias d'État étrangers), titres parlant d'Israël (et d'un scrutin pour les flux généralistes), 4 jours au plus, 3 titres par média au maximum.
- Une source en panne ne retire rien : les articles déjà recueillis restent jusqu'à leur péremption ; si tout est en panne, le dernier fichier publié reste en place.
- Lancer à la main : onglet *Actions → Actualités → Run workflow*, ou `python3 -I scripts/fetch_news.py --out news.json`.

### Participation : relevée automatiquement
La CEC publie la participation toutes les ~2 h sans flux lisible. Le collecteur lit le live-blog de NBC News, qui cite chaque relevé de la CEC (heure + chiffre + comparaison 2022) dans un JSON structuré, ~1 h 30 après l'heure de référence. Le parseur est volontairement strict (mention de la CEC et de la participation, heure locale, plage 07:00–22:00, chiffre qui ne recule pas) : en cas de doute il ignore l'entrée. `source.fetch.turnout` de `live.json` dit si la lecture a marché. Un relevé saisi à la main dans `manual.json` prévaut pour la même heure.

### Totaux de la CEC recopiés à la main
Le site de la CEC protège ses fichiers par un défi anti-bot (AWS WAF : réponse HTTP 202 vide avec `x-amzn-waf-action: challenge`) que seul un vrai navigateur passe ; le projet ne le contourne pas et **n'interroge plus son site** (`CEC_POLL=1 scripts/live.sh` pour réessayer : en-tête honnête, pause de 45 s doublée jusqu'à 10 min en cas de défi). On lit donc le tableau national sur [le site de la CEC](https://votes26.bechirot.gov.il/nationalresults) dans un navigateur et on le recopie :

```bash
python3 -I scripts/cec_manual.py --as-of 23:40 --eligible 7000000 --voters 1500000 --valid 1480000 \
    likud=380000 yashar=350000 together=190000 ...      # identifiants de PARTIES (js/common.js) ou lettres de vote
git diff data/manual.json && git commit -am "Totaux CEC (saisie manuelle)" && git push
python3 -I scripts/cec_manual.py --clear                # retire la saisie
```

L'assistant écrit la clé `cec` de `manual.json` (le reste du fichier n'est pas touché) et refuse, sans rien écrire, une liste inconnue, un total incohérent ou une somme des listes hors de 85–100 % des bulletins valides. Le collecteur relit le fichier depuis `main` à chaque tour (~30 s) et n'en tient compte que si la saisie est plus avancée que le dernier relevé obtenu (fichier importé, ou lecture du site avec `CEC_POLL=1`) et pas plus ancienne que lui (une nouvelle saisie peut corriger la précédente). La page dit alors d'où viennent les voix : « totaux de la CEC, recopiés depuis son tableau (relevé de …, heure d'Israël) ». Les sièges restent estimés (Bader-Ofer) ; il n'y a pas de saisie des sièges officiels.

### Ce qui est fait à la main : `data/manual.json`
La participation peut être saisie ou corrigée dans [`data/manual.json`](data/manual.json) (une PR suffit — le collecteur relit ce fichier à chaque tour, sans redéploiement), ainsi que les totaux de la CEC (clé `cec`, voir plus haut). Les identifiants de parti sont ceux de `PARTIES` dans `js/common.js` (`likud`, `yashar`, `together`, `democrats`, `yb`, `shas`, `otzma`, `utj`, `rzp`, `raam`, `joint`, `reservists`…).

## Lancer en local

```bash
python3 -m http.server 8765      # puis http://localhost:8765
```

- `?demo=1` (dépouillement partiel), `?demo=final` (résultat final) : **chiffres simulés** pour tester l'interface.
- `python3 scripts/fetch_cec.py --out data/live.json --manual data/manual.json` : un relevé à la main.
- `scripts/live.sh 20000 30` : boucle de collecte qui publie sur la branche `data` (nécessite les droits de push).

## Alimenter la page en chiffres de la CEC

Le soir du scrutin la CEC a protégé ses fichiers par un défi anti-bot (AWS WAF : HTTP 202, `x-amzn-waf-action: challenge`). **Le projet ne le contourne pas** et le collecteur n'interroge plus son site. Deux moyens légitimes :

- **Import humain** : télécharger le fichier « תוצאות לפי יישובים » depuis [le site de la CEC](https://votes26.bechirot.gov.il/nationalresults) dans un navigateur, puis `scripts/import_csv.sh` : il retrouve le CSV le plus récent de `~/Downloads`, affiche un résumé (communes, bulletins valides, premières listes), refuse un fichier qui n'est pas de la CEC et demande confirmation avant de publier (`--dry` : résumé seulement). Les autres collecteurs adoptent ces chiffres s'ils sont plus avancés.
- **Totaux recopiés** : voir plus haut (`scripts/cec_manual.py`).
- **Plusieurs collecteurs** : chacun adopte les chiffres plus avancés des autres (`--peer`).

### Relais presse (non officiel)
Le collecteur lit toutes les ~3 min la projection de sièges de [The Petek](https://www.thepetek.com/results) (agrégateur indépendant qui reprend le dépouillement de la CEC ; `robots.txt` : tout autorisé ; en-tête honnête) et la publie sous la clé `press` de `live.json`. La page ne l'utilise **que** si elle est plus avancée que les totaux CEC disponibles (bulletins valides comptés), ou à défaut de tout total CEC ; elle est toujours étiquetée « non officiel · relais presse », et le tableau des voix reste réservé à la CEC. Le relais est strict (liste inconnue, sièges ≠ 120 → rejeté) et ne recule jamais.

## Déployer

1. Fork, puis *Settings → Pages → Deploy from a branch → `main` / root*.
2. Adapter la constante `REPO` en haut de `js/common.js`.
3. Sur une machine qui peut pousser sur le dépôt, lancer la boucle de collecte :
   ```bash
   nohup scripts/live.sh 30000 30 > live.log 2>&1 &   # ~8 h, un relevé toutes les 30 s
   ```
   Elle publie `live.json` sur la branche orpheline `data` (force-push : l'historique ne grossit pas) et relit `data/manual.json` sur `main` à chaque tour.

## Tests

```bash
node tests/seats.test.mjs        # Bader-Ofer : reproduit les 120 sièges de 2022
node tests/compare.test.mjs      # comparaison 2022 (camps, fusions, écarts)
node tests/common.test.mjs       # validation du JSON du collecteur, choix de la source des sièges
python3 -I -m unittest discover tests      # collecteur CEC, relais presse, saisie manuelle, actualités
```

## Limites et mentions

- Les premiers bureaux dépouillés ne sont pas représentatifs : tout classement provisoire peut s'inverser.
- Les résultats définitifs sont proclamés au journal officiel (*Reshumot*) au plus tard le 4 novembre 2026 ; ils peuvent encore évoluer d'ici là.
- Le rattachement des listes aux camps est une **lecture éditoriale** (positions publiques avant le scrutin), modifiable dans `PARTIES` (`js/common.js`) et `GROUPS` (`js/compare.js`) ; les correspondances 2022 → 2026 (fusions, scissions) sont expliquées ligne par ligne sur la page d'analyse.

## Licence

[MIT](LICENSE).
