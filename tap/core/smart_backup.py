"""
Module de sauvegarde et récupération automatique intelligent.

Ce module fournit:
- Sauvegardes automatiques avant modifications
- Récupération automatique en cas d'erreur
- Gestion intelligente de l'espace disque
- Restauration facile des données
"""

import logging
import os
import shutil
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import zipfile

from tap.infrastructure.database import obtenir_connexion

logger = logging.getLogger(__name__)


class SmartBackupManager:
    """Gestionnaire de sauvegarde automatique intelligente."""
    
    def __init__(self, backup_dir: str = "backups", max_backups: int = 10):
        """
        Initialise le gestionnaire de sauvegarde.
        
        Args:
            backup_dir: Répertoire de sauvegarde
            max_backups: Nombre maximum de sauvegardes à conserver
        """
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.backup_history = []
        
        # Créer le répertoire de sauvegarde
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Charger l'historique des sauvegardes
        self._load_backup_history()
    
    def _load_backup_history(self):
        """Charge l'historique des sauvegardes."""
        history_file = self.backup_dir / "backup_history.json"
        
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    self.backup_history = json.load(f)
            except Exception as e:
                logger.error(f"Erreur lors du chargement de l'historique: {e}")
                self.backup_history = []
    
    def _save_backup_history(self):
        """Sauvegarde l'historique des sauvegardes."""
        history_file = self.backup_dir / "backup_history.json"
        
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.backup_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'historique: {e}")
    
    def create_backup(self, reason: str = "manual", auto: bool = False) -> Dict[str, any]:
        """
        Crée une sauvegarde automatique.
        
        Args:
            reason: Raison de la sauvegarde
            auto: Si la sauvegarde est automatique
        
        Returns:
            Dict avec les informations de la sauvegarde
        """
        timestamp = datetime.now()
        backup_name = f"backup_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        backup_path = self.backup_dir / backup_name
        
        try:
            # Créer le répertoire de sauvegarde
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Sauvegarder la base de données
            db_backup = self._backup_database(backup_path)
            
            # Sauvegarder le config.json
            config_backup = self._backup_config(backup_path)
            
            # Créer un fichier metadata
            metadata = {
                "timestamp": timestamp.isoformat(),
                "reason": reason,
                "auto": auto,
                "database_backup": db_backup,
                "config_backup": config_backup,
                "size_mb": self._get_backup_size(backup_path),
            }
            
            metadata_file = backup_path / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            # Ajouter à l'historique
            backup_info = {
                "name": backup_name,
                "path": str(backup_path),
                "timestamp": timestamp.isoformat(),
                "reason": reason,
                "auto": auto,
                "size_mb": metadata["size_mb"],
            }
            
            self.backup_history.append(backup_info)
            self._save_backup_history()
            
            # Nettoyer les vieilles sauvegardes
            self._cleanup_old_backups()
            
            logger.info(f"Sauvegarde créée: {backup_name} ({metadata['size_mb']:.2f} MB)")
            
            return {
                "success": True,
                "backup_name": backup_name,
                "backup_path": str(backup_path),
                "size_mb": metadata["size_mb"],
                "timestamp": timestamp.isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Erreur lors de la création de la sauvegarde: {e}")
            
            # Nettoyer en cas d'erreur
            if backup_path.exists():
                shutil.rmtree(backup_path)
            
            return {
                "success": False,
                "error": str(e),
            }
    
    def _backup_database(self, backup_path: Path) -> Dict[str, any]:
        """Sauvegarde la base de données."""
        try:
            conn = obtenir_connexion()
            if not conn or not conn.is_connected():
                return {"success": False, "error": "Impossible de se connecter à la base de données"}
            
            # Utiliser mysqldump si disponible, sinon exporter les tables
            db_backup_file = backup_path / "database.sql"
            
            try:
                # Export SQL simple
                cursor = conn.cursor()
                
                # Obtenir la liste des tables
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                
                with open(db_backup_file, 'w', encoding='utf-8') as f:
                    for (table_name,) in tables:
                        f.write(f"-- Table: {table_name}\n")
                        f.write(f"DROP TABLE IF EXISTS `{table_name}`;\n")
                        
                        # Obtenir la structure
                        cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
                        create_stmt = cursor.fetchone()[1]
                        f.write(f"{create_stmt};\n\n")
                        
                        # Obtenir les données
                        cursor.execute(f"SELECT * FROM `{table_name}`")
                        columns = [desc[0] for desc in cursor.description]
                        
                        if cursor.rowcount > 0:
                            f.write(f"-- Data for {table_name}\n")
                            f.write(f"INSERT INTO `{table_name}` ({', '.join(columns)}) VALUES\n")
                            
                            rows = cursor.fetchall()
                            values = []
                            for row in rows:
                                row_values = []
                                for value in row:
                                    if value is None:
                                        row_values.append("NULL")
                                    elif isinstance(value, str):
                                        escaped_value = value.replace("'", "''")
                                        row_values.append(f"'{escaped_value}'")
                                    else:
                                        row_values.append(str(value))
                                values.append(f"({', '.join(row_values)})")
                            
                            f.write(',\n'.join(values))
                            f.write(";\n\n")
                
                cursor.close()
                
                return {
                    "success": True,
                    "file": str(db_backup_file),
                    "size_mb": db_backup_file.stat().st_size / (1024 * 1024),
                }
            
            except Exception as e:
                return {"success": False, "error": str(e)}
            
            finally:
                if conn and conn.is_connected():
                    conn.close()
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _backup_config(self, backup_path: Path) -> Dict[str, any]:
        """Sauvegarde le fichier de configuration."""
        try:
            config_file = Path("config.json")
            
            if config_file.exists():
                backup_config_file = backup_path / "config.json"
                shutil.copy2(config_file, backup_config_file)
                
                return {
                    "success": True,
                    "file": str(backup_config_file),
                    "size_mb": backup_config_file.stat().st_size / (1024 * 1024),
                }
            
            return {"success": False, "error": "Fichier config.json introuvable"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_backup_size(self, backup_path: Path) -> float:
        """Calcule la taille de la sauvegarde en MB."""
        total_size = 0
        
        for item in backup_path.rglob('*'):
            if item.is_file():
                total_size += item.stat().st_size
        
        return total_size / (1024 * 1024)
    
    def _cleanup_old_backups(self):
        """Supprime les vieilles sauvegardes."""
        # Trier par timestamp (plus récent en premier)
        sorted_backups = sorted(
            self.backup_history,
            key=lambda x: x["timestamp"],
            reverse=True
        )
        
        # Garder seulement les max_backups plus récentes
        if len(sorted_backups) > self.max_backups:
            backups_to_delete = sorted_backups[self.max_backups:]
            
            for backup in backups_to_delete:
                try:
                    backup_path = Path(backup["path"])
                    if backup_path.exists():
                        shutil.rmtree(backup_path)
                        logger.info(f"Sauvegarde supprimée: {backup['name']}")
                
                except Exception as e:
                    logger.error(f"Erreur lors de la suppression de {backup['name']}: {e}")
            
            # Mettre à jour l'historique
            self.backup_history = sorted_backups[:self.max_backups]
            self._save_backup_history()
    
    def restore_backup(self, backup_name: str) -> Dict[str, any]:
        """
        Restaure une sauvegarde.
        
        Args:
            backup_name: Nom de la sauvegarde à restaurer
        
        Returns:
            Dict avec le résultat de la restauration
        """
        # Trouver la sauvegarde
        backup_info = None
        for backup in self.backup_history:
            if backup["name"] == backup_name:
                backup_info = backup
                break
        
        if not backup_info:
            return {
                "success": False,
                "error": f"Sauvegarde {backup_name} introuvable"
            }
        
        backup_path = Path(backup_info["path"])
        
        if not backup_path.exists():
            return {
                "success": False,
                "error": f"Répertoire de sauvegarde introuvable: {backup_path}"
            }
        
        try:
            # Créer une sauvegarde avant restauration
            pre_restore_backup = self.create_backup(
                reason="pre_restore",
                auto=True
            )
            
            # Restaurer la base de données
            db_restore = self._restore_database(backup_path)
            
            # Restaurer la configuration
            config_restore = self._restore_config(backup_path)
            
            logger.info(f"Restauration terminée: {backup_name}")
            
            return {
                "success": True,
                "backup_name": backup_name,
                "database_restore": db_restore,
                "config_restore": config_restore,
                "pre_restore_backup": pre_restore_backup,
            }
        
        except Exception as e:
            logger.error(f"Erreur lors de la restauration: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def _restore_database(self, backup_path: Path) -> Dict[str, any]:
        """Restaure la base de données."""
        try:
            db_backup_file = backup_path / "database.sql"
            
            if not db_backup_file.exists():
                return {"success": False, "error": "Fichier de sauvegarde DB introuvable"}
            
            conn = obtenir_connexion()
            if not conn or not conn.is_connected():
                return {"success": False, "error": "Impossible de se connecter à la base de données"}
            
            cursor = conn.cursor()
            
            # Lire et exécuter le fichier SQL
            with open(db_backup_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
                
                # Exécuter les commandes SQL
                # Note: Ceci est une simplification, en production il faudrait
                # utiliser un parser SQL plus robuste
                statements = sql_content.split(';')
                
                for statement in statements:
                    statement = statement.strip()
                    if statement and not statement.startswith('--'):
                        try:
                            cursor.execute(statement)
                        except Exception as e:
                            logger.warning(f"Erreur lors de l'exécution: {e}")
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return {"success": True}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _restore_config(self, backup_path: Path) -> Dict[str, any]:
        """Restaure la configuration."""
        try:
            backup_config_file = backup_path / "config.json"
            
            if not backup_config_file.exists():
                return {"success": False, "error": "Fichier de sauvegarde config introuvable"}
            
            # Sauvegarder l'actuel config.json
            current_config = Path("config.json")
            if current_config.exists():
                shutil.copy2(current_config, Path("config.json.backup"))
            
            # Restaurer
            shutil.copy2(backup_config_file, current_config)
            
            return {"success": True}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_available_backups(self) -> List[Dict]:
        """Retourne la liste des sauvegardes disponibles."""
        return self.backup_history.copy()
    
    def auto_backup_before_change(self, change_type: str) -> Dict[str, any]:
        """
        Crée une sauvegarde automatique avant une modification.
        
        Args:
            change_type: Type de modification (ex: "delete", "update")
        
        Returns:
            Dict avec les informations de la sauvegarde
        """
        return self.create_backup(
            reason=f"auto_before_{change_type}",
            auto=True
        )


# Instance globale du gestionnaire de sauvegarde
smart_backup_manager = SmartBackupManager()
