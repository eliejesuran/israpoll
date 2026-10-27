# Collecteur sur un Jetson (ou toute petite machine Linux)

```bash
# sur ton ordinateur, depuis la racine du dépôt
scp deploy/jetson/run.sh deploy/jetson/install.sh bme@<ip>:/tmp/ && ssh bme@<ip> 'bash /tmp/install.sh'
# puis enregistrer la clé affichée comme « deploy key » (écriture) du dépôt :
ssh bme@<ip> 'cat ~/israpoll-collector/deploy_key.pub' > /tmp/k.pub && gh repo deploy-key add /tmp/k.pub --repo eliejesuran/israpoll --title "collecteur" --allow-write
```

- cron relance `run.sh` chaque minute ; `flock` assure un seul superviseur ; il se met à jour depuis `main` toutes les heures.
- État : `tail ~/israpoll-collector/work/live.log` ; la branche `data` indique `"collector": "jetson"`.
- Retrait : supprimer `~/israpoll-collector` et les deux lignes `israpoll-collector` de `crontab -e`.
- **Piège rencontré** : ne jamais stocker l'état dans `/dev/shm` ni `/run/user/…` sous Ubuntu — `systemd-logind` les vide quand la dernière session SSH se ferme.
- **Suivre le Jetson sans être sur son réseau** : il ne sert que de relais vers GitHub, rien n'exige d'être à côté. La branche `data` fait foi : `git fetch -q origin data && git show origin/data:live.json | grep -E '"(checked_at|collector)"'` doit montrer `"collector": "jetson"` et un `checked_at` de moins de ~2 min ; `source.fetch` détaille chaque source (CEC, participation). La pastille « page actualisée » du site dit la même chose.
- **Délais de déploiement** : `data/manual.json` est relu à chaque tour (~30 s). Le code (`scripts/`) n'est rechargé qu'au redémarrage de la boucle, donc **jusqu'à 1 h** après un push sur `main`.
