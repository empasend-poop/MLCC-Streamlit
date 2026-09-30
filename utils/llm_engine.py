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
