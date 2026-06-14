# Compatibilité Système - TAP Gestion des Loyers

## Systèmes Supportés

### Windows
- ✅ Windows 10 (32-bit et 64-bit)
- ✅ Windows 11 (32-bit et 64-bit)
- ✅ Windows Server 2016+
- ✅ Windows 8.1 (avec limitations)

### Résolutions d'écran supportées
- ✅ 1024x768 (minimum)
- ✅ 1366x768 (recommandé)
- ✅ 1920x1080 (optimal)
- ✅ 2560x1440 et plus (supporté)

### Configuration matérielle minimale
- **Processeur** : Intel Core i3 ou équivalent (1.6 GHz)
- **RAM** : 4 Go (8 Go recommandé)
- **Espace disque** : 500 Mo disponibles
- **Carte graphique** : Compatible DirectX 9 ou supérieure

## Configuration Logicielle Requise

### Python (si installation depuis source)
- Python 3.8 ou supérieur
- pip (gestionnaire de paquets)

### Base de données
- MySQL 5.7 ou supérieur
- OU MariaDB 10.2 ou supérieur
- OU XAMPP avec MySQL

### Dépendances
- customtkinter 5.2.0
- mysql-connector-python 8.0.33
- fpdf2 2.7.4
- matplotlib 3.7.1

## Adaptations Automatiques

L'application s'adapte automatiquement à :

### Résolution d'écran
- **Petits écrans** (< 1024px) : Interface compacte
- **Écrans moyens** (1024-1366px) : Interface standard
- **Grands écrans** (> 1366px) : Interface étendue

### Densité de pixels
- Détection automatique du DPI
- Ajustement des polices et espacements
- Support des écrans High DPI (150%, 200%)

### Taille de fenêtre
- Redimensionnement dynamique
- Maintien de la lisibilité
- Adaptation des composants

## Limitations Connues

### Windows 8.1
- Certaines fonctionnalités d'interface peuvent être limitées
- Thème sombre non supporté nativement

### Écrans très petits
- Résolution inférieure à 1024x768 non recommandée
- Certains composants peuvent être coupés

### Systèmes 32-bit
- Performance réduite avec grandes quantités de données
- Limitation de mémoire à 2 Go par processus

## Optimisations Performance

### Pour les ordinateurs moins puissants
1. Réduire le nombre de paiements affichés
2. Utiliser les filtres pour limiter les données
3. Fermer les dialogues inutilisés
4. Éviter les graphiques complexes

### Pour les ordinateurs puissants
1. Augmenter la taille du cache
2. Activer les graphiques avancés
3. Utiliser les filtres multiples
4. Exporter en PDF avec haute qualité

## Dépannage

### Problèmes d'affichage
- **Symptôme** : Interface coupée ou déformée
- **Solution** : Vérifiez la résolution (min. 1024x768)

### Problèmes de performance
- **Symptôme** : Application lente
- **Solution** : Augmentez la RAM à 8 Go minimum

### Problèmes de compatibilité
- **Symptôme** : Erreur de chargement
- **Solution** : Vérifiez que toutes les dépendances sont installées

## Tests de Compatibilité

L'application a été testée sur :
- ✅ Windows 10 Home (64-bit)
- ✅ Windows 10 Pro (64-bit)
- ✅ Windows 11 Home (64-bit)
- ✅ Windows 11 Pro (64-bit)
- ✅ Résolutions : 1024x768, 1366x768, 1920x1080, 2560x1440

---

**© 2026 TAP - Tous droits réservés**
