import json
import os
import re

try:
    import streamlit as st
except Exception:
    st = None

try:
    from groq import Groq
except Exception:
    Groq = None


DEFAULT_MODEL = "openai/gpt-oss-20b"


def _secret(name):
    # Streamlit Cloud secret first, local environment variable second.
    if st is not None:
        try:
            value = st.secrets.get(name)
            if value:
                return str(value)
        except Exception:
            pass
    return os.getenv(name)


def groq_available():
    return bool(_secret("GROQ_API_KEY")) and Groq is not None


def _extract_json(text):
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.I)
    if fenced:
        text = fenced.group(1)
    else:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            text = match.group(0)
    return json.loads(text)


def interpret_question(question, known_materials, known_suppliers):
    """
    Returns (parsed, mode, note).
    mode='groq' on success; otherwise parsed=None and caller must use rule fallback.
    No Excel rows or numeric evaluation results are sent to Groq.
    """
    if not groq_available():
        return None, "rule", "Groq API Key가 없거나 groq 패키지를 사용할 수 없어 규칙 기반으로 처리했습니다."

    prompt = f"""
너는 MLCC 신뢰성 Excel 챗봇의 '질문 분류기'다.
숫자를 계산하거나 평가결과를 만들지 마라.
사용자 문장에서 조회 의도와 필터만 JSON으로 추출하라.

허용 intent:
- lifetime
- aging
- bdv
- overall
- unknown

현재 Excel에 존재하는 자재코드:
{known_materials}

현재 Excel에 존재하는 부품사:
{known_suppliers}

반드시 아래 JSON 객체 하나만 출력:
{{
  "intent": "lifetime|aging|bdv|overall|unknown",
  "material": "자재코드 또는 null",
  "supplier": "부품사 또는 null",
  "voltage": 숫자 또는 null,
  "temperature": 숫자 또는 null
}}

규칙:
- '전체 평가', '종합', '모든 평가'는 overall.
- 수명/라이프/lifetime은 lifetime.
- Aging/에이징/잔여율/열화는 aging.
- BDV/절연파괴는 bdv.
- 질문에 없는 값을 추측하지 마라.
- 자재코드와 부품사는 위 목록의 값과 매칭될 때만 반환하라.

사용자 질문:
{question}
""".strip()

    try:
        client = Groq(api_key=_secret("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model=_secret("GROQ_MODEL") or DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "Return valid JSON only. Do not invent data."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_completion_tokens=300,
        )
        parsed = _extract_json(response.choices[0].message.content)
        if parsed.get("intent") not in {"lifetime", "aging", "bdv", "overall", "unknown"}:
            raise ValueError("invalid intent")
        return parsed, "groq", "Groq가 질문을 해석했습니다."
    except Exception as exc:
        # Includes 429 rate limit, auth errors, network errors, malformed output, etc.
        return None, "rule", f"Groq를 사용할 수 없어 규칙 기반으로 자동 전환했습니다. ({type(exc).__name__})"



def analyze_excel_result(question, context):
    """Excel/Python이 만든 조회 결과만 근거로 Groq가 설명한다.

    Returns (answer, mode, note). Groq 실패 시 answer=None.
    """
    if not groq_available():
        return None, "rule", "Groq API Key가 없거나 groq 패키지를 사용할 수 없습니다."

    # DataFrame이 아니라 JSON-safe dict/list만 받는다. 길이는 과도하게 커지지 않도록 제한.
    try:
        context_json = json.dumps(context, ensure_ascii=False, default=str)
    except Exception:
        context_json = str(context)
    context_json = context_json[:18000]

    prompt = f"""
너는 MLCC 신뢰성 평가 결과를 설명하는 분석 도우미다.
아래 [Excel 조회 결과]는 Python이 실제 Excel에서 조회/계산한 값이다.
반드시 이 데이터만 근거로 답하고, 없는 원인·규격·합격기준·수치를 추측하지 마라.

답변 원칙:
- 한국어로 간결하고 실무적으로 설명한다.
- 숫자를 언급할 때는 [Excel 조회 결과]의 값을 그대로 사용한다.
- '좋다/나쁘다/합격/불합격'은 판정 기준이 데이터에 없으면 단정하지 않는다.
- Aging에서 96시간까지는 실측, 96시간 초과는 회귀분석 예측값임을 구분한다.
- 비교 질문이면 같은 조건 안에서 차이를 설명한다.
- 사용자가 '주의할 점'을 물으면 데이터에서 확인되는 차이/범위와 해석상 주의사항을 말한다.
- 데이터로 답할 수 없는 내용은 '현재 Excel 데이터만으로는 판단할 수 없습니다'라고 명시한다.
- 3~6개의 짧은 bullet 중심으로 답한다.

[Excel 조회 결과]
{context_json}

[사용자 질문]
{question}
""".strip()

    try:
        client = Groq(api_key=_secret("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model=_secret("GROQ_MODEL") or DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "Use only the supplied Excel-derived context. Never invent measurements or pass/fail criteria."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.15,
            max_completion_tokens=700,
        )
        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            raise ValueError("empty answer")
        return answer, "groq", "Groq가 Excel 조회 결과를 바탕으로 분석했습니다."
    except Exception as exc:
        return None, "rule", f"Groq 분석을 사용할 수 없어 규칙 기반으로 자동 전환했습니다. ({type(exc).__name__})"
