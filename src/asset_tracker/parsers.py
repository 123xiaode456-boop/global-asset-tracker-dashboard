from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pdfplumber


SOURCE_COLUMNS = [
    "代码",
    "标的名称",
    "日级别趋势",
    "日级别趋势持续时间",
    "周级别趋势",
    "周级别趋势持续时间",
    "月级别趋势",
    "月级别趋势持续时间",
    "收盘价对比60日位置",
    "相对强度",
    "强度动量",
    "早期转折",
    "当前比价状态持续时间",
    "当前比价状态",
    "当前比价状态涨幅",
    "此前比价状态",
    "此前比价状态涨幅",
    "此前比价状态持续时间",
    "当前杠杆资金状态持续时间",
    "当前杠杆资金状态",
    "当前杠杆资金状态涨幅",
    "此前杠杆资金状态",
    "此前杠杆资金状态涨幅",
    "杠杆资金数值",
    "杠杆资金相比前日变动",
]

CANONICAL_COLUMNS = [
    "asset_code",
    "asset_name",
    "day_trend",
    "day_trend_duration",
    "week_trend",
    "week_trend_duration",
    "month_trend",
    "month_trend_duration",
    "close_position_60d",
    "relative_strength",
    "strength_momentum",
    "early_turn",
    "relative_state_duration",
    "relative_state",
    "relative_state_return",
    "previous_relative_state",
    "previous_relative_state_return",
    "previous_relative_state_duration",
    "capital_state_duration",
    "capital_state",
    "capital_state_return",
    "previous_capital_state",
    "previous_capital_state_return",
    "capital_value",
    "capital_daily_change",
]

MOMENTUM_SOURCE_COLUMNS = [
    "代码",
    "标的名称",
    "当前动能状态持续时间",
    "当前动能状态",
    "当前动能状态累积涨跌幅 (%)",
    "此前动能状态",
    "此前动能状态累积涨跌幅 (%)",
    "动能数值",
    "动能数值相比前日变动",
]

MOMENTUM_CANONICAL_COLUMNS = [
    "asset_code",
    "asset_name",
    "current_momentum_state_duration",
    "current_momentum_state",
    "current_momentum_state_return",
    "previous_momentum_state",
    "previous_momentum_state_return",
    "momentum_value",
    "momentum_daily_change",
]

COLUMN_MAP = dict(zip(SOURCE_COLUMNS, CANONICAL_COLUMNS))

INTEGER_FIELDS = {
    "day_trend_duration",
    "week_trend_duration",
    "month_trend_duration",
    "relative_state_duration",
    "previous_relative_state_duration",
    "capital_state_duration",
}

FLOAT_FIELDS = {
    "close_position_60d",
    "relative_strength",
    "strength_momentum",
    "early_turn",
    "relative_state_return",
    "previous_relative_state_return",
    "capital_state_return",
    "previous_capital_state_return",
    "capital_value",
    "capital_daily_change",
}

MOMENTUM_INTEGER_FIELDS = {"current_momentum_state_duration"}
MOMENTUM_FLOAT_FIELDS = {
    "current_momentum_state_return",
    "previous_momentum_state_return",
    "momentum_value",
    "momentum_daily_change",
}


@dataclass(frozen=True)
class DatasetMetadata:
    dataset_date: date
    dataset_type: str


@dataclass(frozen=True)
class ParsedDataset:
    metadata: DatasetMetadata
    source_path: Path
    source_hash: str
    rows: list[dict[str, Any]]

    @property
    def row_count(self) -> int:
        return len(self.rows)


def detect_metadata(path: str | Path) -> DatasetMetadata:
    source = Path(path)
    match = re.search(r"(\d{2})-(\d{2})-(\d{2})", source.name)
    if not match:
        raise ValueError(f"Cannot detect dataset date from filename: {source.name}")
    year, month, day = (int(part) for part in match.groups())
    dataset_date = date(2000 + year, month, day)

    if "动量状态" in source.name:
        dataset_type = "momentum"
    elif "国内主连" in source.name:
        dataset_type = "domestic_main"
    elif "核心数据集" in source.name:
        dataset_type = "core"
    elif "押注工具" in source.name:
        dataset_type = "betting"
    else:
        dataset_type = "unknown"
    return DatasetMetadata(dataset_date=dataset_date, dataset_type=dataset_type)


def parse_dataset_file(path: str | Path) -> ParsedDataset:
    source = Path(path)
    metadata = detect_metadata(source)
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        rows = _parse_pdf(source)
    elif suffix in {".xlsx", ".xls"}:
        rows = _parse_excel(source, metadata.dataset_type)
    else:
        raise ValueError(f"Unsupported dataset file type: {source.suffix}")

    if not rows:
        raise ValueError(f"No dataset rows parsed from {source}")

    return ParsedDataset(
        metadata=metadata,
        source_path=source,
        source_hash=file_sha256(source),
        rows=rows,
    )


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_pdf(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table:
                    continue
                header = _clean_cells(table[0])
                if not _looks_like_header(header):
                    continue
                for raw_row in table[1:]:
                    cells = _clean_cells(raw_row)
                    if not any(cells):
                        continue
                    rows.append(_normalize_row(cells))
    return rows


def _parse_excel(path: Path, dataset_type: str) -> list[dict[str, Any]]:
    if dataset_type == "momentum":
        return _parse_excel_table(
            path,
            MOMENTUM_SOURCE_COLUMNS,
            MOMENTUM_CANONICAL_COLUMNS,
            MOMENTUM_INTEGER_FIELDS,
            MOMENTUM_FLOAT_FIELDS,
        )
    return _parse_excel_table(path, SOURCE_COLUMNS, CANONICAL_COLUMNS, INTEGER_FIELDS, FLOAT_FIELDS)


def _parse_excel_table(
    path: Path,
    source_columns: list[str],
    canonical_columns: list[str],
    integer_fields: set[str],
    float_fields: set[str],
) -> list[dict[str, Any]]:
    sheets = pd.read_excel(path, sheet_name=None, dtype=str, header=None)
    for frame in sheets.values():
        header_index = _find_excel_header_row(frame, source_columns)
        if header_index is None:
            continue
        header = [_clean_text(value) for value in frame.iloc[header_index].tolist()]
        column_positions = _source_column_positions(header, source_columns)
        parsed_rows: list[dict[str, Any]] = []
        for _, row in frame.iloc[header_index + 1 :].iterrows():
            cells = [_clean_text(row.iloc[index]) if index < len(row) else "" for index in column_positions]
            if any(cells):
                parsed_rows.append(
                    _normalize_columns(cells, source_columns, canonical_columns, integer_fields, float_fields)
                )
        if parsed_rows:
            return parsed_rows
    raise ValueError(f"Could not find a dataset table in Excel workbook: {path}")


def _find_excel_header_row(frame: pd.DataFrame, source_columns: list[str]) -> int | None:
    max_scan = min(15, len(frame))
    for index in range(max_scan):
        values = [_clean_text(value) for value in frame.iloc[index].tolist()]
        if _looks_like_excel_header(values, source_columns):
            return index
    return None


def _source_column_positions(header: list[str], source_columns: list[str]) -> list[int]:
    positions: list[int] = []
    for source_column in source_columns:
        try:
            positions.append(header.index(source_column))
        except ValueError as exc:
            raise ValueError(f"Missing required source column: {source_column}") from exc
    return positions


def _looks_like_header(header: list[str]) -> bool:
    return len(header) >= len(SOURCE_COLUMNS) and header[: len(SOURCE_COLUMNS)] == SOURCE_COLUMNS


def _looks_like_excel_header(header: list[str], source_columns: list[str]) -> bool:
    return set(source_columns).issubset(set(header))


def _normalize_row(cells: list[str]) -> dict[str, Any]:
    if len(cells) < len(SOURCE_COLUMNS):
        raise ValueError(f"Dataset row has {len(cells)} columns; expected {len(SOURCE_COLUMNS)}")
    normalized: dict[str, Any] = {}
    for source_column, canonical in COLUMN_MAP.items():
        raw_value = cells[SOURCE_COLUMNS.index(source_column)]
        if canonical in INTEGER_FIELDS:
            normalized[canonical] = _to_int(raw_value)
        elif canonical in FLOAT_FIELDS:
            normalized[canonical] = _to_float(raw_value)
        else:
            normalized[canonical] = _clean_text(raw_value)
    return {column: normalized[column] for column in CANONICAL_COLUMNS}


def _normalize_columns(
    cells: list[str],
    source_columns: list[str],
    canonical_columns: list[str],
    integer_fields: set[str],
    float_fields: set[str],
) -> dict[str, Any]:
    if len(cells) < len(source_columns):
        raise ValueError(f"Dataset row has {len(cells)} columns; expected {len(source_columns)}")
    normalized: dict[str, Any] = {}
    for index, canonical in enumerate(canonical_columns):
        raw_value = cells[index]
        if canonical in integer_fields:
            normalized[canonical] = _to_int(raw_value)
        elif canonical in float_fields:
            normalized[canonical] = _to_float(raw_value)
        else:
            normalized[canonical] = _clean_text(raw_value)
    return {column: normalized[column] for column in canonical_columns}


def _clean_cells(row: list[Any]) -> list[str]:
    return [_clean_text(cell) for cell in row]


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()


def _to_int(value: str) -> int | None:
    text = _clean_text(value)
    if not text:
        return None
    return int(float(text))


def _to_float(value: str) -> float | None:
    text = _clean_text(value).replace("%", "")
    if not text:
        return None
    return float(text)
