# Audit technique et preparation de livraison

Date de l'audit : 2026-08-20

## Perimetre

L'audit couvre les points d'entree (`main.py`, `mobile_server.py`), les couches `tap.core`, `tap.infrastructure.database`, `tap.mobile`, `tap.presentation`, les tests, la configuration et les fichiers PyInstaller. Les modules sont executes ou testes selon leur nature ; les parcours qui exigent une fenetre Tkinter, XAMPP ou Supabase sont signales comme dependants de l'environnement.

## Constats corriges

| Zone | Constat | Impact | Correction |
| --- | --- | --- | --- |
| `tap/presentation/views/main_window.py` | `HistoriqueDialog` etait reference avant sa declaration | Echec d'import de `main.py` | Methode attachee dans la classe |
| `tap/presentation/dialogs/formulaire.py` | Un ancien root Tk pouvait rester detruit avant `CTkFont` | Ouverture du formulaire impossible apres certaines fermetures | Root vivant reinstalle comme `_default_root` |
| `tap/presentation/bootstrap.py` | Callbacks `after` CustomTkinter restaient actifs pendant la transition login/app | Messages `invalid command name ...update` | Callbacks annules avant destruction du login |
| `tap/mobile/security.py` | Pepper portail par defaut codé en dur | Hash de tokens previsible si configuration absente | Demarrage de l'operation refuse sans `TAP_PORTAL_TOKEN_PEPPER` |
| `tap/mobile/api.py` | Montants convertis directement en `float` | Risque de precision et acceptation de fractions de centime | Validation `Decimal` a deux decimales |
| `migrate_to_supabase.py` | Lecture incorrecte des noms de colonnes SQLite et mauvais appel `executemany` psycopg v3 | Import initial interrompu | Colonnes et curseur corriges |

## Risques restant explicitement ouverts

1. L'application desktop utilise encore `mysql.connector` et la syntaxe SQL MySQL. Supabase est une cible d'import initial, pas encore un backend applicatif interchangeable.
2. `offline_queue`, `offline_sync_events` et `sync_queue` sont trois contrats différents. Un worker SQLite vers Supabase doit etre implemente et teste avant d'annoncer une synchronisation continue.
3. La cle `TAP_MOBILE_API_KEY` authentifie le service mais ne limite pas encore chaque paiement a un locataire/appareil autorise. Une autorisation par ressource est necessaire pour une exposition non locale.
4. Le compte local initial `TAPADM/TAPADM` reste un bootstrap connu ; il doit etre change immediatement ou remplace par un secret aleatoire impose a la premiere installation.
5. Les tests avec vrais MySQL, Supabase, Wi-Fi et navigateur ne sont pas executes dans la suite locale. Ils necessitent des services de test isoles et des secrets fournis hors depot.

## Portail mobile : incident de connexion corrige

La cause racine etait `mobile_portal.host=127.0.0.1` dans `config.json`. Cette adresse accepte le PC local mais refuse toute connexion depuis un smartphone ou une tablette. Le serveur ecoute maintenant sur `0.0.0.0` lorsque la configuration publie une adresse LAN, tandis que le lien genere conserve l'adresse publique detectee.

Validations effectuees le 2026-08-20 :

- serveur Flask lance sur `0.0.0.0:8765` ;
- `/api/mobile/health` repond `200` via `127.0.0.1` et `192.168.133.37` ;
- rendu navigateur sans debordement horizontal a 375x812, 768x1024 et 1440x900 ;
- token invalide retourne proprement `404` ;
- tests mobiles : 11 passes ; suite complete apres correctif : 115 passes.

Pour un telephone, le pare-feu Windows doit autoriser TCP entrant sur le port `8765` et le telephone doit etre sur le meme reseau Wi-Fi que le PC. Safari natif n'est pas disponible sur Windows ; le controle navigateur automatise couvre Chromium et les tests serveur sont independants du navigateur.

## Resultats de validation connus

- Suite fonctionnelle locale : 111 tests passes lors de la derniere execution complete.
- Tests mobiles apres durcissement : 9 tests passes.
- `main.py --demo-cycle --demo-date 2026-08-20` : execute avec XAMPP actif.
- Import initial SQLite vers Supabase Pooler : code de sortie 0, avec 6 locataires et 10 paiements importes.
- Build PyInstaller : executable genere et place dans `LIVRABLE_CLIENT_20260820/application/`.

Un taux de couverture de 95 % ne peut pas etre affirme pour chaque module sans rapport complet produit par `pytest-cov` et sans services externes disponibles. Les modules critiques doivent etre suivis par `coverage`, et les tests d'integration cloud doivent rester separes des tests unitaires.

## Commandes de controle

```powershell
python -m pytest -q -o addopts= --basetemp .pytest-tmp
python -m pytest -q -o addopts= --cov=tap --cov-report=term-missing
ruff check tap tests migrate_*.py
bandit -r tap
```
