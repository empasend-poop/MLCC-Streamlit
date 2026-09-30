import plotly.express as px
import streamlit as st

from utils.chatbot_engine import ReliabilityChatbot


st.title("💬 Reliability Excel Chatbot")
st.caption("Excel 데이터를 그래프 중심으로 조회합니다.")

@st.cache_resource
def get_chatbot():
    return ReliabilityChatbot()


def render_lifetime(chatbot, material, supplier, temperature, voltage=None, chart_key=None):
    # 수명 비교는 서로 다른 사용전압을 한 그래프에 섞지 않습니다.
    all_compare = chatbot.lifetime_comparison(material, temperature)
    if all_compare.empty:
        compare = all_compare
    else:
        available_voltages = sorted(all_compare["사용전압(V)"].dropna().unique().tolist())
        # 질문에 전압이 있으면 그 전압, 없으면 가장 많은 부품사가 존재하는 전압을 자동 선택
        if voltage is None and available_voltages:
            counts = all_compare.groupby("사용전압(V)")["부품사"].nunique()
            voltage = float(counts.sort_values(ascending=False).index[0])
        compare = chatbot.lifetime_comparison(material, temperature, voltage)


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
        title=f"{material} · {voltage:g}V · {temperature}℃ 예측수명 비교" if voltage is not None else f"{material} · {temperature}℃ 예측수명 비교",
    )
    fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside")
    fig.update_layout(
        xaxis_title="부품사 / 사용전압",
        yaxis_title="예측수명",
        legend_title_text="부품사",
        height=460,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    st.plotly_chart(fig, use_container_width=True, key=chart_key)

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
    "2203-007317 3.15V 85도 수명 비교해줘",
    "2203-007317 3.15V 100도 수명 비교해줘",
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

for history_idx, item in enumerate(st.session_state.chat_history):
    with st.chat_message(item["role"]):
        st.markdown(item["text"])
        if item.get("show_lifetime"):
            render_lifetime(
                get_chatbot(),
                item["material"],
                item.get("supplier"),
                item.get("temperature", 85),
                item.get("voltage"),
                chart_key=f"lifetime_history_{history_idx}",
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

    # 새 결과를 history에 넣은 뒤 즉시 rerun하여 한 번만 렌더링합니다.
    # 같은 Plotly 차트가 한 실행에서 2번 생성되어 DuplicateElementId가 나는 것을 방지합니다.
    st.rerun()
