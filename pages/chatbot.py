import streamlit as st
from utils.chatbot_engine import ReliabilityChatbot

st.title("💬 Reliability Excel Chatbot")
st.caption("수명 · Aging · BDV Excel 데이터를 직접 조회합니다. Excel에 없는 값은 임의로 생성하지 않습니다.")
st.markdown("#### 💡 질문 예시")

example_questions = [
    "Supplier A 2203-007317 전체 평가결과 알려줘",
    "2203-007317 수명 결과 알려줘",
    "2203-007317 Aging 결과 알려줘",
    "2203-007317 BDV 결과 알려줘",
]

example_cols = st.columns(2)
for i, example in enumerate(example_questions):
    if example_cols[i % 2].button(
        example,
        key=f"example_question_{i}",
        use_container_width=True,
    ):
        st.session_state["pending_example_question"] = example

@st.cache_resource
def get_chatbot():
    return ReliabilityChatbot()

if "reliability_chat_history" not in st.session_state:
    st.session_state.reliability_chat_history=[{"role":"assistant","content":"안녕하세요. 자재코드와 함께 수명 / Aging / BDV / 전체 평가결과를 질문해보세요."}]

with st.sidebar:
    st.header("Chatbot")
    if st.button("챗봇 데이터 새로고침",use_container_width=True):
        st.cache_data.clear(); st.cache_resource.clear()
        st.session_state.reliability_chat_history=[]
        st.rerun()
    if st.button("대화내용 지우기",use_container_width=True):
        st.session_state.reliability_chat_history=[]
        st.rerun()

for msg in st.session_state.reliability_chat_history:
    with st.chat_message(msg["role"]):st.markdown(msg["content"])

typed_question = st.chat_input("Excel 데이터에 대해 질문하세요.")
example_question = st.session_state.pop("pending_example_question", None)
q = typed_question or example_question

if q:
    st.session_state.reliability_chat_history.append({"role":"user","content":q})
    with st.chat_message("user"):st.markdown(q)
    try:answer=get_chatbot().answer(q)
    except Exception as e:answer=f"Excel 데이터를 조회하는 중 오류가 발생했습니다.\n\n`{type(e).__name__}: {e}`"
    st.session_state.reliability_chat_history.append({"role":"assistant","content":answer})
    with st.chat_message("assistant"):st.markdown(answer)
