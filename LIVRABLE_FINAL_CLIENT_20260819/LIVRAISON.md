# TAP Gestion des Loyers — Livraison client

## Version livrée

- Version : 4.3
- Date : 19 août 2026
- Base validée : MySQL/MariaDB

## Contenu

- `TAP_Gestion_Loyers.exe` : application principale (interface desktop).
- `whatsapp_report_sender.exe` : utilitaire optionnel de rapports WhatsApp.
- `TAP_Mobile_Server.exe` : serveur du portail mobile, lancé automatiquement.
- `Demarrer_TAP_Gestion.bat` : lancement guidé de l'application desktop.
- `Demarrer_Portail_Mobile.bat` : lancement manuel de secours du serveur mobile.
- `config.json` : configuration de la base de données (locale ou réseau).
- `init_database.sql` : création de la base et des données de démonstration.
- `INSTALLATION.md` : installation et dépannage.
- `README_CLIENT.md` : guide rapide.
- `GUIDE_UTILISATION.md` : guide d'utilisation détaillé.
- `GUIDE_CONFIGURATION_WHATSAPP.md` : configuration des fournisseurs WhatsApp.
- `GUIDE_FONCTIONNALITES_INTELLIGENTES.md` : fonctionnalités automatiques.

## Installation rapide

1. Installer et démarrer XAMPP/MySQL, ou rendre le serveur MySQL réseau accessible.
2. Importer `init_database.sql` ou laisser les migrations de l'application créer les éléments manquants.
3. Modifier `config.json` si nécessaire (accès MySQL, portail mobile, rapports).
4. Lancer `Demarrer_TAP_Gestion.bat` ou double-cliquer sur `TAP_Gestion_Loyers.exe`.

## Notes importantes

- Les enregistrements ne sont pas stockés dans l'EXE. Pour partager les mêmes
  données, configurer un serveur MySQL commun ou restaurer la sauvegarde SQL du
  poste source ; `localhost` crée une base indépendante par ordinateur.
- Les migrations créent notamment `date_creation`, le journal de maintenance, les archives, les tarifs et les signatures.
- La signature QR est idempotente, transactionnelle et accepte `TAP_SIGNATURE_HOST` si l'IP automatique n'est pas joignable.
- Le registre `schema_migrations` et le contrôle de cohérence facilitent les migrations sûres.
- Les tokens WhatsApp ne doivent jamais être placés dans Git ou dans `config.json` en clair.
- Sans fournisseur WhatsApp configuré, aucun envoi automatique n'est effectué.
- Sauvegardez régulièrement votre base de données MySQL.

## Support

Pour toute question, consulter `INSTALLATION.md` ou contacter le support technique.
