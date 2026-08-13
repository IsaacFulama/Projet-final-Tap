# TAP Gestion des Loyers - Guide d'Installation

## Prérequis

### 1. MySQL/XAMPP
- Télécharger et installer XAMPP depuis https://www.apachefriends.org/
- Démarrer le service MySQL depuis le panneau de contrôle XAMPP

### 2. Python (si installation depuis source)
- Python 3.10 ou supérieur (https://www.python.org/)
- Cocher "Add Python to PATH" lors de l'installation

## Configuration de la Base de Données

### Création de la base de données
```sql
CREATE DATABASE gestion_loyers;
```

### Création des tables
```sql
USE gestion_loyers;

-- Table des locataires
CREATE TABLE locataires (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    telephone VARCHAR(20)
);

-- Table des paiements
CREATE TABLE paiements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    locataire_id INT NOT NULL,
    mois DATE NOT NULL,
    montant DECIMAL(10, 2) NOT NULL,
    montant_total DECIMAL(10, 2) DEFAULT 0.00,
    montant_paye DECIMAL(10, 2) DEFAULT 0.00,
    reste_a_payer DECIMAL(10, 2) DEFAULT 0.00,
    devise VARCHAR(10) NOT NULL,
    statut_souscription VARCHAR(20) DEFAULT 'Simple',
    statut_paiement VARCHAR(20) DEFAULT 'En attente',
    statut VARCHAR(20) DEFAULT 'En attente',
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (locataire_id) REFERENCES locataires(id)
);
```

## Configuration de l'Application

### Fichier config.json
Le fichier `config.json` contient les paramètres de connexion à la base de données :

```json
{
  "database": {
    "host": "localhost",
    "database": "gestion_loyers",
    "user": "root",
    "password": "",
    "port": 3306
  }
}
```

**Modifier selon votre configuration :**
- `host`: Adresse du serveur MySQL (généralement localhost)
- `database`: Nom de la base de données (gestion_loyers)
- `user`: Nom d'utilisateur MySQL (par défaut: root)
- `password`: Mot de passe MySQL (par défaut: vide pour XAMPP)
- `port`: Port MySQL (3306 par défaut)

## Installation

### Option 1: Exécutable Windows
1. Télécharger le fichier `TAP_Gestion_Loyers.exe`
2. Placer le fichier dans un dossier
3. Créer le fichier `config.json` dans le même dossier
4. Lancer l'application en double-cliquant sur l'exécutable

### Option 1 bis: Rapport WhatsApp autonome
1. Si vous disposez également du fichier `whatsapp_report_sender.exe`, placez-le dans le même dossier pour activer l'envoi automatique des rapports
2. Renseigner les variables d'environnement WhatsApp selon le mode choisi :
   - `TAP_WHATSAPP_ENABLED=1`
   - `TAP_WHATSAPP_MODE=cloud` ou `twilio` ou `webhook`
   - `TAP_WHATSAPP_TO`
3. Planifier l'exécution du compagnon WhatsApp avec le Planificateur de tâches Windows
4. L'application principale reste inchangée

### Option 2: Installation depuis source
1. Cloner ou télécharger le dossier du projet
2. Créer un environnement virtuel :
   ```
   python -m venv venv
   ```
3. Activer l'environnement virtuel :
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`
4. Installer les dépendances :
   ```
   pip install -r requirements.txt
   ```
5. Lancer l'application :
   ```
   python main.py
   ```

## Nouveautés Version 3.7

- Les souscripteurs marqués `Spécial` sont dupliqués automatiquement au changement de mois, avec protection anti-doublon.
- Lors de cette duplication, les paiements `En attente` du mois précédent passent immédiatement en `Litigieux`.
- Les nouveaux enregistrements spéciaux du mois courant démarrent en `En attente`.
- Le sélecteur de mois du formulaire commence à janvier 2025.
- Une notification de fin d'exécution confirme la migration mensuelle dans l'application.
- À partir du 7 du mois, un rappel automatique liste aussi les paiements encore `Litigieux`.
- La page `Enregistrements` centralise l'affichage et les actions sur les paiements.
- Le dashboard est affiché en mode horizontal.
- Le tableau principal affiche davantage de lignes visibles, avec une lecture plus confortable.
- Un utilitaire WhatsApp séparé permet d'envoyer les rapports automatiques sans toucher à l'interface principale.

## Dépendances Python
```
customtkinter==5.2.0
mysql-connector-python==8.0.33
fpdf2==2.7.4
 matplotlib>=3.7.1
```

## Utilisation

### Enregistrement d'un paiement
1. Cliquer sur "Nouveau Paiement"
2. Remplir le formulaire (nom, prénom, téléphone, mois au format date `AAAA-MM-JJ`, montant, devise, statut souscription)
3. Cliquer sur "Enregistrer"
4. Le statut est automatiquement "En attente"

### Modification du statut
1. Clic droit sur une ligne du tableau
2. Choisir le statut (En règle, Litigieux, En attente)

### Historique d'un locataire
1. Double-clic sur une ligne du tableau
2. L'historique des paiements s'affiche

### Export PDF
1. Cliquer sur "Exporter PDF"
2. Appliquer les filtres souhaités (nom, statut, mois)
3. Cliquer sur "Exporter PDF"
4. Choisir l'emplacement de sauvegarde

### Migration mensuelle automatique
1. L'application vérifie automatiquement la migration des souscripteurs `Spécial` au lancement.
2. Si l'opération n'a pas encore été faite pour le mois courant, elle crée les nouvelles lignes du mois.
3. Les paiements `En attente` du mois précédent passent aussitôt en `Litigieux`.
4. Une notification confirme la fin de l'opération.
5. Le journal interne empêche les doublons si l'application est ouverte plusieurs fois.

### Rappel des paiements litigieux
1. À partir du 7 du mois, l'application détecte les paiements toujours `Litigieux`.
2. Une notification s'affiche avec un résumé des lignes à traiter.
3. Le rappel n'est envoyé qu'une seule fois par mois pour éviter le spam.

### Filtre statut souscription
1. Dans la barre de filtres, choisir "Statut souscription"
2. Sélectionner "Spécial" ou "Simple"
3. Ajouter le filtre pour l'appliquer au tableau

### Dashboard
1. Cliquer sur l'onglet "Analyse"
2. Voir les KPIs financiers et les graphiques
3. Filtrer par devise si nécessaire

## Sauvegarde et Restauration

### Sauvegarde manuelle
```sql
-- Via phpMyAdmin ou ligne de commande
mysqldump -u root -p gestion_loyers > backup.sql
```

### Restauration
```sql
-- Via phpMyAdmin ou ligne de commande
mysql -u root -p gestion_loyers < backup.sql
```

## Dépannage

### Erreur de connexion à la base de données
- Vérifier que MySQL est démarré (XAMPP)
- Vérifier les identifiants dans config.json
- Vérifier que la base de données `gestion_loyers` existe

### Erreur "Unknown column 'p.date_creation'"
- La colonne sera ajoutée automatiquement au premier lancement
- Si l'erreur persiste, exécuter :
  ```sql
  ALTER TABLE paiements ADD COLUMN date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
  ```

### L'application ne se lance pas
- Vérifier que Python 3.10+ est installé
- Vérifier que toutes les dépendances sont installées
- Consulter les logs d'erreur dans la console

## Support
Pour toute question ou problème, contacter le support technique.
