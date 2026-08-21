"""
Module de maintenance automatique des paiements.

Le moteur de maintenance :
- crée une seule fois par mois les enregistrements des souscripteurs spéciaux
- évite les doublons même si l'application démarre plusieurs fois
- met à jour les statuts à partir du jour de mise à jour configuré
- expose un rapport exploitable pour la notification utilisateur
"""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Tuple, List, Optional

from tap.config.settings import load_app_config
from tap.core.date_utils import SPECIAL_ROLLOVER_START, format_mois_affichage
from tap.infrastructure.database.connection import connexion_prete, obtenir_connexion

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_status_updater.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

ROLLING_OPERATION_KEY = "special_monthly_rollover"
LITIGIEUX_REMINDER_KEY = "litigieux_monthly_reminder"
RECURRING_RENEWAL_KEY = "recurring_rent_renewal"
STALE_LOCK_MINUTES = 180
DEFAULT_AUTOMATIC_UPDATE_DAY = 7


def _is_special_rollover_automatic_enabled() -> bool:
    """Le basculement Spécial est manuel par défaut (configurable)."""
    config = load_app_config()
    automatic_config = config.get("automatic_maintenance", {})
    return bool(automatic_config.get("special_rollover_enabled", False))


def _get_automatic_update_day() -> int:
    config = load_app_config()
    automatic_config = config.get("automatic_maintenance", {})
    value = automatic_config.get("update_day", DEFAULT_AUTOMATIC_UPDATE_DAY)
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = DEFAULT_AUTOMATIC_UPDATE_DAY
    if value < 1 or value > 28:
        return DEFAULT_AUTOMATIC_UPDATE_DAY
    return value


def _month_key(reference_date: date) -> str:
    return reference_date.strftime("%Y-%m")


def _previous_month_start(reference_date: date) -> date:
    """Retourne le premier jour du mois précédent."""
    first_day_current_month = reference_date.replace(day=1)
    previous_day = first_day_current_month - timedelta(days=1)
    return previous_day.replace(day=1)


def _ensure_maintenance_journal(cursor) -> None:
    """Crée la table de suivi des maintenances si nécessaire."""
    cursor.execute(
        """
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
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def _ensure_database_schema(cursor) -> None:
    """S'assure que les tables contiennent toutes les colonnes requises pour la v3.7."""
    _ensure_maintenance_journal(cursor)
    
    # Vérification des colonnes de la table paiements
    cursor.execute("SHOW COLUMNS FROM paiements")
    cols = [c[0].lower() for c in cursor.fetchall()]
    
    # Liste des colonnes critiques introduites en v3.7
    ajouts = [
        ("montant_total", "DECIMAL(10, 2) DEFAULT 0.00 AFTER montant"),
        ("montant_paye", "DECIMAL(10, 2) DEFAULT 0.00 AFTER montant_total"),
        ("reste_a_payer", "DECIMAL(10, 2) DEFAULT 0.00 AFTER montant_paye"),
        ("statut_paiement", "VARCHAR(20) DEFAULT 'En attente' AFTER statut_souscription")
    ]
    
    for col_name, col_def in ajouts:
        if col_name.lower() not in cols:
            logger.info(f"Mise à jour du schéma : Ajout de la colonne {col_name}")
            try:
                cursor.execute(f"ALTER TABLE paiements ADD COLUMN {col_name} {col_def}")
            except Exception as e:
                logger.error(f"Erreur lors de l'ajout de la colonne {col_name}: {e}")

def _parse_details_json(raw_value):
    if not raw_value:
        return {}
    try:
        if isinstance(raw_value, str):
            return json.loads(raw_value)
        return dict(raw_value)
    except Exception:
        return {}


def _basculer_paiements_anterieurs_en_litigieux(cursor, mois_courant: date) -> int:
    """Bascule en Litigieux tous les paiements antérieurs encore en attente."""
    cursor.execute(
        """
            UPDATE paiements
            SET statut = 'Litigieux'
            WHERE mois < %s
              AND statut = 'En attente'
        """,
        (mois_courant,),
    )
    return max(0, cursor.rowcount or 0)


def _get_litigieux_paiements(reference_date: Optional[date] = None) -> List[dict]:
    """Retourne les paiements litigieux du mois courant."""
    conn = None
    cursor = None
    paiements = []
    date_reference = reference_date or date.today()
    mois_courant = date_reference.replace(day=1)

    try:
        conn = obtenir_connexion()
        if connexion_prete(conn):
            cursor = conn.cursor()
            cursor.execute(
                """
                    SELECT p.id, p.mois, p.montant_total, p.montant_paye, p.reste_a_payer,
                           p.devise, l.nom, l.prenom
                    FROM paiements p
                    JOIN locataires l ON p.locataire_id = l.id
                    WHERE p.statut = 'Litigieux'
                      AND p.mois = %s
                    ORDER BY l.nom ASC, l.prenom ASC, p.id ASC
                """,
                (mois_courant,),
            )
            for row in cursor.fetchall():
                paiements.append({
                    "id": row[0],
                    "mois": row[1],
                    "montant_total": row[2],
                    "montant_paye": row[3],
                    "reste_a_payer": row[4],
                    "devise": row[5],
                    "nom": row[6],
                    "prenom": row[7],
                })
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des paiements litigieux: {e}")
    finally:
        if cursor:
            cursor.close()
        if connexion_prete(conn):
            conn.close()

    return paiements


def verifier_rappel_litigieux(reference_date: Optional[date] = None) -> dict:
    """
    Déclenche un rappel mensuel pour les paiements litigieux à partir du jour de mise à jour configuré.

    Le rappel n'est envoyé qu'une seule fois par mois pour éviter les doublons.
    """
    conn = None
    cursor = None
    date_reference = reference_date or date.today()
    periode = _month_key(date_reference)
    jour_actuel = date_reference.day
    automatic_update_day = _get_automatic_update_day()

    if jour_actuel < automatic_update_day:
        return {
            "status": "skipped",
            "count": 0,
            "month": periode,
            "message": (
                f"Rappel litigieux non déclenché avant le {automatic_update_day} "
                f"({date_reference})."
            ),
            "details": {},
        }

    paiements = _get_litigieux_paiements(date_reference)
    count = len(paiements)
    if count <= 0:
        return {
            "status": "no_alert",
            "count": 0,
            "month": periode,
            "message": f"Aucun paiement litigieux à rappeler pour {periode}.",
            "details": {},
        }

    try:
        conn = obtenir_connexion()
        if connexion_prete(conn):
            cursor = conn.cursor()
            _ensure_database_schema(cursor)
            conn.commit()

            cursor.execute(
                """
                    SELECT status, created_count, error_count, details_json
                    FROM maintenance_journal
                    WHERE operation_key = %s AND period_key = %s
                """,
                (LITIGIEUX_REMINDER_KEY, periode),
            )
            journal_row = cursor.fetchone()
            if journal_row and str(journal_row[0]).lower() == "done":
                details = _parse_details_json(journal_row[3])
                return {
                    "status": "already_done",
                    "count": int(journal_row[1] or count),
                    "month": periode,
                    "message": details.get(
                        "message",
                        f"Le rappel litigieux a déjà été envoyé pour {periode}.",
                    ),
                    "details": details,
                }

            liste_limitee = [
                f"{item['nom']} {item['prenom']} - {item['reste_a_payer']:,.0f} {item['devise']}"
                for item in paiements[:5]
            ]
            message = (
                f"{count} paiement(s) litigieux à traiter pour {periode}. "
                f"Exemple(s): {', '.join(liste_limitee)}"
            )

            cursor.execute(
                """
                    INSERT INTO maintenance_journal (
                        operation_key, period_key, status, created_count, error_count, details_json, completed_at
                    )
                    VALUES (%s, %s, 'done', %s, 0, %s, CURRENT_TIMESTAMP)
                    ON DUPLICATE KEY UPDATE
                        status = 'done',
                        created_count = VALUES(created_count),
                        error_count = VALUES(error_count),
                        details_json = VALUES(details_json),
                        completed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                """,
                (
                    LITIGIEUX_REMINDER_KEY,
                    periode,
                    count,
                    json.dumps(
                        {
                            "month": periode,
                            "count": count,
                            "message": message,
                            "items": liste_limitee,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            conn.commit()

            return {
                "status": "done",
                "count": count,
                "month": periode,
                "message": message,
                "details": {
                    "items": paiements,
                    "sample": liste_limitee,
                },
            }
    except Exception as e:
        logger.error(f"Erreur lors du rappel litigieux: {e}")
        if conn:
            conn.rollback()
        return {
            "status": "error",
            "count": count,
            "month": periode,
            "message": f"Impossible de créer le rappel litigieux pour {periode}: {e}",
            "details": {},
        }
    finally:
        if cursor:
            cursor.close()
        if connexion_prete(conn):
            conn.close()

    return {
        "status": "error",
        "count": count,
        "month": periode,
        "message": f"Impossible de créer le rappel litigieux pour {periode}.",
        "details": {},
    }


def verifier_et_mettre_a_jour_statuts(reference_date: Optional[date] = None) -> Tuple[int, int]:
    """
    Vérifie et met à jour automatiquement les statuts des paiements.
    
    Change le statut à "Litigieux" à partir du jour de mise à jour configuré pour les paiements:
    - En attente (sans paiement)
    - Avec acompte (paiement partiel)
    
    Utilise la date du système de l'ordinateur pour déterminer le jour actuel.
    
    Returns:
        Tuple[int, int]: (nombre de paiements mis à jour, nombre d'erreurs)
    """
    conn = None
    cursor = None
    mis_a_jour = 0
    erreurs = 0
    date_reference = reference_date or date.today()
    mois_courant = date_reference.replace(day=1)
    
    try:
        conn = obtenir_connexion()
        if connexion_prete(conn):
            cursor = conn.cursor()
            
            # Date de référence
            jour_actuel = date_reference.day
            
            logger.info(f"Vérification automatique des statuts - Date référence: {date_reference}")
            automatic_update_day = _get_automatic_update_day()
            
            # Ne faire la mise à jour qu'à partir du jour de mise à jour configuré
            if jour_actuel < automatic_update_day:
                logger.info(
                    f"Aucune mise à jour nécessaire (jour {jour_actuel}, avant le {automatic_update_day})"
                )
                return 0, 0
            
            # Trouver les paiements qui doivent être mis à jour
            # Critères:
            # - Statut = "En attente" ou "Litigieux"
            # - Mois de paiement = mois courant
            query = """
                SELECT id, locataire_id, mois, statut, montant_total, montant_paye, reste_a_payer, statut_souscription
                FROM paiements
                WHERE statut IN ('En attente', 'Litigieux')
                AND mois = %s
                ORDER BY statut_souscription ASC, mois ASC
            """
            
            cursor.execute(query, (mois_courant,))
            paiements = cursor.fetchall()
            
            logger.info(f"{len(paiements)} paiements éligibles pour mise à jour")
            
            for paiement in paiements:
                paiement_id, locataire_id, mois_paiement, statut_actuel, montant_total, montant_paye, reste_a_payer, statut_souscription = paiement
                
                try:
                    # Ne force le statut litigieux que si le paiement n'est pas complet.
                    montant_total_num = float(montant_total or 0)
                    montant_paye_num = float(montant_paye or 0)
                    reste_num = float(reste_a_payer or 0)

                    if montant_total_num > 0 and montant_paye_num >= montant_total_num and reste_num <= 0:
                        logger.info(
                            f"Paiement {paiement_id} déjà complet, aucun passage en Litigieux."
                        )
                        continue

                    # Déterminer le nouveau statut avec traitement spécial pour les souscripteurs spéciaux
                    is_special = statut_souscription == "Spécial"
                    
                    if statut_actuel == "En attente":
                        nouveau_statut = "Litigieux"
                        prefix = "[SPÉCIAL] " if is_special else ""
                        message = f"{prefix}Passage de En attente à Litigieux (paiement du {mois_paiement})"
                    elif statut_actuel == "Litigieux":
                        # Rester litigieux mais on peut logger
                        nouveau_statut = "Litigieux"
                        prefix = "[SPÉCIAL] " if is_special else ""
                        message = f"{prefix}Rester Litigieux (paiement du {mois_paiement}, reste: {reste_a_payer})"
                    else:
                        continue
                    
                    # Mettre à jour le statut
                    update_query = """
                        UPDATE paiements
                        SET statut = %s
                        WHERE id = %s
                    """
                    
                    cursor.execute(update_query, (nouveau_statut, paiement_id))
                    mis_a_jour += 1
                    
                    logger.info(f"Paiement ID {paiement_id}: {message}")
                    
                except Exception as e:
                    erreurs += 1
                    logger.error(f"Erreur lors de la mise à jour du paiement {paiement_id}: {e}")
            
            conn.commit()
            logger.info(f"Mise à jour terminée: {mis_a_jour} paiements mis à jour, {erreurs} erreurs")
            
    except Exception as e:
        erreurs += 1
        logger.error(f"Erreur générale lors de la mise à jour des statuts: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if connexion_prete(conn):
            conn.close()
    
    return mis_a_jour, erreurs


def creer_souscriptions_speciales_mensuelles(reference_date: Optional[date] = None) -> dict:
    """
    Crée automatiquement les enregistrements du mois courant pour les souscripteurs spéciaux.

    Pour chaque locataire ayant un dernier enregistrement avec le statut de souscription
    "Spécial", la fonction crée une ligne pour le mois courant si elle n'existe pas encore.
    Les nouveaux enregistrements sont créés en "En attente" avec montant payé à 0.
    Un journal transactionnel empêche les doublons même si la fonction est appelée deux fois.
    """
    conn = None
    cursor = None
    creations = 0
    erreurs = 0
    souscripteurs_trouves = 0
    statut_execution = "skipped"
    message = ""
    date_reference = reference_date or date.today()
    mois_courant = date_reference.replace(day=1)
    mois_precedent = _previous_month_start(date_reference)
    periode = _month_key(date_reference)
    lock_age_limit = datetime.now() - timedelta(minutes=STALE_LOCK_MINUTES)

    try:
        conn = obtenir_connexion()
        if connexion_prete(conn):
            cursor = conn.cursor()
            _ensure_database_schema(cursor)
            conn.commit()

            logger.info(f"Vérification des souscriptions spéciales pour {mois_courant}")

            # Vérifie si la migration a déjà été exécutée pour cette période.
            cursor.execute(
                """
                    SELECT status, created_count, error_count, details_json, started_at, completed_at
                    FROM maintenance_journal
                    WHERE operation_key = %s AND period_key = %s
                    FOR UPDATE
                """,
                (ROLLING_OPERATION_KEY, periode),
            )
            journal_row = cursor.fetchone()
            if journal_row:
                current_status, previous_created, previous_errors, details_json, started_at, completed_at = journal_row
                if str(current_status).lower() == "done":
                    details = _parse_details_json(details_json)
                    message = details.get(
                        "message",
                        f"La migration mensuelle {periode} a déjà été exécutée.",
                    )
                    logger.info(message)
                    conn.commit()
                    return {
                        "status": "already_done",
                        "created": int(previous_created or 0),
                        "errors": int(previous_errors or 0),
                        "month": periode,
                        "message": message,
                        "details": details,
                    }

                started_value = started_at
                if hasattr(started_value, "replace") and started_value < lock_age_limit:
                    cursor.execute(
                        """
                            UPDATE maintenance_journal
                            SET status = 'running', updated_at = CURRENT_TIMESTAMP
                            WHERE operation_key = %s AND period_key = %s
                        """,
                        (ROLLING_OPERATION_KEY, periode),
                    )
                    conn.commit()
                else:
                    message = f"Une migration mensuelle est déjà en cours pour {periode}."
                    logger.info(message)
                    conn.commit()
                    return {
                        "status": "running",
                        "created": int(previous_created or 0),
                        "errors": int(previous_errors or 0),
                        "month": periode,
                        "message": message,
                        "details": _parse_details_json(details_json),
                    }
            else:
                try:
                    cursor.execute(
                        """
                            INSERT INTO maintenance_journal (
                                operation_key, period_key, status, created_count, error_count, details_json
                            )
                            VALUES (%s, %s, 'running', 0, 0, %s)
                        """,
                        (ROLLING_OPERATION_KEY, periode, json.dumps({"month": periode, "message": "Préparation de la migration mensuelle"})),
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
                    cursor.execute(
                        """
                            SELECT status, created_count, error_count, details_json, started_at, completed_at
                            FROM maintenance_journal
                            WHERE operation_key = %s AND period_key = %s
                        """,
                        (ROLLING_OPERATION_KEY, periode),
                    )
                    journal_row = cursor.fetchone()
                    if journal_row:
                        current_status = str(journal_row[0]).lower()
                        details = _parse_details_json(journal_row[3])
                        if current_status == "done":
                            message = details.get(
                                "message",
                                f"La migration mensuelle {periode} a déjà été exécutée.",
                            )
                            logger.info(message)
                            return {
                                "status": "already_done",
                                "created": int(journal_row[1] or 0),
                                "errors": int(journal_row[2] or 0),
                                "month": periode,
                                "message": message,
                                "details": details,
                            }
                        message = details.get(
                            "message",
                            f"Une migration mensuelle est déjà en cours pour {periode}.",
                        )
                        logger.info(message)
                        return {
                            "status": "running",
                            "created": int(journal_row[1] or 0),
                            "errors": int(journal_row[2] or 0),
                            "month": periode,
                            "message": message,
                            "details": details,
                        }

                    message = f"Impossible de réserver la migration mensuelle pour {periode}."
                    logger.warning(message)
                    return {
                        "status": "error",
                        "created": 0,
                        "errors": 1,
                        "month": periode,
                        "message": message,
                        "details": {},
                    }

            passages_litigieux = _basculer_paiements_anterieurs_en_litigieux(cursor, mois_courant)
            if passages_litigieux > 0:
                logger.info(
                    f"{passages_litigieux} paiement(s) en attente antérieurs au mois {mois_courant} "
                    "passé(s) en Litigieux"
                )

            query = """
                SELECT p.id, p.locataire_id, p.montant_total, p.montant_paye, p.devise,
                       p.statut_souscription, l.nom, l.prenom, l.telephone
                FROM paiements p
                JOIN (
                    SELECT locataire_id, MAX(id) AS dernier_id
                    FROM paiements
                    WHERE statut_souscription = 'Spécial'
                    GROUP BY locataire_id
                ) derniers ON derniers.dernier_id = p.id
                JOIN locataires l ON l.id = p.locataire_id
                WHERE p.statut_souscription = 'Spécial'
                ORDER BY l.nom ASC, l.prenom ASC
            """

            cursor.execute(query)
            souscripteurs = cursor.fetchall()
            souscripteurs_trouves = len(souscripteurs)
            logger.info(f"{len(souscripteurs)} souscripteurs spéciaux trouvés pour duplication mensuelle")

            for (
                paiement_id,
                locataire_id,
                montant_total,
                montant_paye,
                devise,
                statut_souscription,
                nom,
                prenom,
                telephone,
            ) in souscripteurs:
                try:
                    cursor.execute(
                        """
                            SELECT id
                            FROM paiements
                            WHERE locataire_id = %s
                              AND mois = %s
                              AND statut_souscription = 'Spécial'
                            LIMIT 1
                        """,
                        (locataire_id, mois_courant),
                    )
                    existe_deja = cursor.fetchone()
                    if existe_deja:
                        logger.info(
                            f"Enregistrement déjà présent pour {nom} {prenom} au mois {mois_courant}"
                        )
                        continue

                    montant_total_val = float(montant_total or montant_paye or 0)
                    if montant_total_val <= 0:
                        logger.warning(
                            f"Montant invalide pour {nom} {prenom} (paiement ID {paiement_id}), duplication ignorée"
                        )
                        continue

                    cursor.execute(
                        """
                            INSERT INTO paiements (
                                locataire_id, mois, montant, montant_total, montant_paye,
                                reste_a_payer, devise, statut, statut_souscription, statut_paiement
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            locataire_id,
                            mois_courant,
                            montant_total_val,
                            montant_total_val,
                            0,
                            montant_total_val,
                            devise,
                            "En attente",
                            "Spécial",
                            "En attente",
                        ),
                    )
                    creations += 1
                    logger.info(
                        f"Duplication mensuelle créée pour {nom} {prenom} ({telephone or 'sans téléphone'})"
                    )

                except Exception as e:
                    erreurs += 1
                    logger.error(
                        f"Erreur lors de la duplication mensuelle du souscripteur {nom} {prenom}: {e}"
                    )

            message = (
                f"Migration mensuelle terminée pour {periode} : "
                f"{creations} création(s), {passages_litigieux} passage(s) en Litigieux, {erreurs} erreur(s)."
            )
            statut_execution = "done"
            cursor.execute(
                """
                    UPDATE maintenance_journal
                    SET status = %s,
                        created_count = %s,
                        error_count = %s,
                        details_json = %s,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE operation_key = %s AND period_key = %s
                """,
                (
                    statut_execution,
                    creations,
                    erreurs,
                    json.dumps(
                        {
                            "month": periode,
                            "created": creations,
                            "overdue_updates": passages_litigieux,
                            "errors": erreurs,
                            "found": souscripteurs_trouves,
                            "message": message,
                            "previous_month": mois_precedent.isoformat(),
                            "cutoff_month": mois_courant.isoformat(),
                        },
                        ensure_ascii=False,
                    ),
                    ROLLING_OPERATION_KEY,
                    periode,
                ),
            )
            conn.commit()
            logger.info(message)

    except Exception as e:
        erreurs += 1
        logger.error(f"Erreur générale lors de la duplication mensuelle: {e}")
        if conn:
            conn.rollback()
        statut_execution = "error"
        message = f"Échec de la migration mensuelle pour {periode}: {e}"
        try:
            if connexion_prete(conn):
                cursor = conn.cursor()
                _ensure_maintenance_journal(cursor)
                cursor.execute(
                    """
                        INSERT INTO maintenance_journal (
                            operation_key, period_key, status, created_count, error_count, details_json
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            status = VALUES(status),
                            created_count = VALUES(created_count),
                            error_count = VALUES(error_count),
                            details_json = VALUES(details_json),
                            updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        ROLLING_OPERATION_KEY,
                        periode,
                        statut_execution,
                        creations,
                        erreurs,
                        json.dumps({"month": periode, "message": message}, ensure_ascii=False),
                    ),
                )
                conn.commit()
        except Exception:
            pass
    finally:
        if cursor:
            cursor.close()
        if connexion_prete(conn):
            conn.close()

    return {
        "status": statut_execution,
        "created": creations,
        "errors": erreurs,
        "month": periode,
        "message": message or f"Migration mensuelle traitée pour {periode}.",
        "details": {
            "found": souscripteurs_trouves,
            "month": periode,
            "previous_month": mois_precedent.isoformat(),
        },
    }


def obtenir_paiements_a_suivi(reference_date: Optional[date] = None) -> List[dict]:
    """
    Obtient la liste des paiements qui nécessitent un suivi.
    
    Returns:
        List[dict]: Liste des paiements avec informations de suivi
    """
    conn = None
    cursor = None
    paiements = []
    date_reference = reference_date or date.today()
    mois_courant = date_reference.replace(day=1)
    
    try:
        conn = obtenir_connexion()
        if connexion_prete(conn):
            cursor = conn.cursor()
            
            query = """
                SELECT p.id, p.mois, p.statut, p.montant_total, p.montant_paye, p.reste_a_payer,
                       l.nom, l.prenom, l.telephone
                FROM paiements p
                JOIN locataires l ON p.locataire_id = l.id
                WHERE p.statut IN ('En attente', 'Litigieux')
                AND p.mois = %s
                ORDER BY p.mois ASC
            """
            
            cursor.execute(query, (mois_courant,))
            resultats = cursor.fetchall()
            
            for row in resultats:
                paiements.append({
                    'id': row[0],
                    'mois': row[1],
                    'statut': row[2],
                    'montant_total': row[3],
                    'montant_paye': row[4],
                    'reste_a_payer': row[5],
                    'nom': row[6],
                    'prenom': row[7],
                    'telephone': row[8]
                })
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des paiements à suivre: {e}")
    finally:
        if cursor:
            cursor.close()
        if connexion_prete(conn):
            conn.close()
    
    return paiements


def creer_loyers_recurrents_mensuels(reference_date: Optional[date] = None) -> dict:
    """Reconduit les loyers récurrents une seule fois par locataire et par mois.

    Le dernier montant connu est repris par défaut. Si une ligne de ``loyer_tarifs``
    existe avec une date d'effet antérieure ou égale au mois cible, elle est prioritaire.
    """
    config = load_app_config().get("automatic_maintenance", {})
    if not config.get("renew_recurring_rents", False):
        return {"status": "disabled", "created": 0, "errors": 0}

    date_reference = reference_date or date.today()
    mois_courant = date_reference.replace(day=1)
    periode = _month_key(date_reference)
    statuts_config = list(config.get("renewal_statuses", ["Simple", "Spécial"]))
    # Quand le basculement Spécial est manuel, exclure "Spécial" de la
    # reconduction automatique – seul le basculement manuel UI les gère.
    if not _is_special_rollover_automatic_enabled():
        statuts_config = [s for s in statuts_config if s != "Spécial"]
    if not statuts_config:
        return {"status": "skipped", "created": 0, "errors": 0}
    statuts = tuple(statuts_config)
    conn = None
    cursor = None
    created = 0
    errors = 0
    try:
        conn = obtenir_connexion()
        if not connexion_prete(conn):
            return {"status": "error", "created": 0, "errors": 1, "message": "Base de données inaccessible."}
        cursor = conn.cursor()
        placeholders = ", ".join(["%s"] * len(statuts))
        cursor.execute(
            f"""
            SELECT p.locataire_id, p.montant_total, p.devise, p.statut_souscription
            FROM paiements p
            JOIN (
                SELECT locataire_id, MAX(id) AS dernier_id
                FROM paiements
                WHERE statut_souscription IN ({placeholders})
                GROUP BY locataire_id
            ) derniers ON derniers.dernier_id = p.id
            """,
            statuts,
        )
        locataires = cursor.fetchall()
        for locataire_id, montant_total, devise, statut_souscription in locataires:
            cursor.execute(
                "SELECT id FROM paiements WHERE locataire_id = %s AND mois = %s LIMIT 1",
                (locataire_id, mois_courant),
            )
            if cursor.fetchone():
                continue

            cursor.execute(
                """
                SELECT montant, devise FROM loyer_tarifs
                WHERE locataire_id = %s AND effective_from <= %s
                ORDER BY effective_from DESC, id DESC LIMIT 1
                """,
                (locataire_id, mois_courant),
            )
            tariff = cursor.fetchone()
            montant = float(tariff[0] if tariff else montant_total or 0)
            devise_effective = tariff[1] if tariff else devise
            if montant <= 0:
                errors += 1
                continue
            cursor.execute(
                """
                INSERT INTO paiements (
                    locataire_id, mois, montant, montant_total, montant_paye,
                    reste_a_payer, devise, statut, statut_souscription, statut_paiement
                ) VALUES (%s, %s, %s, %s, 0, %s, %s, 'En attente', %s, 'En attente')
                """,
                (locataire_id, mois_courant, montant, montant, montant, devise_effective, statut_souscription),
            )
            created += 1
        conn.commit()
        return {"status": "done", "month": periode, "created": created, "errors": errors}
    except Exception as exc:
        if connexion_prete(conn):
            conn.rollback()
        logger.error("Erreur lors de la reconduction des loyers: %s", exc)
        return {"status": "error", "month": periode, "created": created, "errors": errors + 1, "message": str(exc)}
    finally:
        if cursor:
            cursor.close()
        if connexion_prete(conn):
            conn.close()


def executer_basculement_special_manuel(mois_cible: date) -> dict:
    """
    Bascule manuellement les souscripteurs Spécial vers le mois choisi.

    Crée les lignes du mois cible, bascule les anciens « En attente » en Litigieux
    et journalise l'opération pour éviter les doublons.
    """
    target_month = mois_cible.replace(day=1)
    if target_month < SPECIAL_ROLLOVER_START:
        message = (
            f"Le mois cible doit être au minimum {format_mois_affichage(SPECIAL_ROLLOVER_START)}."
        )
        logger.warning(message)
        return {
            "status": "error",
            "created": 0,
            "errors": 1,
            "month": target_month.strftime("%Y-%m"),
            "message": message,
            "details": {},
        }

    logger.info("Basculement manuel Spécial vers %s", target_month.strftime("%Y-%m"))
    return creer_souscriptions_speciales_mensuelles(target_month)


def executer_mise_a_jour_automatique(reference_date: Optional[date] = None) -> dict:
    """
    Exécute la mise à jour automatique et retourne un rapport.
    
    Returns:
        dict: Rapport de la mise à jour
    """
    logger.info("=" * 60)
    logger.info("Démarrage de la mise à jour automatique des statuts")
    logger.info("=" * 60)

    date_reference = reference_date or date.today()
    
    if _is_special_rollover_automatic_enabled():
        rollover = creer_souscriptions_speciales_mensuelles(date_reference)
    else:
        rollover = {
            "status": "manual_only",
            "created": 0,
            "errors": 0,
            "month": "",
            "message": "Basculement Spécial manuel : choisissez le mois cible dans l'interface.",
            "details": {},
        }
    recurring = creer_loyers_recurrents_mensuels(date_reference)
    mis_a_jour, erreurs_mises_a_jour = verifier_et_mettre_a_jour_statuts(date_reference)
    rappel_litigieux = verifier_rappel_litigieux(date_reference)
    
    paiements_suivi = obtenir_paiements_a_suivi(date_reference)
    erreurs_rappel = 1 if rappel_litigieux.get("status") == "error" else 0
    
    rapport = {
        'date': date_reference.isoformat(),
        'creations_speciales': rollover.get('created', 0),
        'creations_loyers_recurrents': recurring.get('created', 0),
        'renewal_status': recurring.get('status', 'disabled'),
        'rollover_special_status': rollover.get('status', 'unknown'),
        'rollover_special_message': rollover.get('message', ''),
        'rollover_special_month': rollover.get('month', ''),
        'litigieux_reminder_status': rappel_litigieux.get('status', 'unknown'),
        'litigieux_reminder_count': rappel_litigieux.get('count', 0),
        'litigieux_reminder_month': rappel_litigieux.get('month', ''),
        'litigieux_reminder_message': rappel_litigieux.get('message', ''),
        'litigieux_reminder_details': rappel_litigieux.get('details', {}),
        'mis_a_jour': mis_a_jour,
        'erreurs': rollover.get('errors', 0) + recurring.get('errors', 0) + erreurs_mises_a_jour + erreurs_rappel,
        'paiements_a_suivi': len(paiements_suivi),
        'details_paiements': paiements_suivi,
        'rollover_details': rollover.get('details', {}),
    }
    
    logger.info(f"Rapport: {rapport}")
    logger.info("=" * 60)
    
    return rapport


def executer_demo_cycle_mensuel(reference_date: Optional[date] = None) -> dict:
    """
    Simule le passage du 1er et du jour de mise à jour configuré sur une date donnée.
    """
    date_reference = reference_date or date.today().replace(day=1)
    date_premier = date_reference.replace(day=1)
    automatic_update_day = _get_automatic_update_day()
    date_update = date_reference.replace(day=automatic_update_day)

    logger.info("Démarrage de la démo du cycle mensuel")
    rollover = creer_souscriptions_speciales_mensuelles(date_premier)
    mis_a_jour, erreurs_mises_a_jour = verifier_et_mettre_a_jour_statuts(date_update)
    rappel_litigieux = verifier_rappel_litigieux(date_update)
    paiements_suivi = obtenir_paiements_a_suivi(date_update)

    rapport = {
        "date_demo": date_reference.isoformat(),
        "date_premier": date_premier.isoformat(),
        "date_update": date_update.isoformat(),
        "creations_speciales": rollover.get("created", 0),
        "rollover_special_status": rollover.get("status", "unknown"),
        "rollover_special_message": rollover.get("message", ""),
        "litigieux_reminder_status": rappel_litigieux.get("status", "unknown"),
        "litigieux_reminder_count": rappel_litigieux.get("count", 0),
        "litigieux_reminder_message": rappel_litigieux.get("message", ""),
        "mis_a_jour": mis_a_jour,
        "erreurs": rollover.get("errors", 0) + erreurs_mises_a_jour + (1 if rappel_litigieux.get("status") == "error" else 0),
        "paiements_a_suivi": len(paiements_suivi),
        "details_paiements": paiements_suivi,
    }

    logger.info(f"Démo cycle mensuel terminée: {rapport}")
    return rapport


if __name__ == "__main__":
    # Pour tester manuellement
    rapport = executer_mise_a_jour_automatique()
    print(f"Créations mensuelles: {rapport['creations_speciales']}")
    print(f"Mise à jour terminée: {rapport['mis_a_jour']} paiements mis à jour")
    print(f"Paiements à suivre: {rapport['paiements_a_suivi']}")
