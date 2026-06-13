from tkinter import messagebox

from mysql.connector import Error

from tap.core.date_utils import parse_mois_saisie
from tap.infrastructure.database.connection import obtenir_connexion

MOIS_SQL_EXPR = "DATE_FORMAT(p.mois, '%m/%Y')"


def _append_filtre_mois(query: str, params: list, filtre_mois: str) -> tuple[str, list]:
    if not filtre_mois:
        return query, params

    parsed = parse_mois_saisie(filtre_mois)
    if parsed:
        query += " AND YEAR(p.mois) = %s AND MONTH(p.mois) = %s"
        params.extend([parsed.year, parsed.month])
        return query, params

    query += f" AND {MOIS_SQL_EXPR} LIKE %s"
    params.append(f"%{filtre_mois.strip()}%")
    return query, params


def inserer_souscription(
    nom,
    prenom,
    telephone,
    mois,
    montant,
    devise,
    statut="En attente",
    statut_souscription="Simple",
):
    mois_date = parse_mois_saisie(mois)
    if not mois_date:
        return False, "Format de date invalide. Utilisez AAAA-MM-JJ ou AAAA-MM."

    try:
        conn = obtenir_connexion()
        if conn.is_connected():
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id FROM locataires WHERE nom = %s AND prenom = %s AND telephone = %s",
                (nom, prenom, telephone),
            )
            result = cursor.fetchone()

            if result:
                locataire_id = result[0]
            else:
                cursor.execute(
                    "INSERT INTO locataires (nom, prenom, telephone) VALUES (%s, %s, %s)",
                    (nom, prenom, telephone),
                )
                locataire_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO paiements (locataire_id, mois, montant, devise, statut, statut_souscription) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    locataire_id,
                    mois_date,
                    montant,
                    devise,
                    statut or "En attente",
                    statut_souscription or "Simple",
                ),
            )

            conn.commit()
            return True, "Enregistrement réussi avec succès !"

    except Error as e:
        return False, f"Erreur de base de données : {e}"
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def recuperer_inventaire(filtre_nom="", filtre_statut="Tous"):
    try:
        conn = obtenir_connexion()
        cursor = conn.cursor()

        query = (
            f"SELECT l.nom, l.prenom, l.telephone, p.montant, p.devise, {MOIS_SQL_EXPR} AS mois, p.statut "
            "FROM paiements p JOIN locataires l ON p.locataire_id = l.id WHERE 1=1"
        )
        params = []

        if filtre_nom:
            query += " AND (l.nom LIKE %s OR l.prenom LIKE %s)"
            params.append(f"%{filtre_nom}%")
            params.append(f"%{filtre_nom}%")

        if filtre_statut != "Tous":
            query += " AND p.statut = %s"
            params.append(filtre_statut)

        query += " ORDER BY p.id DESC"
        cursor.execute(query, params)
        return cursor.fetchall()

    except Error as e:
        messagebox.showerror("Erreur", f"Impossible de charger les données : {e}")
        return []
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def get_souscriptions(
    filtre_nom="",
    filtre_statut="Tous",
    filtre_devise="Toutes",
    filtre_mois="",
    filtre_statut_souscription="Tous",
):
    try:
        conn = obtenir_connexion()
        cursor = conn.cursor()

        query = (
            f"SELECT p.id, l.id, l.nom, l.prenom, {MOIS_SQL_EXPR} AS mois, p.montant, p.devise, "
            "p.statut_souscription, p.statut "
            "FROM paiements p JOIN locataires l ON p.locataire_id = l.id WHERE 1=1"
        )
        params = []

        if filtre_nom:
            query += " AND (l.nom LIKE %s OR l.prenom LIKE %s)"
            params.append(f"%{filtre_nom}%")
            params.append(f"%{filtre_nom}%")

        if filtre_statut != "Tous":
            query += " AND p.statut = %s"
            params.append(filtre_statut)

        if filtre_devise != "Toutes":
            query += " AND UPPER(TRIM(p.devise)) = %s"
            params.append(filtre_devise.upper())

        query, params = _append_filtre_mois(query, params, filtre_mois)

        if filtre_statut_souscription != "Tous":
            query += " AND p.statut_souscription = %s"
            params.append(filtre_statut_souscription)

        query += " ORDER BY p.mois DESC, p.id DESC"
        cursor.execute(query, params)
        return cursor.fetchall()

    except Error as e:
        messagebox.showerror("Erreur", f"Impossible de charger les données : {e}")
        return []
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def mettre_a_jour_statut(paiement_id, nouveau_statut):
    try:
        conn = obtenir_connexion()
        cursor = conn.cursor()

        query = "UPDATE paiements SET statut = %s WHERE id = %s"
        cursor.execute(query, (nouveau_statut, paiement_id))
        conn.commit()
        return True, "Statut mis à jour avec succès !"

    except Error as e:
        return False, f"Erreur de mise à jour : {e}"
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def get_souscriptions_avec_filtres(
    filtre_nom="",
    filtre_statut="Tous",
    date_debut="",
    date_fin="",
    filtre_statut_souscription="Tous",
):
    try:
        conn = obtenir_connexion()
        cursor = conn.cursor()

        query = (
            f"SELECT p.id, l.id, l.nom, l.prenom, {MOIS_SQL_EXPR} AS mois, p.montant, p.devise, "
            "p.statut_souscription, p.statut, "
            "DATE_FORMAT(p.date_creation, '%Y-%m-%d') as date_creation "
            "FROM paiements p "
            "JOIN locataires l ON p.locataire_id = l.id "
            "WHERE 1=1"
        )
        params = []

        if filtre_nom:
            query += " AND (l.nom LIKE %s OR l.prenom LIKE %s)"
            params.append(f"%{filtre_nom}%")
            params.append(f"%{filtre_nom}%")

        if filtre_statut != "Tous":
            query += " AND p.statut = %s"
            params.append(filtre_statut)

        if filtre_statut_souscription != "Tous":
            query += " AND p.statut_souscription = %s"
            params.append(filtre_statut_souscription)

        if date_debut:
            query += " AND DATE(p.date_creation) >= %s"
            params.append(date_debut)

        if date_fin:
            query += " AND DATE(p.date_creation) <= %s"
            params.append(date_fin)

        cursor.execute(query, params)
        return cursor.fetchall()

    except Error as e:
        messagebox.showerror("Erreur", f"Impossible de charger les données : {e}")
        return []
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def get_historique_locataire(locataire_id):
    conn = obtenir_connexion()
    cursor = conn.cursor()
    try:
        query = (
            f"SELECT {MOIS_SQL_EXPR} AS mois, p.montant, p.devise, p.statut_souscription, p.statut "
            "FROM paiements p "
            "WHERE p.locataire_id = %s "
            "ORDER BY p.mois DESC, p.id DESC"
        )
        cursor.execute(query, (locataire_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
