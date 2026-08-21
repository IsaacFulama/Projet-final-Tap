# Preparation XAMPP et flux de donnees

## Pourquoi XAMPP doit etre demarre

L'application desktop actuelle n'utilise pas encore SQLite ou Supabase comme base operationnelle. Son provider par defaut appelle `mysql.connector.connect()` vers `localhost:3306`, avec la base `gestion_loyers`. Si le serveur MySQL/MariaDB n'est pas actif, la connexion echoue et l'application affiche un demarrage guide au lieu d'acceder aux locataires et paiements.

## Composants XAMPP concernes

- **MySQL/MariaDB** : seul composant obligatoire pour la base. Il ecoute normalement sur le port `3306`, gere les tables InnoDB, les transactions, les cles et les requetes de l'application.
- **phpMyAdmin** : interface web facultative pour executer `init_database.sql`, verifier les tables et administrer les donnees. Elle ne sert pas de serveur SQL.
- **Apache** : inutile pour l'application desktop et inutile pour la connexion MySQL. Il est necessaire seulement si un autre site PHP ou une interface phpMyAdmin en depend.
- **FileZilla, Mercury, Tomcat** : sans role dans le fonctionnement de TAP Gestion des Loyers.

## Flux de connexion

```text
main.py
  -> ensure_startup_ready()
  -> load_db_config() depuis config.json/.env
  -> MySQLConnectionProvider
  -> mysql.connector.connect(host, port, database, user, password)
  -> migrations MySQL
  -> repository et services metier
  -> interface CustomTkinter
```

Le serveur mobile Flask utilise le meme repository MySQL lorsqu'il traite les paiements, les preuves et les evenements offline. Il ne remplace pas le serveur MySQL.

## Preparation avant lancement

1. Ouvrir XAMPP Control Panel.
2. Demarrer **MySQL/MariaDB** et verifier l'etat `Running`.
3. Creer `gestion_loyers` et ses tables avec `init_database.sql` si necessaire.
4. Verifier `config.json` : `host=localhost`, `port=3306`, `database=gestion_loyers`, utilisateur et mot de passe corrects.
5. Installer les dependances dans le meme Python que celui utilise par VS Code :

```powershell
python -m pip install -r requirements.txt
```

6. Tester sans ouvrir l'interface :

```powershell
python -c "from tap.core.startup_manager import ensure_startup_ready; print(ensure_startup_ready())"
```

7. Lancer l'application :

```powershell
python main.py
```

## Migration cloud

`migrate_mysql_to_sqlite.py` produit `app_data.db` et `migrate_to_supabase.py` charge le stock initial vers Supabase. Cette migration ne change pas encore le provider runtime de l'application : XAMPP reste donc obligatoire au lancement desktop tant qu'un provider PostgreSQL/SQLite et un worker de synchronisation n'ont pas ete integres.

Ne placez jamais un mot de passe dans `config.json`, un script versionne ou une commande partagee. Utilisez `.env` local, deja ignore par Git, et une URI Pooler Supabase avec `sslmode=require`.
