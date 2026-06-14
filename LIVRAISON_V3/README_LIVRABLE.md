# 📦 Livrable TAP Gestion des Loyers v3.3

## 🎯 Résumé du Livrable

Ce dossier contient la version 3.3 de l'application TAP Gestion des Loyers avec toutes les améliorations de sécurité, de fonctionnalités et de qualité.

## 📁 Contenu du Dossier

```
LIVRAISON_V3/
├── TAP_Gestion_Loyers.exe       # Exécutable de l'application
├── init_database.sql            # Script d'initialisation de la base de données
├── config.json                  # Fichier de configuration (à modifier)
├── requirements.txt             # Dépendances Python (si installation depuis source)
├── README_CLIENT.md             # Guide utilisateur complet
├── INSTALLATION.md              # Guide d'installation détaillé
├── LIVRAISON.md                 # Notes de livraison
├── CHANGELOG.md                 # Historique des versions
└── README_LIVRABLE.md           # Ce fichier
```

## 🚀 Installation Rapide (3 étapes)

### 1. Installer MySQL
- Téléchargez et installez XAMPP : https://www.apachefriends.org/
- Démarrez MySQL depuis le panneau de contrôle XAMPP

### 2. Importer la base de données
- Ouvrez phpMyAdmin : http://localhost/phpmyadmin
- Importez le fichier `init_database.sql`

### 3. Lancer l'application
- Modifiez `config.json` avec vos paramètres MySQL
- Double-cliquez sur `TAP_Gestion_Loyers.exe`
- Connectez-vous avec : TAPADM / TAPADM

## ✨ Nouveautés de la Version 3.3

### 🔐 Sécurité Renforcée
- **Authentification sécurisée** avec hashage SHA-256
- **Gestion des tentatives** avec verrouillage après 5 échecs
- **Rapport d'erreurs** automatique

### 💰 Gestion des Paiements
- **Montant souscrit obligatoire** avec validation stricte
- **Montant payé optionnel** pour les acomptes
- **Statut automatique** : "En règle" si paiement complet
- **Mise à jour automatique** le 7 du mois pour les retards

### 🎨 Interface Utilisateur
- **Dates dynamiques** : S'adapte à l'année courante
- **Validation en temps réel** des champs
- **Filtrage avancé** combinable

### 🧪 Qualité
- **44 tests unitaires** tous réussis
- **Architecture modulaire** et maintenable
- **Documentation complète**

## 🔑 Identifiants de Connexion

- **Utilisateur** : `TAPADM`
- **Mot de passe** : `TAPADM`

⚠️ **IMPORTANT** : Changez le mot de passe par défaut après installation !

## 📖 Documentation

### Pour les utilisateurs
- **README_CLIENT.md** : Guide complet d'utilisation
- **INSTALLATION.md** : Instructions d'installation détaillées

### Pour les développeurs
- **LIVRAISON.md** : Notes de livraison techniques
- **CHANGELOG.md** : Historique des versions

## 🛠️ Configuration

### Modifier config.json

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

## ⚙️ Configuration Requise

- **Système** : Windows 10 ou supérieur
- **RAM** : 4 Go minimum (8 Go recommandé)
- **Espace disque** : 500 Mo
- **MySQL** : 5.7 ou supérieur

## 🐛 Dépannage

### Problème de connexion MySQL
1. Vérifiez que MySQL est démarré
2. Vérifiez les paramètres dans `config.json`
3. Vérifiez que la base de données existe

### Erreur "database not found"
1. Importez `init_database.sql` dans phpMyAdmin
2. Vérifiez que la base `gestion_loyers` existe

### Interface ne s'affiche pas
1. Vérifiez votre résolution (min. 1366x768)
2. Redémarrez l'application

## 📞 Support

Pour toute question ou problème :
- Consultez `README_CLIENT.md`
- Vérifiez les logs dans `app.log`
- Contactez le support technique TAP

## ✅ Checklist de Vérification

Avant de considérer l'installation comme terminée :

- [ ] MySQL est installé et fonctionne
- [ ] La base de données `gestion_loyers` existe
- [ ] Le fichier `config.json` est configuré
- [ ] L'application se lance sans erreur
- [ ] La connexion à la base de données fonctionne
- [ ] L'ajout de paiements fonctionne
- [ ] Les filtres fonctionnent
- [ ] L'export PDF fonctionne
- [ ] Le mot de passe par défaut a été changé

## 🎉 Félicitations !

Vous êtes maintenant prêt à utiliser TAP Gestion des Loyers v3.3 !

---

**Version** : 3.3  
**Date** : 14 Juin 2026  
**© 2026 TAP - Tous droits réservés**
