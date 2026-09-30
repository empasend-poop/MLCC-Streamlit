import re
import pandas as pd
from utils.data_loader import get_lifetime_data, get_aging_data, get_bdv_data


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
                    "구분": "실측" if hour <= 1000 else "회귀분석 예측",
                })
        return pd.DataFrame(rows)

    def available_aging_voltages(self, material=None, supplier=None):
        x = self.filt(self.aging, material, supplier)
        if x.empty or "시험전압" not in x.columns:
            return []
        return sorted(pd.to_numeric(x["시험전압"], errors="coerce").dropna().unique().tolist())

    def short_answer(self, q):
        material = self.find_material(q)
        supplier = self.find_supplier(q)
        temperature = self.find_temperature(q, 85)
        voltage = self.find_voltage(q)

        asks_aging = any(x in q.lower() for x in ["aging", "에이징", "잔여율"])
        asks_lifetime = any(x in q.lower() for x in ["수명", "lifetime"])

        if asks_aging:
            if not material and not supplier:
                return {"text": "자재코드 또는 부품사를 입력해주세요.", "show_aging": False, "show_lifetime": False}
            return {
                "text": "**Aging 비교**",
                "material": material,
                "supplier": supplier,
                "voltage": voltage,
                "temperature": temperature,
                "show_aging": True,
                "show_lifetime": False,
            }

        if asks_lifetime:
            if not material:
                return {"text": "수명 비교에는 자재코드를 입력해주세요.", "show_lifetime": False, "show_aging": False}
            return {
                "text": f"**{material} 수명평가 비교**",
                "material": material,
                "supplier": supplier,
                "temperature": temperature,
                "voltage": voltage,
                "show_lifetime": True,
                "show_aging": False,
            }

        return {
            "text": "질문에 `수명` 또는 `Aging`을 포함해주세요.",
            "show_lifetime": False,
            "show_aging": False,
        }
