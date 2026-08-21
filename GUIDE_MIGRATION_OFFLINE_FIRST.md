# Migration Offline-First

La migration suit ce flux : XAMPP MySQL/MariaDB -> `app_data.db` SQLite -> Supabase PostgreSQL.
Le fichier SQLite devient la source locale embarquee ; `sync_queue` est son outbox pour les evenements a synchroniser.

## 1. Installer les dependances

Depuis la racine du projet :

```powershell
python -m pip install -r requirements.txt
```

Le serveur XAMPP doit etre demarre. Les parametres MySQL viennent de `config.json` par defaut (`localhost`, `root`, port `3306`).

## 2. Exporter XAMPP vers SQLite

```powershell
python migrate_mysql_to_sqlite.py --output app_data.db
```

Les options `--host`, `--port`, `--database`, `--user` et `--password` permettent de surcharger la configuration. Les memes valeurs peuvent etre fournies via `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER` et `MYSQL_PASSWORD`.

Le script reconstruit les tables, types, cles et index, copie les donnees existantes et conserve les identifiants. Il remplace les dates par leur representation ISO SQLite et les blobs par `BLOB`.

## 3. Creer le schema Supabase

Dans le SQL Editor du projet Supabase, executer [supabase_schema.sql](supabase_schema.sql). Le script est idempotent et ne supprime aucune table.

Recuperer ensuite la chaine PostgreSQL dans Supabase, sans la publier dans le depot :

```powershell
$env:SUPABASE_DB_URL = "postgresql://postgres:<mot-de-passe>@<host>:5432/postgres?sslmode=require"
```

## 4. Charger le stock initial

```powershell
python migrate_to_supabase.py --sqlite app_data.db
```

Le chargement utilise `ON CONFLICT DO NOTHING`, donc il peut etre relance apres une interruption. Les sequences PostgreSQL sont recalees apres l'import. Les lignes de `sync_queue` sont chargees comme JSONB ; les blobs restent des octets.

## Verification

Comparer le nombre de lignes de chaque table dans SQLite et Supabase avant de basculer l'application. Tester ensuite un ajout hors ligne : il doit creer une ligne `pending` dans `sync_queue`, puis passer a `synced`, `conflict` ou `failed` apres traitement par le futur worker de synchronisation.

Le schema Supabase ne remplace pas a lui seul la politique d'authentification : les regles RLS doivent etre definies selon les roles de l'application avant une exposition publique.