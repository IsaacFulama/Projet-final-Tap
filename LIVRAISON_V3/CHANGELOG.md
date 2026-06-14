# Changelog - TAP Gestion des Loyers

Toutes les versions notables de ce projet sont documentées dans ce fichier.

## [3.3.0] - 2026-06-14

### Ajouté
- ✅ Système d'authentification sécurisé avec hashage SHA-256
- ✅ Gestion des tentatives de connexion avec verrouillage (5 essais max)
- ✅ Module de validation robuste avec expressions régulières
- ✅ Tests unitaires complets (44 tests)
- ✅ Documentation complète avec docstrings
- ✅ Mise à jour automatique des statuts le 7 du mois
- ✅ Dates dynamiques (année courante + 5 ans)
- ✅ Statut automatique "En règle" si paiement complet
- ✅ Statut par défaut "En attente" pour paiements incomplets
- ✅ Système de rapport d'erreurs automatique
- ✅ Configuration pytest pour les tests
- ✅ Fichier .gitignore complet

### Changé
- 🔄 Refonte complète de l'architecture du projet
- 🔄 Suppression des fichiers dupliqués
- 🔄 Amélioration de la gestion des erreurs
- 🔄 Logging complet avec fichiers et console
- 🔄 Type hints complets sur toutes les fonctions
- 🔄 Validation stricte des données entrées
- 🔄 Interface utilisateur améliorée

### Corrigé
- 🐛 Correction des dates hardcodées (2025-2030 → dynamique)
- 🐛 Correction de la logique des statuts de paiement
- 🐛 Amélioration de la validation des montants (formats multiples)
- 🐛 Correction de la validation des téléphones
- 🐛 Correction de la validation des statuts (insensible à la casse)
- 🐛 Amélioration de la gestion des connexions MySQL

### Sécurité
- 🔐 Hashage des mots de passe avec SHA-256
- 🔐 Sel unique pour chaque utilisateur
- 🔐 Verrouillage automatique après tentatives échouées
- 🔐 Rapport d'erreurs sans interaction avec la base de données

### Documentation
- 📝 README.md complet avec architecture et guide
- 📝 README_CLIENT.md pour les utilisateurs finaux
- 📝 INSTALLATION.md avec instructions détaillées
- 📝 LIVRAISON.md avec notes de livraison
- 📝 Docstrings Google-style complètes

## [3.2.0] - 2026-05-15

### Ajouté
- ✅ Filtres combinables (Nom, Mois, Statut, Devise)
- ✅ Export PDF amélioré avec mise en page
- ✅ Historique des paiements par locataire
- ✅ Dashboard avec statistiques
- ✅ Cache des données pour améliorer les performances

### Changé
- 🔄 Amélioration de l'interface utilisateur
- 🔄 Optimisation des requêtes SQL
- 🔄 Amélioration de la gestion des erreurs

### Corrigé
- 🐛 Correction des bugs d'affichage
- 🐛 Amélioration de la stabilité de l'application

## [3.1.0] - 2026-04-20

### Ajouté
- ✅ Architecture modulaire avec séparation des responsabilités
- ✅ Module de configuration centralisé
- ✅ Système de thèmes pour l'interface
- ✅ Utilitaires de dates
- ✅ Gestionnaire d'erreurs

### Changé
- 🔄 Refonte de la structure du projet
- 🔄 Séparation couches présentation/domaine/infrastructure
- 🔄 Amélioration de la maintenabilité

### Corrigé
- 🐛 Correction des problèmes de performance
- 🐛 Amélioration de la gestion de la mémoire

## [3.0.0] - 2026-03-10

### Ajouté
- ✅ Nouvelle interface moderne avec CustomTkinter
- ✅ Gestion des acomptes et paiements partiels
- ✅ Tableau de bord avec graphiques matplotlib
- ✅ Export PDF avec FPDF
- ✅ Système de filtres avancé
- ✅ Dialogue de connexion
- ✅ Formulaire de souscription avec validation

### Changé
- 🔄 Migration complète de l'interface Tkinter vers CustomTkinter
- 🔄 Refonte du design avec thème sombre
- 🔄 Amélioration de l'expérience utilisateur

### Corrigé
- 🐛 Correction des problèmes d'affichage sur différents écrans
- 🐛 Amélioration de la gestion des erreurs

## [2.0.0] - 2026-02-05

### Ajouté
- ✅ Base de données MySQL
- ✅ Gestion des locataires
- ✅ Gestion des paiements
- ✅ Interface graphique basique avec Tkinter
- ✅ Export des données

### Changé
- 🔄 Migration des données depuis Excel vers MySQL
- 🔄 Implémentation de l'interface graphique

### Corrigé
- 🐛 Correction des problèmes de connexion à la base de données

## [1.0.0] - 2026-01-15

### Ajouté
- ✅ Version initiale
- ✅ Gestion des locataires via Excel
- ✅ Calculs manuels des paiements
- ✅ Rapports basiques

---

## Format du Changelog

Basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/)

### Catégories

- **Ajouté** : Nouvelles fonctionnalités
- **Changé** : Changements dans les fonctionnalités existantes
- **Déprécié** : Fonctionnalités bientôt supprimées
- **Supprimé** : Fonctionnalités supprimées
- **Corrigé** : Corrections de bugs
- **Sécurité** : Améliorations de sécurité

---

**© 2026 TAP - Tous droits réservés**
