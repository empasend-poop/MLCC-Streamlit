import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import (
    get_lifetime_data,
    get_aging_data,
)


# ============================================================
# DATA
# ============================================================

life_df = get_lifetime_data()
aging_df = get_aging_data()


# ============================================================
# TITLE
# ============================================================

st.title("📊 MLCC Reliability Dashboard")

st.caption(
    "MLCC 수명 평가 및 Aging 평가 통합 현황"
)


# ============================================================
# KPI
# ============================================================

all_materials = set(
    life_df["자재코드"]
    .dropna()
    .astype(str)
)

all_materials.update(
    aging_df["자재코드"]
    .dropna()
    .astype(str)
)


all_suppliers = set(
    life_df["부품사"]
    .dropna()
    .astype(str)
)

all_suppliers.update(
    aging_df["부품사"]
    .dropna()
    .astype(str)
)


c1, c2, c3, c4 = st.columns(4)


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


st.divider()


# ============================================================
# MATERIAL STATUS
# ============================================================

st.subheader("평가 데이터 보유 현황")


life_materials = set(
    life_df["자재코드"]
    .astype(str)
)


aging_materials = set(
    aging_df["자재코드"]
    .astype(str)
)


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
        }
    )


status_df = pd.DataFrame(
    status_rows
)


st.dataframe(
    status_df,
    hide_index=True,
    use_container_width=True,
)
