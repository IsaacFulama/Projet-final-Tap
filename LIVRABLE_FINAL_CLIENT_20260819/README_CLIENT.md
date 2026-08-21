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
- MySQL / XAMPP démarré, ou serveur MySQL réseau accessible
- Base de données `gestion_loyers` importée et restaurée avec les données utiles

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
- Vérifier que `config.json` pointe vers le même serveur et la même base que le poste source
- Consulter `INSTALLATION.md`
