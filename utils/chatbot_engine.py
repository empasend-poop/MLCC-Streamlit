import re
import pandas as pd
from utils.data_loader import get_lifetime_data, get_aging_data, get_bdv_data

def fmt(v, digits=1, suffix=""):
    if v is None or pd.isna(v): return "-"
    try: return f"{float(v):,.{digits}f}{suffix}"
    except (TypeError, ValueError): return str(v)

class ReliabilityChatbot:
    def __init__(self):
        self.life = get_lifetime_data().copy()
        self.aging = get_aging_data().copy()
        self.bdv = get_bdv_data().copy()
        for df in (self.life, self.aging, self.bdv):
            for c in ("부품사","자재코드"):
                if c in df.columns: df[c] = df[c].astype(str).str.strip()
        self.materials = sorted(set().union(*[
            set(df["자재코드"].dropna().astype(str)) if "자재코드" in df else set()
            for df in (self.life,self.aging,self.bdv)
        ]))
        self.suppliers = sorted(set().union(*[
            set(df["부품사"].dropna().astype(str)) if "부품사" in df else set()
            for df in (self.life,self.aging,self.bdv)
        ]))

    def find_material(self, q):
        for x in sorted(self.materials, key=len, reverse=True):
            if x.lower() in q.lower(): return x
        m=re.search(r"\b\d{4}-\d{5,8}\b",q)
        return m.group(0) if m else None

    def find_supplier(self,q):
        for x in sorted(self.suppliers,key=len,reverse=True):
            if x.lower() in q.lower(): return x
        return None

    def filt(self,df,m=None,s=None):
        x=df.copy()
        if m and "자재코드" in x: x=x[x["자재코드"]==m]
        if s and "부품사" in x: x=x[x["부품사"]==s]
        return x

    def latest(self,df):
        if df.empty:return None
        x=df.copy()
        if "업데이트일자" in x:
            x["_d"]=pd.to_datetime(x["업데이트일자"],errors="coerce")
            x=x.sort_values("_d")
        return x.iloc[-1]

    def availability(self,m):
        if not m:return "자재코드를 함께 입력해주세요."
        return "\n".join([
            f"**{m} 평가 데이터 보유현황**",
            f"- 수명평가: {'있음' if not self.filt(self.life,m).empty else '없음'}",
            f"- Aging평가: {'있음' if not self.filt(self.aging,m).empty else '없음'}",
            f"- BDV평가: {'있음' if not self.filt(self.bdv,m).empty else '없음'}"])

    def basic(self,m,s):
        for df in (self.aging,self.life,self.bdv):
            r=self.latest(self.filt(df,m,s))
            if r is not None:
                lines=["**기본 정보**"]
                for c,label,d,suf in [("부품사","부품사",0,""),("자재코드","자재코드",0,""),
                    ("정격전압(V)","정격전압",1," V"),("정격용량(uF)","정격용량",1," µF"),
                    ("Grade","Grade",0,""),("Size","Size",0,"")]:
                    if c in r.index and pd.notna(r[c]):
                        val=str(r[c]) if d==0 and not suf else fmt(r[c],d,suf)
                        lines.append(f"- {label}: {val}")
                return lines
        return ["**기본 정보**","- 해당 조건의 데이터가 없습니다."]

    def life_summary(self,m,s):
        d=self.filt(self.life,m,s)
        if d.empty:return ["**수명 평가**","- 해당 조건의 수명 평가 데이터가 없습니다."]
        lines=["**수명 평가**"]
        if "사용전압(V)" in d:d=d.sort_values("사용전압(V)")
        for _,r in d.iterrows():
            parts=[]
            if "사용전압(V)" in r.index:parts.append("사용전압 "+fmt(r["사용전압(V)"],1," V"))
            for c,label,dig in [("Bx수명","Bx수명",1),("Ea","Ea",3),("n","n",2),("형상모수","형상모수",2),("척도모수","척도모수",2)]:
                if c in r.index and pd.notna(r[c]):parts.append(f"{label} {fmt(r[c],dig)}")
            temps=[f"{c} {fmt(r[c],1)}" for c in r.index if re.fullmatch(r"\d{2,3}℃",str(c)) and pd.notna(r[c])]
            if temps:parts.append("온도별 수명: "+", ".join(temps))
            lines.append("- "+" / ".join(parts))
        return lines

    def aging_summary(self,m,s):
        d=self.filt(self.aging,m,s)
        if d.empty:return ["**Aging 평가**","- 해당 조건의 Aging 평가 데이터가 없습니다."]
        lines=["**Aging 평가**"]
        if "시험전압" in d:d=d.sort_values("시험전압")
        for _,r in d.iterrows():
            p=[]
            if "시험전압" in r.index:p.append("시험전압 "+fmt(r["시험전압"],1," V"))
            if "시험온도" in r.index:p.append("시험온도 "+fmt(r["시험온도"],0," ℃"))
            for c in ("25℃ / 0V","고온 / No Bias","고온 / DC Bias"):
                if c in r.index and pd.notna(r[c]):p.append(f"{c} {fmt(r[c],1,' µF')}")
            lines.append("- "+(" / ".join(p) if p else "평가 데이터 있음"))
        return lines

    def bdv_summary(self,m,s):
        r=self.latest(self.filt(self.bdv,m,s))
        if r is None:return ["**BDV 평가**","- 해당 조건의 BDV 평가 데이터가 없습니다."]
        lines=["**BDV 평가**"]
        for c,label,dig,suf in [("BDV 결과 (Typ.)","BDV 결과 (Typ.)",1," V"),("정격대비수준","정격 대비 BDV Typ.",1," 배"),
            ("1ppm Lower","1ppm Lower",1," V"),("1ppm Typ.","1ppm Typ.",1," V"),("1ppm Upper","1ppm Upper",1," V"),
            ("10ppm Lower","10ppm Lower",1," V"),("10ppm Typ.","10ppm Typ.",1," V"),("10ppm Upper","10ppm Upper",1," V")]:
            if c in r.index and pd.notna(r[c]):lines.append(f"- {label}: {fmt(r[c],dig,suf)}")
        return lines

    def answer(self,q):
        q=q.strip(); m=self.find_material(q); s=self.find_supplier(q)
        if any(x in q.lower() for x in ["보유현황","보유 현황","데이터 있","평가 있"]):return self.availability(m)
        if not m and not s:return "자재코드 또는 부품사를 질문에 포함해주세요.\n\n예: `Supplier A 2203-007317 전체 평가결과 알려줘`"
        if s and not m:
            mats=sorted(set().union(*[set(self.filt(df,s=s)["자재코드"].astype(str)) for df in (self.life,self.aging,self.bdv) if "자재코드" in df]))
            return f"**{s} 등록 자재코드**\n"+ "\n".join(f"- {x}" for x in mats)+"\n\n원하는 자재코드를 함께 입력해주세요."
        life=any(x in q.lower() for x in ["수명","lifetime"])
        aging=any(x in q.lower() for x in ["aging","에이징","잔여율"])
        bdv=any(x in q.lower() for x in ["bdv","1ppm","10ppm","절연파괴"])
        allq=any(x in q.lower() for x in ["전체","종합","모든","신뢰성","요약","한번에","한 번에"])
        lines=[]
        if allq or not (life or aging or bdv):
            lines=self.basic(m,s)+[""]+self.life_summary(m,s)+[""]+self.aging_summary(m,s)+[""]+self.bdv_summary(m,s)
        else:
            if life:lines+=self.life_summary(m,s)
            if aging:lines+=([""] if lines else [])+self.aging_summary(m,s)
            if bdv:lines+=([""] if lines else [])+self.bdv_summary(m,s)
        cond=f"**조회 조건:** 자재코드 {m}"+(f" / 부품사 {s}" if s else "")
        return cond+"\n\n"+"\n".join(lines)
