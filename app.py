import streamlit as st


st.set_page_config(
    page_title="MLCC Reliability Dashboard",
    page_icon="📊",
    layout="wide",
)


# ------------------------------------------------------------
# Pages
# ------------------------------------------------------------

overview_page = st.Page(
    "pages/overview.py",
    title="Overview",
    icon="🏠",
    default=True,
)

lifetime_page = st.Page(
    "pages/lifetime.py",
    title="수명 분석",
    icon="⏱️",
)

aging_page = st.Page(
    "pages/aging.py",
    title="Aging 분석",
    icon="📉",
)


# ------------------------------------------------------------
# Navigation
# ------------------------------------------------------------

pg = st.navigation(
    {
        "MLCC Reliability": [
            overview_page,
        ],

        "Analysis": [
            lifetime_page,
            aging_page,
        ],
    }
)


pg.run()
