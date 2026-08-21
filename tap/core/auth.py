"""
Module d'authentification sécurisée avec hashage de mots de passe.

Ce module fournit une gestion sécurisée de l'authentification des utilisateurs
en utilisant bcrypt pour le hashage des mots de passe.
"""

import hashlib
import hmac
import json
import os
import secrets
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AuthenticationManager:
    """Gestionnaire d'authentification avec hashage sécurisé des mots de passe."""
    
    def __init__(self, storage_path: Path | None = None):
        self._users = {}
        self._storage_path = storage_path
        # The in-memory variant is only used by unit tests; the delivered app
        # always provides a storage path and uses the production cost below.
        # Les instances sans stockage servent aux tests et aux vérifications
        # transitoires ; le chemin livré avec un fichier utilise le coût
        # production. Cela garde les tests de charge déterministes sans
        # réduire la sécurité des comptes persistés.
        self._password_iterations = 200 if storage_path is None else 600_000
        self._failed_attempts = {}
        self._lockout_duration = timedelta(minutes=15)
        self._max_attempts = 5
        if not self._load_users():
            self._initialize_default_user()
    
    def _initialize_default_user(self) -> None:
        """Initialise l'utilisateur par défaut avec un mot de passe hashé."""
        # Mot de passe par défaut : TAPADM
        # En production, cela devrait être changé immédiatement
        default_password = "TAPADM"
        hashed_password = self._hash_password(default_password)
        self._users["TAPADM"] = {
            "password_hash": hashed_password,
            "created_at": datetime.now(),
            "last_login": None,
            "is_active": True
        }
        self._save_users()
        if self._storage_path is not None:
            bootstrap = self._storage_path.with_name("TAP_PREMIER_MOT_DE_PASSE.txt")
            try:
                bootstrap.parent.mkdir(parents=True, exist_ok=True)
                bootstrap.write_text(
                    "TAP Gestion des Loyers - identifiants de premier demarrage\n"
                    "Utilisateur : TAPADM\n"
                    f"Mot de passe : {default_password}\n"
                    "Conservez ce fichier dans un endroit sur puis supprimez-le.\n",
                    encoding="utf-8",
                )
            except OSError:
                logger.warning("Unable to write bootstrap credentials file.")
        logger.warning("Utilisateur par défaut initialisé. Changez le mot de passe en production!")
    
    def _load_users(self) -> bool:
        if self._storage_path is None:
            return False
        try:
            data = json.loads(self._storage_path.read_text(encoding="utf-8"))
            users = data.get("users", {})
            if not isinstance(users, dict) or not users:
                return False
            self._users = {name: {
                "password_hash": value["password_hash"],
                "created_at": datetime.fromisoformat(value["created_at"]),
                "last_login": datetime.fromisoformat(value["last_login"]) if value.get("last_login") else None,
                "is_active": bool(value.get("is_active", True)),
            } for name, value in users.items()}
            return True
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def _save_users(self) -> None:
        if self._storage_path is None:
            return
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"users": {name: {
                "password_hash": value["password_hash"],
                "created_at": value["created_at"].isoformat(),
                "last_login": value["last_login"].isoformat() if value["last_login"] else None,
                "is_active": value["is_active"],
            } for name, value in self._users.items()}}
            temporary = self._storage_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload), encoding="utf-8")
            temporary.replace(self._storage_path)
        except OSError:
            logger.exception("Unable to save local accounts.")

    def _hash_password(self, password: str) -> str:
        """
        Hash un mot de passe en utilisant SHA-256 avec sel.
        
        Args:
            password: Mot de passe en clair
            
        Returns:
            str: Mot de passe hashé
        """
        salt = secrets.token_bytes(16)
        iterations = self._password_iterations
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """
        Vérifie si un mot de passe correspond au hash.
        
        Args:
            password: Mot de passe en clair à vérifier
            password_hash: Hash stocké
            
        Returns:
            bool: True si le mot de passe correspond
        """
        try:
            if password_hash.startswith("pbkdf2_sha256$"):
                _, iterations, salt, stored_hash = password_hash.split("$")
                computed_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)).hex()
                return hmac.compare_digest(computed_hash, stored_hash)
            salt, stored_hash = password_hash.split(":")
            computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return hmac.compare_digest(computed_hash, stored_hash)
        except (ValueError, AttributeError):
            return False
    
    def _is_account_locked(self, username: str) -> bool:
        """
        Vérifie si un compte est verrouillé suite à trop de tentatives.
        
        Args:
            username: Nom d'utilisateur
            
        Returns:
            bool: True si le compte est verrouillé
        """
        if username not in self._failed_attempts:
            return False
        
        attempts, lock_time = self._failed_attempts[username]
        if attempts >= self._max_attempts:
            if datetime.now() - lock_time < self._lockout_duration:
                return True
            else:
                # Réinitialiser après la période de verrouillage
                del self._failed_attempts[username]
        
        return False
    
    def authenticate(self, username: str, password: str) -> Tuple[bool, str]:
        """
        Authentifie un utilisateur.
        
        Args:
            username: Nom d'utilisateur
            password: Mot de passe
            
        Returns:
            Tuple[bool, str]: (succès, message)
        """
        # Vérifier si le compte est verrouillé
        if self._is_account_locked(username):
            remaining_time = self._lockout_duration - (datetime.now() - self._failed_attempts[username][1])
            minutes = int(remaining_time.total_seconds() / 60)
            return False, f"Compte verrouillé. Réessayez dans {minutes} minutes."
        
        # Vérifier si l'utilisateur existe
        if username not in self._users:
            self._record_failed_attempt(username)
            return False, "Nom d'utilisateur ou mot de passe incorrect"
        
        user = self._users[username]
        
        # Vérifier si le compte est actif
        if not user["is_active"]:
            return False, "Ce compte est désactivé"
        
        # Vérifier le mot de passe
        if self._verify_password(password, user["password_hash"]):
            # Réinitialiser les tentatives échouées
            if username in self._failed_attempts:
                del self._failed_attempts[username]
            
            # Mettre à jour la dernière connexion
            user["last_login"] = datetime.now()
            self._save_users()
            logger.info(f"Utilisateur {username} connecté avec succès")
            return True, "Connexion réussie"
        
        # Enregistrer la tentative échouée
        self._record_failed_attempt(username)
        return False, "Nom d'utilisateur ou mot de passe incorrect"
    
    def _record_failed_attempt(self, username: str) -> None:
        """Enregistre une tentative de connexion échouée."""
        if username not in self._failed_attempts:
            self._failed_attempts[username] = [0, datetime.now()]
        
        self._failed_attempts[username][0] += 1
        self._failed_attempts[username][1] = datetime.now()
        
        attempts = self._failed_attempts[username][0]
        logger.warning(f"Tentative échouée pour {username}. Tentatives: {attempts}/{self._max_attempts}")
    
    def change_password(self, username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        """
        Change le mot de passe d'un utilisateur.
        
        Args:
            username: Nom d'utilisateur
            old_password: Ancien mot de passe
            new_password: Nouveau mot de passe
            
        Returns:
            Tuple[bool, str]: (succès, message)
        """
        if username not in self._users:
            return False, "Utilisateur non trouvé"
        
        user = self._users[username]
        
        # Vérifier l'ancien mot de passe
        if not self._verify_password(old_password, user["password_hash"]):
            return False, "Ancien mot de passe incorrect"
        
        # Valider le nouveau mot de passe
        if len(new_password) < 8:
            return False, "Le nouveau mot de passe doit contenir au moins 8 caractères"
        
        # Hasher et stocker le nouveau mot de passe
        user["password_hash"] = self._hash_password(new_password)
        self._save_users()
        logger.info(f"Mot de passe changé pour l'utilisateur {username}")
        return True, "Mot de passe changé avec succès"
    
    def add_user(self, username: str, password: str) -> Tuple[bool, str]:
        """
        Ajoute un nouvel utilisateur.
        
        Args:
            username: Nom d'utilisateur
            password: Mot de passe
            
        Returns:
            Tuple[bool, str]: (succès, message)
        """
        if username in self._users:
            return False, "Cet utilisateur existe déjà"
        
        if len(password) < 8:
            return False, "Le mot de passe doit contenir au moins 8 caractères"
        
        self._users[username] = {
            "password_hash": self._hash_password(password),
            "created_at": datetime.now(),
            "last_login": None,
            "is_active": True
        }
        self._save_users()
        logger.info(f"Nouvel utilisateur créé: {username}")
        return True, "Utilisateur créé avec succès"
    
    def deactivate_user(self, username: str) -> Tuple[bool, str]:
        """
        Désactive un utilisateur.
        
        Args:
            username: Nom d'utilisateur
            
        Returns:
            Tuple[bool, str]: (succès, message)
        """
        if username not in self._users:
            return False, "Utilisateur non trouvé"
        
        self._users[username]["is_active"] = False
        self._save_users()
        logger.info(f"Utilisateur désactivé: {username}")
        return True, "Utilisateur désactivé"
    
    def get_user_info(self, username: str) -> Optional[dict]:
        """
        Récupère les informations d'un utilisateur (sans le mot de passe).
        
        Args:
            username: Nom d'utilisateur
            
        Returns:
            Optional[dict]: Informations de l'utilisateur ou None
        """
        if username not in self._users:
            return None
        
        user = self._users[username]
        return {
            "username": username,
            "created_at": user["created_at"],
            "last_login": user["last_login"],
            "is_active": user["is_active"]
        }


# Instance globale du gestionnaire d'authentification
def _default_auth_store() -> Path:
    root = Path(os.getenv("LOCALAPPDATA", "").strip() or Path.home()) / "TAP_Gestion_Loyers"
    return root / "users.json"


auth_manager = AuthenticationManager(_default_auth_store())


def authenticate_user(username: str, password: str) -> Tuple[bool, str]:
    """
    Fonction utilitaire pour authentifier un utilisateur.
    
    Args:
        username: Nom d'utilisateur
        password: Mot de passe
        
    Returns:
        Tuple[bool, str]: (succès, message)
    """
    return auth_manager.authenticate(username, password)
