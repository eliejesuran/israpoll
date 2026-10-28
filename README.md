# IsraPoll 🇮🇱 — élections israéliennes 2026, en direct

Une page web unique (HTML + un peu de JS, **sans build ni dépendance**) qui affiche, pour les élections à la 26ᵉ Knesset du **27 octobre 2026** :

1. **Un simulateur**, juste sous l'hémicycle : coche des partis, vois si ta coalition a la majorité, et partage-la par lien ;
2. **Le résultat brut**, tel que publié par la [Commission électorale centrale](https://votes26.bechirot.gov.il/nationalresults) (voix, %, seuil de 3,25 %, sièges), avec la source à chaque bloc ;
3. **Les blocs pressentis** (coalition sortante, bloc Eisenkot, partis arabes) et ce qu'il leur manque pour atteindre 61 sièges ;
4. **L'actualité du scrutin** : les derniers titres de la presse francophone, avec un lien vers chaque article.

> English: a dependency-free, open-source live dashboard for Israel's 2026 Knesset election — official CEC results, bloc math and a coalition builder. Independent project, not affiliated with the CEC.

## Comment ça marche

```
CEC (media26.bechirot.gov.il/files/expc.csv)
        │  toutes les 30 s  (scripts/live.sh → scripts/fetch_cec.py, sur une machine non filtrée)
        ▼
branche `data` : live.json ──(API GitHub ~1 min · raw 5 min)──►  index.html (GitHub Pages) ── recalcule les sièges (js/seats.js)
```

- Le site de la CEC n'envoie pas d'en-tête CORS : un navigateur ne peut pas le lire directement. Le collecteur le relaie vers une branche `data` (l'API GitHub et `raw.githubusercontent.com` autorisent le CORS). La page lit les deux et garde la plus récente : l'API GitHub répond en ~1 min mais est limitée à 60 requêtes/h/IP (la page s'en détache avant d'être bloquée) ; `raw` garde 5 min en cache. Pour du vrai temps réel, il faudrait un petit relais sans cache (Cloudflare Worker).
- **GitHub Actions ne convient pas pour la CEC** : depuis les serveurs de GitHub, elle répond par un défi anti-bot (HTTP 202 à corps vide). Le collecteur doit donc tourner depuis une IP non filtrée (un ordinateur personnel, un petit VPS). Les actualités (flux RSS publics) n'ont pas ce problème : voir ci-dessous.
- Les **voix** sont la somme du fichier officiel par localité. Vérifié sur 2022 : le total reproduit exactement les résultats nationaux publiés par la CEC.
- Les **sièges** : si la CEC les affiche, on les reprend ; sinon ils sont **estimés** (seuil 3,25 % + quotient + méthode Bader-Ofer + accords de surplus) et marqués « est. ». Le calcul reproduit exactement les 120 sièges de 2022 (`tests/seats.test.mjs`).
- **Aucun sondage n'est affiché** (ni sondages d'avant-scrutin, ni sorties des urnes) : tant que la CEC n'a rien publié, l'hémicycle, le tableau et le simulateur restent vides.

### Actualités : titres de presse relevés par GitHub Actions
Les flux RSS des médias n'envoient pas d'en-tête CORS : la page ne peut pas les lire. [`.github/workflows/news.yml`](.github/workflows/news.yml) lance toutes les ~10 min `scripts/fetch_news.py`, qui lit Google Actualités (recherche en français) et les flux « Moyen-Orient » du Monde, de France 24 et de RFI, puis publie `news.json` sur la branche orpheline `news` (force-push : l'historique ne grossit pas). La page le lit via `raw.githubusercontent.com` ; `data/news.json`, un instantané versionné, sert de repli.
- Seuls quatre champs sont repris : **titre, média, lien, date**. Aucun texte d'article.
- Sélection : presse d'information généraliste (constante `MEDIA` dans le script, à compléter au besoin ; ni sites d'opinion ou confessionnels, ni médias d'État étrangers), titres parlant d'Israël (et d'un scrutin pour les flux généralistes), 4 jours au plus, 3 titres par média au maximum.
- Une source en panne ne retire rien : les articles déjà recueillis restent jusqu'à leur péremption ; si tout est en panne, le dernier fichier publié reste en place.
- Lancer à la main : onglet *Actions → Actualités → Run workflow*, ou `python3 -I scripts/fetch_news.py --out news.json`.

### Participation : relevée automatiquement
La CEC publie la participation toutes les ~2 h sans flux lisible. Le collecteur lit le live-blog de NBC News, qui cite chaque relevé de la CEC (heure + chiffre + comparaison 2022) dans un JSON structuré, ~1 h 30 après l'heure de référence. Le parseur est volontairement strict (mention de la CEC et de la participation, heure locale, plage 07:00–22:00, chiffre qui ne recule pas) : en cas de doute il ignore l'entrée. `source.fetch.turnout` de `live.json` dit si la lecture a marché. Un relevé saisi à la main dans `manual.json` prévaut pour la même heure.

### Secours : totaux de la CEC recopiés à la main
Le site de la CEC protège ses fichiers par un défi anti-bot (AWS WAF : réponse HTTP 202 vide avec `x-amzn-waf-action: challenge`) que seul un vrai navigateur passe ; le collecteur ne le contourne pas. Si le flux automatique reste bloqué pendant le dépouillement, on lit le tableau national sur [le site de la CEC](https://votes26.bechirot.gov.il/nationalresults) dans un navigateur et on le recopie :

```bash
python3 -I scripts/cec_manual.py --as-of 23:40 --eligible 7000000 --voters 1500000 --valid 1480000 \
    likud=380000 yashar=350000 together=190000 ...      # identifiants de PARTIES (index.html) ou lettres de vote
git diff data/manual.json && git commit -am "Totaux CEC (saisie manuelle)" && git push
python3 -I scripts/cec_manual.py --clear                # retire la saisie ; le flux automatique reprend seul
```

L'assistant écrit la clé `cec` de `manual.json` (le reste du fichier n'est pas touché) et refuse, sans rien écrire, une liste inconnue, un total incohérent ou une somme des listes hors de 85–100 % des bulletins valides. Le collecteur relit le fichier depuis `main` à chaque tour (~30 s) et n'en tient compte que si la saisie est plus avancée que le flux automatique et pas plus ancienne que le dernier relevé (une nouvelle saisie peut corriger la précédente). La page affiche alors un bandeau « Totaux recopiés à la main » avec l'heure du relevé : ce sont des chiffres recopiés, pas le flux de la CEC. Les sièges restent estimés (Bader-Ofer) ; il n'y a pas de saisie des sièges officiels.

### Ce qui est fait à la main : `data/manual.json`
La participation peut être saisie ou corrigée dans [`data/manual.json`](data/manual.json) (une PR suffit — le collecteur relit ce fichier à chaque tour, sans redéploiement), ainsi que, en secours, les totaux de la CEC (clé `cec`, voir plus haut). Les sorties des urnes qui y figurent encore (`exit_polls`) ne sont **plus affichées** par la page ; les identifiants de parti sont ceux de `PARTIES` dans `index.html` (`likud`, `yashar`, `together`, `democrats`, `yb`, `shas`, `otzma`, `utj`, `rzp`, `raam`, `joint`, `reservists`…).

## Lancer en local

```bash
python3 -m http.server 8765      # puis http://localhost:8765
```

- `?demo=1` (dépouillement partiel), `?demo=final` (résultat final) : **chiffres simulés** pour tester l'interface.
- `python3 scripts/fetch_cec.py --out data/live.json --manual data/manual.json` : un relevé à la main.
- `scripts/live.sh 20000 30` : boucle de collecte qui publie sur la branche `data` (nécessite les droits de push).

## Si la CEC bloque les lectures automatiques

Le soir du scrutin la CEC a protégé ses fichiers par un défi anti-bot (AWS WAF : HTTP 202, `x-amzn-waf-action: challenge`). **Le projet ne le contourne pas** : le collecteur s'identifie honnêtement, cesse d'insister (pause de 45 s doublée jusqu'à 10 min), publie `challenge: true` et la page l'affiche clairement. Deux replis légitimes :

- **Import humain** : télécharger le fichier « תוצאות לפי יישובים » depuis [le site de la CEC](https://votes26.bechirot.gov.il/nationalresults) dans un navigateur, puis `CSV_FILE=~/Downloads/expc.csv scripts/live.sh` (un passage ; les autres collecteurs adoptent ces chiffres s'ils sont plus avancés).
- **Plusieurs collecteurs** : chacun adopte les chiffres plus avancés des autres (`--peer`).

## Déployer

1. Fork, puis *Settings → Pages → Deploy from a branch → `main` / root*.
2. Adapter la constante `REPO` en haut du script de `index.html`.
3. Sur une machine qui peut joindre la CEC et pousser sur le dépôt, lancer la boucle de collecte :
   ```bash
   nohup scripts/live.sh 30000 30 > live.log 2>&1 &   # ~8 h, un relevé toutes les 30 s
   ```
   Elle publie `live.json` sur la branche orpheline `data` (force-push : l'historique ne grossit pas) et relit `data/manual.json` sur `main` à chaque tour.

## Tests

```bash
node tests/seats.test.mjs
python3 -I -m unittest discover tests      # collecteur CEC + relais d'actualités
```

## Limites et mentions

- Les premiers bureaux dépouillés ne sont pas représentatifs : tout classement provisoire peut s'inverser.
- Les résultats définitifs sont proclamés au journal officiel (*Reshumot*) au plus tard le 4 novembre 2026 ; ils peuvent encore évoluer d'ici là.
- Le rattachement des listes aux blocs est une **lecture éditoriale** (positions publiques avant le scrutin), modifiable dans `PARTIES`.

## Licence

[MIT](LICENSE).
