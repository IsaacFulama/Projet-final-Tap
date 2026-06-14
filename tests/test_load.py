"""
Tests de charge pour TAP Gestion des Loyers
Simule des charges élevées pour vérifier la stabilité
"""

import time
import threading
import pytest
from tap.core.validators import validate_name, validate_phone, validate_amount
from tap.core.auth import AuthenticationManager


class TestLoadValidation:
    """Tests de charge des validateurs"""
    
    def test_mass_validation_load(self):
        """Test de validation massive (10 000 opérations)"""
        start_time = time.time()
        
        # 10 000 validations
        for i in range(10000):
            validate_name("Jean Dupont")
            validate_phone(f"+243 123 456 789")
            validate_amount(str((i + 1) * 100.50))
        
        end_time = time.time()
        
        # Doit terminer en moins de 10 secondes
        assert end_time - start_time < 10.0, f"Charge trop lente: {end_time - start_time}s"
    
    def test_concurrent_users_simulation(self):
        """Simule 50 utilisateurs simultanés"""
        results = []
        errors = []
        
        def user_simulation(user_id):
            """Simule un utilisateur effectuant des opérations"""
            try:
                for i in range(100):
                    validate_name("Jean Dupont")
                    validate_phone(f"+243 123 456 789")
                    validate_amount(str((user_id + 1) * 100.50 + i))
                results.append(user_id)
            except Exception as e:
                errors.append((user_id, str(e)))
        
        start_time = time.time()
        
        # Créer 50 threads (utilisateurs simultanés)
        threads = []
        for user_id in range(50):
            thread = threading.Thread(target=user_simulation, args=(user_id,))
            threads.append(thread)
            thread.start()
        
        # Attendre que tous les threads terminent
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        # Vérifier les résultats
        assert len(errors) == 0, f"Erreurs sous charge: {errors}"
        assert len(results) == 50, "Tous les utilisateurs n'ont pas terminé"
        
        # 50 utilisateurs × 100 opérations = 5000 opérations
        # Doit terminer en moins de 15 secondes
        assert end_time - start_time < 15.0, f"Charge trop lente: {end_time - start_time}s"


class TestLoadAuth:
    """Tests de charge de l'authentification"""
    
    def test_mass_authentication_load(self):
        """Test d'authentification massive"""
        auth = AuthenticationManager()
        
        start_time = time.time()
        
        # 1000 hashages de mots de passe (méthode privée)
        for i in range(1000):
            auth._hash_password(f"password_{i}")
        
        end_time = time.time()
        
        # Doit terminer en moins de 30 secondes (hashage est coûteux)
        assert end_time - start_time < 30.0, f"Charge d'authentification trop lente: {end_time - start_time}s"
    
    def test_concurrent_authentication(self):
        """Test d'authentification concurrente"""
        auth = AuthenticationManager()
        results = []
        errors = []
        
        def auth_simulation(user_id):
            """Simule un utilisateur s'authentifiant"""
            try:
                password = f"password_{user_id}"
                hashed = auth._hash_password(password)
                
                # 10 vérifications par utilisateur (méthode privée)
                for i in range(10):
                    auth._verify_password(password, hashed)
                
                results.append(user_id)
            except Exception as e:
                errors.append((user_id, str(e)))
        
        start_time = time.time()
        
        # 20 utilisateurs simultanés
        threads = []
        for user_id in range(20):
            thread = threading.Thread(target=auth_simulation, args=(user_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        assert len(errors) == 0, f"Erreurs sous charge: {errors}"
        assert len(results) == 20, "Tous les utilisateurs n'ont pas terminé"
        assert end_time - start_time < 20.0, f"Charge d'authentification trop lente: {end_time - start_time}s"


class TestStressTests:
    """Tests de stress extrêmes"""
    
    def test_extreme_validation_stress(self):
        """Test de stress extrême (100 000 opérations)"""
        start_time = time.time()
        
        # 100 000 validations (stress test)
        for i in range(100000):
            validate_name("Jean Dupont")
        
        end_time = time.time()
        
        # Doit terminer en moins de 60 secondes
        assert end_time - start_time < 60.0, f"Stress test trop lent: {end_time - start_time}s"
    
    def test_rapid_operations(self):
        """Test d'opérations très rapides"""
        start_time = time.time()
        
        # 1000 opérations en succession rapide
        for i in range(1000):
            validate_name("Test User")
            validate_phone("+243 123 456 789")
            validate_amount("1000.50")
        
        end_time = time.time()
        
        # Doit être très rapide (< 2 secondes)
        assert end_time - start_time < 2.0, f"Opérations trop lentes: {end_time - start_time}s"


class TestResourceLimits:
    """Tests des limites de ressources"""
    
    def test_memory_stability(self):
        """Test la stabilité mémoire sous charge"""
        import tracemalloc
        
        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()
        
        # Effectuer beaucoup d'opérations
        for i in range(50000):
            validate_name("Jean Dupont")
            validate_phone("+243 123 456 789")
        
        snapshot2 = tracemalloc.take_snapshot()
        
        # Comparer les snapshots
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        total_increase = sum(stat.size_diff for stat in top_stats)
        
        # La croissance mémoire doit être raisonnable (< 5 Mo)
        assert total_increase < 5_000_000, f"Instabilité mémoire: {total_increase / 1_000_000} Mo"
        
        tracemalloc.stop()
    
    def test_cpu_efficiency(self):
        """Test l'efficacité CPU"""
        try:
            import psutil
            import os
        except ImportError:
            pytest.skip("psutil non installé")
        
        process = psutil.Process(os.getpid())
        
        # Effectuer des opérations
        for i in range(1000):
            validate_name("Jean Dupont")
            validate_phone(f"+243 123 456 789")
            validate_amount("1000.50")
        
        # Mesurer l'utilisation CPU après
        cpu_after = process.cpu_percent(interval=0.1)
        
        # L'utilisation CPU ne doit pas être excessive (< 80%)
        assert cpu_after < 80.0, "Utilisation CPU excessive: {}%".format(cpu_after)
