# Héberger IsraPoll sur eliejesuran.be (Infomaniak)

À chaque modification du site sur `main`, l'Action **« Déploiement sur eliejesuran.be »** dépose les fichiers dans
`https://eliejesuran.be/israpoll/` par FTP chiffré (FTPS), puis vérifie que le site publié correspond au dépôt.
Les données (résultats, actualités) ne passent pas par là : la page les lit en direct sur GitHub, comme sur GitHub Pages
(qui reste disponible en miroir : <https://eliejesuran.github.io/israpoll/>).

## Mise en route (une fois)

1. **Infomaniak Manager → Hébergement web → eliejesuran.be → FTP / SSH** : créer un utilisateur FTP **dédié** (pas ton compte principal),
   idéalement limité au dossier `israpoll` (il n'a alors accès à rien d'autre). Noter le **serveur** (du type `xxxxx.ftp.infomaniak.com`).
   Le dossier `israpoll` est créé automatiquement s'il n'existe pas. **`FTP_HOST` = ce nom de serveur FTP, pas `eliejesuran.be`** : le serveur du
   site lui-même n'accepte que le FTP en clair, que le déploiement refuse par sécurité.
2. **Enregistrer quatre secrets GitHub**, toi-même, dans un terminal (chaque commande demande la valeur ; elle n'est ni affichée ni conservée) :

   ```bash
   gh secret set FTP_HOST     --repo eliejesuran/israpoll   # le serveur FTP, sans « ftp:// » ni port
   gh secret set FTP_USER     --repo eliejesuran/israpoll
   gh secret set FTP_PASSWORD --repo eliejesuran/israpoll
   gh secret set FTP_PATH     --repo eliejesuran/israpoll   # dossier du site vu depuis la racine FTP
   ```

   `FTP_PATH` dépend du compte : avec un utilisateur FTP **limité au dossier du site** mets `.` ; avec un accès à toute l'hébergement c'est
   typiquement `sites/eliejesuran.be/israpoll` (à vérifier avec un client FTP : c'est le chemin, depuis la racine que tu vois, du dossier qui doit
   contenir `index.html`).
3. **Lancer le premier déploiement** : onglet *Actions → Déploiement sur eliejesuran.be → Run workflow*. Résultat attendu :
   `https://eliejesuran.be/israpoll/` s'affiche. Tant que les secrets manquent, le workflow se termine sans rien faire (message « secrets manquants »).

## Ce que fait (et ne fait pas) le déploiement

- **FTP chiffré obligatoire** (`--ssl-reqd`) et certificat vérifié : le mot de passe ne circule jamais en clair. Aucune action tierce : tout tient dans
  [`scripts/deploy_ftp.sh`](../../scripts/deploy_ftp.sh) (curl).
- **Dépose uniquement** `index.html`, `resultats.html`, `analyse.html`, `css/site.css`, `js/*.js` et `.htaccess` ; **ne supprime jamais rien** sur le
  serveur. La page actuelle de la racine d'eliejesuran.be et la redirection `/GP` ne sont pas touchées.
- Scripts et styles partent **avant** les pages HTML. Puis vérification : `js/common.js` et `index.html` publiés doivent être identiques à ceux du dépôt
  (le job devient rouge sinon).
- [`.htaccess`](.htaccess) impose la revalidation des pages, styles et scripts (pas de décalage de cache après un déploiement) et active la compression.
  **S'il provoquait une erreur 500**, le supprimer sur le serveur : le site fonctionne sans.
- Le mot de passe est transmis à curl par un fichier temporaire (droits 600), jamais par la ligne de commande.

## En cas de problème

| Symptôme | Piste |
|---|---|
| « secrets manquants » | Les quatre secrets doivent exister (*Settings → Secrets and variables → Actions*) |
| `curl: (64) Requested SSL level failed` | Le serveur indiqué dans `FTP_HOST` ne propose pas le FTP chiffré. **Cas rencontré** : `FTP_HOST` = le nom de domaine du site, dont le serveur répond « 500 This security scheme is not implemented » à `AUTH TLS` (FTP en clair seulement). Utilise le **serveur FTP dédié** affiché dans le Manager Infomaniak (type `xxxxx.ftp.infomaniak.com`) ; l'étape « Diagnostic » du workflow l'explique en clair |
| `curl: (67)` / `530 Login incorrect` | Identifiant ou mot de passe FTP |
| `curl: (60)` certificat | `FTP_HOST` doit être le nom officiel du serveur FTP Infomaniak (pas l'adresse IP) |
| `curl: (9)` / `550` accès refusé | `FTP_PATH` : le dossier est mal indiqué ou hors des droits de l'utilisateur FTP |
| « vérification échouée » | Fichiers déposés au mauvais endroit (`FTP_PATH`), ou cache serveur : relancer le workflow |
| Page blanche | Console du navigateur ; les adresses des données sont absolues, rien d'autre ne dépend du domaine |

Pour tout couper : supprimer les secrets (ou l'utilisateur FTP) ; le site GitHub Pages continue de fonctionner.
