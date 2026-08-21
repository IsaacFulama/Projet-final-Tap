-- Script d'initialisation complet pour TAP Gestion des Loyers
-- Version responsive + schéma compatible application
-- Script non destructif : il ne supprime pas une base existante.

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE DATABASE IF NOT EXISTS gestion_loyers
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE gestion_loyers;

SET FOREIGN_KEY_CHECKS = 1;

-- Table des locataires
CREATE TABLE IF NOT EXISTS locataires (
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
CREATE TABLE IF NOT EXISTS maintenance_journal (
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

-- Registre des versions de migration et de leur empreinte
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(32) PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    checksum CHAR(64) NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Liens temporaires du portail locataire
CREATE TABLE IF NOT EXISTS portail_locataire_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    locataire_id INT NOT NULL,
    token_hash CHAR(64) NOT NULL UNIQUE,
    expires_at DATETIME NOT NULL,
    last_used_at DATETIME NULL,
    revoked_at DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_portail_token_locataire
        FOREIGN KEY (locataire_id) REFERENCES locataires(id) ON DELETE CASCADE,
    INDEX idx_portail_token_locataire (locataire_id),
    INDEX idx_portail_token_expiration (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Journal idempotent des événements créés hors ligne
CREATE TABLE IF NOT EXISTS offline_sync_events (
    event_id CHAR(36) PRIMARY KEY,
    device_id VARCHAR(100) NOT NULL,
    event_type VARCHAR(60) NOT NULL,
    payload_json TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    conflict_json TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    synced_at DATETIME NULL,
    INDEX idx_sync_status (status),
    INDEX idx_sync_device (device_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Archives de paiements
CREATE TABLE IF NOT EXISTS archives_paiements LIKE paiements;

-- Demandes de paiement par lien et preuves envoyées par le locataire
CREATE TABLE IF NOT EXISTS demandes_paiement (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    paiement_id INT NOT NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    montant_demande DECIMAL(10, 2) NOT NULL,
    devise VARCHAR(10) NOT NULL,
    expires_at DATETIME NOT NULL,
    statut VARCHAR(24) NOT NULL DEFAULT 'pending',
    preuve_data MEDIUMBLOB NULL,
    preuve_mime VARCHAR(100) NULL,
    note_locataire VARCHAR(500) NULL,
    cree_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    soumis_at DATETIME NULL,
    traite_at DATETIME NULL,
    note_traitement VARCHAR(500) NULL,
    CONSTRAINT fk_demande_paiement
        FOREIGN KEY (paiement_id) REFERENCES paiements(id) ON DELETE CASCADE,
    INDEX idx_demande_paiement (paiement_id),
    INDEX idx_demande_statut (statut),
    INDEX idx_demande_expiration (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Historique des tarifs par locataire
CREATE TABLE IF NOT EXISTS loyer_tarifs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    locataire_id INT NOT NULL,
    montant DECIMAL(10, 2) NOT NULL,
    devise VARCHAR(10) NOT NULL,
    effective_from DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_loyer_tarifs_locataires
        FOREIGN KEY (locataire_id) REFERENCES locataires(id)
        ON DELETE CASCADE,
    INDEX idx_tarif_locataire_date (locataire_id, effective_from)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Signatures numériques liées aux paiements
CREATE TABLE IF NOT EXISTS signatures_paiements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paiement_id INT NOT NULL,
    locataire_id INT NOT NULL,
    document_hash VARCHAR(64) NOT NULL,
    consentement TINYINT(1) NOT NULL DEFAULT 1,
    signature_png LONGBLOB NOT NULL,
    signataire_nom VARCHAR(201) NOT NULL,
    signed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    signer_ip VARCHAR(45) NULL,
    user_agent VARCHAR(255) NULL,
    CONSTRAINT fk_signatures_paiements
        FOREIGN KEY (paiement_id) REFERENCES paiements(id) ON DELETE CASCADE,
    CONSTRAINT fk_signatures_locataires
        FOREIGN KEY (locataire_id) REFERENCES locataires(id) ON DELETE CASCADE,
    INDEX idx_signature_paiement (paiement_id),
    INDEX idx_signature_locataire (locataire_id),
    INDEX idx_signature_signed_at (signed_at)
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
