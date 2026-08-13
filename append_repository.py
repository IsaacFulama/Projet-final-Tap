
def get_archives(
    filtre_nom="",
    filtre_mois="",
    connection_provider: ConnectionProvider | None = None,
):
    try:
        conn = obtenir_connexion(connection_provider)
        cursor = conn.cursor()

        query = (
            f"SELECT p.id, l.id, l.nom, l.prenom, {MOIS_SQL_EXPR} AS mois, p.montant, p.devise, "
            "p.statut_souscription, p.statut, "
            "DATE_FORMAT(p.date_creation, '%Y-%m-%d') as date_creation "
            "FROM archives_paiements p "
            "JOIN locataires l ON p.locataire_id = l.id "
            "WHERE 1=1"
        )
        params = []

        query, params = _append_filtre_nom(query, params, filtre_nom)

        if filtre_mois:
            query, params = _append_filtre_mois(query, params, filtre_mois)

        query += " ORDER BY p.id DESC"

        cursor.execute(query, params)
        return cursor.fetchall()

    except Error as e:
        messagebox.showerror("Erreur", f"Impossible de charger les archives : {e}")
        return []
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def restaurer_archive(
    archive_id,
    connection_provider: ConnectionProvider | None = None,
):
    """Restaure un paiement depuis les archives vers la table principale."""
    try:
        conn = obtenir_connexion(connection_provider)
        if conn.is_connected():
            cursor = conn.cursor()

            # Copier depuis archives_paiements vers paiements
            query_insert = "INSERT IGNORE INTO paiements SELECT * FROM archives_paiements WHERE id = %s"
            cursor.execute(query_insert, (archive_id,))
            
            # Supprimer de archives_paiements
            query_delete = "DELETE FROM archives_paiements WHERE id = %s"
            cursor.execute(query_delete, (archive_id,))

            conn.commit()
            return True, "Archive restaurée avec succès !"

    except Error as e:
        if "conn" in locals() and conn.is_connected():
            conn.rollback()
        return False, f"Erreur de restauration de l'archive : {e}"
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()
