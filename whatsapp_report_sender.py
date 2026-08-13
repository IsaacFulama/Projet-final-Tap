"""Utilitaire autonome pour envoyer un rapport TAP sur WhatsApp.

Ce script est volontairement séparé de l'application principale pour ne rien
casser dans l'interface. Il peut être planifié par le Planificateur de tâches
Windows ou appelé après la maintenance mensuelle.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

from tap.core.whatsapp_reports import (
    build_whatsapp_report_message,
    has_already_sent,
    load_latest_maintenance_report,
    load_whatsapp_config,
    mark_as_sent,
    send_monthly_pdf_reports,
    send_whatsapp_report,
)

# Configuration d'un logging propre pour la traçabilité (Planificateur de tâches)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("tap.cli.whatsapp")


def _load_report_from_file(path: Path) -> dict | None:
    if not path.is_file():
        logger.error(f"Le chemin spécifié n'est pas un fichier valide : {path}")
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as err:
        logger.error(f"Fichier JSON malformé ({path}) : {err}")
        return None
    except OSError as err:
        logger.error(f"Erreur d'accès au fichier ({path}) : {err}")
        return None


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Envoi automatique de rapports TAP sur WhatsApp",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--report-file",
        type=Path,
        metavar="FILE",
        help="Chemin vers un fichier JSON de rapport spécifique",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Afficher les actions et messages sans effectuer d'envois réels",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forcer l'envoi même si le rapport a déjà été marqué comme envoyé",
    )
    parser.add_argument(
        "--send-monthly-pdf",
        action="store_true",
        help="Envoyer les rapports PDF mensuels (En règle et Litigieux)",
    )
    parser.add_argument(
        "--month",
        type=str,
        metavar="YYYY-MM",
        help="Mois à utiliser pour le rapport PDF mensuel",
    )
    parser.add_argument(
        "--report-types",
        nargs="+",
        metavar="TYPE",
        help="Types de rapports à inclure: en_regle et/ou litigieux",
    )
    parser.add_argument(
        "--recipients",
        nargs="+",
        metavar="PHONE",
        help="Liste des numéros de téléphone des destinataires (format international)",
    )
    
    args = parser.parse_args(argv)

    # 1. Mode : Envoi des rapports PDF mensuels
    if args.send_monthly_pdf:
        logger.info("Démarrage du mode de transmission des rapports PDF mensuels...")
        try:
            result = send_monthly_pdf_reports(
                recipients=args.recipients,
                month=args.month,
                report_types=args.report_types,
                dry_run=args.preview,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
            success_statuses = {"completed", "dry_run", "disabled", "no_internet", "already_sent"}
            return 0 if result.get("status") in success_statuses else 1
        except Exception as err:
            logger.exception(f"Erreur critique lors de l'envoi des rapports PDF : {err}")
            return 1

    # 2. Mode : Envoi de rapport texte standard
    report = None
    if args.report_file:
        report = _load_report_from_file(args.report_file)
    else:
        logger.info("Recherche du dernier rapport de maintenance disponible...")
        try:
            report = load_latest_maintenance_report()
        except Exception as err:
            logger.error(f"Impossible de charger le dernier rapport automatique : {err}")
            return 1

    if not report:
        logger.error("Aucun rapport exploitable trouvé.")
        return 1

    # Sécurisation du contenu du message
    try:
        report.setdefault("message", build_whatsapp_report_message(report))
        config = load_whatsapp_config()
    except Exception as err:
        logger.exception(f"Erreur lors de la préparation des données du rapport : {err}")
        return 1

    # Mode Preview (Short-circuit rapide)
    if args.preview:
        logger.info("=== [MODE PREVIEW] Message généré ===")
        print(report.get("message", "[Message vide]"))
        logger.info("=====================================")

    # Vérification des doublons d'envoi
    if not args.force and has_already_sent(report):
        logger.warning("Rapport déjà envoyé pour cette période. Utilisez --force pour passer outre.")
        return 0

    # Exécution de l'envoi
    try:
        result = send_whatsapp_report(report, config=config, dry_run=args.preview)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        status = result.get("status")
        if status == "sent" and not args.preview:
            mark_as_sent(report)
            logger.info("Rapport marqué comme envoyé avec succès.")
            
        return 0 if status in {"sent", "dry_run", "disabled"} else 2

    except Exception as err:
        logger.exception(f"Échec de la communication avec le service de transmission : {err}")
        return 2


if __name__ == "__main__":
    sys.exit(_main())