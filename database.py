import mysql.connector
from mysql.connector import Error
from tkinter import messagebox
import json
import os
import sys
from pathlib import Path


DEFAULT_DB_CONFIG = {
    "host": "localhost",
    "database": "gestion_loyers",
    "user": "root",
    "password": "",
}


def _get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _load_db_config():
    search_paths = [
        _get_base_dir() / "config.json",
        Path(getattr(sys, "_MEIPASS", "")) / "config.json" if getattr(sys, "_MEIPASS", None) else None,
    ]

    for path in search_paths:
        if not path:
            continue
        try:
            if path.exists():
                with path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                db_data = data.get("database", {})
                return {
                    "host": db_data.get("host", DEFAULT_DB_CONFIG["host"]),
                    "database": db_data.get("database", DEFAULT_DB_CONFIG["database"]),
                    "user": db_data.get("user", DEFAULT_DB_CONFIG["user"]),
                    "password": db_data.get("password", DEFAULT_DB_CONFIG["password"]),
                }
        except Exception:
            continue

    return DEFAULT_DB_CONFIG.copy()

def obtenir_connexion():
    config = _load_db_config()
    return mysql.connector.connect(
        host=config["host"],
        database=config["database"],
        user=config["user"],
        password=config["password"]
    )

def inserer_souscription(nom, prenom, telephone, mois, montant, devise, statut='En attente'):
    try:
        conn = obtenir_connexion()
        if conn.is_connected():
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT id FROM locataires WHERE nom = %s AND prenom = %s AND telephone = %s',
                (nom, prenom, telephone)
            )
            result = cursor.fetchone()
            
            if result:
                locataire_id = result[0]
            else:
                cursor.execute('INSERT INTO locataires (nom, prenom, telephone) VALUES (%s, %s, %s)', (nom, prenom, telephone))
                locataire_id = cursor.lastrowid
            
            cursor.execute(
                'INSERT INTO paiements (locataire_id, mois, montant, devise, statut) VALUES (%s, %s, %s, %s, %s)',
                (locataire_id, mois, montant, devise, statut or 'En attente')
            )
            
            conn.commit()
            return True, 'Enregistrement réussi avec succès !'
            
    except Error as e:
        return False, f'Erreur de base de données : {e}'
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def recuperer_inventaire(filtre_nom='', filtre_statut='Tous'):
    try:
        conn = obtenir_connexion()
        cursor = conn.cursor()

        query = (
            'SELECT l.nom, l.prenom, l.telephone, p.montant, p.devise, p.mois, p.statut '
            'FROM paiements p JOIN locataires l ON p.locataire_id = l.id WHERE 1=1'
        )
        params = []

        if filtre_nom:
            query += ' AND (l.nom LIKE %s OR l.prenom LIKE %s)'
            params.append(f'%{filtre_nom}%')
            params.append(f'%{filtre_nom}%')

        if filtre_statut != 'Tous':
            query += ' AND p.statut = %s'
            params.append(filtre_statut)

        query += ' ORDER BY p.id DESC'
        cursor.execute(query, params)
        return cursor.fetchall()

    except Error as e:
        messagebox.showerror('Erreur', f'Impossible de charger les données : {e}')
        return []
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def get_souscriptions(filtre_nom='', filtre_statut='Tous', filtre_devise='Toutes', filtre_mois=''):
    try:
        conn = obtenir_connexion()
        cursor = conn.cursor()
        
        query = (
            'SELECT p.id, l.id, l.nom, l.prenom, p.mois, p.montant, p.devise, p.statut '
            'FROM paiements p JOIN locataires l ON p.locataire_id = l.id WHERE 1=1'
        )
        params = []
        
        if filtre_nom:
            query += ' AND (l.nom LIKE %s OR l.prenom LIKE %s)'
            params.append(f'%{filtre_nom}%')
            params.append(f'%{filtre_nom}%')
        
        if filtre_statut != 'Tous':
            query += ' AND p.statut = %s'
            params.append(filtre_statut)

        if filtre_devise != 'Toutes':
            query += ' AND UPPER(TRIM(p.devise)) = %s'
            params.append(filtre_devise.upper())

        if filtre_mois:
            query += ' AND p.mois LIKE %s'
            params.append(f'%{filtre_mois}%')

        cursor.execute(query, params)
        return cursor.fetchall()
        
    except Error as e:
        messagebox.showerror('Erreur', f'Impossible de charger les données : {e}')
        return []
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def mettre_a_jour_statut(paiement_id, nouveau_statut):
    try:
        conn = obtenir_connexion()
        cursor = conn.cursor()
        
        query = 'UPDATE paiements SET statut = %s WHERE id = %s'
        cursor.execute(query, (nouveau_statut, paiement_id))
        conn.commit()
        return True, 'Statut mis à jour avec succès !'
        
    except Error as e:
        return False, f'Erreur de mise à jour : {e}'
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def ajouter_colonne_date_creation():
    """Ajoute la colonne date_creation si elle n'existe pas"""
    try:
        conn = obtenir_connexion()
        if conn.is_connected():
            cursor = conn.cursor()
            
            # Vérifier si la colonne existe
            cursor.execute("SHOW COLUMNS FROM paiements LIKE 'date_creation'")
            if not cursor.fetchone():
                # Ajouter la colonne avec la date actuelle comme valeur par défaut
                cursor.execute("ALTER TABLE paiements ADD COLUMN date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                conn.commit()
                print("Colonne date_creation ajoutée avec succès")
            
            cursor.close()
            conn.close()
    except Error as e:
        print(f"Erreur lors de l'ajout de la colonne: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

# Appeler la fonction pour s'assurer que la colonne existe
ajouter_colonne_date_creation()

def get_souscriptions_avec_filtres(filtre_nom='', filtre_statut='Tous', date_debut='', date_fin=''):
    try:
        conn = obtenir_connexion()
        cursor = conn.cursor()
        
        query = (
            'SELECT p.id, l.id, l.nom, l.prenom, p.mois, p.montant, p.devise, p.statut, '
            "DATE_FORMAT(p.date_creation, '%Y-%m-%d') as date_creation "
            'FROM paiements p '
            'JOIN locataires l ON p.locataire_id = l.id '
            'WHERE 1=1'
        )
        params = []
        
        if filtre_nom:
            query += ' AND (l.nom LIKE %s OR l.prenom LIKE %s)'
            params.append(f'%{filtre_nom}%')
            params.append(f'%{filtre_nom}%')
        
        if filtre_statut != 'Tous':
            query += ' AND p.statut = %s'
            params.append(filtre_statut)
        
        if date_debut:
            query += ' AND DATE(p.date_creation) >= %s'
            params.append(date_debut)
        
        if date_fin:
            query += ' AND DATE(p.date_creation) <= %s'
            params.append(date_fin)
        
        cursor.execute(query, params)
        return cursor.fetchall()
        
    except Error as e:
        messagebox.showerror('Erreur', f'Impossible de charger les données : {e}')
        return []
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
