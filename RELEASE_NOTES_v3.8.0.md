# TAP Gestion des Loyers v3.8.0

## Nouveautés

- Page dédiée aux enregistrements avec filtres combinables et affichage responsive.
- Rappels WhatsApp intelligents : total dû, niveau d’urgence et réponses guidées.
- Sauvegarde SQL automatique tous les 14 jours, archive ZIP vérifiée par SHA-256 et rotation configurable.
- Portail mobile, liens de paiement et mode hors ligne conservés.
- Landing page responsive et documentation web publiées avec GitHub Pages.

## Corrections

- Meilleure lisibilité des enregistrements sur les écrans compacts.
- Restauration des fonctions de liens et de preuves de paiement mobile.
- Fallback de dossier pour les sauvegardes lorsque le profil Windows n’est pas accessible.

## Installation

1. Démarrer MySQL/MariaDB dans XAMPP.
2. Télécharger `TAP_Gestion_Loyers.exe` depuis la release.
3. Placer `config.json` à côté de l’exécutable et renseigner les paramètres de base.
4. Lancer l’application et modifier le mot de passe initial.

## Validation

- 122 tests automatisés passés.
- Couverture de tests : 50,33 %.
- Exécutable Windows généré avec PyInstaller et démarré avec succès.
