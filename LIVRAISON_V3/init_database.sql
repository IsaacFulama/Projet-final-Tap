-- Script d'initialisation de la base de données pour TAP Gestion des Loyers
-- Version 3.3 - Juin 2026
-- Ce script crée la base de données et les tables nécessaires

-- Création de la base de données
CREATE DATABASE IF NOT EXISTS gestion_loyers CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE gestion_loyers;

-- Table des locataires
CREATE TABLE IF NOT EXISTS locataires (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    telephone VARCHAR(20),
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_nom (nom),
    INDEX idx_prenom (prenom),
    INDEX idx_telephone (telephone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table des paiements
CREATE TABLE IF NOT EXISTS paiements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    locataire_id INT NOT NULL,
    mois DATE NOT NULL,
    montant DECIMAL(10, 2) NOT NULL,
    devise VARCHAR(10) NOT NULL,
    statut_souscription VARCHAR(20) DEFAULT 'Simple',
    statut VARCHAR(20) DEFAULT 'En attente',
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    montant_total DECIMAL(10, 2) DEFAULT 0,
    montant_paye DECIMAL(10, 2) DEFAULT 0,
    reste_a_payer DECIMAL(10, 2) DEFAULT 0,
    statut_paiement VARCHAR(20) DEFAULT 'En attente',
    FOREIGN KEY (locataire_id) REFERENCES locataires(id) ON DELETE CASCADE,
    INDEX idx_statut (statut),
    INDEX idx_statut_souscription (statut_souscription),
    INDEX idx_mois (mois),
    INDEX idx_devise (devise),
    INDEX idx_statut_paiement (statut_paiement)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insertion d'un utilisateur par défaut pour l'authentification
-- Note: L'authentification utilise maintenant un système sécurisé avec hashage
-- Le mot de passe par défaut est "TAPADM" (à changer en production)
