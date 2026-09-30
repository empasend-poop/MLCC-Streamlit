import re
import pandas as pd
from utils.data_loader import get_lifetime_data, get_aging_data, get_bdv_data


def _canonical_supplier(value):
    """Excel의 'Supplie A'와 질문의 'Supplier A'를 동일하게 취급."""
    text = "" if pd.isna(value) else str(value).strip()
    text = re.sub(r"(?i)^supplie\s+", "Supplier ", text)
    return " ".join(text.split())


def _fmt(value, digits=1, suffix=""):
    if value is None or pd.isna(value):
        return "-"
    try:
        return f"{float(value):,.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


class ReliabilityChatbot:
    def __init__(self):
        self.life = get_lifetime_data().copy()
        self.aging = get_aging_data().copy()
        self.bdv = get_bdv_data().copy()

        for df in (self.life, self.aging, self.bdv):
            if "자재코드" in df.columns:
                df["자재코드"] = df["자재코드"].astype(str).str.strip()
            if "부품사" in df.columns:
                df["_부품사표시"] = df["부품사"].map(_canonical_supplier)

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

    def find_material(self, question):
        for material in sorted(self.materials, key=len, reverse=True):
            if material.lower() in question.lower():
                return material
        match = re.search(r"\b\d{4}-\d{5,8}\b", question)
        return match.group(0) if match else None

    def find_supplier(self, question):
        normalized = _canonical_supplier(question)
        for supplier in sorted(self.suppliers, key=len, reverse=True):
            if supplier.lower() in normalized.lower():
                return supplier
        return None

    @staticmethod
    def find_temperature(question, default=85):
        patterns = [
            r"(\d{2,3})\s*℃",
            r"(\d{2,3})\s*°\s*C",
            r"(\d{2,3})\s*도",
        ]
        for pattern in patterns:
            match = re.search(pattern, question, flags=re.I)
            if match:
                return int(match.group(1))
        return default

    def filt(self, df, material=None, supplier=None):
        result = df.copy()
        if material and "자재코드" in result.columns:
            result = result[result["자재코드"] == material]
        if supplier and "_부품사표시" in result.columns:
            result = result[result["_부품사표시"] == _canonical_supplier(supplier)]
        return result

    def lifetime_comparison(self, material, temperature=85):
        """동일 자재코드의 부품사/사용전압별 특정온도 수명을 반환."""
        column = f"{temperature}℃"
        data = self.filt(self.life, material=material)

        if data.empty or column not in data.columns:
            return pd.DataFrame()

        cols = ["_부품사표시", "사용전압(V)", column]
        if "Size" in data.columns:
            cols.append("Size")

        result = data[cols].copy()
        result[column] = pd.to_numeric(result[column], errors="coerce")
        result["사용전압(V)"] = pd.to_numeric(result["사용전압(V)"], errors="coerce")
        result = result.dropna(subset=[column])

        result = result.rename(columns={
            "_부품사표시": "부품사",
            column: "예측수명",
        })

        result["조건"] = (
            result["부품사"].astype(str)
            + " / "
            + result["사용전압(V)"].map(lambda x: f"{x:g}V")
        )
        return result.sort_values(["부품사", "사용전압(V)"]).reset_index(drop=True)

    def lifetime_rows(self, material, supplier=None):
        data = self.filt(self.life, material, supplier)
        if data.empty:
            return pd.DataFrame()

        keep = [c for c in [
            "_부품사표시", "사용전압(V)", "Bx수명", "Ea", "n",
            "형상모수", "척도모수", "85℃"
        ] if c in data.columns]

        result = data[keep].copy().rename(columns={"_부품사표시": "부품사"})
        return result.sort_values(["부품사", "사용전압(V)"]).reset_index(drop=True)

    def short_answer(self, question):
        material = self.find_material(question)
        supplier = self.find_supplier(question)
        temperature = self.find_temperature(question, 85)

        if not material:
            return {
                "text": "자재코드를 입력해주세요.",
                "material": None,
                "supplier": supplier,
                "temperature": temperature,
                "show_lifetime": False,
            }

        asks_lifetime = any(x in question.lower() for x in ["수명", "lifetime"])
        asks_all = any(x in question.lower() for x in ["전체", "종합", "신뢰성", "요약"])

        if asks_lifetime or asks_all:
            rows = self.lifetime_rows(material, supplier)

            if rows.empty:
                target = f"{supplier} / " if supplier else ""
                text = f"**{target}{material}** 수명평가 데이터가 없습니다."
            else:
                supplier_count = rows["부품사"].nunique()
                text = (
                    f"**{material} 수명평가** · "
                    f"{temperature}℃ 기준 · "
                    f"{supplier_count}개 부품사 비교"
                )
                if supplier:
                    text = (
                        f"**{supplier} / {material} 수명평가** · "
                        f"{temperature}℃ 기준"
                    )

            return {
                "text": text,
                "material": material,
                "supplier": supplier,
                "temperature": temperature,
                "show_lifetime": True,
            }

        return {
            "text": f"**{material}** 데이터를 조회했습니다.",
            "material": material,
            "supplier": supplier,
            "temperature": temperature,
            "show_lifetime": False,
        }
