# Guide d'Utilisation - TAP Gestion des Loyers

## Table des matières
1. [Installation](#installation)
2. [Premier lancement](#premier-lancement)
3. [Interface principale](#interface-principale)
4. [Enregistrement d'un paiement](#enregistrement-dun-paiement)
5. [Gestion des acomptes](#gestion-des-acomptes)
6. [Modification d'un paiement](#modification-dun-paiement)
7. [Suppression d'un paiement](#suppression-dun-paiement)
8. [Historique d'un locataire](#historique-dun-locataire)
9. [Filtres et recherche](#filtres-et-recherche)
10. [Dashboard et statistiques](#dashboard-et-statistiques)
11. [Export des données](#export-des-données)
12. [Gestion des statuts](#gestion-des-statuts)

---

## Installation

### Prérequis
- Python 3.8 ou supérieur
- Windows, Mac ou Linux

### Étapes d'installation

1. **Extraire le fichier ZIP**
   - Décompressez le fichier `LIVRAISON_CLIENT.zip`
   - Placez le dossier extrait dans un emplacement de votre choix

2. **Créer un environnement virtuel (recommandé)**
   ```bash
   python -m venv .venv
   ```

3. **Activer l'environnement virtuel**
   - Windows : `.venv\Scripts\activate`
   - Mac/Linux : `source .venv/bin/activate`

4. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

5. **Lancer l'application**
   ```bash
   python main.py
   ```

---

## Premier lancement

Au premier lancement, l'application :
- Crée automatiquement la base de données si elle n'existe pas
- Exécute les migrations nécessaires pour mettre à jour la structure
- Affiche un message de confirmation dans la console

---

## Interface principale

L'interface se compose de trois onglets principaux :

### 1. Onglet Tableau
- Affiche la liste de tous les paiements
- Colonnes : Nom, Prénom, Mois, Montant, Devise, Type, Statut
- Permet le tri par colonne
- Menu contextuel par clic droit

### 2. Onglet Dashboard
- Statistiques en temps réel
- Graphiques d'évolution
- Cartes de KPI (Key Performance Indicators)
- Répartition par devise et par statut

### 3. Onglet Filtres
- Filtres avancés pour rechercher des paiements
- Filtres par nom, devise, mois, statut
- Réinitialisation des filtres en un clic

---

## Enregistrement d'un paiement

### Étape 1 : Ouvrir le formulaire
- Cliquez sur le bouton **"Nouveau Paiement"** dans la barre latérale
- Le formulaire de souscription s'ouvre

### Étape 2 : Remplir les informations

**Champs obligatoires :**
- **Nom** : Nom du locataire (ex: "Dupont")
- **Prénom** : Prénom du locataire (ex: "Jean")
- **Mois** : Sélectionnez le mois dans la liste déroulante (ex: "Janvier 2024")
- **Montant total** : Montant total de la souscription (ex: "500")
- **Devise** : Devise du paiement (CDF, USD, EUR, XAF, CAD)
- **Type de souscription** : "Simple" ou "Spécial"

**Champs optionnels :**
- **Téléphone** : Numéro de téléphone (optionnel, format: +243 XXX XXX XXX)
- **Montant payé** : Si vous enregistrez un acompte, entrez le montant payé (ex: "200" pour un acompte sur 500)

### Étape 3 : Enregistrer
- Cliquez sur le bouton **"Enregistrer"**
- Un message de confirmation s'affiche si l'enregistrement réussit
- Le tableau se met à jour automatiquement

### Comportement intelligent
- **Détection de doublons** : Si un locataire avec le même nom et prénom existe déjà (insensible à la casse), le paiement est automatiquement ajouté à ce locataire au lieu de créer un doublon. Par exemple :
  - Premier enregistrement : "FULAMA ISAAC" → Création du locataire
  - Deuxième enregistrement : "fulama isaac" → Ajout du paiement au même locataire (pas de doublon)
  - Cela permet d'avoir un historique complet par personne
- **Statut automatique** :
  - Si aucun montant payé → Statut "En attente"
  - Si acompte (montant payé < total) → Statut "Litigieux"
  - Si paiement complet → Statut "En règle"

---

## Gestion des acomptes

### Enregistrer un acompte initial
Lors de l'enregistrement d'un nouveau paiement :
1. Entrez le montant total dans le champ "Montant total"
2. Entrez le montant de l'acompte dans le champ "Montant payé"
3. Le reste à payer est calculé automatiquement
4. Le statut passe automatiquement à "Litigieux"

### Ajouter un paiement complémentaire
Pour ajouter un paiement à un acompte existant :
1. Clic droit sur la ligne du paiement dans le tableau
2. Sélectionnez **"💰 Ajouter paiement"**
3. Une boîte de dialogue s'affiche avec :
   - Montant total
   - Déjà payé
   - Reste à payer
4. Entrez le montant à ajouter
5. Le statut se met à jour automatiquement :
   - Reste encore à payer → "Litigieux"
   - Paiement complet → "En règle"

---

## Modification d'un paiement

### Étape 1 : Sélectionner le paiement
- Clic droit sur la ligne du paiement dans le tableau
- Sélectionnez **"✏️ Modifier"**

### Étape 2 : Modifier les informations
- Le formulaire s'ouvre avec les données pré-remplies
- Modifiez les champs nécessaires
- Vous pouvez aussi ajuster le montant payé (acompte)

### Étape 3 : Enregistrer
- Cliquez sur **"Enregistrer"**
- Les modifications sont sauvegardées
- Le tableau se met à jour automatiquement

---

## Suppression d'un paiement

### Étape 1 : Sélectionner le paiement
- Clic droit sur la ligne du paiement dans le tableau
- Sélectionnez **"🗑️ Supprimer"**

### Étape 2 : Confirmer
- Une boîte de confirmation s'affiche
- Cliquez sur **"Oui"** pour confirmer la suppression
- Le paiement est supprimé définitivement

---

## Historique d'un locataire

### Afficher l'historique
- Double-clic sur une ligne du tableau
- OU sélectionnez la ligne et appuyez sur **Entrée**

### Contenu de l'historique
- Liste de tous les paiements du locataire
- Montant total, montant payé, reste à payer
- Statut de paiement (Complet/Partiel/En attente)
- Statut de la souscription (En règle/Litigieux/En attente)

### Fonctionnalités de l'historique
- **Export CSV** : Exporter l'historique en fichier CSV
- **Graphique d'évolution** : Voir l'évolution des paiements dans le temps
- **Statistiques** : Total payé, reste à payer, nombre de paiements complets/partiels

---

## Filtres et recherche

### Filtres disponibles
- **Par nom** : Recherche par nom ou prénom
- **Par devise** : Filtrer par devise (CDF, USD, EUR, XAF, CAD)
- **Par mois** : Filtrer par période
- **Par statut** : En règle, Litigieux, En attente
- **Par type de souscription** : Simple, Spécial

### Utilisation
1. Allez dans l'onglet **"Filtres"**
2. Remplissez les critères souhaités
3. Cliquez sur **"Appliquer les filtres"**
4. Le tableau se met à jour avec les résultats

### Réinitialisation
- Cliquez sur **"Réinitialiser les filtres"** pour afficher tous les paiements

---

## Dashboard et statistiques

### Indicateurs clés (KPI)
- **Total des paiements** : Nombre total de paiements enregistrés
- **En règle** : Nombre de paiements complètement payés
- **Litigieux** : Nombre de paiements avec acompte
- **En attente** : Nombre de paiements sans paiement
- **Total collecté** : Somme de tous les montants payés
- **Reste à collecter** : Somme de tous les restes à payer

### Graphiques disponibles
- **Évolution mensuelle** : Évolution des paiements dans le temps
- **Répartition par devise** : Camembert des paiements par devise
- **Répartition par statut** : Barres des paiements par statut
- **Top locataires** : Locataires avec le plus de paiements

---

## Export des données

### Export en PDF
1. Cliquez sur le bouton **"Exporter PDF"** dans la barre latérale
2. Sélectionnez les options d'export :
   - Période
   - Filtres à appliquer
3. Cliquez sur **"Générer PDF"**
4. Le PDF est généré et ouvert automatiquement

### Export en CSV (Historique)
1. Ouvrez l'historique d'un locataire
2. Cliquez sur **"Exporter CSV"**
3. Choisissez l'emplacement de sauvegarde
4. Le fichier CSV est généré avec toutes les données

---

## Gestion des statuts

### Statuts automatiques
Le système calcule automatiquement le statut selon le montant payé :
- **En attente** : Aucun paiement effectué
- **Litigieux** : Acompte payé (paiement partiel)
- **En règle** : Paiement complet effectué

### Modification manuelle du statut
Vous pouvez aussi modifier manuellement le statut si nécessaire :
1. Clic droit sur la ligne du paiement
2. Sélectionnez l'option souhaitée :
   - **"✅ Marquer En règle"**
   - **"⚠️ Marquer Litigieux"**
   - **"⏳ Marquer En attente"**
3. Le statut est mis à jour immédiatement

### Indicateurs visuels
- 🟢 **En règle** : Texte en vert
- 🟠 **Litigieux** : Texte en orange
- 🔵 **En attente** : Texte en bleu

---

## Conseils et bonnes pratiques

### Enregistrement efficace
- Utilisez le même format de noms pour éviter les doublons
- Le système détecte automatiquement les doublons insensibles à la casse
- Le téléphone est optionnel, mais recommandé pour le suivi

### Gestion des acomptes
- Enregistrez toujours le montant total lors de la souscription
- Utilisez la fonction "Ajouter paiement" pour les paiements complémentaires
- Vérifiez régulièrement les paiements "Litigieux" pour le suivi

### Sauvegarde des données
- La base de données est stockée localement
- Effectuez régulièrement des sauvegardes du dossier de l'application
- Exportez en PDF ou CSV pour archivage

---

## Dépannage

### Problème : L'application ne se lance pas
- **Solution** : Vérifiez que Python est installé et que les dépendances sont à jour

### Problème : Erreur de connexion à la base de données
- **Solution** : Vérifiez que le fichier de base de données n'est pas utilisé par une autre instance

### Problème : Le paiement ne s'enregistre pas
- **Solution** : Vérifiez que tous les champs obligatoires sont remplis correctement

### Problème : Les doublons apparaissent
- **Solution** : Le système détecte maintenant les doublons insensibles à la casse. Vérifiez les noms/prénoms.

---

## Support

Pour toute question ou problème :
1. Consultez ce guide d'utilisation
2. Vérifiez les messages d'erreur dans la console
3. Contactez le support technique si nécessaire

---

**Version** : 3.1
**Date** : Juin 2026
