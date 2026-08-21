# TAP Gestion des Loyers — Installation

## Prérequis

- Windows 10 ou 11.
- XAMPP/MySQL ou MariaDB démarré.
- Port MySQL par défaut : `3306`.

## Base de données

### Méthode recommandée

Importer `init_database.sql` depuis phpMyAdmin ou avec :

```powershell
mysql -u root -p < init_database.sql
```

Le script crée la base `gestion_loyers`, les tables principales et des données de démonstration. Il ne contient pas les enregistrements réels de votre poste de développement. Pour les retrouver, restaurez une sauvegarde SQL de cette base.

> Important : le script livré est non destructif et ne contient pas les données réelles du poste source. Faites tout de même une sauvegarde avant toute opération sur une base client, puis laissez l'application exécuter ses migrations automatiques.

### Migrations automatiques

Les migrations vérifient notamment :

- `locataires.date_creation` et `paiements.date_creation` ;
- le journal des maintenances ;
- les archives de paiements ;
- les tarifs historiques ;
- les signatures numériques.
- les demandes de paiement par lien et les preuves envoyées par téléphone.
- le registre `schema_migrations`, qui conserve la version et l'empreinte de la migration ;
- les incohérences de paiements : paiements orphelins, montants négatifs, restes incohérents et signatures orphelines.

Avant une migration importante, faire une sauvegarde :

```powershell
mysqldump -u root -p --single-transaction --routines --triggers gestion_loyers > backup_avant_migration.sql
```

La migration ne supprime pas les lignes. Elle remet uniquement `reste_a_payer` à zéro lorsqu'il est négatif, sans modifier `montant_paye`. Les anomalies restantes doivent être vérifiées avec le client avant toute correction métier.

## Configuration

Dans `config.json` :

```json
{
  "database": {
    "host": "localhost",
    "database": "gestion_loyers",
    "user": "root",
    "password": "",
    "port": 3306
  }
}
```

`localhost` désigne le MySQL installé sur le même ordinateur. Pour que
plusieurs postes voient les mêmes enregistrements, utilisez l'adresse réseau
d'un serveur MySQL commun à la place de `localhost`.

## Utilisation

- `Nouveau Paiement` : créer un locataire ou enregistrer un paiement.
- Double-cliquer sur une ligne : ouvrir l'historique.
- `Exporter PDF` : générer un rapport filtré.
- `Ajouter paiement` : enregistrer un acompte.
- `Souscripteurs spéciaux` : lancer une bascule mensuelle manuelle.
- `Archives` : consulter ou restaurer les anciennes données.
- `Créer lien de paiement` : copier/partager un lien ou QR temporaire pour que le locataire envoie sa preuve de paiement.
- `À valider` : ouvrir la preuve reçue, puis la valider ou la refuser. La validation ajoute automatiquement le montant demandé au paiement.

Les liens de paiement sont gratuits : ils ne débitent pas automatiquement une carte et ne nécessitent aucun compte de paiement en ligne. Le locataire paie avec son moyen habituel, puis transmet simplement le reçu. Le gestionnaire conserve la validation finale.

Pour un utilisateur non informaticien, utiliser directement
`Demarrer_TAP_Gestion.bat`. Il vérifie la présence de l'application et lance
le logiciel avec sa configuration locale.

## WhatsApp

Le fichier `whatsapp_report_sender.exe` est optionnel. Pour Meta Cloud API :

```powershell
[Environment]::SetEnvironmentVariable('TAP_WHATSAPP_ENABLED', '1', 'User')
[Environment]::SetEnvironmentVariable('TAP_WHATSAPP_MODE', 'cloud', 'User')
[Environment]::SetEnvironmentVariable('TAP_WHATSAPP_TO', '+243XXXXXXXXX', 'User')
[Environment]::SetEnvironmentVariable('TAP_WHATSAPP_TOKEN', 'VOTRE_TOKEN', 'User')
[Environment]::SetEnvironmentVariable('TAP_WHATSAPP_PHONE_NUMBER_ID', 'VOTRE_ID', 'User')
```

Test sans envoi réel :

```powershell
.\whatsapp_report_sender.exe --send-monthly-pdf --preview
```

Un fournisseur absent produit le statut `not_configured`, pas un faux succès.

## Signature QR

Le téléphone et le PC doivent être sur le même Wi-Fi. Si l'adresse détectée automatiquement n'est pas joignable, définir l'adresse LAN du PC avant de lancer l'application :

```powershell
[Environment]::SetEnvironmentVariable('TAP_SIGNATURE_HOST', '192.168.1.20', 'User')
```

Le QR expire après 10 minutes. La signature et la mise à jour du paiement sont validées dans une transaction unique ; un double envoi ne recrédite pas le paiement.

## Portail mobile et fonctionnement hors ligne

Le portail mobile est préparé automatiquement quand l'application desktop est
lancée. Il n'est normalement pas nécessaire de démarrer une deuxième fenêtre.
Depuis un paiement, utiliser le menu **Créer lien portail locataire** : le
programme crée le lien, l'affiche sous forme de QR code et le copie aussi dans
le presse-papiers. Le téléphone et le PC doivent être connectés au même Wi-Fi.

Les clés techniques sont générées automatiquement et conservées dans le profil
Windows de l'utilisateur (`%LOCALAPPDATA%\TAP_Gestion_Loyers`). Elles ne doivent
pas être copiées dans Git ni dans `config.json`. Le QR du reçu permet de rouvrir
le reçu depuis le téléphone et reste inclus lors de l'impression ou de
l'enregistrement en PDF.

Si l'adresse affichée dans le QR n'est pas joignable sur le réseau, renseigner
une fois l'adresse LAN du PC dans `config.json`, sous
`mobile_portal.public_host` (par exemple `192.168.1.20`), puis relancer TAP.
Pour un accès Internet, ajouter HTTPS, un proxy sécurisé et une authentification
forte ; le mode Wi-Fi local est recommandé.

## Sauvegarde

Sauvegarde manuelle :

```powershell
mysqldump -u root -p gestion_loyers > backup.sql
```

L'application utilise également `mysqldump` pour ses sauvegardes automatiques lorsqu'il est disponible.

## Dépannage

- **Liste vide** : vérifier le serveur, la base et le nombre d'enregistrements ;
  une base locale nouvellement créée est normalement vide (hors démonstration).
- **Connexion refusée** : vérifier MySQL, le port et `config.json`.
- **Unknown column** : relancer l'application pour exécuter les migrations.
- **WhatsApp not_configured** : configurer un fournisseur API dans les variables `TAP_WHATSAPP_`.
- **Installation depuis le code source** : installer Python 3.10+ et les dépendances de `requirements.txt`.
