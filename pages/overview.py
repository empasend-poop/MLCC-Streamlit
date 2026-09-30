import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import (
    get_lifetime_data,
    get_aging_data,
    get_bdv_data,
)


# ============================================================
# COMMON STYLE
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --section-blue: #178FCB;
        --section-blue-dark: #0F78AE;
        --section-border: #B9DCEB;
    }

    .mlcc-section-title {
        margin-top: 1.15rem;
        margin-bottom: 0.65rem;
        padding: 0.48rem 0.85rem;
        border-left: 6px solid var(--section-blue-dark);
        border-radius: 6px;
        background: linear-gradient(
            90deg,
            rgba(23,143,203,0.18) 0%,
            rgba(23,143,203,0.07) 55%,
            rgba(23,143,203,0.00) 100%
        );
        color: var(--section-blue-dark);
        font-size: 1.55rem;
        font-weight: 800;
        line-height: 1.35;
    }

    .mlcc-section-divider {
        height: 1px;
        margin: 0.15rem 0 0.85rem 0;
        background: linear-gradient(
            90deg,
            var(--section-border) 0%,
            rgba(185,220,235,0.35) 75%,
            transparent 100%
        );
    }

    /* 평가 데이터 보유 현황 DataFrame 헤더 강조 */
    div[data-testid="stDataFrame"] [role="columnheader"] {
        font-size: 15px !important;
        font-weight: 700 !important;
    }

    div[data-testid="stDataFrame"] [role="columnheader"] * {
        font-size: 15px !important;
        font-weight: 700 !important;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


def section_title(title):
    st.markdown(
        f'<div class="mlcc-section-title">{title}</div>'
        '<div class="mlcc-section-divider"></div>',
        unsafe_allow_html=True,
    )


def material_set(df):
    if "자재코드" not in df.columns:
        return set()

    return set(
        df["자재코드"]
        .dropna()
        .astype(str)
        .str.strip()
    )


def supplier_set(df):
    if "부품사" not in df.columns:
        return set()

    return set(
        df["부품사"]
        .dropna()
        .astype(str)
        .str.strip()
    )


# ============================================================
# DATA
# ============================================================

try:
    life_df = get_lifetime_data()
    aging_df = get_aging_data()
    bdv_df = get_bdv_data()

except Exception as error:
    st.error("Overview 데이터를 불러오는 중 오류가 발생했습니다.")
    st.exception(error)
    st.stop()


# ============================================================
# TITLE
# ============================================================

st.title("📊 MLCC Reliability Dashboard")

st.caption(
    "MLCC 수명 평가 · Aging 평가 · BDV 평가 통합 현황"
)


# ============================================================
# KPI
# ============================================================

life_materials = material_set(life_df)
aging_materials = material_set(aging_df)
bdv_materials = material_set(bdv_df)

all_materials = (
    life_materials
    | aging_materials
    | bdv_materials
)

life_suppliers = supplier_set(life_df)
aging_suppliers = supplier_set(aging_df)
bdv_suppliers = supplier_set(bdv_df)

all_suppliers = (
    life_suppliers
    | aging_suppliers
    | bdv_suppliers
)


section_title("평가 데이터 요약")

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric(
    "전체 자재코드",
    len(all_materials),
)

c2.metric(
    "부품사",
    len(all_suppliers),
)

c3.metric(
    "수명 평가 데이터",
    len(life_df),
)

c4.metric(
    "Aging 평가 데이터",
    len(aging_df),
)

c5.metric(
    "BDV 평가 데이터",
    len(bdv_df),
)


# ============================================================
# MATERIAL STATUS
# ============================================================

section_title("평가 데이터 보유 현황")

status_rows = []

for material in sorted(all_materials):

    status_rows.append(
        {
            "자재코드": material,

            "수명평가":
                "●"
                if material in life_materials
                else "-",

            "Aging평가":
                "●"
                if material in aging_materials
                else "-",

            "BDV평가":
                "●"
                if material in bdv_materials
                else "-",
        }
    )


status_df = pd.DataFrame(
    status_rows,
    columns=[
        "자재코드",
        "수명평가",
        "Aging평가",
        "BDV평가",
    ],
)

st.dataframe(
    status_df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "자재코드": st.column_config.TextColumn("자재코드", width="medium"),
        "수명평가": st.column_config.TextColumn("수명평가", width="medium"),
        "Aging평가": st.column_config.TextColumn("Aging평가", width="medium"),
        "BDV평가": st.column_config.TextColumn("BDV평가", width="medium"),
    },
)
