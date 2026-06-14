# TAP Gestion des Loyers - Guide Client

**Version 3.3** | Juin 2026

## 📋 Vue d'ensemble

TAP Gestion des Loyers est une application professionnelle de gestion des souscriptions et paiements de loyers avec interface moderne et sécurisée.

## ✨ Nouveautés de la Version 3.3

### 🔐 Sécurité Renforcée
- **Authentification sécurisée** avec hashage des mots de passe (SHA-256)
- **Gestion des tentatives** avec verrouillage automatique après 5 échecs
- **Système de rapport d'erreurs** automatique

### 💰 Gestion des Paiements Améliorée
- **Montant souscrit obligatoire** avec validation stricte
- **Montant payé optionnel** pour les acomptes
- **Statut automatique** : "En règle" si paiement complet, "En attente" sinon
- **Mise à jour automatique** le 7 de chaque mois pour les statuts litigieux

### 🎨 Interface Utilisateur
- **Dates dynamiques** : L'application s'adapte automatiquement à l'année courante
- **Validation en temps réel** des champs de saisie
- **Filtrage avancé** combinable par nom, mois, statut, devise

### 🧪 Qualité et Fiabilité
- **Tests unitaires complets** (44 tests)
- **Architecture modulaire** pour une meilleure maintenabilité
- **Documentation complète** et intégrée

## 🚀 Installation Rapide

### Prérequis
- Windows 10 ou supérieur
- MySQL 5.7 ou supérieur (ou XAMPP avec MySQL)
- 4 Go de RAM minimum
- 500 Mo d'espace disque

### Étapes d'installation

1. **Extraire les fichiers**
   - Décompressez le dossier `LIVRAISON_V3` dans un emplacement de votre choix

2. **Installer MySQL**
   - Si vous n'avez pas MySQL, installez XAMPP : https://www.apachefriends.org/
   - Démarrez le service MySQL depuis le panneau de contrôle XAMPP

3. **Importer la base de données**
   - Ouvrez phpMyAdmin (http://localhost/phpmyadmin)
   - Cliquez sur "Importer" et sélectionnez le fichier `init_database.sql`
   - Cliquez sur "Exécuter"

4. **Configurer l'application**
   - Éditez le fichier `config.json` avec vos paramètres MySQL
   - Modifiez le mot de passe si nécessaire

5. **Lancer l'application**
   - Double-cliquez sur `TAP_Gestion_Loyers.exe`
   - Ou exécutez `python main.py` si vous avez Python installé

## 🔑 Connexion

### Identifiants par défaut
- **Utilisateur** : `TAPADM`
- **Mot de passe** : `TAPADM`

⚠️ **Important** : Changez le mot de passe par défaut après la première connexion !

## 📖 Utilisation

### Ajouter un Paiement

1. Cliquez sur le bouton "Nouveau Paiement"
2. Remplissez le formulaire :
   - **Nom et Prénom** : Informations du locataire
   - **Téléphone** : Optionnel
   - **Mois** : Sélectionnez le mois de paiement
   - **Montant souscrit** : Montant total à payer (obligatoire)
   - **Montant payé** : Optionnel
     - Laissez vide → Statut "En attente"
     - Entrez un montant égal au montant souscrit → Statut "En règle"
     - Entrez un montant inférieur → Statut "En attente" (acompte)
   - **Devise** : CDF, USD, EUR, XAF ou CAD
   - **Statut souscription** : Simple ou Spécial
3. Cliquez sur "Enregistrer"

### Comprendre les Statuts

- **En attente** : Paiement en attente (montant payé vide ou inférieur au montant souscrit)
- **En règle** : Paiement complet (montant payé >= montant souscrit)
- **Litigieux** : Paiement en retard (automatique le 7 du mois suivant)

### Voir l'Historique

- Double-cliquez sur une ligne du tableau
- L'historique complet du locataire s'affiche

### Exporter en PDF

1. Cliquez sur le bouton "Exporter PDF"
2. Sélectionnez le dossier de destination
3. Le rapport est généré automatiquement

### Filtrer les Données

1. Cliquez sur le bouton "Ajouter un filtre"
2. Sélectionnez le type de filtre (Nom, Mois, Statut, Devise)
3. Entrez la valeur de recherche
4. Cliquez sur "Appliquer"

## 🔧 Configuration

### Fichier config.json

```json
{
  "database": {
    "host": "localhost",
    "database": "gestion_loyers",
    "user": "root",
    "password": "votre_mot_de_passe"
  }
}
```

### Modifier le mot de passe

Le mot de passe peut être modifié via le code source ou en contactant le support technique.

## 📊 Fonctionnalités Automatiques

### Mise à jour des Statuts

Le système met automatiquement à jour les statuts :
- **Le 7 de chaque mois** : Les paiements "En attente" passent en "Litigieux"
- **En temps réel** : Les statuts changent automatiquement lors de l'enregistrement

### Gestion des Erreurs

- Les erreurs sont automatiquement enregistrées dans `error_reports/`
- Les logs sont disponibles dans `app.log`
- En cas d'erreur critique, un rapport est généré

## 🛠️ Dépannage

### Problème de connexion à la base de données

**Symptôme** : "Erreur de connexion à la base de données"

**Solutions** :
1. Vérifiez que MySQL est démarré
2. Vérifiez les paramètres dans `config.json`
3. Vérifiez que la base de données `gestion_loyers` existe

### Erreur "database not found"

**Symptôme** : "Base de données non trouvée"

**Solution** :
1. Importez le fichier `init_database.sql` dans phpMyAdmin
2. Vérifiez que la base de données `gestion_loyers` a été créée

### Interface ne s'affiche pas correctement

**Symptôme** : L'interface est déformée ou ne s'affiche pas

**Solutions** :
1. Vérifiez que votre résolution d'écran est d'au moins 1366x768
2. Redémarrez l'application
3. Vérifiez que toutes les dépendances sont installées

## 📞 Support Technique

### En cas de problème

1. Consultez les logs dans `app.log`
2. Vérifiez les rapports d'erreurs dans `error_reports/`
3. Consultez le guide d'installation complet (`INSTALLATION.md`)

### Contact

Pour toute question ou problème technique, contactez l'équipe de support TAP.

## 📝 Notes de Version

### Version 3.3 (Juin 2026)
- ✅ Authentification sécurisée avec hashage
- ✅ Gestion des tentatives de connexion
- ✅ Statuts automatiques des paiements
- ✅ Mise à jour automatique le 7 du mois
- ✅ Dates dynamiques (année courante)
- ✅ Tests unitaires complets
- ✅ Documentation améliorée

### Version 3.2
- Amélioration de l'interface utilisateur
- Ajout des filtres combinables
- Export PDF amélioré

### Version 3.1
- Refonte de l'architecture
- Séparation des responsabilités
- Amélioration des performances

### Version 3.0
- Nouvelle interface moderne
- Gestion des acomptes
- Tableau de bord avec statistiques

---

**© 2026 TAP - Tous droits réservés**
