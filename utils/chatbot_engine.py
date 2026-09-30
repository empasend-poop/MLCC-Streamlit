import re
import pandas as pd
from utils.data_loader import get_lifetime_data, get_aging_data, get_bdv_data
from utils.llm_engine import interpret_question, analyze_excel_result


def _canonical_supplier(value):
    text = "" if pd.isna(value) else str(value).strip()
    text = re.sub(r"(?i)^supplie\s+", "Supplier ", text)
    return " ".join(text.split())


def _hour_columns(columns):
    result = []
    pattern = re.compile(r"^\s*([\d,]+)\s*hr\s*$", re.I)
    for col in columns:
        m = pattern.match(str(col))
        if m:
            result.append((col, int(m.group(1).replace(",", ""))))
    return sorted(result, key=lambda x: x[1])


class ReliabilityChatbot:
    def __init__(self):
        self.life = get_lifetime_data().copy()
        self.aging = get_aging_data().copy()
        self.bdv = get_bdv_data().copy()

        for df in (self.life, self.aging, self.bdv):
            df.columns = [str(c).replace("\n", " ").strip() for c in df.columns]
            if "자재코드" in df.columns:
                df["자재코드"] = df["자재코드"].astype(str).str.strip()
            if "부품사" in df.columns:
                df["_부품사표시"] = df["부품사"].map(_canonical_supplier)

        for col in ["사용전압(V)"]:
            if col in self.life.columns:
                self.life[col] = pd.to_numeric(self.life[col], errors="coerce")
        for col in ["시험전압", "시험온도", "① 25℃, 0V"]:
            if col in self.aging.columns:
                self.aging[col] = pd.to_numeric(self.aging[col], errors="coerce")

        self.materials = sorted(set().union(*[
            set(df["자재코드"].dropna().astype(str))
            if "자재코드" in df.columns else set()
            for df in (self.life, self.aging, self.bdv)
        ]))
        self.suppliers = sorted(set().union(*[
            set(df["_부품사표시"].dropna().astype(str))
            if "_부품사표시" in df.columns else set()
            for df in (self.life, self.aging, self.bdv)
        ]))

    def find_material(self, q):
        for material in sorted(self.materials, key=len, reverse=True):
            if material.lower() in q.lower():
                return material
        m = re.search(r"\b\d{4}-\d{5,8}\b", q)
        return m.group(0) if m else None

    def find_supplier(self, q):
        qn = _canonical_supplier(q)
        for supplier in sorted(self.suppliers, key=len, reverse=True):
            if supplier.lower() in qn.lower():
                return supplier
        return None

    @staticmethod
    def find_temperature(q, default=85):
        for p in [r"(\d{2,3})\s*℃", r"(\d{2,3})\s*°\s*C", r"(\d{2,3})\s*도"]:
            m = re.search(p, q, re.I)
            if m:
                return int(m.group(1))
        return default

    @staticmethod
    def find_voltage(q):
        m = re.search(r"(\d+(?:\.\d+)?)\s*[vV]\b", q)
        return float(m.group(1)) if m else None

    def filt(self, df, material=None, supplier=None):
        x = df.copy()
        if material and "자재코드" in x.columns:
            x = x[x["자재코드"] == material]
        if supplier and "_부품사표시" in x.columns:
            x = x[x["_부품사표시"] == _canonical_supplier(supplier)]
        return x

    def lifetime_comparison(self, material, temperature=85, voltage=None):
        col = f"{temperature}℃"
        x = self.filt(self.life, material=material)
        if voltage is not None and "사용전압(V)" in x.columns:
            x = x[(x["사용전압(V)"] - float(voltage)).abs() < 1e-9]
        if x.empty or col not in x.columns:
            return pd.DataFrame()
        out = x[["_부품사표시", "사용전압(V)", col]].copy()
        out[col] = pd.to_numeric(out[col], errors="coerce")
        out = out.dropna(subset=[col]).rename(
            columns={"_부품사표시": "부품사", col: "예측수명"}
        )
        return out.sort_values(["부품사", "사용전압(V)"]).reset_index(drop=True)

    def lifetime_rows(self, material, supplier=None, temperature=85, voltage=None):
        x = self.filt(self.life, material, supplier)
        if voltage is not None and "사용전압(V)" in x.columns:
            x = x[(x["사용전압(V)"] - float(voltage)).abs() < 1e-9]
        if x.empty:
            return pd.DataFrame()
        temp_col = f"{temperature}℃"
        keep = [c for c in [
            "_부품사표시", "사용전압(V)", "Bx수명", "Ea", "n",
            "형상모수", "척도모수", temp_col
        ] if c in x.columns]
        return (
            x[keep].copy()
            .rename(columns={"_부품사표시": "부품사"})
            .sort_values(["부품사", "사용전압(V)"])
            .reset_index(drop=True)
        )

    def aging_comparison(self, material=None, supplier=None, voltage=None):
        x = self.filt(self.aging, material, supplier)
        if voltage is not None and "시험전압" in x.columns:
            x = x[(x["시험전압"] - float(voltage)).abs() < 1e-9]
        if x.empty:
            return pd.DataFrame()

        hours = _hour_columns(x.columns)
        rows = []
        for _, r in x.iterrows():
            initial = pd.to_numeric(r.get("① 25℃, 0V"), errors="coerce")
            for col, hour in hours:
                value = pd.to_numeric(r.get(col), errors="coerce")
                if pd.isna(value):
                    continue
                rows.append({
                    "부품사": r["_부품사표시"],
                    "자재코드": r["자재코드"],
                    "시험전압": float(r["시험전압"]) if pd.notna(r["시험전압"]) else None,
                    "시간(hr)": hour,
                    "잔여용량(uF)": float(value),
                    "잔여율(%)": float(value / initial * 100) if pd.notna(initial) and initial != 0 else None,
                    "구분": "실측" if hour <= 96 else "회귀분석 예측",
                })
        return pd.DataFrame(rows)

    def available_aging_voltages(self, material=None, supplier=None):
        x = self.filt(self.aging, material, supplier)
        if x.empty or "시험전압" not in x.columns:
            return []
        return sorted(pd.to_numeric(x["시험전압"], errors="coerce").dropna().unique().tolist())


    def bdv_comparison(self, material, supplier=None):
        x = self.filt(self.bdv, material, supplier)
        if x.empty:
            return pd.DataFrame()

        keep = [c for c in [
            "_부품사표시", "자재코드", "정격전압(V)", "BDV 결과 (Typ.)",
            "1ppm Lower", "1ppm Typ.", "1ppm Upper",
            "10ppm Lower", "10ppm Typ.", "10ppm Upper",
            "1ppm Lower / 정격전압 (배)", "정격전압 / 1ppm Lower (%)"
        ] if c in x.columns]

        out = x[keep].copy().rename(columns={"_부품사표시": "부품사"})
        numeric_cols = [c for c in out.columns if c not in ["부품사", "자재코드"]]
        for c in numeric_cols:
            out[c] = pd.to_numeric(out[c], errors="coerce")
        return out.sort_values("부품사").reset_index(drop=True)

    def evaluation_availability(self, material):
        def exists(df):
            return not self.filt(df, material=material).empty

        return {
            "수명": exists(self.life),
            "Aging": exists(self.aging),
            "BDV": exists(self.bdv),
        }

    @staticmethod
    def _records(df, limit=80):
        if df is None or df.empty:
            return []
        clean = df.head(limit).copy()
        clean = clean.where(pd.notna(clean), None)
        return clean.to_dict(orient="records")

    def build_result_context(self, result):
        """현재 화면에 표시할 데이터를 LLM 후속질문용 JSON-safe context로 만든다."""
        material = result.get("material")
        supplier = result.get("supplier")
        voltage = result.get("voltage")
        temperature = result.get("temperature", 85)
        context = {
            "material": material,
            "supplier_filter": supplier,
            "voltage_filter": voltage,
            "temperature": temperature,
            "aging_measurement_rule": "96시간까지 실측, 96시간 초과는 회귀분석 예측",
        }

        if result.get("show_lifetime") and material:
            data = self.lifetime_comparison(material, temperature, voltage)
            if supplier and not data.empty:
                data = data[data["부품사"] == supplier]
            context["evaluation"] = "lifetime"
            context["lifetime_rows"] = self._records(data)

        elif result.get("show_aging"):
            volts = self.available_aging_voltages(material, supplier)
            chosen = voltage if voltage in volts else (volts[0] if volts else None)
            data = self.aging_comparison(material, supplier, chosen) if chosen is not None else pd.DataFrame()
            context["evaluation"] = "aging"
            context["voltage_filter"] = chosen
            context["aging_rows"] = self._records(data)

        elif result.get("show_bdv") and material:
            data = self.bdv_comparison(material, supplier)
            context["evaluation"] = "bdv"
            context["bdv_rows"] = self._records(data)

        elif result.get("show_overall") and material:
            context["evaluation"] = "overall"
            context["availability"] = self.evaluation_availability(material)
            life = self.lifetime_comparison(material, temperature, voltage)
            if supplier and not life.empty:
                life = life[life["부품사"] == supplier]
            context["lifetime_rows"] = self._records(life)
            volts = self.available_aging_voltages(material, supplier)
            chosen = voltage if voltage in volts else (volts[0] if volts else None)
            aging = self.aging_comparison(material, supplier, chosen) if chosen is not None else pd.DataFrame()
            context["aging_voltage"] = chosen
            context["aging_rows"] = self._records(aging)
            context["bdv_rows"] = self._records(self.bdv_comparison(material, supplier))
        else:
            return None
        return context

    @staticmethod
    def _looks_like_followup(q):
        ql = q.lower().strip()
        cues = [
            "이 결과", "이결과", "방금", "위 결과", "위의 결과", "이 데이터", "이데이터",
            "주의", "해석", "요약", "설명", "차이", "의미", "어때", "어떻게 보여",
            "뭐가 중요", "무엇이 중요", "왜", "특징", "포인트",
        ]
        return any(c in ql for c in cues)

    def _context_fallback_answer(self, context):
        ev = context.get("evaluation") if context else None
        if ev == "aging":
            return "직전 Aging 결과를 기준으로 보면 **96시간까지는 실측**, 그 이후는 **회귀분석 예측값**입니다. 상세 해석은 Groq 사용 가능 시 Excel 조회값을 함께 전달해 분석합니다."
        if ev == "bdv":
            return "직전 BDV 비교 결과가 유지되어 있습니다. Groq를 사용할 수 없을 때는 표의 `BDV 결과 (Typ.)`, `1ppm Lower`, `10ppm Lower` 값을 직접 비교해 확인해주세요."
        if ev == "lifetime":
            return "직전 수명 비교 결과가 유지되어 있습니다. Groq를 사용할 수 없을 때는 동일 전압·동일 온도 조건의 예측수명을 기준으로 비교해주세요."
        return "직전 Excel 조회 결과는 유지되어 있지만 현재는 Groq 분석을 사용할 수 없어 규칙 기반으로 처리했습니다."

    def _rule_answer(self, q):
        material = self.find_material(q)
        supplier = self.find_supplier(q)
        temperature = self.find_temperature(q, 85)
        voltage = self.find_voltage(q)
        q_lower = q.lower()

        asks_aging = any(x in q_lower for x in ["aging", "에이징", "잔여율"])
        asks_bdv = "bdv" in q_lower
        asks_lifetime = any(x in q_lower for x in ["수명", "lifetime"])
        asks_overall = any(x in q_lower for x in ["전체 평가", "전체평가", "종합", "모든 평가"])

        if asks_overall:
            if not material:
                return {
                    "text": "전체 평가결과를 보려면 자재코드를 입력해주세요.",
                    "show_overall": False, "show_lifetime": False,
                    "show_aging": False, "show_bdv": False,
                }
            return {
                "text": f"**{material} 전체 평가결과**",
                "material": material,
                "supplier": supplier,
                "temperature": temperature,
                "voltage": voltage,
                "show_overall": True,
                "show_lifetime": False,
                "show_aging": False,
                "show_bdv": False,
            }

        if asks_bdv:
            if not material:
                return {
                    "text": "BDV 비교에는 자재코드를 입력해주세요.",
                    "show_bdv": False, "show_lifetime": False, "show_aging": False,
                }
            return {
                "text": f"**{material} BDV 부품사 비교**",
                "material": material,
                "supplier": supplier,
                "show_bdv": True,
                "show_lifetime": False,
                "show_aging": False,
            }

        if asks_aging:
            if not material and not supplier:
                return {
                    "text": "자재코드 또는 부품사를 입력해주세요.",
                    "show_aging": False, "show_lifetime": False, "show_bdv": False,
                }
            return {
                "text": "**Aging 비교**",
                "material": material,
                "supplier": supplier,
                "voltage": voltage,
                "temperature": temperature,
                "show_aging": True,
                "show_lifetime": False,
                "show_bdv": False,
            }

        if asks_lifetime:
            if not material:
                return {
                    "text": "수명 비교에는 자재코드를 입력해주세요.",
                    "show_lifetime": False, "show_aging": False, "show_bdv": False,
                }
            return {
                "text": f"**{material} 수명평가 비교**",
                "material": material,
                "supplier": supplier,
                "temperature": temperature,
                "voltage": voltage,
                "show_lifetime": True,
                "show_aging": False,
                "show_bdv": False,
            }

        return {
            "text": "질문에 `수명`, `Aging`, `BDV`, 또는 `전체 평가결과`를 포함해주세요.",
            "show_lifetime": False, "show_aging": False,
            "show_bdv": False, "show_overall": False,
        }

    def short_answer(self, q, previous_context=None):
        """
        Groq 우선 -> 실패/429/키 없음/파싱 실패 시 기존 규칙 기반 자동 fallback.
        실제 Excel 조회와 그래프용 데이터는 항상 기존 Python 로직이 담당.
        """
        # "이 결과에서...", "방금 결과..." 같은 질문은 직전 Excel 조회 결과를 문맥으로 사용한다.
        if previous_context and self._looks_like_followup(q):
            answer, analysis_mode, analysis_note = analyze_excel_result(q, previous_context)
            if answer:
                return {
                    "text": "### 🧠 AI 분석\n" + answer,
                    "answer_mode": "groq_analysis",
                    "mode_note": analysis_note,
                    "context": previous_context,
                    "show_lifetime": False, "show_aging": False,
                    "show_bdv": False, "show_overall": False,
                }
            return {
                "text": self._context_fallback_answer(previous_context),
                "answer_mode": "rule", "mode_note": analysis_note,
                "context": previous_context,
                "show_lifetime": False, "show_aging": False,
                "show_bdv": False, "show_overall": False,
            }

        parsed, mode, note = interpret_question(q, self.materials, self.suppliers)

        if parsed is None:
            result = self._rule_answer(q)
            result["answer_mode"] = "rule"
            result["mode_note"] = note
            context = self.build_result_context(result)
            if context:
                result["context"] = context
            return result

        intent = parsed.get("intent", "unknown")
        material = parsed.get("material")
        supplier = parsed.get("supplier")
        voltage = parsed.get("voltage")
        temperature = parsed.get("temperature")

        # Normalize/validate LLM-extracted entities against Excel-known values.
        if material not in self.materials:
            material = self.find_material(q)
        if supplier not in self.suppliers:
            supplier = self.find_supplier(q)

        try:
            voltage = float(voltage) if voltage is not None else self.find_voltage(q)
        except (TypeError, ValueError):
            voltage = self.find_voltage(q)
        try:
            temperature = int(float(temperature)) if temperature is not None else self.find_temperature(q, 85)
        except (TypeError, ValueError):
            temperature = self.find_temperature(q, 85)

        if intent == "overall":
            if not material:
                result = self._rule_answer(q)
            else:
                result = {
                    "text": f"**{material} 전체 평가결과**",
                    "material": material, "supplier": supplier,
                    "temperature": temperature, "voltage": voltage,
                    "show_overall": True, "show_lifetime": False,
                    "show_aging": False, "show_bdv": False,
                }
        elif intent == "bdv":
            if not material:
                result = self._rule_answer(q)
            else:
                result = {
                    "text": f"**{material} BDV 부품사 비교**",
                    "material": material, "supplier": supplier,
                    "show_bdv": True, "show_lifetime": False,
                    "show_aging": False, "show_overall": False,
                }
        elif intent == "aging":
            if not material and not supplier:
                result = self._rule_answer(q)
            else:
                result = {
                    "text": "**Aging 비교**",
                    "material": material, "supplier": supplier,
                    "voltage": voltage, "temperature": temperature,
                    "show_aging": True, "show_lifetime": False,
                    "show_bdv": False, "show_overall": False,
                }
        elif intent == "lifetime":
            if not material:
                result = self._rule_answer(q)
            else:
                result = {
                    "text": f"**{material} 수명평가 비교**",
                    "material": material, "supplier": supplier,
                    "temperature": temperature, "voltage": voltage,
                    "show_lifetime": True, "show_aging": False,
                    "show_bdv": False, "show_overall": False,
                }
        else:
            result = self._rule_answer(q)

        result["answer_mode"] = "groq"
        result["mode_note"] = note
        context = self.build_result_context(result)
        if context:
            result["context"] = context
            analysis, analysis_mode, analysis_note = analyze_excel_result(
                "현재 조회 결과에서 핵심적으로 확인할 내용을 짧게 요약해줘.", context
            )
            if analysis:
                result["ai_analysis"] = analysis
        return result

