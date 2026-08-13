# TAP Gestion des Loyers — Guide client

**Version 3.7** | Juillet 2026

## Lancement
1. Ouvrir `TAP_Gestion_Loyers.exe`
2. Se connecter avec :
   - utilisateur : `TAPADM`
   - mot de passe : `TAPADM`

## Configuration
- Le fichier `config.json` contient les paramètres MySQL.
- Si votre mot de passe MySQL change, modifiez uniquement ce fichier.
- Si MySQL utilise un port différent, modifiez aussi la clé `port`.

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
- Interface claire et professionnelle avec fond blanc
- Tableau des enregistrements agrandi pour une lecture plus confortable

## En cas de souci
- Vérifier que MySQL est bien lancé
- Vérifier que `config.json` pointe vers la bonne base
- Vérifier le port MySQL si la connexion refuse
- Consulter `INSTALLATION.md`
