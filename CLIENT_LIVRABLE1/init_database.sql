-- Script d'initialisation complet pour TAP Gestion des Loyers
-- Version responsive + schéma compatible application
-- ATTENTION: ce script supprime l'ancienne base et la recrée à zéro.

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP DATABASE IF EXISTS gestion_loyers;
CREATE DATABASE gestion_loyers
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE gestion_loyers;

SET FOREIGN_KEY_CHECKS = 1;

-- Table des locataires
CREATE TABLE locataires (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    telephone VARCHAR(20) NULL,
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_nom (nom),
    INDEX idx_prenom (prenom),
    INDEX idx_telephone (telephone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table des paiements
CREATE TABLE paiements (
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
    CONSTRAINT fk_paiements_locataires
        FOREIGN KEY (locataire_id) REFERENCES locataires(id)
        ON DELETE CASCADE,
    INDEX idx_statut (statut),
    INDEX idx_statut_souscription (statut_souscription),
    INDEX idx_mois (mois),
    INDEX idx_devise (devise),
    INDEX idx_statut_paiement (statut_paiement),
    INDEX idx_locataire_mois_statut (locataire_id, mois, statut_souscription)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Journal des maintenances automatiques
CREATE TABLE maintenance_journal (
    id INT AUTO_INCREMENT PRIMARY KEY,
    operation_key VARCHAR(64) NOT NULL,
    period_key VARCHAR(16) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    created_count INT NOT NULL DEFAULT 0,
    error_count INT NOT NULL DEFAULT 0,
    details_json TEXT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    UNIQUE KEY uq_operation_period (operation_key, period_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Données de démonstration
-- Elles permettent de vérifier immédiatement l'affichage dans l'app.

INSERT INTO locataires (nom, prenom, telephone)
SELECT 'FULAMA', 'ISAAC', NULL
WHERE NOT EXISTS (
    SELECT 1
    FROM locataires
    WHERE UPPER(TRIM(nom)) = 'FULAMA'
      AND UPPER(TRIM(prenom)) = 'ISAAC'
);

INSERT INTO locataires (nom, prenom, telephone)
SELECT 'KABONGO', 'MARIE', '+243810000002'
WHERE NOT EXISTS (
    SELECT 1
    FROM locataires
    WHERE UPPER(TRIM(nom)) = 'KABONGO'
      AND UPPER(TRIM(prenom)) = 'MARIE'
);

INSERT INTO locataires (nom, prenom, telephone)
SELECT 'MUKENDI', 'PAUL', '+243810000003'
WHERE NOT EXISTS (
    SELECT 1
    FROM locataires
    WHERE UPPER(TRIM(nom)) = 'MUKENDI'
      AND UPPER(TRIM(prenom)) = 'PAUL'
);

INSERT INTO paiements (
    locataire_id, mois, montant, montant_total, montant_paye,
    reste_a_payer, devise, statut, statut_souscription, statut_paiement
)
SELECT
    l.id,
    '2026-05-01',
    15.00,
    15.00,
    15.00,
    0.00,
    'CDF',
    'En règle',
    'Simple',
    'Complet'
FROM locataires l
WHERE UPPER(TRIM(l.nom)) = 'FULAMA'
  AND UPPER(TRIM(l.prenom)) = 'ISAAC'
  AND NOT EXISTS (
      SELECT 1
      FROM paiements p
      WHERE p.locataire_id = l.id
        AND p.mois = '2026-05-01'
        AND UPPER(TRIM(p.devise)) = 'CDF'
  );

INSERT INTO paiements (
    locataire_id, mois, montant, montant_total, montant_paye,
    reste_a_payer, devise, statut, statut_souscription, statut_paiement
)
SELECT
    l.id,
    '2026-06-01',
    20.00,
    20.00,
    0.00,
    20.00,
    'CDF',
    'Litigieux',
    'Spécial',
    'En attente'
FROM locataires l
WHERE UPPER(TRIM(l.nom)) = 'FULAMA'
  AND UPPER(TRIM(l.prenom)) = 'ISAAC'
  AND NOT EXISTS (
      SELECT 1
      FROM paiements p
      WHERE p.locataire_id = l.id
        AND p.mois = '2026-06-01'
        AND UPPER(TRIM(p.devise)) = 'CDF'
  );

INSERT INTO paiements (
    locataire_id, mois, montant, montant_total, montant_paye,
    reste_a_payer, devise, statut, statut_souscription, statut_paiement
)
SELECT
    l.id,
    '2026-06-01',
    25.00,
    25.00,
    10.00,
    15.00,
    'USD',
    'Litigieux',
    'Simple',
    'Partiel'
FROM locataires l
WHERE UPPER(TRIM(l.nom)) = 'KABONGO'
  AND UPPER(TRIM(l.prenom)) = 'MARIE'
  AND NOT EXISTS (
      SELECT 1
      FROM paiements p
      WHERE p.locataire_id = l.id
        AND p.mois = '2026-06-01'
        AND UPPER(TRIM(p.devise)) = 'USD'
  );

INSERT INTO paiements (
    locataire_id, mois, montant, montant_total, montant_paye,
    reste_a_payer, devise, statut, statut_souscription, statut_paiement
)
SELECT
    l.id,
    '2026-06-01',
    30.00,
    30.00,
    0.00,
    30.00,
    'CDF',
    'En attente',
    'Simple',
    'En attente'
FROM locataires l
WHERE UPPER(TRIM(l.nom)) = 'MUKENDI'
  AND UPPER(TRIM(l.prenom)) = 'PAUL'
  AND NOT EXISTS (
      SELECT 1
      FROM paiements p
      WHERE p.locataire_id = l.id
        AND p.mois = '2026-06-01'
        AND UPPER(TRIM(p.devise)) = 'CDF'
  );

-- Rappel: le compte admin se gère dans le système d'authentification de l'app.
