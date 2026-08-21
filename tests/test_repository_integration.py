from decimal import Decimal

from tap.infrastructure.database import repository
from tap.infrastructure.database import migrations


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, list(params or [])))

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class FakeConnection:
    def __init__(self, rows=None):
        self.cursor_instance = FakeCursor(rows)
        self.closed = False

    def is_connected(self):
        return True

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


def test_get_souscriptions_uses_injected_connection_provider(monkeypatch):
    fake_conn = FakeConnection(rows=[(1, 2, "KABONGO", "MARIE", "Janvier 2025", 100, "USD", "Spécial", "En règle", 100, 100, 0, "Complet")])

    def guarded_obtenir_connexion(provider=None):
        assert provider is not None, "Le provider doit être injecté"
        return provider()

    monkeypatch.setattr(repository, "obtenir_connexion", guarded_obtenir_connexion)

    result = repository.get_souscriptions(
        filtre_nom="Marie",
        filtre_statut="En règle",
        filtre_devise="usd",
        filtre_mois="Janvier 2025",
        filtre_statut_souscription="Spécial",
        connection_provider=lambda: fake_conn,
    )

    assert result == fake_conn.cursor_instance.rows
    assert fake_conn.closed is True


def test_get_souscriptions_ignores_toutes_devise(monkeypatch):
    fake_conn = FakeConnection(rows=[(1, 2, "KABONGO", "MARIE", "Janvier 2025", 100, "USD", "Spécial", "En règle", 100, 100, 0, "Complet")])
    monkeypatch.setattr(repository, "obtenir_connexion", lambda provider=None: fake_conn)

    result = repository.get_souscriptions(
        filtre_nom="Marie",
        filtre_statut="En règle",
        filtre_devise="Toutes",
        filtre_mois="Janvier 2025",
        filtre_statut_souscription="Spécial",
    )

    assert result == fake_conn.cursor_instance.rows
    _, params = fake_conn.cursor_instance.executed[0]
    assert "TOUTES" not in params


def test_get_souscriptions_combines_filters(monkeypatch):
    fake_conn = FakeConnection(rows=[(1, 2, "KABONGO", "MARIE", "Janvier 2025", 100, "USD", "Spécial", "En règle", 100, 100, 0, "Complet")])
    monkeypatch.setattr(repository, "obtenir_connexion", lambda provider=None: fake_conn)

    result = repository.get_souscriptions(
        filtre_nom="Marie",
        filtre_statut="En règle",
        filtre_devise="usd",
        filtre_mois="Janvier 2025",
        filtre_statut_souscription="Spécial",
    )

    assert result == fake_conn.cursor_instance.rows

    assert len(fake_conn.cursor_instance.executed) == 1
    query, params = fake_conn.cursor_instance.executed[0]

    assert "CONCAT(l.nom, ' ', l.prenom) LIKE %s" in query
    assert "YEAR(p.mois) = %s AND MONTH(p.mois) = %s" in query
    assert "p.statut_souscription = %s" in query
    assert params == ["%Marie%", "%Marie%", "%Marie%", "En règle", "USD", 2025, 1, "Spécial"]
    assert fake_conn.closed is True


def test_get_souscriptions_handles_missing_connection(monkeypatch):
    monkeypatch.setattr(repository, "obtenir_connexion", lambda provider=None: None)

    result = repository.get_souscriptions(filtre_nom="Marie")

    assert result == []


def test_get_historique_locataire_returns_rows_with_injected_connection():
    rows = [("08/2026", Decimal("120.00"), "USD", "Spécial", "Litigieux", Decimal("120.00"), Decimal("0"), Decimal("120.00"), "En attente")]
    fake_conn = FakeConnection(rows=rows)

    result = repository.get_historique_locataire(52, connection_provider=lambda: fake_conn)

    assert result == rows
    assert fake_conn.closed is True
    query, params = fake_conn.cursor_instance.executed[0]
    assert "p.locataire_id = %s" in query
    assert params == [52]


def test_history_model_is_safe_with_legacy_five_column_row():
    from tap.core.models import HistoryPayment

    history = HistoryPayment.from_row(("08/2026", Decimal("120"), "USD", "Simple", "En attente"))

    assert history.total_amount == Decimal("120")
    assert history.paid_amount == 0
    assert history.remaining_amount == 120
    assert history.payment_status == "En attente"


def test_initialiser_schema_si_absent_creates_missing_tables(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.executed = []

        def execute(self, query, params=None):
            self.executed.append((query, list(params or [])))

        def fetchone(self):
            return None

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()
            self.closed = False

        def is_connected(self):
            return True

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            pass

        def close(self):
            self.closed = True

    fake_conn = FakeConnection()
    monkeypatch.setattr(migrations, "obtenir_connexion", lambda: fake_conn)

    migrations.initialiser_schema_si_absent()

    executed_queries = [query for query, _ in fake_conn.cursor_instance.executed]
    assert any("CREATE TABLE IF NOT EXISTS locataires" in query for query in executed_queries)
    assert any("CREATE TABLE IF NOT EXISTS paiements" in query for query in executed_queries)


def test_inserer_souscription_marks_partial_advance_as_litigieux(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.executed = []
            self._rows = []
            self.lastrowid = 1

        def execute(self, query, params=None):
            self.executed.append((query, list(params or [])))
            if query.startswith("SELECT id, telephone"):
                self._rows = []
            elif query.startswith("INSERT INTO locataires"):
                self._rows = []
            elif query.startswith("INSERT INTO paiements"):
                self._rows = []

        def fetchone(self):
            return None

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def is_connected(self):
            return True

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            pass

        def close(self):
            pass

        def rollback(self):
            pass

    fake_conn = FakeConnection()
    monkeypatch.setattr(repository, "obtenir_connexion", lambda provider=None: fake_conn)

    success, message = repository.inserer_souscription(
        "Dupont",
        "Jean",
        "",
        "2026-07-01",
        "100",
        "CDF",
        montant_paye="40",
    )

    assert success is True
    assert message == "Enregistrement réussi avec succès !"
    inserted_query = next(query for query, _ in fake_conn.cursor_instance.executed if query.startswith("INSERT INTO paiements"))
    _, params = next((query, params) for query, params in fake_conn.cursor_instance.executed if query.startswith("INSERT INTO paiements"))
    assert params[7] == "Litigieux"


def test_repartir_versement_special_du_plus_ancien_au_plus_recent():
    allocations = repository._repartir_versement_fifo(
        [
            (10, "2026-06-01", "100", "0", "100"),
            (11, "2026-07-01", "100", "20", "80"),
        ],
        Decimal("150"),
    )

    assert [item["id"] for item in allocations] == [10, 11]
    assert [float(item["montant_affecte"]) for item in allocations] == [100.0, 50.0]
    assert allocations[0]["statut"] == "En règle"
    assert allocations[0]["statut_paiement"] == "Complet"
    assert allocations[1]["statut"] == "Litigieux"
    assert float(allocations[1]["reste_a_payer"]) == 30.0


def test_repartir_versement_special_refuse_un_montant_sans_mois_disponible():
    try:
        repository._repartir_versement_fifo(
            [(10, "2026-06-01", "100", "0", "100")],
            Decimal("150"),
        )
    except ValueError as exc:
        assert "mois Spéciaux impayés disponibles" in str(exc)
    else:
        raise AssertionError("Un versement supérieur aux dettes doit être refusé")


def test_restaurer_archive_refuses_to_overwrite_existing_active_payment(monkeypatch):
    class RestoreCursor:
        def __init__(self):
            self.executed = []
            self._fetchone_results = [(1,)]

        def execute(self, query, params=None):
            self.executed.append((query, list(params or [])))

        def fetchone(self):
            if self._fetchone_results:
                return self._fetchone_results.pop(0)
            return None

        def close(self):
            pass

    class RestoreConnection:
        def __init__(self):
            self.cursor_instance = RestoreCursor()
            self.closed = False

        def is_connected(self):
            return True

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            self.closed = True

    fake_conn = RestoreConnection()
    monkeypatch.setattr(repository, "obtenir_connexion", lambda provider=None: fake_conn)

    success, message = repository.restaurer_archive(12)

    assert success is False
    assert "existe déjà" in message
    assert len(fake_conn.cursor_instance.executed) == 1
    assert fake_conn.closed is True


def test_crud_survives_unavailable_database(monkeypatch):
    monkeypatch.setattr(repository, "obtenir_connexion", lambda provider=None: None)

    ok, message = repository.inserer_souscription(
        "Dupont", "Jean", "", "2026-07-01", "100", "CDF"
    )
    assert ok is False
    assert "n'est pas accessible" in message

    assert repository.recuperer_inventaire() == []
    assert repository.get_archives() == []
    assert repository.get_historique_locataire(1) == []

    ok, message = repository.modifier_souscription(
        1, "Dupont", "Jean", "", "2026-07-01", "100", "CDF"
    )
    assert ok is False
    assert "n'est pas accessible" in message

    ok, message = repository.supprimer_souscription(1)
    assert ok is False
    assert "n'est pas accessible" in message

    ok, message = repository.mettre_a_jour_statut(1, "Litigieux")
    assert ok is False
    assert "n'est pas accessible" in message

    ok, message = repository.ajouter_paiement_complementaire(1, "10")
    assert ok is False
    assert "n'est pas accessible" in message

    ok, message = repository.restaurer_archive(1)
    assert ok is False
    assert "n'est pas accessible" in message


def test_migrations_do_not_crash_without_database(monkeypatch):
    monkeypatch.setattr(migrations, "obtenir_connexion", lambda: None)
    migrations.run_migrations()
