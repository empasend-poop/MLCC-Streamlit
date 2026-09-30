from pathlib import Path
import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
LIFETIME_FILE = DATA_DIR / "test_수명.xlsx"
AGING_FILE = DATA_DIR / "test_aging.xlsx"
BDV_FILE = DATA_DIR / "test_bdv.xlsx"


def _normalize_text(value):
    if pd.isna(value):
        return ""
    return " ".join(str(value).replace("\n", " ").replace("\r", " ").split())


def _find_header_row(file_path, sheet_name, required_columns, scan_rows=30):
    preview = pd.read_excel(file_path, sheet_name=sheet_name, header=None,
                            nrows=scan_rows, engine="openpyxl")
    required = {_normalize_text(c) for c in required_columns}
    for row_index, row in preview.iterrows():
        values = {_normalize_text(v) for v in row.tolist() if _normalize_text(v)}
        if required.issubset(values):
            return int(row_index)
    raise ValueError(f"'{sheet_name}' 시트에서 헤더 행을 찾지 못했습니다. 필수 컬럼: {required_columns}")


def _load_excel_table(file_path, sheet_name, required_columns):
    header_row = _find_header_row(file_path, sheet_name, required_columns)
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row, engine="openpyxl")
    df = df.dropna(axis=1, how="all").dropna(how="all")
    df.columns = [_normalize_text(c) for c in df.columns]
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise KeyError(f"'{sheet_name}' 시트 필수 컬럼 누락: {missing}. 현재 컬럼: {list(df.columns)}")
    return df.dropna(subset=required_columns).copy()


@st.cache_data(show_spinner=False)
def load_lifetime_data(file_path, modified_time):
    _ = modified_time
    return _load_excel_table(file_path, "수명", ["자재코드", "부품사", "사용전압(V)"])


@st.cache_data(show_spinner=False)
def load_aging_data(file_path, modified_time):
    _ = modified_time
    return _load_excel_table(file_path, "Aging", ["자재코드", "부품사", "시험전압"])


@st.cache_data(show_spinner=False)
def load_bdv_data(file_path, modified_time):
    _ = modified_time
    df = _load_excel_table(file_path, "BDV", ["부품사", "자재코드", "BDV 결과 (Typ.)"])

    # 실제 test_bdv.xlsx 구조: 1ppm = Lower/Typ./Upper, 10ppm = Lower.1/Typ..1/Upper.1
    df = df.rename(columns={
        "Lower": "1ppm Lower", "Typ.": "1ppm Typ.", "Upper": "1ppm Upper",
        "Lower.1": "10ppm Lower", "Typ..1": "10ppm Typ.", "Upper.1": "10ppm Upper",
    })

    # 병합 헤더로 Unnamed가 되는 Excel 계산열은 위치/수식에 의존하지 않고 Python에서 재계산.
    numeric = ["정격전압(V)", "정격용량(uF)", "Size", "BDV평가수량", "BDV평가온도",
               "BDV 결과 (Typ.)", "정격대비수준", "1ppm Lower", "1ppm Typ.", "1ppm Upper",
               "10ppm Lower", "10ppm Typ.", "10ppm Upper"]
    for c in numeric:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    rated = df["정격전압(V)"].replace(0, pd.NA)
    lower = df["1ppm Lower"].replace(0, pd.NA)
    df["1ppm Lower / 정격전압 (배)"] = lower / rated
    df["정격전압 / 1ppm Lower (%)"] = rated / lower * 100

    # 원본 Excel 마지막 열(Outlier 제거여부)은 헤더가 병합되어 Unnamed가 될 수 있음.
    unnamed = [c for c in df.columns if str(c).startswith("Unnamed:")]
    if unnamed:
        last = unnamed[-1]
        values = df[last].dropna().astype(str).str.upper()
        if not values.empty and values.isin(["Y", "N"]).mean() >= 0.8:
            df = df.rename(columns={last: "Outlier 제거여부"})

    return df


def _get(file_path, loader, label):
    if not file_path.exists():
        raise FileNotFoundError(f"{label} Excel 파일이 없습니다: {file_path}")
    return loader(str(file_path), file_path.stat().st_mtime_ns)


def get_lifetime_data():
    return _get(LIFETIME_FILE, load_lifetime_data, "수명")


def get_aging_data():
    return _get(AGING_FILE, load_aging_data, "Aging")


def get_bdv_data():
    return _get(BDV_FILE, load_bdv_data, "BDV")
