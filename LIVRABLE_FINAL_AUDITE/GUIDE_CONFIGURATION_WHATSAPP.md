# Guide de Configuration WhatsApp API pour TAP Gestion des Loyers

Ce guide explique comment configurer l'envoi automatique de rapports PDF mensuels via WhatsApp.

## Prérequis

1. **Compte WhatsApp Business** - Vous devez avoir un compte WhatsApp Business
2. **Meta for Developers Account** - Créer un compte sur [developers.facebook.com](https://developers.facebook.com)
3. **Application WhatsApp Business** - Créer une application dans Meta for Developers

## Option 1: WhatsApp Cloud API (Recommandé)

### Étape 1: Créer une application Meta

1. Allez sur [developers.facebook.com](https://developers.facebook.com)
2. Connectez-vous avec votre compte Facebook
3. Cliquez sur "Create App" → "Business" → "WhatsApp"
4. Remplissez les informations de l'application
5. Notez l'**App ID** et l'**App Secret**

### Étape 2: Configurer WhatsApp

1. Dans votre application, allez dans "WhatsApp" → "Configuration"
2. Cliquez sur "Get Started" pour WhatsApp Cloud API
3. Sélectionnez ou créez un **WhatsApp Business Account**
4. Ajoutez un numéro de téléphone WhatsApp Business
5. Notez le **Phone Number ID** (ex: 123456789012345)

### Étape 3: Générer un Token d'accès

1. Dans "WhatsApp" → "Configuration" → "API Setup"
2. Cliquez sur "Generate Token"
3. Choisissez la durée (recommandé: 60 jours ou plus)
4. Copiez le **Access Token** (commence par `EAAB...`)

### Étape 4: Configurer les variables d'environnement

**Sur Windows (PowerShell):**
```powershell
# Définir les variables d'environnement
$env:TAP_WHATSAPP_MODE = "cloud"
$env:TAP_WHATSAPP_ENABLED = "1"
$env:TAP_WHATSAPP_TO = "+243852382067"  # Votre numéro de téléphone
$env:TAP_WHATSAPP_TOKEN = "EAABwzLixjkY..."  # Votre token d'accès
$env:TAP_WHATSAPP_PHONE_NUMBER_ID = "123456789012345"  # Votre Phone Number ID
```

**Pour rendre les variables permanentes sur Windows:**
```powershell
# Variables utilisateur (permanentes)
[System.Environment]::SetEnvironmentVariable('TAP_WHATSAPP_MODE', 'cloud', 'User')
[System.Environment]::SetEnvironmentVariable('TAP_WHATSAPP_ENABLED', '1', 'User')
[System.Environment]::SetEnvironmentVariable('TAP_WHATSAPP_TO', '+243852382067', 'User')
[System.Environment]::SetEnvironmentVariable('TAP_WHATSAPP_TOKEN', 'EAABwzLixjkY...', 'User')
[System.Environment]::SetEnvironmentVariable('TAP_WHATSAPP_PHONE_NUMBER_ID', '123456789012345', 'User')
```

**Sur Linux/Mac:**
```bash
# Ajouter à ~/.bashrc ou ~/.zshrc
export TAP_WHATSAPP_MODE=cloud
export TAP_WHATSAPP_ENABLED=1
export TAP_WHATSAPP_TO="+243852382067"
export TAP_WHATSAPP_TOKEN="EAABwzLixjkY..."
export TAP_WHATSAPP_PHONE_NUMBER_ID="123456789012345"
```

### Étape 5: Tester la configuration

```bash
# Test en mode preview (sans envoi réel)
python whatsapp_report_sender.py --send-monthly-pdf --preview

# Test avec envoi réel
python whatsapp_report_sender.py --send-monthly-pdf
```

## Option 2: Twilio WhatsApp API

### Étape 1: Créer un compte Twilio

1. Allez sur [twilio.com](https://www.twilio.com)
2. Créez un compte gratuit
3. Vérifiez votre numéro de téléphone

### Étape 2: Configurer WhatsApp Sandbox

1. Dans le tableau de bord Twilio, allez dans "Messaging" → "Try it out" → "Send a WhatsApp message"
2. Suivez les instructions pour rejoindre le sandbox WhatsApp
3. Notez le **Account SID** et le **Auth Token**

### Étape 3: Configurer les variables d'environnement

**Sur Windows (PowerShell):**
```powershell
$env:TAP_WHATSAPP_MODE = "twilio"
$env:TAP_WHATSAPP_ENABLED = "1"
$env:TAP_WHATSAPP_TO = "+243852382067"
$env:TAP_WHATSAPP_TWILIO_SID = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
$env:TAP_WHATSAPP_TWILIO_TOKEN = "your_auth_token"
$env:TAP_WHATSAPP_TWILIO_FROM = "+14155238886"  # Numéro Twilio Sandbox
```

**Pour rendre les variables permanentes sur Windows:**
```powershell
[System.Environment]::SetEnvironmentVariable('TAP_WHATSAPP_MODE', 'twilio', 'User')
[System.Environment]::SetEnvironmentVariable('TAP_WHATSAPP_ENABLED', '1', 'User')
[System.Environment]::SetEnvironmentVariable('TAP_WHATSAPP_TO', '+243852382067', 'User')
[System.Environment]::SetEnvironmentVariable('TAP_WHATSAPP_TWILIO_SID', 'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 'User')
[System.Environment]::SetEnvironmentVariable('TAP_WHATSAPP_TWILIO_TOKEN', 'your_auth_token', 'User')
[System.Environment]::SetEnvironmentVariable('TAP_WHATSAPP_TWILIO_FROM', '+14155238886', 'User')
```

## Configuration de config.json

Le fichier `config.json` doit contenir la configuration des destinataires:

```json
{
  "database": {
    "host": "localhost",
    "database": "gestion_loyers",
    "user": "root",
    "password": ""
  },
  "whatsapp_reports": {
    "enabled": true,
    "recipients": ["+243852382067", "+241987654321"],
    "check_internet": true,
    "send_monthly_pdf": true
  }
}
```

### Explication des paramètres:

- **enabled**: Active/désactive l'envoi automatique des rapports PDF
- **recipients**: Liste des numéros de téléphone des destinataires (avec code pays)
- **check_internet**: Vérifie la connexion internet avant envoi
- **send_monthly_pdf**: Active l'envoi des rapports PDF mensuels

## Fonctionnement automatique

Une fois configuré, l'envoi des rapports se fait automatiquement:

1. Au démarrage de l'application (`python main.py`)
2. Après la mise à jour automatique des statuts (à partir du 7 du mois)
3. Si la connexion internet est active (si `check_internet: true`)
4. Les rapports PDF sont générés pour:
   - Les paiements "En règle" du mois courant
   - Les paiements "Litigieux" du mois courant
5. Chaque PDF est envoyé à tous les destinataires configurés

## Dépannage

### Erreur: "Pas de connexion internet"
- Vérifiez votre connexion internet
- Si vous voulez tester sans internet, mettez `"check_internet": false` dans config.json

### Erreur: "Configuration Cloud API incomplète"
- Vérifiez que toutes les variables d'environnement sont définies
- Vérifiez que le token est valide et n'a pas expiré

### Erreur: "Aucun destinataire configuré"
- Vérifiez que la liste `recipients` dans config.json n'est pas vide
- Vérifiez le format des numéros (avec code pays, ex: +243...)

### Erreur: "Aucune donnée disponible"
- Vérifiez qu'il y a des paiements pour le mois courant dans la base de données
- Vérifiez que les statuts "En règle" et "Litigieux" existent

## Sécurité

⚠️ **Important:**
- Ne partagez jamais vos tokens d'accès
- Ne commitez jamais les tokens dans Git
- Utilisez des variables d'environnement plutôt que des fichiers de configuration
- Faites tourner vos tokens régulièrement
- Limitez les permissions de votre application Meta

## Test et validation

### Test manuel:
```bash
# Test en mode preview (sans envoi réel)
python whatsapp_report_sender.py --send-monthly-pdf --preview

# Test avec envoi réel
python whatsapp_report_sender.py --send-monthly-pdf
```

### Test automatique:
```bash
# Lancer l'application normale
python main.py
```

Les logs montreront:
- "Rapports PDF mensuels envoyés avec succès à X destinataire(s)" si succès
- "Pas de connexion internet - rapports PDF non envoyés" si pas d'internet
- "Envoi automatique des rapports PDF désactivé" si désactivé

## Support

Pour plus d'informations:
- Documentation Meta Cloud API: https://developers.facebook.com/docs/whatsapp/cloud-api
- Documentation Twilio WhatsApp: https://www.twilio.com/docs/whatsapp
- Issues du projet: https://github.com/IsaacFulama/TAP1/issues
