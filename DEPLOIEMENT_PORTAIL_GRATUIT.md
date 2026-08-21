# Déploiement du portail web

## Limite importante

Le portail actuel utilise encore `mysql.connector` et des requêtes MySQL. Un hébergeur gratuit ne fournit généralement pas un serveur MySQL durable avec stockage fiable. Supabase PostgreSQL est déjà une cible d'import, mais n'est pas encore un backend runtime compatible avec le repository MySQL.

Il est donc possible de publier le portail sur Render Free ou équivalent uniquement après avoir fourni une base MySQL distante compatible, ou après migration complète du repository vers PostgreSQL. Publier immédiatement avec `config.json` local casserait les paiements et les preuves.

## Préparation locale

```powershell
python -m pytest -q -o addopts=
python -m py_compile mobile_server.py tap/mobile/api.py tap/mobile/payment_links.py
docker build -f Dockerfile.portal -t tap-portal .
docker run --rm -p 10000:10000 `
  -e DB_HOST=host.docker.internal `
  -e DB_NAME=gestion_loyers `
  -e DB_USER=root `
  -e DB_PASS= `
  tap-portal
```

Le conteneur est configuré avec Gunicorn, `0.0.0.0` et le port fourni par l'hébergeur. Ne mettez jamais le mot de passe de production dans cette commande ou dans Git.

## Render Free choisi

Render Free accepte un service web Docker et plusieurs routes dynamiques dans le même projet : `/portal/<token>` pour le portail et `/pay/<token>` pour les liens de paiement. Le fichier [render.yaml](render.yaml) déclare ces routes via l'application Flask et utilise `/api/mobile/health` comme health check.

## Déploiement Render par ligne de commande

Avant le lancement, publier les fichiers de déploiement dans un dépôt Git distant :

```powershell
git add render.yaml Dockerfile.portal .dockerignore requirements.txt tap mobile_server.py
git commit -m "Prepare portal deployment"
git push origin main
```

Render nécessite un compte, un dépôt Git et un token API. Ces secrets doivent être saisis dans le terminal par l'opérateur, jamais dans le code. Le CLI Render n'était pas installé dans cet environnement ; installez-le selon la documentation officielle, puis authentifiez-vous :

```powershell
npm install -g @render/cli
render login
render blueprint launch
```

Le dépôt doit contenir `render.yaml`, `Dockerfile.portal`, `requirements.txt` et le package `tap/`. La commande `render blueprint launch` ouvre la sélection du dépôt et crée le service sans demander de mot de passe dans le code.

Le plan gratuit peut mettre le service en veille après inactivité et impose des limites de CPU, heures mensuelles et bande passante. Il convient à une démonstration ou un faible trafic, pas à une garantie de disponibilité.

Paramètres du service :

```text
Build command : pip install -r requirements.txt gunicorn
Start command : gunicorn -b 0.0.0.0:$PORT --workers 2 --timeout 60 tap.mobile.api:create_app()
Health path   : /api/mobile/health
```

Variables obligatoires : `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASS`, `DB_PORT`, `TAP_PORTAL_TOKEN_PEPPER`, `TAP_MOBILE_API_KEY`. L'URL de la base doit être un MySQL managé accessible depuis Internet, avec TLS et liste blanche réseau. `config.json` local ne doit pas être déployé comme source de secrets.

## Vérification après publication

```powershell
Invoke-WebRequest https://<service>.onrender.com/api/mobile/health
Invoke-WebRequest https://<service>.onrender.com/portal/<token>
Invoke-WebRequest https://<service>.onrender.com/pay/<token>
```

Tester ensuite : dépôt PNG/JPEG/PDF, rejet d'un fichier déguisé, empreinte SHA-256, apparition dans la file gestionnaire, refus, approbation et consultation du statut final. Le serveur gratuit peut dormir après inactivité : le premier appel peut être lent et les fichiers stockés en base doivent rester sous la limite de taille.

## Validation d'une preuve

1. Le portail vérifie MIME déclaré, signature binaire et limite de 2 Mo.
2. Le serveur calcule `SHA-256` et stocke l'empreinte avec la preuve.
3. La demande passe à `proof_submitted` / `pending_review`.
4. Le gestionnaire vérifie visuellement la preuve, le montant, la date, la référence, le bénéficiaire et le relevé bancaire.
5. Le bouton Valider utilise un verrou SQL pour empêcher un double crédit.
6. L'approbation crédite le paiement et passe l'état à `approved`; un refus passe à `rejected` avec note.
7. L'utilisateur voit le résultat lors du rechargement de son portail. Un email nécessite un SMTP configuré séparément.

## Statut de déploiement

Aucun déploiement public n'est exécuté automatiquement ici : il manque un compte/token Render, un dépôt distant connecté et une base MySQL distante compatible. Le Dockerfile, `render.yaml` et les commandes sont prêts ; l'étape suivante doit être exécutée par le propriétaire du compte avec les secrets de production.