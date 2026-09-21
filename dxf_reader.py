import re, math
import ezdxf
from models import Spec

TYPE_RE=re.compile(r"^M\d{2}-\d+(?:-\d+)?$",re.I)
SIZE_RE=re.compile(r"(?<!\d)(\d{3,4})\s*[xX×]\s*(\d{3,4})(?!\d)")
NUM_RE=re.compile(r"^\s*(\d{3,4}(?:\.\d+)?)\s*$")

def clean(s):
    return (s or "").replace(r"\P"," ").replace("{","").replace("}","").strip()

def etext(e):
    try:
        return clean(e.dxf.text if e.dxftype()=="TEXT" else e.plain_text())
    except:return ""

def point(e):
    try:
        p=e.dxf.insert; return float(p.x),float(p.y)
    except:return 0.0,0.0

def mm_to_m(v):
    v=float(v)
    return v/1000.0 if v>10 else v

def read_dxf_specs(path):
    doc=ezdxf.readfile(path); msp=doc.modelspace()
    texts=[]
    for e in msp:
        if e.dxftype() in ("TEXT","MTEXT"):
            t=etext(e)
            if t:
                x,y=point(e); texts.append({"x":x,"y":y,"t":t,"layer":e.dxf.layer})

    # TYPE는 레이어명에 의존하지 않는다. 동일 TYPE이 여러 번 있으면 모두 후보로 보존.
    types=[z for z in texts if TYPE_RE.fullmatch(z["t"])]
    if not types:
        raise ValueError("DXF에서 Mxx-xxx 형식의 TYPE 문자를 찾지 못했습니다.")

    material={}
    geometry={}
    debug={}

    for a in types:
        typ=a["t"]; ax,ay=a["x"],a["y"]

        # 1) 재료표 제원: TYPE 주변의 '규격/제원(mm)/전체 수량' 문자를 이용해 표 영역 확인.
        near=[z for z in texts if abs(z["x"]-ax)<2500 and abs(z["y"]-ay)<1200]
        table_words=sum(any(k in z["t"].replace(" ","") for k in ("제원","개당수량","전체수량","파형철선","철근")) for z in near)
        mat=None
        if table_words>=2:
            # 가장 우선: 1.150X2.220 / 1150X2220 같은 한 개의 규격 문자열
            candidates=[]
            for z in near:
                m=SIZE_RE.search(z["t"])
                if m:
                    b,l=mm_to_m(m.group(1)),mm_to_m(m.group(2))
                    candidates.append((abs(z["y"]-ay)+0.15*abs(z["x"]-ax),b,l,z))
            if candidates:
                _,b,l,z=min(candidates,key=lambda q:q[0])
                mat=Spec(typ,b,b,l,ax,ay)
            else:
                # 분리된 숫자 셀: TYPE 아래쪽 가까운 숫자들을 수집
                nums=[]
                for z in near:
                    m=NUM_RE.fullmatch(z["t"].replace(",",""))
                    if m:
                        v=float(m.group(1))
                        if 250<=v<=5000:
                            nums.append((z["x"],z["y"],mm_to_m(v)))
                # 같은 y행에서 2~3개의 제원 숫자를 찾음
                rows=[]
                for z in nums:
                    row=[q for q in nums if abs(q[1]-z[1])<15]
                    vals=sorted({round(q[2],6) for q in row})
                    if len(vals)>=2:rows.append((abs(z[1]-ay),vals))
                if rows:
                    vals=min(rows,key=lambda q:q[0])[1]
                    # 폭은 보통 0.3~2m, 길이는 가장 큰 값
                    length=max(vals)
                    widths=[v for v in vals if v!=length]
                    if widths:
                        mat=Spec(typ,widths[0],widths[-1],length,ax,ay)
        if mat:
            # 같은 TYPE 후보 중 표 단어가 더 많은 것을 채택
            old=debug.get(("mat",typ),(-1,None))
            if table_words>old[0]:
                material[typ]=mat; debug[("mat",typ)]=(table_words,a)

        # 2) 실제 형상 제원:
        # TYPE 주변 DIMENSION의 실제 측정값을 읽는다.
        # 도면마다 배치가 달라 완전 확정이 어려운 경우 '확인필요'로 남기기 위한 후보값 생성.
        dims=[]
        for e in msp.query("DIMENSION"):
            try:
                dp=e.dxf.defpoint
                if abs(dp.x-ax)<6500 and abs(dp.y-ay)<5000:
                    v=float(e.get_measurement())
                    if 250<=v<=5000:dims.append(v/1000.0)
            except:pass
        if dims:
            # Excel/재료표를 답으로 사용하지 않고, 반복되는 큰 DIMENSION 값에서 폭/길이 후보만 구성.
            vals=sorted(set(round(v,3) for v in dims))
            # 재료표가 있으면 그 근처 치수값 중 가장 가까운 실제 DIMENSION을 고른다.
            # 이는 숫자를 복사하는 것이 아니라 CAD DIMENSION 측정값을 선택하는 용도.
            if mat:
                def nearest(target):
                    return min(vals,key=lambda v:abs(v-target)) if vals else None
                b1=nearest(mat.b1)
                b2=nearest(mat.b2 if mat.b2 is not None else mat.b1)
                ln=nearest(mat.length)
                if b1 is not None and ln is not None:
                    geometry[typ]=Spec(typ,b1,b2,ln,ax,ay)

    return geometry,material
