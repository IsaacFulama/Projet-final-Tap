# TAP Gestion des Loyers — Guide client

**Version 3.7** | Juillet 2026

## Lancement
1. Ouvrir `TAP_Gestion_Loyers.exe`
2. Se connecter avec :
   - utilisateur : `TAPADM`
   - mot de passe : `TAPADM`

## Configuration
- Le fichier `config.json` contient les paramètres MySQL.
- Le port MySQL est configurable (`3306` par défaut).
- Si votre mot de passe MySQL change, modifiez uniquement ce fichier.

## Prérequis
- Windows 10 ou 11
- MySQL / XAMPP démarré
- Base de données `gestion_loyers` importée

## Fonctionnalités
- Ajout et suivi des paiements
- Statut de souscription sur chaque paiement : Spécial ou Simple
- Filtrage par nom, mois, statut et devise
- Filtrage par statut de souscription
- Export PDF et CSV
- Historique des paiements par locataire
- Migration automatique des souscripteurs `Spécial` au changement de mois, avec notification de fin d'exécution
- Bascule automatique des paiements `En attente` du mois précédent vers `Litigieux` dès la duplication mensuelle
- Les nouveaux enregistrements du mois courant démarrent en `En attente`
- Le choix du mois commence en janvier 2025 dans le formulaire de saisie
- Rappel automatique des paiements `Litigieux` à partir du 7 du mois, avec notification intégrée
- Page dédiée aux enregistrements avec actions rapides et historique par locataire
- Interface claire et professionnelle avec fond blanc
- Tableau des enregistrements agrandi pour une lecture plus confortable
- Envoi automatique de rapports PDF mensuels via WhatsApp, basé sur les paiements du mois courant
- Utilitaire WhatsApp autonome pour envoyer les rapports automatiques sans modifier l'application principale

## Configuration WhatsApp requise
- `whatsapp_reports.enabled` doit être `true` dans `config.json`
- `whatsapp_reports.send_monthly_pdf` doit être `true`
- Les destinataires sont listés dans `whatsapp_reports.recipients`
- Les variables d'environnement nécessaires pour l'API sont décrites dans `GUIDE_CONFIGURATION_WHATSAPP.md`

## En cas de souci
- Vérifier que MySQL est bien lancé
- Vérifier que `config.json` pointe vers la bonne base
- Consulter `INSTALLATION.md`
