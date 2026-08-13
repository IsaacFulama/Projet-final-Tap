from datetime import timedelta
from decimal import Decimal, InvalidOperation
from tkinter import messagebox

from mysql.connector import Error

from tap.core.date_utils import parse_mois_saisie
from tap.infrastructure.database.connection import ConnectionProvider, obtenir_connexion

MOIS_SQL_EXPR = "DATE_FORMAT(p.mois, '%m/%Y')"


def _normaliser_identite(value) -> str:
    """Nettoie un nom pour éviter les doublons dus aux espaces superflus."""
    return " ".join(str(value or "").strip().split())


def _decimal_amount(value) -> Decimal:
    """Convertit un montant utilisateur en Decimal sans erreur d'arrondi binaire."""
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Montant invalide.") from exc


def _statuts_montant(montant_total: Decimal, montant_paye: Decimal) -> tuple[str, str, Decimal]:
    """Retourne (statut, statut_paiement, reste_a_payer) pour une ligne."""
    reste = max(Decimal("0"), montant_total - montant_paye)
    if montant_paye >= montant_total:
        return "En règle", "Complet", reste
    if montant_paye > 0:
        return "Litigieux", "Partiel", reste
    return "En attente", "En attente", reste


def _repartir_versement_fifo(lignes, montant_versement: Decimal) -> list[dict]:
    """Répartit un versement sur les lignes impayées, de la plus ancienne à la plus récente.

    ``lignes`` contient des tuples ``(id, mois, montant_total, montant_paye, reste)``.
    La fonction est volontairement indépendante de MySQL pour rendre la règle métier
    testable et éviter toute perte de montant lors de la répartition.
    """
    restant = _decimal_amount(montant_versement)
    if restant <= 0:
        return []

    allocations = []
    for paiement_id, mois, montant_total, montant_paye, reste in lignes:
        if restant <= 0:
            break

        total = _decimal_amount(montant_total)
        deja_paye = _decimal_amount(montant_paye)
        # Le reste stocké peut être ancien ou incohérent après une migration.
        # Le montant total et le montant payé sont la source de vérité.
        reste_ligne = max(Decimal("0"), total - deja_paye)
        if reste_ligne <= 0:
            continue

        montant_affecte = min(restant, reste_ligne)
        nouveau_paye = deja_paye + montant_affecte
        nouveau_reste = max(Decimal("0"), total - nouveau_paye)
        statut, statut_paiement, _ = _statuts_montant(total, nouveau_paye)
        allocations.append(
            {
                "id": paiement_id,
                "mois": mois,
                "montant_affecte": montant_affecte,
                "montant_paye": nouveau_paye,
                "reste_a_payer": nouveau_reste,
                "statut": statut,
                "statut_paiement": statut_paiement,
            }
        )
        restant -= montant_affecte

    if restant > 0:
        raise ValueError(
            "Le montant dépasse les mois Spéciaux impayés disponibles. "
            "Enregistrez d'abord le mois suivant ou vérifiez le montant."
        )
    return allocations


def _allouer_versement_special(
    cursor,
    locataire_id,
    mois_cible,
    montant_total_cible,
    devise,
    montant_versement,
    *,
    creer_mois_cible: bool,
) -> list[dict]:
    """Affecte un versement Spécial aux mois impayés dans l'ordre chronologique.

    Le mois cible est créé avec zéro payé lorsqu'il n'existe pas encore. Cela permet
    de conserver la dette du mois courant même si le versement sert d'abord à solder
    un mois antérieur.
    """
    montant_versement_decimal = _decimal_amount(montant_versement)
    if montant_versement_decimal <= 0:
        return []

    cursor.execute(
        """
            SELECT id, mois, montant_total, montant_paye, reste_a_payer, devise
            FROM paiements
            WHERE locataire_id = %s
              AND mois = %s
              AND statut_souscription = 'Spécial'
            ORDER BY id ASC
            LIMIT 1
            FOR UPDATE
        """,
        (locataire_id, mois_cible),
    )
    cible = cursor.fetchone()

    if cible and str(cible[5]).upper() != str(devise).upper():
        raise ValueError(
            f"Le mois {mois_cible} existe déjà dans une autre devise ({cible[5]})."
        )

    if not cible and creer_mois_cible:
        total_cible = _decimal_amount(montant_total_cible)
        if total_cible <= 0:
            raise ValueError("Le montant souscrit doit être supérieur à zéro.")
        cursor.execute(
            """
                INSERT INTO paiements (
                    locataire_id, mois, montant, montant_total, montant_paye,
                    reste_a_payer, devise, statut, statut_souscription, statut_paiement
                ) VALUES (%s, %s, %s, %s, 0, %s, %s, 'En attente', 'Spécial', 'En attente')
            """,
            (
                locataire_id,
                mois_cible,
                float(total_cible),
                float(total_cible),
                float(total_cible),
                devise,
            ),
        )
        cursor.execute(
            """
                SELECT id, mois, montant_total, montant_paye, reste_a_payer, devise
                FROM paiements
                WHERE locataire_id = %s
                  AND mois = %s
                  AND statut_souscription = 'Spécial'
                  AND UPPER(devise) = UPPER(%s)
                ORDER BY id DESC
                LIMIT 1
                FOR UPDATE
            """,
            (locataire_id, mois_cible, devise),
        )

    def charger_lignes_impayees():
        cursor.execute(
            """
                SELECT id, mois, montant_total, montant_paye, reste_a_payer
                FROM paiements
                WHERE locataire_id = %s
                  AND statut_souscription = 'Spécial'
                  AND UPPER(devise) = UPPER(%s)
                  AND GREATEST(
                        0,
                        COALESCE(montant_total, 0) - COALESCE(montant_paye, 0)
                      ) > 0
                ORDER BY mois ASC, id ASC
                FOR UPDATE
            """,
            (locataire_id, devise),
        )
        return cursor.fetchall()

    lignes = charger_lignes_impayees()
    capacite = sum(
        max(Decimal("0"), _decimal_amount(ligne[2]) - _decimal_amount(ligne[3]))
        for ligne in lignes
    )

    # Si le versement dépasse les mois existants, créer automatiquement les mois
    # suivants avec le dernier montant connu afin que le surplus soit affecté.
    mois_crees = 0
    while capacite < montant_versement_decimal:
        cursor.execute(
            """
                SELECT mois, montant_total
                FROM paiements
                WHERE locataire_id = %s
                  AND statut_souscription = 'Spécial'
                  AND UPPER(devise) = UPPER(%s)
                ORDER BY mois DESC, id DESC
                LIMIT 1
                FOR UPDATE
            """,
            (locataire_id, devise),
        )
        derniere_ligne = cursor.fetchone()
        if not derniere_ligne or _decimal_amount(derniere_ligne[1]) <= 0:
            break

        mois_a_creer = _mois_suivant(derniere_ligne[0])
        montant_mensuel = _decimal_amount(derniere_ligne[1])
        cursor.execute(
            """
                SELECT id
                FROM paiements
                WHERE locataire_id = %s
                  AND mois = %s
                  AND statut_souscription = 'Spécial'
                  AND UPPER(devise) = UPPER(%s)
                LIMIT 1
                FOR UPDATE
            """,
            (locataire_id, mois_a_creer, devise),
        )
        if cursor.fetchone():
            break

        cursor.execute(
            """
                INSERT INTO paiements (
                    locataire_id, mois, montant, montant_total, montant_paye,
                    reste_a_payer, devise, statut, statut_souscription, statut_paiement
                ) VALUES (%s, %s, %s, %s, 0, %s, %s, 'En attente', 'Spécial', 'En attente')
            """,
            (
                locataire_id,
                mois_a_creer,
                float(montant_mensuel),
                float(montant_mensuel),
                float(montant_mensuel),
                devise,
            ),
        )
        mois_crees += 1
        lignes = charger_lignes_impayees()
        capacite = sum(
            max(Decimal("0"), _decimal_amount(ligne[2]) - _decimal_amount(ligne[3]))
            for ligne in lignes
        )
        if mois_crees > 120:
            break

    allocations = _repartir_versement_fifo(lignes, montant_versement_decimal)

    for allocation in allocations:
        cursor.execute(
            """
                UPDATE paiements
                SET montant_paye = %s,
                    reste_a_payer = %s,
                    statut = %s,
                    statut_paiement = %s
                WHERE id = %s
            """,
            (
                float(allocation["montant_paye"]),
                float(allocation["reste_a_payer"]),
                allocation["statut"],
                allocation["statut_paiement"],
                allocation["id"],
            ),
        )

    return allocations


def _message_allocation_special(allocations: list[dict]) -> str:
    """Construit un retour utilisateur lisible après une répartition automatique."""
    details = []
    for allocation in allocations:
        mois = allocation["mois"]
        if hasattr(mois, "strftime"):
            mois = mois.strftime("%m/%Y")
        details.append(f"{mois}: {float(allocation['montant_affecte']):g}")
    return "Paiement réparti automatiquement sur les mois suivants : " + ", ".join(details)


def _mois_suivant(mois):
    """Retourne le premier jour du mois suivant une date MySQL."""
    return (mois.replace(day=1) + timedelta(days=32)).replace(day=1)


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


def _append_filtre_nom(query: str, params: list, filtre_nom: str) -> tuple[str, list]:
    if not filtre_nom:
        return query, params

    texte = filtre_nom.strip()
    query += " AND (CONCAT(l.nom, ' ', l.prenom) LIKE %s OR l.nom LIKE %s OR l.prenom LIKE %s)"
    params.extend([f"%{texte}%", f"%{texte}%", f"%{texte}%"])
    return query, params


def _append_filtre_devise(query: str, params: list, filtre_devise: str) -> tuple[str, list]:
    if not filtre_devise:
        return query, params

    devise_normalisee = filtre_devise.strip()
    if devise_normalisee.lower() in {"toutes", "tous", "toutes les devises"}:
        return query, params

    query += " AND UPPER(p.devise) = %s"
    params.append(devise_normalisee.upper())
    return query, params


def inserer_souscription(
    nom,
    prenom,
    telephone,
    mois,
    montant_souscrit,
    devise,
    statut="En attente",
    statut_souscription="Simple",
    montant_paye=None,
    avance=None,
    connection_provider: ConnectionProvider | None = None,
    return_details: bool = False,
):
    def _result(success: bool, message: str, details: dict | None = None):
        if return_details:
            return success, message, details or {}
        return success, message

    nom = _normaliser_identite(nom)
    prenom = _normaliser_identite(prenom)
    telephone = str(telephone or "").strip()
    if not nom or not prenom:
        return _result(False, "Le nom et le prénom du locataire sont obligatoires.")

    mois_date = parse_mois_saisie(mois)
    if not mois_date:
        return _result(False, "Format de date invalide. Utilisez AAAA-MM-JJ ou AAAA-MM.")

    # Si montant_paye n'est pas spécifié, on considère que c'est 0 (pas de paiement)
    if montant_paye is None:
        montant_paye = 0.0
    if avance is None:
        avance = 0.0
    if montant_paye in (None, ""):
        montant_paye = 0.0
    if avance in (None, ""):
        avance = 0.0

    montant_paye_val = float(montant_paye)
    avance_val = float(avance)
    montant_total = float(montant_souscrit)
    montant_paye_effectif = montant_paye_val + avance_val
    reste_a_payer = max(0, montant_total - montant_paye_effectif)

    # Déterminer le statut de paiement
    if montant_paye_effectif >= montant_total:
        statut_paiement = "Complet"
    elif montant_paye_effectif > 0:
        statut_paiement = "Partiel"
    else:
        statut_paiement = "En attente"

    # Le paiement partiel ou avance doit rester visible comme litigieux jusqu'au règlement total.
    if montant_paye_effectif >= montant_total:
        statut = "En règle"
    elif montant_paye_effectif > 0:
        statut = "Litigieux"
    else:
        statut = "En attente"

    try:
        conn = obtenir_connexion(connection_provider)
        if conn.is_connected():
            cursor = conn.cursor()

            # Recherche insensible à la casse et tolérante aux espaces.
            cursor.execute(
                "SELECT id, telephone FROM locataires "
                "WHERE LOWER(TRIM(nom)) = LOWER(TRIM(%s)) "
                "AND LOWER(TRIM(prenom)) = LOWER(TRIM(%s)) "
                "ORDER BY id ASC LIMIT 1",
                (nom, prenom),
            )
            result = cursor.fetchone()

            if result:
                locataire_id = result[0]
                # Si un téléphone est fourni et différent, on peut mettre à jour (optionnel)
                if telephone and telephone != result[1]:
                    # Créer un nouveau curseur pour l'UPDATE
                    update_cursor = conn.cursor()
                    update_cursor.execute(
                        "UPDATE locataires SET telephone = %s WHERE id = %s",
                        (telephone, locataire_id),
                    )
                    update_cursor.close()
            else:
                # Le téléphone est optionnel, peut être NULL
                telephone_value = telephone if telephone else None
                # Créer un nouveau curseur pour l'INSERT
                insert_cursor = conn.cursor()
                insert_cursor.execute(
                    "INSERT INTO locataires (nom, prenom, telephone) VALUES (%s, %s, %s)",
                    (nom, prenom, telephone_value),
                )
                locataire_id = insert_cursor.lastrowid
                insert_cursor.close()

            type_souscription = statut_souscription or "Simple"
            if type_souscription == "Spécial" and montant_paye_effectif > 0:
                allocations = _allouer_versement_special(
                    cursor,
                    locataire_id,
                    mois_date,
                    montant_total,
                    devise,
                    montant_paye_effectif,
                    creer_mois_cible=True,
                )
                conn.commit()
                details = {
                    "paiement_id": allocations[0]["id"] if allocations else None,
                    "locataire_id": locataire_id,
                    "montant_paye": float(montant_paye_effectif),
                    "allocation_speciale": True,
                }
                message = _message_allocation_special(allocations)
                return _result(True, message, details)

            # Insertion classique pour les souscriptions Simples ou sans versement.
            # Le montant payé stocké inclut aussi l'avance éventuelle.
            cursor.execute(
                "INSERT INTO paiements (locataire_id, mois, montant, montant_total, montant_paye, reste_a_payer, devise, statut, statut_souscription, statut_paiement) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    locataire_id,
                    mois_date,
                    montant_souscrit,
                    montant_souscrit,
                    montant_paye_effectif,
                    reste_a_payer,
                    devise,
                    statut or "En attente",
                    type_souscription,
                    statut_paiement,
                ),
            )
            paiement_id = cursor.lastrowid

            conn.commit()
            details = {
                "paiement_id": paiement_id,
                "locataire_id": locataire_id,
                "montant_paye": float(montant_paye_effectif),
                "allocation_speciale": False,
            }
            return _result(True, "Enregistrement réussi avec succès !", details)

    except (Error, ValueError) as e:
        if "conn" in locals() and conn.is_connected():
            conn.rollback()
        return _result(False, f"Erreur de base de données : {e}")
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def recuperer_inventaire(
    filtre_nom="",
    filtre_statut="Tous",
    connection_provider: ConnectionProvider | None = None,
):
    try:
        conn = obtenir_connexion(connection_provider)
        cursor = conn.cursor()

        query = (
            f"SELECT l.nom, l.prenom, l.telephone, p.montant, p.devise, {MOIS_SQL_EXPR} AS mois, p.statut "
            "FROM paiements p JOIN locataires l ON p.locataire_id = l.id WHERE 1=1"
        )
        params = []

        query, params = _append_filtre_nom(query, params, filtre_nom)

        if filtre_statut != "Tous":
            query += " AND p.statut = %s"
            params.append(filtre_statut)

        query += " ORDER BY p.id DESC"

        cursor.execute(query, params)
        return cursor.fetchall()

    except Error as e:
        print(f"Erreur lors de la récupération de l'inventaire : {e}")
        return []
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals() and conn.is_connected():
            conn.close()


def mettre_a_jour_statut(
    paiement_id,
    nouveau_statut,
    connection_provider: ConnectionProvider | None = None,
):
    try:
        conn = obtenir_connexion(connection_provider)
        cursor = conn.cursor()

        query = "UPDATE paiements SET statut = %s WHERE id = %s"
        cursor.execute(query, (nouveau_statut, paiement_id))
        conn.commit()
        if cursor.rowcount == 0:
            return False, "Aucune ligne n'a été mise à jour. Le paiement est peut-être introuvable."
        return True, "Statut mis à jour avec succès !"

    except Error as e:
        if "conn" in locals() and conn.is_connected():
            conn.rollback()
        return False, f"Erreur de mise à jour : {e}"
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def get_souscriptions(
    filtre_nom="",
    filtre_statut="Tous",
    filtre_devise="",
    filtre_mois="",
    filtre_statut_souscription="Tous",
    connection_provider: ConnectionProvider | None = None,
):
    """Fonction de compatibilité pour les appels existants."""
    return get_souscriptions_avec_filtres(
        filtre_nom=filtre_nom,
        filtre_statut=filtre_statut,
        filtre_devise=filtre_devise,
        filtre_mois=filtre_mois,
        filtre_statut_souscription=filtre_statut_souscription,
        date_debut="",
        date_fin="",
        connection_provider=connection_provider,
    )


def get_souscriptions_avec_filtres(
    filtre_nom="",
    filtre_statut="Tous",
    filtre_devise="",
    filtre_mois="",
    date_debut="",
    date_fin="",
    filtre_statut_souscription="Tous",
    connection_provider: ConnectionProvider | None = None,
):
    conn = None
    cursor = None
    try:
        conn = obtenir_connexion(connection_provider)
        if conn is None:
            return []

        cursor = conn.cursor()

        query = (
            f"SELECT p.id, l.id, l.nom, l.prenom, {MOIS_SQL_EXPR} AS mois, p.montant, p.devise, "
            "p.statut_souscription, p.statut, "
            "DATE_FORMAT(p.date_creation, '%Y-%m-%d') as date_creation, "
            "p.montant_total, p.montant_paye, p.reste_a_payer, p.statut_paiement, "
            "EXISTS(SELECT 1 FROM signatures_paiements sp WHERE sp.paiement_id = p.id) AS est_signe "
            "FROM paiements p "
            "JOIN locataires l ON p.locataire_id = l.id "
            "WHERE 1=1"
        )
        params = []

        query, params = _append_filtre_nom(query, params, filtre_nom)

        if filtre_statut != "Tous":
            query += " AND p.statut = %s"
            params.append(filtre_statut)

        query, params = _append_filtre_devise(query, params, filtre_devise)

        if filtre_mois:
            query, params = _append_filtre_mois(query, params, filtre_mois)

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
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        if conn is not None and hasattr(conn, "is_connected") and conn.is_connected():
            try:
                conn.close()
            except Exception:
                pass


def get_historique_locataire(
    locataire_id,
    connection_provider: ConnectionProvider | None = None,
):
    conn = obtenir_connexion(connection_provider)
    cursor = conn.cursor()
    try:
        query = (
            f"SELECT {MOIS_SQL_EXPR} AS mois, p.montant, p.devise, p.statut_souscription, p.statut, "
            "p.montant_total, p.montant_paye, p.reste_a_payer, p.statut_paiement "
            "FROM paiements p "
            "WHERE p.locataire_id = %s "
            "ORDER BY p.mois DESC, p.id DESC"
        )
        cursor.execute(query, (locataire_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def modifier_souscription(
    paiement_id,
    nom,
    prenom,
    telephone,
    mois,
    montant_souscrit,
    devise,
    statut="En attente",
    statut_souscription="Simple",
    montant_paye=None,
    avance=None,
    connection_provider: ConnectionProvider | None = None,
):
    """Modifie une souscription existante."""
    nom = _normaliser_identite(nom)
    prenom = _normaliser_identite(prenom)
    telephone = str(telephone or "").strip()
    if not nom or not prenom:
        return False, "Le nom et le prénom du locataire sont obligatoires."

    mois_date = parse_mois_saisie(mois)
    if not mois_date:
        return False, "Format de date invalide. Utilisez AAAA-MM-JJ ou AAAA-MM."

    try:
        conn = obtenir_connexion(connection_provider)
        if conn.is_connected():
            cursor = conn.cursor()

            # Récupérer le locataire_id actuel
            cursor.execute(
                "SELECT locataire_id FROM paiements WHERE id = %s",
                (paiement_id,),
            )
            result = cursor.fetchone()
            if not result:
                return False, "Paiement non trouvé."

            locataire_id = result[0]

            # Mettre à jour ou réutiliser le locataire (recherche insensible à la casse
            # et tolérante aux espaces) afin de ne jamais créer un doublon.
            # Créer un nouveau curseur pour cette requête
            locataire_cursor = conn.cursor()
            locataire_cursor.execute(
                "SELECT id, telephone FROM locataires "
                "WHERE LOWER(TRIM(nom)) = LOWER(TRIM(%s)) "
                "AND LOWER(TRIM(prenom)) = LOWER(TRIM(%s)) "
                "ORDER BY id ASC LIMIT 1",
                (nom, prenom),
            )
            locataire_result = locataire_cursor.fetchone()
            locataire_cursor.close()

            if locataire_result:
                new_locataire_id = locataire_result[0]
                # Si un téléphone est fourni et différent, on peut mettre à jour (optionnel)
                if telephone and telephone != locataire_result[1]:
                    # Créer un nouveau curseur pour l'UPDATE
                    update_cursor = conn.cursor()
                    update_cursor.execute(
                        "UPDATE locataires SET telephone = %s WHERE id = %s",
                        (telephone, new_locataire_id),
                    )
                    update_cursor.close()
            else:
                # Le téléphone est optionnel, peut être NULL
                telephone_value = telephone if telephone else None
                # Créer un nouveau curseur pour l'INSERT
                insert_cursor = conn.cursor()
                insert_cursor.execute(
                    "INSERT INTO locataires (nom, prenom, telephone) VALUES (%s, %s, %s)",
                    (nom, prenom, telephone_value),
                )
                new_locataire_id = insert_cursor.lastrowid
                insert_cursor.close()

            if montant_paye is None:
                montant_paye = 0.0
            if avance is None:
                avance = 0.0
            if montant_paye in (None, ""):
                montant_paye = 0.0
            if avance in (None, ""):
                avance = 0.0

            montant_paye_val = float(montant_paye)
            avance_val = float(avance)
            montant_total = float(montant_souscrit)
            montant_paye_effectif = montant_paye_val + avance_val
            reste_a_payer = max(0, montant_total - montant_paye_effectif)

            if montant_paye_effectif >= montant_total:
                statut_paiement = "Complet"
            elif montant_paye_effectif > 0:
                statut_paiement = "Partiel"
            else:
                statut_paiement = "En attente"

            if montant_paye_effectif >= montant_total:
                statut = "En règle"
            elif montant_paye_effectif > 0:
                statut = "Litigieux"
            else:
                statut = "En attente"

            # Mettre à jour le paiement
            cursor.execute(
                "UPDATE paiements SET locataire_id = %s, mois = %s, montant = %s, montant_total = %s, montant_paye = %s, reste_a_payer = %s, devise = %s, statut = %s, statut_souscription = %s, statut_paiement = %s WHERE id = %s",
                (
                    new_locataire_id,
                    mois_date,
                    montant_souscrit,
                    montant_souscrit,
                    montant_paye_effectif,
                    reste_a_payer,
                    devise,
                    statut or "En attente",
                    statut_souscription or "Simple",
                    statut_paiement,
                    paiement_id,
                ),
            )

            conn.commit()
            return True, "Modification réussie avec succès !"

    except Error as e:
        if "conn" in locals() and conn.is_connected():
            conn.rollback()
        return False, f"Erreur de base de données : {e}"
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def supprimer_souscription(
    paiement_id,
    connection_provider: ConnectionProvider | None = None,
):
    """Supprime une souscription."""
    try:
        conn = obtenir_connexion(connection_provider)
        if conn.is_connected():
            cursor = conn.cursor()

            # Vérifier si le paiement existe
            cursor.execute(
                "SELECT id FROM paiements WHERE id = %s",
                (paiement_id,),
            )
            if not cursor.fetchone():
                return False, f"Paiement avec ID {paiement_id} introuvable."

            # Supprimer le paiement
            cursor.execute(
                "DELETE FROM paiements WHERE id = %s",
                (paiement_id,),
            )

            affected_rows = cursor.rowcount
            conn.commit()

            if affected_rows > 0:
                return True, "Suppression réussie avec succès !"
            else:
                return False, "Aucune ligne supprimée. Le paiement n'existe peut-être pas."

    except Error as e:
        if "conn" in locals() and conn.is_connected():
            conn.rollback()
        return False, f"Erreur de base de données : {e}"
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def ajouter_paiement_complementaire(
    paiement_id,
    montant_additionnel,
    connection_provider: ConnectionProvider | None = None,
):
    """Ajoute un paiement complémentaire à un paiement existant."""
    try:
        conn = obtenir_connexion(connection_provider)
        if conn.is_connected():
            cursor = conn.cursor()

            # Récupérer les informations actuelles
            cursor.execute(
                "SELECT locataire_id, mois, statut_souscription, devise, montant_total, montant_paye "
                "FROM paiements WHERE id = %s FOR UPDATE",
                (paiement_id,),
            )
            result = cursor.fetchone()
            if not result:
                return False, "Paiement non trouvé."

            locataire_id, mois, statut_souscription, devise, montant_total, montant_paye_actuel = result

            if statut_souscription == "Spécial":
                allocations = _allouer_versement_special(
                    cursor,
                    locataire_id,
                    mois,
                    montant_total,
                    devise,
                    montant_additionnel,
                    creer_mois_cible=False,
                )
                conn.commit()
                return True, _message_allocation_special(allocations)

            # Calculer le nouveau montant payé
            nouveau_montant_paye = float(montant_paye_actuel) + float(montant_additionnel)

            # Calculer le nouveau reste à payer
            nouveau_reste = max(0, float(montant_total) - nouveau_montant_paye)

            # Déterminer le nouveau statut de paiement
            if nouveau_montant_paye >= float(montant_total):
                nouveau_statut_paiement = "Complet"
            elif nouveau_montant_paye > 0:
                nouveau_statut_paiement = "Partiel"
            else:
                nouveau_statut_paiement = "En attente"

            # Déterminer le statut automatiquement selon le montant payé
            if nouveau_montant_paye <= 0:
                nouveau_statut = "En attente"
            elif nouveau_montant_paye < float(montant_total):
                nouveau_statut = "Litigieux"
            else:
                nouveau_statut = "En règle"

            # Mettre à jour le paiement
            cursor.execute(
                "UPDATE paiements SET montant_paye = %s, reste_a_payer = %s, statut_paiement = %s, statut = %s WHERE id = %s",
                (nouveau_montant_paye, nouveau_reste, nouveau_statut_paiement, nouveau_statut, paiement_id),
            )

            conn.commit()
            return True, f"Paiement complémentaire de {montant_additionnel} ajouté avec succès ! Nouveau montant payé : {nouveau_montant_paye}"

    except (Error, ValueError) as e:
        if "conn" in locals() and conn.is_connected():
            conn.rollback()
        return False, f"Erreur de base de données : {e}"
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


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
            "DATE_FORMAT(p.date_creation, '%Y-%m-%d') as date_creation, "
            "p.montant_total, p.montant_paye, p.reste_a_payer, p.statut_paiement "
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


def update_payment_details_after_signature(
    paiement_id: int,
    montant_paye_signature: Decimal,
    montant_total: Decimal,
    devise: str,
    connection_provider: ConnectionProvider | None = None,
) -> tuple[bool, str]:
    """
    Met à jour les détails d'un paiement après une signature.
    Prend en compte le montant payé via la signature et met à jour le statut.
    """
    try:
        conn = obtenir_connexion(connection_provider)
        cursor = conn.cursor()

        # Récupérer le montant_paye actuel pour ce paiement
        cursor.execute(
            "SELECT montant_paye FROM paiements WHERE id = %s FOR UPDATE",
            (paiement_id,),
        )
        current_paid_amount_row = cursor.fetchone()
        if not current_paid_amount_row:
            return False, "Paiement introuvable."

        current_paid_amount = _decimal_amount(current_paid_amount_row[0])
        
        # Le montant payé total est le montant déjà payé plus le montant de la signature
        new_total_paid_amount = current_paid_amount + montant_paye_signature

        # Calculer les nouveaux statuts et reste à payer
        statut, statut_paiement, reste_a_payer = _statuts_montant(
            montant_total, new_total_paid_amount
        )

        cursor.execute(
            """
                UPDATE paiements
                SET montant_paye = %s,
                    reste_a_payer = %s,
                    statut = %s,
                    statut_paiement = %s
                WHERE id = %s
            """,
            (
                float(new_total_paid_amount),
                float(reste_a_payer),
                statut,
                statut_paiement,
                paiement_id,
            ),
        )
        conn.commit()
        return True, "Paiement mis à jour avec succès après signature."

    except (Error, ValueError) as e:
        if "conn" in locals() and conn.is_connected():
            conn.rollback()
        return False, f"Erreur de base de données lors de la mise à jour du paiement: {e}"
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()
