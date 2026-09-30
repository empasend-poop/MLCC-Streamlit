import plotly.express as px
import streamlit as st

from utils.chatbot_engine import ReliabilityChatbot


st.title("💬 Reliability Excel Chatbot")
st.caption("Excel 데이터를 그래프 중심으로 조회합니다.")

@st.cache_resource
def get_chatbot():
    return ReliabilityChatbot()


def render_lifetime(chatbot, material, supplier, temperature):
    compare = chatbot.lifetime_comparison(material, temperature)

    if supplier and not compare.empty:
        selected = compare[compare["부품사"] == supplier]
    else:
        selected = compare

    if selected.empty:
        st.warning("해당 조건의 수명평가 데이터가 없습니다.")
        return

    # 핵심 KPI
    best = selected.loc[selected["예측수명"].idxmax()]
    c1, c2, c3 = st.columns(3)
    c1.metric("비교 온도", f"{temperature}℃")
    c2.metric("비교 조건 수", len(selected))
    c3.metric(
        "최대 예측수명",
        f"{best['예측수명']:,.1f}",
        help=f"{best['부품사']} / {best['사용전압(V)']:g}V",
    )

    # 부품사 + 사용전압을 함께 구분해 특정온도 수명 비교
    fig = px.bar(
        selected,
        x="조건",
        y="예측수명",
        color="부품사",
        text="예측수명",
        hover_data={
            "부품사": True,
            "사용전압(V)": True,
            "예측수명": ":,.2f",
            "조건": False,
        },
        title=f"{material} · {temperature}℃ 예측수명 비교",
    )
    fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside")
    fig.update_layout(
        xaxis_title="부품사 / 사용전압",
        yaxis_title="예측수명",
        legend_title_text="부품사",
        height=460,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    # 필요한 상세값만 간결한 표로 표시
    detail = chatbot.lifetime_rows(material, supplier)
    if not detail.empty:
        temp_col = f"{temperature}℃"
        if temp_col not in detail.columns and temperature == 85 and "85℃" in detail.columns:
            temp_col = "85℃"

        cols = [c for c in ["부품사", "사용전압(V)", "Bx수명", "Ea", "n", temp_col] if c in detail.columns]
        show = detail[cols].copy()
        if temp_col in show.columns:
            show = show.rename(columns={temp_col: f"{temperature}℃ 예측수명"})

        st.dataframe(
            show,
            hide_index=True,
            use_container_width=True,
        )


st.markdown("#### 💡 질문 예시")
examples = [
    "2203-007317 수명평가 결과 보여줘",
    "Supplier A 2203-007317 수명평가 결과 보여줘",
    "2203-007317 85도 수명 비교해줘",
    "2203-007317 100도 수명 비교해줘",
]
cols = st.columns(2)
for i, example in enumerate(examples):
    if cols[i % 2].button(example, key=f"example_{i}", use_container_width=True):
        st.session_state["pending_question"] = example

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

with st.sidebar:
    if st.button("챗봇 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.session_state.chat_history = []
        st.rerun()

for item in st.session_state.chat_history:
    with st.chat_message(item["role"]):
        st.markdown(item["text"])
        if item.get("show_lifetime"):
            render_lifetime(
                get_chatbot(),
                item["material"],
                item.get("supplier"),
                item.get("temperature", 85),
            )

typed = st.chat_input("예: 2203-007317 85도 수명 비교해줘")
clicked = st.session_state.pop("pending_question", None)
question = typed or clicked

if question:
    with st.chat_message("user"):
        st.markdown(question)

    result = get_chatbot().short_answer(question)

    st.session_state.chat_history.append({
        "role": "user",
        "text": question,
    })
    st.session_state.chat_history.append({
        "role": "assistant",
        **result,
    })

    with st.chat_message("assistant"):
        st.markdown(result["text"])
        if result.get("show_lifetime"):
            render_lifetime(
                get_chatbot(),
                result["material"],
                result.get("supplier"),
                result.get("temperature", 85),
            )
