# TAP Gestion des Loyers - Livraison au Client

## Contenu du dossier

### Fichiers essentiels
- `TAP_Gestion_Loyers.exe` - Application principale (exécutable Windows)
- `config.json` - Configuration de la base de données (à modifier selon votre environnement)
- `INSTALLATION.md` - Guide d'installation détaillé

### Documentation
- `INSTALLATION.md` - Instructions complètes d'installation et d'utilisation

## Instructions rapides pour le client

### 1. Prérequis
- XAMPP avec MySQL installé et démarré
- Base de données `gestion_loyers` créée (voir INSTALLATION.md pour les scripts SQL)

### 2. Configuration
1. Ouvrir le fichier `config.json`
2. Modifier les paramètres selon votre environnement :
   ```json
   {
     "database": {
       "host": "localhost",
       "database": "gestion_loyers",
       "user": "root",
       "password": "votre_mot_de_passe"
     }
   }
   ```

### 3. Lancement
- Double-cliquer sur `TAP_Gestion_Loyers.exe`

## Fonctionnalités principales

- **Gestion des paiements** : Enregistrement des paiements de loyers
- **Suivi des statuts** : Payé, Litigieux, En attente
- **Historique** : Historique des paiements par locataire
- **Export PDF** : Export filtré avec totaux par devise
- **Dashboard** : Analyse financière avec graphiques
- **Filtres** : Par nom, statut, devise, mois

## Support technique

Pour toute question, consulter le fichier `INSTALLATION.md` ou contacter le support.

## Notes importantes

- L'application nécessite MySQL/XAMPP pour fonctionner
- Les données sont stockées dans la base de données MySQL
- Sauvegardez régulièrement votre base de données
- Le fichier `config.json` doit être dans le même dossier que l'exécutable

## Version
- Version : 3.0
- Date de livraison : Juin 2026
