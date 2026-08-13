from datetime import date

from tap.core.auto_status_updater import _basculer_paiements_anterieurs_en_litigieux


class FakeCursor:
    def __init__(self, rowcount=0):
        self.rowcount = rowcount
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, list(params or [])))


def test_bascule_anterieure_en_litigieux_ne_touche_pas_le_mois_courant():
    cursor = FakeCursor(rowcount=3)

    count = _basculer_paiements_anterieurs_en_litigieux(cursor, date(2026, 9, 1))

    assert count == 3
    assert len(cursor.executed) == 1
    query, params = cursor.executed[0]
    assert "mois < %s" in query
    assert "statut = 'En attente'" in query
    assert params == [date(2026, 9, 1)]
