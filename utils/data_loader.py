from pathlib import Path

import pandas as pd
import streamlit as st


# 프로젝트 ROOT
ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "data"

LIFETIME_FILE = DATA_DIR / "test_수명.xlsx"
AGING_FILE = DATA_DIR / "test_aging.xlsx"


# ============================================================
# Lifetime
# ============================================================

@st.cache_data
def load_lifetime_data(file_path, modified_time):

    df = pd.read_excel(
        file_path,
        sheet_name="수명",
        header=6,
        engine="openpyxl",
    )

    df = df.dropna(
        axis=1,
        how="all",
    )

    df = df.dropna(
        how="all",
    )

    df.columns = [
        str(col)
        .replace("\n", " ")
        .strip()
        for col in df.columns
    ]

    df = df.dropna(
        subset=[
            "자재코드",
            "부품사",
            "사용전압(V)",
        ]
    )

    return df


# ============================================================
# Aging
# ============================================================

@st.cache_data
def load_aging_data(file_path, modified_time):

    df = pd.read_excel(
        file_path,
        sheet_name="Aging",
        header=5,
        engine="openpyxl",
    )

    df = df.dropna(
        axis=1,
        how="all",
    )

    df = df.dropna(
        how="all",
    )

    df.columns = [
        str(col)
        .replace("\n", " ")
        .strip()
        for col in df.columns
    ]

    df = df.dropna(
        subset=[
            "자재코드",
            "부품사",
            "시험전압",
        ]
    )

    return df


# ============================================================
# Convenience functions
# ============================================================

def get_lifetime_data():

    modified_time = (
        LIFETIME_FILE
        .stat()
        .st_mtime
    )

    return load_lifetime_data(
        str(LIFETIME_FILE),
        modified_time,
    )


def get_aging_data():

    modified_time = (
        AGING_FILE
        .stat()
        .st_mtime
    )

    return load_aging_data(
        str(AGING_FILE),
        modified_time,
    )
