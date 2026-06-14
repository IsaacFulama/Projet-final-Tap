"""
Tests de performance pour TAP Gestion des Loyers
Mesure les temps de réponse et l'utilisation des ressources
"""

import time
import tracemalloc
from tap.core.validators import validate_name, validate_phone, validate_amount
from tap.core.auth import AuthenticationManager


class TestPerformanceValidation:
    """Tests de performance des validateurs"""
    
    def test_validate_name_performance(self):
        """Test la performance de validation de nom"""
        tracemalloc.start()
        start_time = time.time()
        
        # 1000 validations de nom
        for i in range(1000):
            _ = validate_name("Jean Dupont")
        
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Le temps total doit être inférieur à 1 seconde
        assert end_time - start_time < 1.0, f"Validation trop lente: {end_time - start_time}s"
        
        # L'utilisation mémoire doit être raisonnable (< 1 Mo)
        assert peak < 1_000_000, f"Utilisation mémoire trop élevée: {peak / 1_000_000} Mo"
    
    def test_validate_phone_performance(self):
        """Test la performance de validation de téléphone"""
        tracemalloc.start()
        start_time = time.time()
        
        # 1000 validations de téléphone
        for i in range(1000):
            _ = validate_phone("+243 123 456 789")
        
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        assert end_time - start_time < 1.0, f"Validation trop lente: {end_time - start_time}s"
        assert peak < 1_000_000, f"Utilisation mémoire trop élevée: {peak / 1_000_000} Mo"
    
    def test_validate_amount_performance(self):
        """Test la performance de validation de montant"""
        tracemalloc.start()
        start_time = time.time()
        
        # 1000 validations de montant
        for i in range(1000):
            _ = validate_amount("1000.50")
        
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        assert end_time - start_time < 1.0, f"Validation trop lente: {end_time - start_time}s"
        assert peak < 1_000_000, f"Utilisation mémoire trop élevée: {peak / 1_000_000} Mo"


class TestPerformanceAuth:
    """Tests de performance de l'authentification"""
    
    def test_password_hashing_performance(self):
        """Test la performance du hashage de mot de passe"""
        auth = AuthenticationManager()
        tracemalloc.start()
        start_time = time.time()
        
        # 100 hashages de mot de passe (méthode privée)
        for i in range(100):
            auth._hash_password("test_password_123")
        
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Le hashage peut être plus lent, mais doit rester raisonnable
        assert end_time - start_time < 5.0, f"Hashage trop lent: {end_time - start_time}s"
        assert peak < 5_000_000, f"Utilisation mémoire trop élevée: {peak / 1_000_000} Mo"
    
    def test_password_verification_performance(self):
        """Test la performance de la vérification de mot de passe"""
        auth = AuthenticationManager()
        password = "test_password_123"
        hashed = auth._hash_password(password)
        
        tracemalloc.start()
        start_time = time.time()
        
        # 1000 vérifications (méthode privée)
        for i in range(1000):
            auth._verify_password(password, hashed)
        
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        assert end_time - start_time < 1.0, f"Vérification trop lente: {end_time - start_time}s"
        assert peak < 1_000_000, f"Utilisation mémoire trop élevée: {peak / 1_000_000} Mo"


class TestMemoryLeaks:
    """Tests de fuites mémoire"""
    
    def test_no_memory_leak_validation(self):
        """Vérifie qu'il n'y a pas de fuite mémoire dans les validateurs"""
        tracemalloc.start()
        
        # Snapshot initial
        snapshot1 = tracemalloc.take_snapshot()
        
        # Effectuer beaucoup d'opérations
        for i in range(10000):
            validate_name("Test User")
            validate_phone("+243 123 456 789")
            validate_amount("1000.50")
        
        # Snapshot final
        snapshot2 = tracemalloc.take_snapshot()
        
        # Comparer les snapshots
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        
        # Vérifier que la croissance mémoire est raisonnable (< 100 Ko)
        total_increase = sum(stat.size_diff for stat in top_stats)
        assert total_increase < 100_000, f"Fuite mémoire détectée: {total_increase / 1_000_000} Mo"
        
        tracemalloc.stop()


class TestConcurrency:
    """Tests de concurrence"""
    
    def test_concurrent_validation(self):
        """Test la validation en concurrence"""
        import threading
        
        results = []
        errors = []
        
        def validate_worker():
            try:
                for i in range(100):
                    validate_name("Jean Dupont")
                    validate_phone(f"+243 {i:03d} {i:03d} {i:04d}")
                    validate_amount(str((i + 1) * 100.50))
                results.append(True)
            except Exception as e:
                errors.append(e)
        
        # Créer 10 threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=validate_worker)
            threads.append(thread)
            thread.start()
        
        # Attendre que tous les threads terminent
        for thread in threads:
            thread.join()
        
        # Vérifier qu'il n'y a pas d'erreurs
        assert len(errors) == 0, f"Erreurs en concurrence: {errors}"
        assert len(results) == 10, "Tous les threads n'ont pas terminé"


class TestDatabasePerformance:
    """Tests de performance de base de données (simulés)"""
    
    def test_query_performance_simulation(self):
        """Simulation de performance des requêtes base de données"""
        # Note: Ce test simule les performances car nous ne pouvons pas
        # tester avec une vraie base de données dans l'environnement de test
        
        start_time = time.time()
        
        # Simuler 100 opérations de base de données
        for i in range(100):
            # Simulation d'une requête
            time.sleep(0.001)  # 1ms par requête
        
        end_time = time.time()
        
        # 100 requêtes à 1ms = 100ms total
        assert end_time - start_time < 0.2, f"Requêtes trop lentes: {end_time - start_time}s"
