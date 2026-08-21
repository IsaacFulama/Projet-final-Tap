"""Journal local et récupérable des opérations administratives."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _path() -> Path:
    root = Path(os.getenv("LOCALAPPDATA", "").strip() or Path.home()) / "TAP_Gestion_Loyers"
    root.mkdir(parents=True, exist_ok=True)
    return root / "audit.jsonl"


def record_audit(action: str, actor: str = "system", details: dict | None = None) -> None:
    """Ajoute une trace sans interrompre l'opération métier en cas d'erreur."""
    event = {"at": datetime.now(timezone.utc).isoformat(), "actor": actor, "action": action, "details": details or {}}
    try:
        with _path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_recent_audit(limit: int = 100) -> list[dict]:
    try:
        lines = _path().read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 1000)):]
        return [json.loads(line) for line in lines if line.strip()]
    except (OSError, ValueError):
        return []
