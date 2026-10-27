# IsraPoll 🇮🇱 — élections israéliennes 2026, en direct

Une page web unique (HTML + un peu de JS, **sans build ni dépendance**) qui affiche, pour les élections à la 26ᵉ Knesset du **27 octobre 2026** :

1. **Le résultat brut**, tel que publié par la [Commission électorale centrale](https://votes26.bechirot.gov.il/nationalresults) (voix, %, seuil de 3,25 %, sièges), avec la source à chaque bloc ;
2. **Les blocs pressentis** (coalition sortante, bloc Eisenkot, partis arabes) et ce qu'il leur manque pour atteindre 61 sièges ;
3. **Un simulateur** : coche des partis, vois si ta coalition a la majorité, et partage-la par lien.

> English: a dependency-free, open-source live dashboard for Israel's 2026 Knesset election — official CEC results, bloc math and a coalition builder. Independent project, not affiliated with the CEC.

## Comment ça marche

```
CEC (media26.bechirot.gov.il/files/expc.csv)
        │  toutes les 30 s  (scripts/live.sh → scripts/fetch_cec.py, sur une machine non filtrée)
        ▼
branche `data` : live.json ──(API GitHub ~1 min · raw 5 min)──►  index.html (GitHub Pages) ── recalcule les sièges (js/seats.js)
```

- Le site de la CEC n'envoie pas d'en-tête CORS : un navigateur ne peut pas le lire directement. Le collecteur le relaie vers une branche `data` (l'API GitHub et `raw.githubusercontent.com` autorisent le CORS). La page lit les deux et garde la plus récente : l'API GitHub répond en ~1 min mais est limitée à 60 requêtes/h/IP (la page s'en détache avant d'être bloquée) ; `raw` garde 5 min en cache. Pour du vrai temps réel, il faudrait un petit relais sans cache (Cloudflare Worker).
- **GitHub Actions ne convient pas** : depuis les serveurs de GitHub, la CEC répond par un défi anti-bot (HTTP 202 à corps vide). Le collecteur doit donc tourner depuis une IP non filtrée (un ordinateur personnel, un petit VPS).
- Les **voix** sont la somme du fichier officiel par localité. Vérifié sur 2022 : le total reproduit exactement les résultats nationaux publiés par la CEC.
- Les **sièges** : si la CEC les affiche, on les reprend ; sinon ils sont **estimés** (seuil 3,25 % + quotient + méthode Bader-Ofer + accords de surplus) et marqués « est. ». Le calcul reproduit exactement les 120 sièges de 2022 (`tests/seats.test.mjs`).
- Avant le dépouillement, **aucun sondage n'est présenté comme un résultat** : le tableau reste vide, les sondages sont dans leur propre section, étiquetés comme tels.

### Ce qui est fait à la main : `data/manual.json`
Participation heure par heure et sorties des urnes (Kan 11, Channel 12, Channel 13) n'ont pas de flux officiel. Ils sont saisis dans [`data/manual.json`](data/manual.json) (une PR suffit — le collecteur relit ce fichier à chaque tour, sans redéploiement). Les sièges y sont indexés par identifiant de parti (`likud`, `yashar`, `together`, `democrats`, `yb`, `shas`, `otzma`, `utj`, `rzp`, `raam`, `joint`, `reservists`…, voir `PARTIES` dans `index.html`).

## Lancer en local

```bash
python3 -m http.server 8765      # puis http://localhost:8765
```

- `?demo=1` (dépouillement partiel), `?demo=exit` (sorties des urnes), `?demo=final` (résultat final) : **chiffres simulés** pour tester l'interface.
- `python3 scripts/fetch_cec.py --out data/live.json --manual data/manual.json` : un relevé à la main.
- `scripts/live.sh 20000 30` : boucle de collecte qui publie sur la branche `data` (nécessite les droits de push).

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
python3 -I -m unittest discover tests
```

## Limites et mentions

- Les premiers bureaux dépouillés ne sont pas représentatifs : tout classement provisoire peut s'inverser.
- Les résultats définitifs sont proclamés au journal officiel (*Reshumot*) au plus tard le 4 novembre 2026 ; ils peuvent encore évoluer d'ici là.
- Le rattachement des listes aux blocs est une **lecture éditoriale** (positions publiques avant le scrutin), modifiable dans `PARTIES`.
- Sondages : dernière vague du 21–23 octobre 2026, compilée par [israel2026.co.il](https://israel2026.co.il/en/election-polls.html) et recoupée avec Haaretz / Arutz Sheva.

## Licence

[MIT](LICENSE).
