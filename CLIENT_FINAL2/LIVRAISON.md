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
- **Suivi des statuts** : En règle, Litigieux, En attente
- **Statut souscription** : Spécial ou Simple
- **Historique** : Historique des paiements par locataire
- **Export PDF** : Export filtré avec totaux par devise
- **Envoi WhatsApp automatique** : génération et envoi de rapports PDF mensuels depuis les paiements du mois courant (statuts `En règle` et `Litigieux`)
- **Dashboard** : Analyse financière avec graphiques
- **Filtres** : Par nom, statut, statut souscription, devise, mois
- **Maintenance mensuelle** : migration automatique des souscripteurs `Spécial` vers le mois courant, avec bascule des anciens `En attente` en `Litigieux`
- **Affectation automatique des paiements Spéciaux** : un versement est affecté au plus ancien mois impayé, puis aux mois suivants si nécessaire
- **Rappel litigieux** : notification automatique à partir du 7 du mois pour les paiements toujours en retard
- **Sélecteur de mois** : choix disponible à partir de janvier 2025 dans le formulaire
- **Interface revue** : fond blanc professionnel, texte plus lisible et tableau des enregistrements agrandi

## Support technique

Pour toute question, consulter le fichier `INSTALLATION.md` ou contacter le support.

## Configuration WhatsApp

- Le mode WhatsApp est activé uniquement si `config.json` contient `whatsapp_reports.enabled: true`.
- Les tokens et identifiants API sont lus depuis les variables d'environnement :
  - `TAP_WHATSAPP_ENABLED`
  - `TAP_WHATSAPP_MODE`
  - `TAP_WHATSAPP_TO`
  - `TAP_WHATSAPP_TOKEN`
  - `TAP_WHATSAPP_PHONE_NUMBER_ID`
- Le document `GUIDE_CONFIGURATION_WHATSAPP.md` décrit la configuration complète et la validation.

## Notes importantes

- L'application nécessite MySQL/XAMPP pour fonctionner
- Les données sont stockées dans la base de données MySQL
- Sauvegardez régulièrement votre base de données
- Le fichier `config.json` doit être dans le même dossier que l'exécutable

## Version
- Version : 3.8
- Date de livraison : 29 juillet 2026
