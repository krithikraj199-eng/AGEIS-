"""Persistent institutional memory backed by the Python standard-library SQLite."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


class MemoryBank:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS episodic_memory (
                    incident_id TEXT PRIMARY KEY,
                    root_cause TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    action_taken TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    affected_assets TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS procedural_memory (
                    pattern TEXT NOT NULL,
                    action TEXT NOT NULL,
                    total_uses INTEGER NOT NULL DEFAULT 0,
                    successes INTEGER NOT NULL DEFAULT 0,
                    avg_recovery_seconds REAL NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (pattern, action)
                );
                """
            )

    def remember(
        self,
        *,
        incident_id: str,
        root_cause: str,
        pattern: str,
        action: str,
        outcome: str,
        severity: str,
        affected_assets: List[str],
        duration_seconds: float,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT OR REPLACE INTO episodic_memory
                (incident_id, root_cause, pattern, action_taken, outcome, severity,
                 affected_assets, duration_seconds, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    incident_id,
                    root_cause,
                    pattern,
                    action,
                    outcome,
                    severity,
                    json.dumps(affected_assets),
                    duration_seconds,
                    now,
                ),
            )
            current = self._connection.execute(
                "SELECT total_uses, successes, avg_recovery_seconds FROM procedural_memory WHERE pattern=? AND action=?",
                (pattern, action),
            ).fetchone()
            uses = (current["total_uses"] if current else 0) + 1
            successes = (current["successes"] if current else 0) + (1 if outcome == "success" else 0)
            previous_avg = current["avg_recovery_seconds"] if current else 0.0
            average = ((previous_avg * (uses - 1)) + duration_seconds) / uses
            self._connection.execute(
                """INSERT OR REPLACE INTO procedural_memory
                (pattern, action, total_uses, successes, avg_recovery_seconds, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (pattern, action, uses, successes, average, now),
            )

    def recommendation(self, pattern: str) -> Dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                """SELECT pattern, action, total_uses, successes, avg_recovery_seconds
                FROM procedural_memory WHERE pattern=?
                ORDER BY (1.0 * successes / MAX(total_uses, 1)) DESC, total_uses DESC LIMIT 1""",
                (pattern,),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["success_rate"] = round(result["successes"] / max(result["total_uses"], 1), 3)
        return result

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM episodic_memory ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 500)),)
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["affected_assets"] = json.loads(item["affected_assets"])
            results.append(item)
        return results

    def procedures(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM procedural_memory ORDER BY updated_at DESC LIMIT ?", (max(1, min(limit, 500)),)
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["success_rate"] = round(item["successes"] / max(item["total_uses"], 1), 3)
            results.append(item)
        return results

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            episodes = self._connection.execute("SELECT COUNT(*) FROM episodic_memory").fetchone()[0]
            procedures = self._connection.execute("SELECT COUNT(*) FROM procedural_memory").fetchone()[0]
        return {"episodic": episodes, "procedural": procedures, "semantic": procedures}

    def close(self) -> None:
        with self._lock:
            self._connection.close()

