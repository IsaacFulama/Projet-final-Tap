from datetime import date

from mysql.connector import Error

from tap.core.date_utils import parse_mois_saisie
from tap.infrastructure.database.connection import obtenir_connexion


def ajouter_colonne_date_creation():
    """Ajoute la colonne date_creation si elle n'existe pas."""
    try:
        conn = obtenir_connexion()
        if conn.is_connected():
            cursor = conn.cursor()

            cursor.execute("SHOW COLUMNS FROM paiements LIKE 'date_creation'")
            if not cursor.fetchone():
                cursor.execute(
                    "ALTER TABLE paiements ADD COLUMN date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                )
                conn.commit()
                print("Colonne date_creation ajoutée avec succès")

            cursor.close()
            conn.close()
    except Error as e:
        print(f"Erreur lors de l'ajout de la colonne: {e}")
    finally:
        if "conn" in locals() and conn.is_connected():
            conn.close()


def ajouter_colonne_statut_souscription():
    """Ajoute la colonne statut_souscription si elle n'existe pas."""
    try:
        conn = obtenir_connexion()
        if conn.is_connected():
            cursor = conn.cursor()

            cursor.execute("SHOW COLUMNS FROM paiements LIKE 'statut_souscription'")
            if not cursor.fetchone():
                cursor.execute(
                    "ALTER TABLE paiements ADD COLUMN statut_souscription VARCHAR(20) DEFAULT 'Simple' AFTER devise"
                )
                try:
                    cursor.execute(
                        "CREATE INDEX idx_statut_souscription ON paiements(statut_souscription)"
                    )
                except Error:
                    pass
                conn.commit()
                print("Colonne statut_souscription ajoutée avec succès")

            cursor.close()
            conn.close()
    except Error as e:
        print(f"Erreur lors de l'ajout de la colonne statut_souscription: {e}")
    finally:
        if "conn" in locals() and conn.is_connected():
            conn.close()


def migrer_mois_vers_date():
    """Convertit la colonne mois de VARCHAR vers DATE."""
    try:
        conn = obtenir_connexion()
        if not conn.is_connected():
            return

        cursor = conn.cursor()
        cursor.execute("SHOW COLUMNS FROM paiements LIKE 'mois'")
        column = cursor.fetchone()
        if not column:
            cursor.close()
            conn.close()
            return

        column_type = str(column[1]).lower()
        if "date" in column_type and "datetime" not in column_type:
            cursor.close()
            conn.close()
            return

        cursor.execute("SELECT id, mois FROM paiements")
        rows = cursor.fetchall()
        fallback = date(2000, 1, 1)

        for paiement_id, raw_mois in rows:
            parsed = parse_mois_saisie(raw_mois) or fallback
            cursor.execute(
                "UPDATE paiements SET mois = %s WHERE id = %s",
                (parsed, paiement_id),
            )

        conn.commit()
        cursor.execute("ALTER TABLE paiements MODIFY COLUMN mois DATE NOT NULL")
        conn.commit()
        print("Colonne mois migrée vers DATE avec succès")

        cursor.close()
        conn.close()
    except Error as e:
        print(f"Erreur lors de la migration mois -> DATE: {e}")
    finally:
        if "conn" in locals() and conn.is_connected():
            conn.close()


def renommer_statut_ordinaire_en_simple():
    """Remplace la valeur historique Ordinaire par Simple."""
    try:
        conn = obtenir_connexion()
        if not conn.is_connected():
            return

        cursor = conn.cursor()
        cursor.execute("SHOW COLUMNS FROM paiements LIKE 'statut_souscription'")
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return

        cursor.execute(
            "UPDATE paiements SET statut_souscription = 'Simple' "
            "WHERE statut_souscription = 'Ordinaire'"
        )
        cursor.execute(
            "ALTER TABLE paiements MODIFY COLUMN statut_souscription "
            "VARCHAR(20) DEFAULT 'Simple'"
        )
        conn.commit()
        print("Statut souscription Ordinaire renommé en Simple")

        cursor.close()
        conn.close()
    except Error as e:
        print(f"Erreur lors du renommage Ordinaire -> Simple: {e}")
    finally:
        if "conn" in locals() and conn.is_connected():
            conn.close()


def renommer_statut_paye_en_en_regle():
    """Remplace la valeur de statut 'Payé' par 'En règle'."""
    try:
        conn = obtenir_connexion()
        if not conn.is_connected():
            return

        cursor = conn.cursor()
        cursor.execute("SHOW COLUMNS FROM paiements LIKE 'statut'")
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return

        cursor.execute(
            "UPDATE paiements SET statut = 'En règle' "
            "WHERE statut = 'Payé'"
        )
        conn.commit()
        print("Statut Payé renommé en En règle")

        cursor.close()
        conn.close()
    except Error as e:
        print(f"Erreur lors du renommage Payé -> En règle: {e}")
    finally:
        if "conn" in locals() and conn.is_connected():
            conn.close()


def ajouter_colonnes_acompte():
    """Ajoute les colonnes pour la gestion des acomptes."""
    try:
        conn = obtenir_connexion()
        if conn.is_connected():
            cursor = conn.cursor()

            # Vérifier et ajouter montant_total
            cursor.execute("SHOW COLUMNS FROM paiements LIKE 'montant_total'")
            if not cursor.fetchone():
                cursor.execute(
                    "ALTER TABLE paiements ADD COLUMN montant_total DECIMAL(10,2) DEFAULT montant"
                )
                # Initialiser montant_total avec la valeur actuelle de montant
                cursor.execute("UPDATE paiements SET montant_total = montant WHERE montant_total IS NULL")
                print("Colonne montant_total ajoutée avec succès")

            # Vérifier et ajouter montant_paye
            cursor.execute("SHOW COLUMNS FROM paiements LIKE 'montant_paye'")
            if not cursor.fetchone():
                cursor.execute(
                    "ALTER TABLE paiements ADD COLUMN montant_paye DECIMAL(10,2) DEFAULT 0"
                )
                # Initialiser montant_paye avec la valeur actuelle de montant pour les enregistrements existants
                cursor.execute("UPDATE paiements SET montant_paye = montant WHERE montant_paye IS NULL OR montant_paye = 0")
                print("Colonne montant_paye ajoutée avec succès")

            # Vérifier et ajouter reste_a_payer
            cursor.execute("SHOW COLUMNS FROM paiements LIKE 'reste_a_payer'")
            if not cursor.fetchone():
                cursor.execute(
                    "ALTER TABLE paiements ADD COLUMN reste_a_payer DECIMAL(10,2) DEFAULT 0"
                )
                # Calculer le reste initial
                cursor.execute("UPDATE paiements SET reste_a_payer = GREATEST(0, montant_total - montant_paye) WHERE reste_a_payer IS NULL OR reste_a_payer = 0")
                print("Colonne reste_a_payer ajoutée avec succès")

            # Vérifier et ajouter statut_paiement
            cursor.execute("SHOW COLUMNS FROM paiements LIKE 'statut_paiement'")
            if not cursor.fetchone():
                cursor.execute(
                    "ALTER TABLE paiements ADD COLUMN statut_paiement VARCHAR(20) DEFAULT 'En attente'"
                )
                # Définir le statut initial
                cursor.execute(
                    "UPDATE paiements SET statut_paiement = "
                    "CASE "
                    "WHEN montant_paye >= montant_total THEN 'Complet' "
                    "WHEN montant_paye > 0 THEN 'Partiel' "
                    "ELSE 'En attente' "
                    "END WHERE statut_paiement IS NULL OR statut_paiement = 'En attente'"
                )
                print("Colonne statut_paiement ajoutée avec succès")

            conn.commit()

            cursor.close()
            conn.close()
    except Error as e:
        print(f"Erreur lors de l'ajout des colonnes acompte: {e}")
    finally:
        if "conn" in locals() and conn.is_connected():
            conn.close()


def run_migrations():
    ajouter_colonne_date_creation()
    ajouter_colonne_statut_souscription()
    renommer_statut_ordinaire_en_simple()
    renommer_statut_paye_en_en_regle()
    migrer_mois_vers_date()
    ajouter_colonnes_acompte()
