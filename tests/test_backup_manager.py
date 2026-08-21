from datetime import datetime, timedelta
from pathlib import Path

from tap.core.backup_manager import backup_is_due, _rotation_backups


def test_biweekly_backup_schedule_is_due(tmp_path: Path):
    now = datetime(2026, 8, 21, 12, 0)
    assert backup_is_due(now=now, backup_dir=tmp_path, interval_days=14)

    (tmp_path / "backup_schedule.json").write_text(
        '{"last_success_at": "2026-08-10T12:00:00"}', encoding="utf-8"
    )
    assert not backup_is_due(now=now, backup_dir=tmp_path, interval_days=14)
    assert backup_is_due(
        now=now + timedelta(days=3), backup_dir=tmp_path, interval_days=14
    )


def test_backup_rotation_keeps_requested_number(tmp_path: Path):
    files = []
    for index in range(3):
        path = tmp_path / f"backup_gestion_loyers_{index}.zip"
        path.write_bytes(b"backup")
        files.append(path)

    _rotation_backups(tmp_path, "gestion_loyers", max_backups=2)

    assert len(list(tmp_path.glob("backup_gestion_loyers_*.zip"))) == 2
