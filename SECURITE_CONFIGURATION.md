# Configuration privée et données de contact

Les fichiers `config.json` suivis dans ce dépôt sont des modèles publics. Les destinataires WhatsApp sont volontairement vides et les envois automatiques WhatsApp sont désactivés par défaut.

## Configurer une installation locale

1. Copiez `config.json` vers un fichier local nommé `config.local.json`.
2. Renseignez les paramètres privés et les destinataires dans ce fichier.
3. Définissez `TAP_CONFIG` avant de lancer l'application.

Exemple PowerShell :

```powershell
$env:TAP_CONFIG = "C:\chemin\vers\config.local.json"
python main.py
```

Pour une application Windows empaquetée, définissez aussi `TAP_CONFIG` dans l'environnement du processus qui lance l'exécutable. Limitez les permissions de lecture du fichier local.

`config.local.json` et `config.private.json` sont ignorés par Git. Ne forcez pas leur ajout au dépôt. Ne placez jamais de mot de passe réel, de jeton ou de données personnelles dans les fichiers d'exemple.

## Historique Git et anciennes livraisons

Cette modification nettoie les fichiers de la version courante, mais ne supprime pas les anciennes valeurs de l'historique Git. Les anciennes versions des exécutables et les archives de livraison peuvent aussi contenir une configuration antérieure. Reconstruisez les livrables depuis la version corrigée avant redistribution. Le nettoyage de l'historique doit être planifié séparément, car il réécrit les références Git et peut affecter les clones existants.
