-- Script d'initialisation de la base de données TAP Gestion des Loyers
-- Exécuter ce script dans phpMyAdmin ou via la ligne de commande MySQL

-- Création de la base de données
CREATE DATABASE IF NOT EXISTS gestion_loyers;
USE gestion_loyers;

-- Table des locataires
CREATE TABLE IF NOT EXISTS locataires (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    telephone VARCHAR(20),
    INDEX idx_nom_prenom (nom, prenom)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table des paiements
CREATE TABLE IF NOT EXISTS paiements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    locataire_id INT NOT NULL,
    mois VARCHAR(50) NOT NULL,
    montant DECIMAL(10, 2) NOT NULL,
    devise VARCHAR(10) NOT NULL,
    statut VARCHAR(20) DEFAULT 'En attente',
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (locataire_id) REFERENCES locataires(id) ON DELETE CASCADE,
    INDEX idx_statut (statut),
    INDEX idx_mois (mois),
    INDEX idx_devise (devise)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Afficher un message de succès
SELECT 'Base de données initialisée avec succès!' AS Message;
