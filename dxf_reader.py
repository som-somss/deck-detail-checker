import re
import ezdxf
from models import Spec

TYPE_RE=re.compile(r"^M\d{2}-\d+(?:-\d+)?$",re.I)

def _txt(e):
    try:
        return (e.dxf.text if e.dxftype()=="TEXT" else e.plain_text()).strip()
    except:
        return ""

def _m(v):
    v=float(v)
    return v/1000.0 if abs(v)>10 else v

def _outline_spec(e, typ):
    pts=list(e.get_points("xy"))
    if len(pts)<4 or not e.closed:
        return None
    xs=[float(p[0]) for p in pts]
    ys=[float(p[1]) for p in pts]
    ymin,ymax=min(ys),max(ys)
    height=ymax-ymin
    width=max(xs)-min(xs)
    # DECK 평면 외곽만: 청람교 상세도의 실제 패널 범위
    if not (300 <= width <= 2500 and 800 <= height <= 5000):
        return None

    tol=max(2.0,height*0.002)
    top=[float(p[0]) for p in pts if abs(float(p[1])-ymax)<=tol]
    bot=[float(p[0]) for p in pts if abs(float(p[1])-ymin)<=tol]
    if len(top)<2 or len(bot)<2:
        return None
    top_w=max(top)-min(top)
    bot_w=max(bot)-min(bot)
    if not (250<=top_w<=2500 and 250<=bot_w<=2500):
        return None
    return Spec(typ,_m(top_w),_m(bot_w),_m(height))

def read_dxf_specs(path):
    doc=ezdxf.readfile(path)
    msp=doc.modelspace()

    texts=[]
    all_types=set()
    table_pos={}
    title_pos={}
    for e in msp:
        if e.dxftype() not in ("TEXT","MTEXT"):
            continue
        t=_txt(e)
        if not t:
            continue
        p=e.dxf.insert
        x,y=float(p.x),float(p.y)
        layer=e.dxf.layer
        texts.append((x,y,t,layer))
        if TYPE_RE.fullmatch(t):
            all_types.add(t)
            if layer=="CZ-DIMT":
                table_pos[t]=(x,y)
            if layer=="CZ-TEX0":
                title_pos[t]=(x,y)

    # 1. 상세도 재료표
    material={}
    for typ,(ax,ay) in table_pos.items():
        cells=[]
        for x,y,t,layer in texts:
            if layer!="데크규격":
                continue
            # TYPE 재료표 기준: 아래쪽의 데크규격 셀
            if -150 <= x-ax <= 550 and -260 <= y-ay <= -40:
                try:
                    cells.append((x,y,float(t.replace(",",""))))
                except:
                    pass

        # y행으로 묶는다.
        groups=[]
        for c in cells:
            group=sorted([q for q in cells if abs(q[1]-c[1])<8],key=lambda q:q[0])
            ky=round(sum(q[1] for q in group)/len(group),1)
            if not any(abs(ky+k)<1 for k,_ in groups):
                groups.append((ky,group))

        two=[g for _,g in groups if len(g)>=2]
        one=[g for _,g in groups if len(g)==1]

        if len(cells)>=3 and two and one:
            # 경사형: 같은 행의 폭 2개 + 별도 행 길이
            w=two[0]
            material[typ]=Spec(typ,float(w[0][2]),float(w[1][2]),float(one[0][0][2]),ax,ay)
        elif len(cells)>=2:
            # 일반형: 폭 + 길이
            s=sorted(cells,key=lambda q:q[0])
            material[typ]=Spec(typ,float(s[0][2]),float(s[0][2]),float(s[1][2]),ax,ay)

    # 2. 실제 평면도 형상
    # TYPE 제목 주변의 닫힌 CS-CONC 외곽선에서 상부폭/하부폭/길이를 직접 계산한다.
    geometry={}
    outlines=[]
    for e in msp.query("LWPOLYLINE"):
        if e.dxf.layer!="CS-CONC" or not e.closed:
            continue
        pts=list(e.get_points("xy"))
        if not pts:
            continue
        cx=sum(float(p[0]) for p in pts)/len(pts)
        cy=sum(float(p[1]) for p in pts)/len(pts)
        outlines.append((cx,cy,e))

    for typ,(tx,ty) in title_pos.items():
        candidates=[]
        for cx,cy,e in outlines:
            dx,dy=cx-tx,cy-ty
            # 상면 평면도는 TYPE 제목 아래쪽 영역.
            if not (-4500<=dx<=4500 and -5000<=dy<=-900):
                continue
            spec=_outline_spec(e,typ)
            if not spec:
                continue
            # 재료표를 답으로 복사하지 않는다.
            # 제목에서 가까운 실제 DECK 외곽형상을 우선한다.
            score=abs(dy+2400)+0.12*abs(dx)
            candidates.append((score,spec))
        if candidates:
            candidates.sort(key=lambda q:q[0])
            geometry[typ]=candidates[0][1]

    return geometry,material,all_types
