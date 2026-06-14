# Guide d'Installation - TAP Gestion des Loyers

**Version 3.3** | Juin 2026

## 📋 Table des matières

1. [Prérequis](#prérequis)
2. [Installation de MySQL](#installation-de-mysql)
3. [Configuration de la base de données](#configuration-de-la-base-de-données)
4. [Installation de l'application](#installation-de-lapplication)
5. [Configuration de l'application](#configuration-de-lapplication)
6. [Premier lancement](#premier-lancement)
7. [Vérification de l'installation](#vérification-de-linstallation)
8. [Mise à jour](#mise-à-jour)
9. [Désinstallation](#désinstallation)

## 🔧 Prérequis

### Configuration minimale requise

- **Système** : Windows 10 ou supérieur (64 bits)
- **Processeur** : Intel Core i3 ou équivalent
- **Mémoire RAM** : 4 Go minimum (8 Go recommandé)
- **Espace disque** : 500 Mo disponibles
- **Résolution** : 1366x768 minimum

### Logiciels requis

- **MySQL 5.7+** ou **XAMPP** (incluant MySQL)
- **Python 3.8+** (si installation depuis le code source)
- **Navigateur web** (pour phpMyAdmin)

## 🗄️ Installation de MySQL

### Option 1 : Installation avec XAMPP (Recommandé)

1. **Télécharger XAMPP**
   - Allez sur https://www.apachefriends.org/
   - Téléchargez la version pour Windows
   - Exécutez l'installateur

2. **Installer XAMPP**
   - Suivez les instructions de l'assistant
   - Cochez "MySQL" et "phpMyAdmin"
   - Terminez l'installation

3. **Démarrer MySQL**
   - Ouvrez le "XAMPP Control Panel"
   - Cliquez sur "Start" à côté de "MySQL"
   - Le service doit passer au vert

4. **Vérifier l'installation**
   - Ouvrez http://localhost/phpmyadmin dans votre navigateur
   - Vous devriez voir l'interface phpMyAdmin

### Option 2 : Installation MySQL Standalone

1. **Télécharger MySQL**
   - Allez sur https://dev.mysql.com/downloads/mysql/
   - Téléchargez la version Community Server
   - Exécutez l'installateur

2. **Configurer MySQL**
   - Choisissez "Developer Default"
   - Définissez un mot de passe root (notez-le !)
   - Terminez l'installation

3. **Démarrer le service**
   - Ouvrez "Services" dans Windows
   - Trouvez "MySQL80" (ou similaire)
   - Démarrez le service

## 🗃️ Configuration de la Base de Données

### Importer le schéma de base de données

1. **Ouvrir phpMyAdmin**
   - Allez sur http://localhost/phpmyadmin
   - Connectez-vous avec vos identifiants MySQL

2. **Créer la base de données**
   - Cliquez sur l'onglet "SQL"
   - Copiez le contenu du fichier `init_database.sql`
   - Collez-le dans l'éditeur
   - Cliquez sur "Exécuter"

3. **Vérifier la création**
   - Vous devriez voir la base de données `gestion_loyers`
   - Elle contient deux tables : `locataires` et `paiements`

### Alternative : Import via fichier

1. Dans phpMyAdmin, cliquez sur "Importer"
2. Sélectionnez le fichier `init_database.sql`
3. Cliquez sur "Exécuter"

## 💻 Installation de l'Application

### Option 1 : Via l'exécutable (Recommandé)

1. **Extraire les fichiers**
   - Décompressez le dossier `LIVRAISON_V3`
   - Placez-le dans un emplacement permanent (ex: `C:\Program Files\TAP\`)

2. **Lancer l'application**
   - Double-cliquez sur `TAP_Gestion_Loyers.exe`
   - L'application devrait se lancer

### Option 2 : Depuis le code source

1. **Installer Python**
   - Téléchargez Python 3.8+ sur https://www.python.org/
   - Cochez "Add Python to PATH" lors de l'installation
   - Vérifiez l'installation : `python --version`

2. **Créer un environnement virtuel**
   ```bash
   cd "chemin/vers/LIVRAISON_V3"
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

4. **Copier les fichiers source**
   - Copiez le dossier `tap/` depuis le projet principal
   - Copiez `main.py` et les autres fichiers nécessaires

5. **Lancer l'application**
   ```bash
   python main.py
   ```

## ⚙️ Configuration de l'Application

### Modifier le fichier config.json

1. **Ouvrir le fichier**
   - Éditez `config.json` avec un éditeur de texte
   - Vous pouvez utiliser Notepad, VS Code, etc.

2. **Configurer les paramètres**
   ```json
   {
     "database": {
       "host": "localhost",
       "database": "gestion_loyers",
       "user": "root",
       "password": "votre_mot_de_passe_mysql"
     }
   }
   ```

3. **Paramètres expliqués**
   - `host` : Adresse du serveur MySQL (généralement "localhost")
   - `database` : Nom de la base de données ("gestion_loyers")
   - `user` : Utilisateur MySQL (généralement "root")
   - `password` : Mot de passe MySQL (celui défini lors de l'installation)

### Variables d'environnement (Optionnel)

Vous pouvez également utiliser des variables d'environnement :

- `DB_HOST` : Hôte de la base de données
- `DB_NAME` : Nom de la base de données
- `DB_USER` : Utilisateur de la base de données
- `DB_PASSWORD` : Mot de passe de la base de données

## 🚀 Premier Lancement

### Connexion initiale

1. **Lancer l'application**
   - Double-cliquez sur `TAP_Gestion_Loyers.exe`
   - Ou exécutez `python main.py`

2. **Se connecter**
   - Utilisateur : `TAPADM`
   - Mot de passe : `TAPADM`

3. **Changer le mot de passe**
   - ⚠️ Important : Changez le mot de passe par défaut
   - Contactez le support technique pour le modifier

### Vérifier le fonctionnement

1. **Tester l'ajout d'un paiement**
   - Cliquez sur "Nouveau Paiement"
   - Remplissez le formulaire avec des données de test
   - Vérifiez que l'enregistrement fonctionne

2. **Tester les filtres**
   - Ajoutez plusieurs paiements
   - Testez les filtres par nom, mois, statut

3. **Tester l'export PDF**
   - Sélectionnez des paiements
   - Cliquez sur "Exporter PDF"
   - Vérifiez que le fichier est généré

## ✅ Vérification de l'Installation

### Liste de contrôle

- [ ] MySQL est installé et fonctionne
- [ ] La base de données `gestion_loyers` existe
- [ ] Les tables `locataires` et `paiements` sont créées
- [ ] Le fichier `config.json` est configuré
- [ ] L'application se lance sans erreur
- [ ] La connexion à la base de données fonctionne
- [ ] L'ajout de paiements fonctionne
- [ ] Les filtres fonctionnent
- [ ] L'export PDF fonctionne

### Résoudre les problèmes courants

**Erreur de connexion MySQL**
- Vérifiez que MySQL est démarré
- Vérifiez les paramètres dans `config.json`
- Vérifiez que le port 3306 n'est pas bloqué

**Erreur "database not found"**
- Importez le fichier `init_database.sql`
- Vérifiez que la base de données existe dans phpMyAdmin

**Interface ne s'affiche pas**
- Vérifiez votre résolution d'écran
- Redémarrez l'application
- Vérifiez que CustomTkinter est installé

## 🔄 Mise à Jour

### Depuis une version précédente

1. **Sauvegarder les données**
   - Exportez vos données depuis phpMyAdmin
   - Sauvegardez le fichier `config.json`

2. **Remplacer les fichiers**
   - Supprimez l'ancienne version
   - Extrayez la nouvelle version
   - Restaurez votre `config.json`

3. **Mettre à jour la base de données**
   - Importez le nouveau `init_database.sql`
   - Vos données existantes seront préservées

4. **Vérifier**
   - Lancez l'application
   - Vérifiez que vos données sont intactes

## 🗑️ Désinstallation

### Supprimer l'application

1. **Arrêter l'application**
   - Fermez toutes les instances de l'application

2. **Supprimer les fichiers**
   - Supprimez le dossier `LIVRAISON_V3`
   - Supprimez le raccourci du bureau si présent

3. **Supprimer la base de données** (Optionnel)
   - Ouvrez phpMyAdmin
   - Sélectionnez la base de données `gestion_loyers`
   - Cliquez sur "Supprimer"

### Nettoyer le système

1. **Supprimer l'environnement virtuel** (si installé depuis le code)
   ```bash
   cd "chemin/vers/LIVRAISON_V3"
   .venv\Scripts\deactivate
   rmdir /s .venv
   ```

2. **Supprimer les logs**
   - Supprimez `app.log`
   - Supprimez le dossier `error_reports/`

## 📞 Support Technique

### Obtenir de l'aide

Si vous rencontrez des problèmes lors de l'installation :

1. Consultez le guide de dépannage dans `README_CLIENT.md`
2. Vérifiez les logs dans `app.log`
3. Consultez les rapports d'erreurs dans `error_reports/`
4. Contactez le support technique TAP

### Informations de diagnostic

Pour accélérer le support, fournissez :
- Votre version de Windows
- Votre version de MySQL
- Le contenu de `app.log`
- Les messages d'erreur exacts

---

**© 2026 TAP - Tous droits réservés**
