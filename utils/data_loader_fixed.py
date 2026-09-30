from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# Project paths
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

LIFETIME_FILE = DATA_DIR / "test_수명.xlsx"
AGING_FILE = DATA_DIR / "test_aging.xlsx"


# ============================================================
# Common helpers
# ============================================================

def _normalize_text(value):
    """Normalize Excel cell/header text for reliable matching."""
    if pd.isna(value):
        return ""

    return (
        str(value)
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
    )


def _find_header_row(file_path, sheet_name, required_columns, scan_rows=30):
    """
    Find the 0-based Excel header row automatically.

    The first row containing all required column names is used as the header.
    This allows title/blank rows to be inserted above the table without
    changing Python code.
    """
    preview = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        header=None,
        nrows=scan_rows,
        engine="openpyxl",
    )

    required = {
        _normalize_text(column)
        for column in required_columns
    }

    for row_index, row in preview.iterrows():
        values = {
            _normalize_text(value)
            for value in row.tolist()
            if _normalize_text(value)
        }

        if required.issubset(values):
            return int(row_index)

    raise ValueError(
        f"'{sheet_name}' 시트에서 헤더 행을 찾지 못했습니다. "
        f"필수 컬럼: {', '.join(required_columns)}"
    )


def _load_excel_table(file_path, sheet_name, required_columns):
    """Load an Excel table after automatically detecting its header row."""
    header_row = _find_header_row(
        file_path=file_path,
        sheet_name=sheet_name,
        required_columns=required_columns,
    )

    df = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        header=header_row,
        engine="openpyxl",
    )

    # Remove completely empty columns/rows.
    df = df.dropna(axis=1, how="all")
    df = df.dropna(how="all")

    # Normalize column names.
    df.columns = [
        _normalize_text(column)
        for column in df.columns
    ]

    # Validate the final parsed table before filtering.
    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise KeyError(
            f"'{sheet_name}' 시트에서 필요한 컬럼을 찾지 못했습니다: "
            f"{missing_columns}. 현재 컬럼: {list(df.columns)}"
        )

    # Keep only valid data rows for the dashboard hierarchy.
    df = df.dropna(subset=required_columns).copy()

    return df


# ============================================================
# Lifetime
# ============================================================

@st.cache_data
def load_lifetime_data(file_path, modified_time):
    # modified_time is intentionally part of the cache key.
    # When the Excel file changes, Streamlit reloads the data.
    _ = modified_time

    return _load_excel_table(
        file_path=file_path,
        sheet_name="수명",
        required_columns=[
            "자재코드",
            "부품사",
            "사용전압(V)",
        ],
    )


# ============================================================
# Aging
# ============================================================

@st.cache_data
def load_aging_data(file_path, modified_time):
    _ = modified_time

    return _load_excel_table(
        file_path=file_path,
        sheet_name="Aging",
        required_columns=[
            "자재코드",
            "부품사",
            "시험전압",
        ],
    )


# ============================================================
# Convenience functions
# ============================================================

def get_lifetime_data():
    if not LIFETIME_FILE.exists():
        raise FileNotFoundError(
            f"수명 Excel 파일이 없습니다: {LIFETIME_FILE}"
        )

    modified_time = LIFETIME_FILE.stat().st_mtime

    return load_lifetime_data(
        str(LIFETIME_FILE),
        modified_time,
    )


def get_aging_data():
    if not AGING_FILE.exists():
        raise FileNotFoundError(
            f"Aging Excel 파일이 없습니다: {AGING_FILE}"
        )

    modified_time = AGING_FILE.stat().st_mtime

    return load_aging_data(
        str(AGING_FILE),
        modified_time,
    )
