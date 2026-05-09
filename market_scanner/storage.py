"""SQLite and CSV logging for every generated signal."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Iterable

from .signals import Signal


SIGNAL_COLUMNS = [
    "symbol",
    "timestamp",
    "close",
    "previous_close",
    "pct_change",
    "volume",
    "avg_volume",
    "volume_multiple",
    "recent_high",
    "recent_low",
    "volatility",
    "avg_volatility",
    "volatility_multiple",
    "is_big_mover",
    "is_unusual_volume",
    "is_breakout",
    "is_pullback",
    "is_volatility_spike",
    "reasons",
    "score",
    "confidence",
    "trade_idea",
    "entry_zone_low",
    "entry_zone_high",
    "stop_loss",
    "target",
    "risk_reward",
]


class SignalStore:
    """Persist generated signals to SQLite and CSV for auditability."""

    def __init__(self, database_path: Path, csv_log_path: Path) -> None:
        self.database_path = database_path
        self.csv_log_path = csv_log_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.csv_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    close REAL,
                    previous_close REAL,
                    pct_change REAL,
                    volume REAL,
                    avg_volume REAL,
                    volume_multiple REAL,
                    recent_high REAL,
                    recent_low REAL,
                    volatility REAL,
                    avg_volatility REAL,
                    volatility_multiple REAL,
                    is_big_mover INTEGER,
                    is_unusual_volume INTEGER,
                    is_breakout INTEGER,
                    is_pullback INTEGER,
                    is_volatility_spike INTEGER,
                    reasons TEXT,
                    score INTEGER,
                    confidence REAL,
                    trade_idea TEXT,
                    entry_zone_low REAL,
                    entry_zone_high REAL,
                    stop_loss REAL,
                    target REAL,
                    risk_reward REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def save_signals(self, signals: Iterable[Signal]) -> None:
        records = [signal.to_record() for signal in signals]
        if not records:
            return
        self._save_sqlite(records)
        self._save_csv(records)

    def _save_sqlite(self, records: list[dict[str, object]]) -> None:
        placeholders = ", ".join([":" + column for column in SIGNAL_COLUMNS])
        columns = ", ".join(SIGNAL_COLUMNS)
        sql = f"INSERT INTO signals ({columns}) VALUES ({placeholders})"
        with sqlite3.connect(self.database_path) as conn:
            conn.executemany(sql, records)

    def _save_csv(self, records: list[dict[str, object]]) -> None:
        write_header = not self.csv_log_path.exists()
        with self.csv_log_path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=SIGNAL_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerows(records)

    def load_recent(self, limit: int = 100) -> list[dict[str, object]]:
        with sqlite3.connect(self.database_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM signals ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
