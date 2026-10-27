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
