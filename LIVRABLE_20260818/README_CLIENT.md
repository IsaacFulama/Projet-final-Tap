# TAP Gestion des Loyers — Guide client

**Version 4.1 | 13 août 2026**

## Lancement

1. Démarrer MySQL/XAMPP.
2. Ouvrir `TAP_Gestion_Loyers.exe`.
3. Se connecter avec le compte initial `TAPADM` / `TAPADM`, puis modifier le mot de passe.

## Configuration

Le fichier `config.json` situé à côté de l'exécutable contient la connexion MySQL. Modifiez uniquement les valeurs de la section `database` selon votre installation. Les données ne sont pas contenues dans l'EXE : restaurez la base source ou utilisez un serveur MySQL commun si plusieurs postes doivent voir les mêmes enregistrements.

## Fonctionnalités

- Gestion des locataires et paiements.
- Acomptes et répartition FIFO des paiements spéciaux.
- Statuts `En règle`, `Litigieux`, `En attente`, `Complet` et `Partiel`.
- Filtres par nom, mois, statut, souscription et devise.
- Dashboard avec statistiques et graphiques.
- Historique par locataire, exports PDF et CSV.
- Maintenance mensuelle et rappels des impayés.
- Sauvegardes automatiques et restauration.
- Signature numérique locale par QR code.
- Affichage responsive : sur petit écran, les enregistrements restent lisibles et les détails sont accessibles par l'historique.
- Rapports WhatsApp configurables.
- Portail locataire mobile avec consultation, reçus et signature tactile.
- Paiement par lien gratuit : QR/lien temporaire, dépôt de preuve et validation manuelle.
- Archivage automatique des paiements clôturés anciens, avec consultation et restauration.
- Synchronisation hors ligne avec détection des conflits.

## WhatsApp

L'envoi automatique nécessite un fournisseur configuré dans les variables d'environnement : Meta Cloud API, Twilio ou webhook. Si seul le destinataire de `config.json` est renseigné, l'application retourne `not_configured` et n'annonce pas de faux envoi.

Consultez `GUIDE_CONFIGURATION_WHATSAPP.md`.

## Migration et cohérence

Les migrations sont journalisées dans `schema_migrations` et contrôlent les paiements orphelins, les montants invalides, les restes à payer et les signatures. Faites toujours une sauvegarde SQL avant une migration manuelle.

## En cas de souci

- Vérifier que MySQL est démarré.
- Vérifier `config.json`.
- Consulter `INSTALLATION.md` et les fichiers du dossier `error_reports`.
