"""Archivage automatique sûr des paiements anciens."""

from __future__ import annotations

import logging
import threading
from datetime import date

from tap.config.settings import load_app_config
from tap.infrastructure.database.connection import connexion_prete, obtenir_connexion

logger = logging.getLogger(__name__)

DEFAULT_MONTHS = 24
DEFAULT_BATCH_SIZE = 500


def _archive_settings() -> dict:
    config = load_app_config()
    value = config.get("archiving", {}) if isinstance(config, dict) else {}
    value = value if isinstance(value, dict) else {}
    try:
        months = max(12, min(int(value.get("months", DEFAULT_MONTHS)), 120))
    except (TypeError, ValueError):
        months = DEFAULT_MONTHS
    try:
        batch_size = max(1, min(int(value.get("batch_size", DEFAULT_BATCH_SIZE)), 5000))
    except (TypeError, ValueError):
        batch_size = DEFAULT_BATCH_SIZE
    return {
        "enabled": value.get("enabled", True) is not False,
        "months": months,
        "only_paid": value.get("only_paid", True) is not False,
        "batch_size": batch_size,
    }


def executer_archivage() -> dict[str, int | str | bool]:
    """Archive par lots les paiements clôturés vieux d'au moins 24 mois.

    Les lignes sont d'abord copiées dans ``archives_paiements`` puis supprimées
    uniquement si leur identifiant existe bien dans cette table. Les paiements
    litigieux ou en attente restent toujours dans la table active.
    """
    settings = _archive_settings()
    result: dict[str, int | str | bool] = {
        "enabled": settings["enabled"],
        "archived": 0,
        "skipped": 0,
        "cutoff": "",
    }
    if not settings["enabled"]:
        return result

    conn = None
    cursor = None
    try:
        conn = obtenir_connexion()
        if not connexion_prete(conn):
            return result
        cursor = conn.cursor()
        cutoff = date.today().replace(day=1)
        # Calcul robuste sans dépendre de la présence de dateutil.
        year = cutoff.year * 12 + cutoff.month - 1 - int(settings["months"])
        cutoff = date(year // 12, year % 12 + 1, 1)
        result["cutoff"] = cutoff.isoformat()

        conditions = ["mois < %s"]
        params: list[object] = [cutoff]
        if settings["only_paid"]:
            conditions.extend([
                "statut = 'En règle'",
                "COALESCE(montant_paye, 0) >= COALESCE(montant_total, montant)",
            ])
        # Les signatures restent rattachées à la table active par une clé
        # étrangère. On ne supprime donc jamais un paiement signé sans avoir
        # prévu un archivage dédié de sa signature.
        conditions.append(
            "NOT EXISTS (SELECT 1 FROM signatures_paiements s "
            "WHERE s.paiement_id = paiements.id)"
        )
        cursor.execute(
            "SELECT id FROM paiements WHERE " + " AND ".join(conditions)
            + " ORDER BY mois ASC, id ASC LIMIT %s",
            [*params, settings["batch_size"]],
        )
        ids = [int(row[0]) for row in cursor.fetchall()]
        result["skipped"] = len(ids)
        if not ids:
            conn.commit()
            return result

        marks = ",".join(["%s"] * len(ids))
        cursor.execute(
            f"INSERT IGNORE INTO archives_paiements "
            f"SELECT * FROM paiements WHERE id IN ({marks})",
            ids,
        )
        cursor.execute(
            f"DELETE FROM paiements WHERE id IN ({marks}) "
            f"AND id IN (SELECT id FROM archives_paiements)",
            ids,
        )
        archived = max(0, cursor.rowcount)
        conn.commit()
        result["archived"] = archived
        result["skipped"] = max(0, len(ids) - archived)
        logger.info(
            "Archivage automatique: archived=%s skipped=%s cutoff=%s",
            result["archived"], result["skipped"], result["cutoff"],
        )
        return result
    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("Erreur lors de l'archivage automatique")
        return result
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def lancer_archivage_en_arriere_plan() -> None:
    thread = threading.Thread(target=executer_archivage, daemon=True, name="AutoArchiverThread")
    thread.start()
