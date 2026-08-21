# TAP Gestion des Loyers — Livrable client

## Démarrage

1. Installer et démarrer MySQL/MariaDB (XAMPP convient).
2. Importer `init_database.sql`.
3. Vérifier ou modifier `config.json`.
4. Double-cliquer sur `Demarrer_TAP_Gestion.bat`.

L’application principale est `TAP_Gestion_Loyers.exe`. Le fichier `config.json`
reste volontairement à côté de l’exécutable afin de pouvoir être adapté au
serveur MySQL du client.

## Contenu

- `TAP_Gestion_Loyers.exe` : application Windows autonome.
- `Demarrer_TAP_Gestion.bat` : lancement guidé.
- `config.json` : paramètres de connexion et options.
- `init_database.sql` : initialisation de la base.
- `INSTALLATION.md`, `README_CLIENT.md` et guides fonctionnels.

Les données et sauvegardes du client ne sont pas incluses dans ce paquet.
