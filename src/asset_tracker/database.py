from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .asset_names import translate_asset_name
from .parsers import CANONICAL_COLUMNS, MOMENTUM_CANONICAL_COLUMNS, ParsedDataset


OBSERVATION_COLUMNS = [
    "dataset_date",
    "dataset_type",
    "source_row_number",
    "asset_key",
    *CANONICAL_COLUMNS,
    "asset_name_cn",
    "asset_name_translation_status",
    "source_file_hash",
    "imported_at",
]

MOMENTUM_OBSERVATION_COLUMNS = [
    "dataset_date",
    "source_row_number",
    "asset_key",
    *MOMENTUM_CANONICAL_COLUMNS,
    "asset_name_cn",
    "asset_name_translation_status",
    "source_file_hash",
    "imported_at",
]


@dataclass(frozen=True)
class ImportResult:
    file_hash: str
    dataset_date: str
    dataset_type: str
    inserted_rows: int
    duplicate: bool


class AssetDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS assets (
                    asset_key TEXT PRIMARY KEY,
                    asset_code TEXT NOT NULL,
                    asset_name TEXT NOT NULL,
                    asset_name_cn TEXT,
                    asset_name_translation_status TEXT NOT NULL DEFAULT 'unmapped',
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    last_dataset_type TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS observations (
                    dataset_date TEXT NOT NULL,
                    dataset_type TEXT NOT NULL,
                    source_row_number INTEGER NOT NULL,
                    asset_key TEXT NOT NULL,
                    asset_code TEXT NOT NULL,
                    asset_name TEXT NOT NULL,
                    asset_name_cn TEXT,
                    asset_name_translation_status TEXT,
                    day_trend TEXT,
                    day_trend_duration INTEGER,
                    week_trend TEXT,
                    week_trend_duration INTEGER,
                    month_trend TEXT,
                    month_trend_duration INTEGER,
                    close_position_60d REAL,
                    relative_strength REAL,
                    strength_momentum REAL,
                    early_turn REAL,
                    relative_state_duration INTEGER,
                    relative_state TEXT,
                    relative_state_return REAL,
                    previous_relative_state TEXT,
                    previous_relative_state_return REAL,
                    previous_relative_state_duration INTEGER,
                    capital_state_duration INTEGER,
                    capital_state TEXT,
                    capital_state_return REAL,
                    previous_capital_state TEXT,
                    previous_capital_state_return REAL,
                    capital_value REAL,
                    capital_daily_change REAL,
                    source_file_hash TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    PRIMARY KEY (dataset_date, dataset_type, source_row_number)
                );

                CREATE TABLE IF NOT EXISTS momentum_observations (
                    dataset_date TEXT NOT NULL,
                    source_row_number INTEGER NOT NULL,
                    asset_key TEXT NOT NULL,
                    asset_code TEXT NOT NULL,
                    asset_name TEXT NOT NULL,
                    asset_name_cn TEXT,
                    asset_name_translation_status TEXT,
                    current_momentum_state_duration INTEGER,
                    current_momentum_state TEXT,
                    current_momentum_state_return REAL,
                    previous_momentum_state TEXT,
                    previous_momentum_state_return REAL,
                    momentum_value REAL,
                    momentum_daily_change REAL,
                    source_file_hash TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    PRIMARY KEY (dataset_date, source_row_number)
                );

                CREATE INDEX IF NOT EXISTS idx_momentum_observations_asset_date
                ON momentum_observations(asset_key, dataset_date);

                CREATE TABLE IF NOT EXISTS import_logs (
                    file_hash TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    dataset_date TEXT NOT NULL,
                    dataset_type TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    imported_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT
                );

                CREATE TABLE IF NOT EXISTS price_bars (
                    asset_code TEXT NOT NULL,
                    bar_date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    source TEXT NOT NULL,
                    PRIMARY KEY (asset_code, bar_date, source)
                );

                CREATE TABLE IF NOT EXISTS symbol_map (
                    asset_code TEXT PRIMARY KEY,
                    asset_name TEXT NOT NULL,
                    market_symbol TEXT,
                    price_source TEXT,
                    status TEXT NOT NULL DEFAULT 'unmapped',
                    note TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS price_fetch_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_key TEXT NOT NULL,
                    asset_code TEXT NOT NULL,
                    asset_name TEXT,
                    dataset_date TEXT,
                    market_symbol TEXT,
                    status TEXT NOT NULL,
                    message TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    attempted_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_price_fetch_logs_asset_key_attempted_at
                ON price_fetch_logs(asset_key, attempted_at);
                """
            )
            _ensure_column(connection, "assets", "asset_name_cn", "TEXT")
            _ensure_column(
                connection,
                "assets",
                "asset_name_translation_status",
                "TEXT NOT NULL DEFAULT 'unmapped'",
            )
            _ensure_column(connection, "observations", "asset_name_cn", "TEXT")
            _ensure_column(connection, "observations", "asset_name_translation_status", "TEXT")

    def import_parsed_dataset(self, parsed: ParsedDataset, source_path: str | Path) -> ImportResult:
        dataset_date = parsed.metadata.dataset_date.isoformat()
        dataset_type = parsed.metadata.dataset_type
        imported_at = datetime.now().isoformat(timespec="seconds")
        source = Path(source_path)

        with self.connect() as connection:
            existing = connection.execute(
                "SELECT file_hash FROM import_logs WHERE file_hash = ?",
                (parsed.source_hash,),
            ).fetchone()
            if existing:
                return ImportResult(parsed.source_hash, dataset_date, dataset_type, 0, True)

            for row_number, row in enumerate(parsed.rows, start=1):
                asset_key = make_asset_key(row["asset_code"], row["asset_name"])
                translation = translate_asset_name(row["asset_code"], row["asset_name"])
                connection.execute(
                    """
                    INSERT INTO assets (
                        asset_key, asset_code, asset_name, asset_name_cn,
                        asset_name_translation_status, first_seen, last_seen, last_dataset_type
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(asset_key) DO UPDATE SET
                        asset_name = excluded.asset_name,
                        asset_name_cn = excluded.asset_name_cn,
                        asset_name_translation_status = excluded.asset_name_translation_status,
                        last_seen = excluded.last_seen,
                        last_dataset_type = excluded.last_dataset_type
                    """,
                    (
                        asset_key,
                        row["asset_code"],
                        row["asset_name"],
                        translation.name_cn,
                        translation.status,
                        dataset_date,
                        dataset_date,
                        dataset_type,
                    ),
                )
                if dataset_type == "momentum":
                    observation = {
                        "dataset_date": dataset_date,
                        "source_row_number": row_number,
                        "asset_key": asset_key,
                        **row,
                        "asset_name_cn": translation.name_cn,
                        "asset_name_translation_status": translation.status,
                        "source_file_hash": parsed.source_hash,
                        "imported_at": imported_at,
                    }
                    _insert_observation(
                        connection,
                        "momentum_observations",
                        MOMENTUM_OBSERVATION_COLUMNS,
                        observation,
                    )
                else:
                    observation = {
                        "dataset_date": dataset_date,
                        "dataset_type": dataset_type,
                        "source_row_number": row_number,
                        "asset_key": asset_key,
                        **row,
                        "asset_name_cn": translation.name_cn,
                        "asset_name_translation_status": translation.status,
                        "source_file_hash": parsed.source_hash,
                        "imported_at": imported_at,
                    }
                    _insert_observation(connection, "observations", OBSERVATION_COLUMNS, observation)

            connection.execute(
                """
                INSERT INTO import_logs (
                    file_hash, file_name, source_path, dataset_date, dataset_type,
                    row_count, imported_at, status, message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    parsed.source_hash,
                    source.name,
                    str(source),
                    dataset_date,
                    dataset_type,
                    parsed.row_count,
                    imported_at,
                    "imported",
                    "",
                ),
            )

        return ImportResult(parsed.source_hash, dataset_date, dataset_type, parsed.row_count, False)

    def count_observations(self) -> int:
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0])

    def count_assets(self) -> int:
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0])

    def list_import_logs(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM import_logs ORDER BY imported_at, file_name"
            ).fetchall()
            return [_row_to_dict(row) for row in rows]

    def get_dataset_types(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT dataset_type FROM observations ORDER BY dataset_type"
            ).fetchall()
            return [row[0] for row in rows]

    def get_latest_date(self, dataset_type: str | None = None) -> str | None:
        query = "SELECT MAX(dataset_date) FROM observations"
        params: tuple[Any, ...] = ()
        if dataset_type:
            query += " WHERE dataset_type = ?"
            params = (dataset_type,)
        with self.connect() as connection:
            return connection.execute(query, params).fetchone()[0]

    def list_dataset_dates(self, dataset_type: str | None = None) -> list[str]:
        query = "SELECT DISTINCT dataset_date FROM observations"
        params: tuple[Any, ...] = ()
        if dataset_type:
            query += " WHERE dataset_type = ?"
            params = (dataset_type,)
        query += " ORDER BY dataset_date"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
            return [row[0] for row in rows]

    def get_latest_observations(self, dataset_type: str | None = None) -> list[dict[str, Any]]:
        latest_date = self.get_latest_date(dataset_type)
        if latest_date is None:
            return []
        query = "SELECT * FROM observations WHERE dataset_date = ?"
        params: list[Any] = [latest_date]
        if dataset_type:
            query += " AND dataset_type = ?"
            params.append(dataset_type)
        query += " ORDER BY dataset_type, asset_code"
        with self.connect() as connection:
            return [_row_to_dict(row) for row in connection.execute(query, params).fetchall()]

    def get_observations_for_date(
        self,
        dataset_date: str,
        dataset_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM observations WHERE dataset_date = ?"
        params: list[Any] = [dataset_date]
        if dataset_type:
            query += " AND dataset_type = ?"
            params.append(dataset_type)
        query += " ORDER BY dataset_type, source_row_number"
        with self.connect() as connection:
            return [_row_to_dict(row) for row in connection.execute(query, params).fetchall()]

    def list_momentum_dates(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT dataset_date FROM momentum_observations ORDER BY dataset_date"
            ).fetchall()
            return [row[0] for row in rows]

    def get_momentum_for_date(self, dataset_date: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM momentum_observations
                WHERE dataset_date = ?
                ORDER BY source_row_number
                """,
                (dataset_date,),
            ).fetchall()
            return [_row_to_dict(row) for row in rows]

    def get_momentum_history(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM momentum_observations
                ORDER BY asset_key, dataset_date, source_row_number
                """
            ).fetchall()
            return [_row_to_dict(row) for row in rows]

    def get_asset_history(self, asset_code: str) -> list[dict[str, Any]]:
        lookup_code = _asset_code_prefix(asset_code)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM observations
                WHERE asset_code = ? OR asset_key = ?
                ORDER BY dataset_date, dataset_type, source_row_number
                """,
                (lookup_code, asset_code),
            ).fetchall()
            if "|" not in str(asset_code):
                return [_row_to_dict(row) for row in rows]
            return [
                _row_to_dict(row)
                for row in rows
                if asset_identifiers_match(asset_code, str(row["asset_key"]), lookup_code)
            ]

    def get_price_history(self, asset_code: str) -> list[dict[str, Any]]:
        lookup_code = _asset_code_prefix(asset_code)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM price_bars
                WHERE asset_code = ? OR asset_code = ? OR asset_code LIKE ?
                ORDER BY bar_date, source
                """,
                (asset_code, lookup_code, f"{lookup_code}|%"),
            ).fetchall()
            matching_rows = [
                _row_to_dict(row)
                for row in rows
                if asset_identifiers_match(asset_code, str(row["asset_code"]), lookup_code)
            ]
            return _dedupe_price_rows(matching_rows)

    def upsert_price_bars(self, asset_code: str, rows: list[dict[str, Any]], source: str) -> int:
        with self.connect() as connection:
            for row in rows:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO price_bars (
                        asset_code, bar_date, open, high, low, close, volume, source
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        asset_code,
                        row["bar_date"],
                        row.get("open"),
                        row.get("high"),
                        row.get("low"),
                        row.get("close"),
                        row.get("volume"),
                        source,
                    ),
                )
        return len(rows)

    def upsert_symbol_mapping(
        self,
        asset_code: str,
        asset_name: str,
        market_symbol: str | None,
        price_source: str | None,
        status: str,
        note: str = "",
    ) -> None:
        updated_at = datetime.now().isoformat(timespec="seconds")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO symbol_map (
                    asset_code, asset_name, market_symbol, price_source, status, note, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_code) DO UPDATE SET
                    asset_name = excluded.asset_name,
                    market_symbol = excluded.market_symbol,
                    price_source = excluded.price_source,
                    status = excluded.status,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (asset_code, asset_name, market_symbol, price_source, status, note, updated_at),
            )

    def get_symbol_mapping(self, asset_code: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM symbol_map WHERE asset_code = ?",
                (asset_code,),
            ).fetchone()
            return _row_to_dict(row) if row else None

    def list_symbol_mappings(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM symbol_map ORDER BY asset_code").fetchall()
            return [_row_to_dict(row) for row in rows]

    def refresh_asset_name_translations(self) -> dict[str, int]:
        updated_assets = 0
        updated_observations = 0
        with self.connect() as connection:
            asset_rows = connection.execute("SELECT asset_key, asset_code, asset_name FROM assets").fetchall()
            for row in asset_rows:
                translation = translate_asset_name(row["asset_code"], row["asset_name"])
                connection.execute(
                    """
                    UPDATE assets
                    SET asset_name_cn = ?, asset_name_translation_status = ?
                    WHERE asset_key = ?
                    """,
                    (translation.name_cn, translation.status, row["asset_key"]),
                )
                updated_assets += 1

            observation_rows = connection.execute(
                "SELECT rowid, asset_code, asset_name FROM observations"
            ).fetchall()
            for row in observation_rows:
                translation = translate_asset_name(row["asset_code"], row["asset_name"])
                connection.execute(
                    """
                    UPDATE observations
                    SET asset_name_cn = ?, asset_name_translation_status = ?
                    WHERE rowid = ?
                    """,
                    (translation.name_cn, translation.status, row["rowid"]),
                )
                updated_observations += 1
            momentum_rows = connection.execute(
                "SELECT rowid, asset_code, asset_name FROM momentum_observations"
            ).fetchall()
            for row in momentum_rows:
                translation = translate_asset_name(row["asset_code"], row["asset_name"])
                connection.execute(
                    """
                    UPDATE momentum_observations
                    SET asset_name_cn = ?, asset_name_translation_status = ?
                    WHERE rowid = ?
                    """,
                    (translation.name_cn, translation.status, row["rowid"]),
                )
        return {"assets": updated_assets, "observations": updated_observations}

    def list_untranslated_asset_names(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT asset_key, asset_code, asset_name,
                       COALESCE(asset_name_cn, '') AS asset_name_cn,
                       COALESCE(asset_name_translation_status, 'unmapped') AS asset_name_translation_status
                FROM assets
                WHERE COALESCE(asset_name_translation_status, 'unmapped') = 'unmapped'
                ORDER BY asset_code, asset_name
                """
            ).fetchall()
            return [_row_to_dict(row) for row in rows]

    def record_price_fetch_log(
        self,
        asset_key: str,
        asset_code: str,
        asset_name: str | None,
        dataset_date: str | None,
        market_symbol: str | None,
        status: str,
        message: str,
        start_date: str | None,
        end_date: str | None,
    ) -> None:
        attempted_at = datetime.now().isoformat(timespec="seconds")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO price_fetch_logs (
                    asset_key, asset_code, asset_name, dataset_date, market_symbol,
                    status, message, start_date, end_date, attempted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_key,
                    asset_code,
                    asset_name,
                    dataset_date,
                    market_symbol,
                    status,
                    message,
                    start_date,
                    end_date,
                    attempted_at,
                ),
            )

    def get_latest_price_fetch_logs(self, asset_keys: list[str]) -> dict[str, dict[str, Any]]:
        if not asset_keys:
            return {}
        placeholders = ", ".join("?" for _ in asset_keys)
        query = f"""
            SELECT * FROM price_fetch_logs
            WHERE asset_key IN ({placeholders})
            ORDER BY attempted_at DESC, id DESC
        """
        latest: dict[str, dict[str, Any]] = {}
        with self.connect() as connection:
            rows = connection.execute(query, asset_keys).fetchall()
        for row in rows:
            item = _row_to_dict(row)
            key = str(item["asset_key"])
            if key not in latest:
                latest[key] = item
        return latest


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _insert_observation(
    connection: sqlite3.Connection,
    table_name: str,
    columns: list[str],
    observation: dict[str, Any],
) -> None:
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    values = [observation[column] for column in columns]
    connection.execute(
        f"INSERT OR REPLACE INTO {table_name} ({column_sql}) VALUES ({placeholders})",
        values,
    )


def _ensure_column(connection: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def make_asset_key(asset_code: str, asset_name: str) -> str:
    return f"{str(asset_code).strip()}|{str(asset_name).strip()}"


def asset_identifiers_match(target_identifier: str, candidate_identifier: str, asset_code: str | None = None) -> bool:
    target = str(target_identifier).strip()
    candidate = str(candidate_identifier).strip()
    if target == candidate:
        return True

    target_code, target_name = _split_asset_identifier(target)
    candidate_code, candidate_name = _split_asset_identifier(candidate)
    lookup_code = str(asset_code or target_code).strip()
    if candidate_code != lookup_code or target_code not in {lookup_code, target}:
        return False
    if not target_name or not candidate_name:
        return candidate == lookup_code
    return _asset_names_compatible(target_name, candidate_name)


def _asset_code_prefix(asset_code: str) -> str:
    return str(asset_code).split("|", 1)[0].strip()


def _split_asset_identifier(identifier: str) -> tuple[str, str]:
    value = str(identifier).strip()
    if "|" not in value:
        return value, ""
    code, name = value.split("|", 1)
    return code.strip(), name.strip()


def _asset_names_compatible(left: str, right: str) -> bool:
    left_norm = _normalize_asset_name(left)
    right_norm = _normalize_asset_name(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm or left_norm in right_norm or right_norm in left_norm:
        return True

    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    if not left_tokens or not right_tokens:
        return False
    overlap = left_tokens & right_tokens
    jaccard = len(overlap) / len(left_tokens | right_tokens)
    return len(overlap) >= 2 and jaccard >= 0.5


def _normalize_asset_name(value: str) -> str:
    lowered = str(value).lower().replace("&", " and ")
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", lowered)
    return " ".join(normalized.split())


def _dedupe_price_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, Any]] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = (row.get("bar_date"), row.get("source"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped
