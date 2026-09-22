import re
from collections import defaultdict
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
    xs=[float(p[0]) for p in pts]; ys=[float(p[1]) for p in pts]
    ymin,ymax=min(ys),max(ys); height=ymax-ymin; width=max(xs)-min(xs)
    if not (300 <= width <= 2500 and 800 <= height <= 5000):
        return None
    tol=max(2.0,height*0.002)
    top=[float(p[0]) for p in pts if abs(float(p[1])-ymax)<=tol]
    bot=[float(p[0]) for p in pts if abs(float(p[1])-ymin)<=tol]
    if len(top)<2 or len(bot)<2:
        return None
    top_w=max(top)-min(top); bot_w=max(bot)-min(bot)
    if not (250<=top_w<=2500 and 250<=bot_w<=2500):
        return None
    return Spec(typ,_m(top_w),_m(bot_w),_m(height))

def _dimension_measurement(e):
    try:
        return abs(float(e.get_measurement()))
    except:
        return None

def read_dxf_specs(path):
    doc=ezdxf.readfile(path); msp=doc.modelspace()
    texts=[]; all_types=set(); table_pos={}; title_pos={}
    for e in msp:
        if e.dxftype() not in ("TEXT","MTEXT"): continue
        t=_txt(e)
        if not t: continue
        p=e.dxf.insert; x,y=float(p.x),float(p.y); layer=e.dxf.layer
        texts.append((x,y,t,layer))
        if TYPE_RE.fullmatch(t):
            all_types.add(t)
            if layer=="CZ-DIMT": table_pos[t]=(x,y)
            if layer=="CZ-TEX0": title_pos[t]=(x,y)

    # 상세도 재료표의 데크 폭/길이
    material={}
    for typ,(ax,ay) in table_pos.items():
        cells=[]
        for x,y,t,layer in texts:
            if layer!="데크규격": continue
            if -150 <= x-ax <= 550 and -260 <= y-ay <= -40:
                try: cells.append((x,y,float(t.replace(",",""))))
                except: pass
        groups=[]
        for c in cells:
            group=sorted([q for q in cells if abs(q[1]-c[1])<8],key=lambda q:q[0])
            ky=round(sum(q[1] for q in group)/len(group),1)
            if not any(abs(ky-k)<1 for k,_ in groups): groups.append((ky,group))
        two=[g for _,g in groups if len(g)>=2]; one=[g for _,g in groups if len(g)==1]
        if len(cells)>=3 and two and one:
            w=two[0]; material[typ]=Spec(typ,float(w[0][2]),float(w[1][2]),float(one[0][0][2]),ax,ay)
        elif len(cells)>=2:
            s=sorted(cells,key=lambda q:q[0])
            material[typ]=Spec(typ,float(s[0][2]),float(s[0][2]),float(s[1][2]),ax,ay)

    # 평면도(상면) 실제 외곽
    geometry={}; outlines=[]
    for e in msp.query("LWPOLYLINE"):
        if e.dxf.layer!="CS-CONC" or not e.closed: continue
        pts=list(e.get_points("xy"))
        if not pts: continue
        cx=sum(float(p[0]) for p in pts)/len(pts); cy=sum(float(p[1]) for p in pts)/len(pts)
        outlines.append((cx,cy,e))
    for typ,(tx,ty) in title_pos.items():
        cand=[]
        for cx,cy,e in outlines:
            dx,dy=cx-tx,cy-ty
            if not (-4500<=dx<=4500 and -5000<=dy<=-900): continue
            spec=_outline_spec(e,typ)
            if spec: cand.append((abs(dy+2400)+0.12*abs(dx),spec))
        if cand:
            cand.sort(key=lambda q:q[0]); geometry[typ]=cand[0][1]

    # 추가 제원: 두께 / 일반형·평판형 / 리브 길이·수량
    extra={}
    dims=list(msp.query("DIMENSION"))
    rib_polys=[]
    for e in msp.query("LWPOLYLINE"):
        if e.dxf.layer!="CS-CONC-MINR" or not e.closed: continue
        pts=list(e.get_points("xy"))
        if len(pts)<4: continue
        xs=[float(p[0]) for p in pts]; ys=[float(p[1]) for p in pts]
        rib_polys.append(((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,max(xs)-min(xs),max(ys)-min(ys)))

    for typ,(tx,ty) in title_pos.items():
        # 평면도(하면) 제목 존재 = 일반형, 없으면 평판형
        has_bottom=any(
            "평면도" in t and "하면" in t and -2600 <= x-tx <= -300 and -1300 <= y-ty <= -250
            for x,y,t,layer in texts
        )
        kind="일반형" if has_bottom else "평판형"

        # 단면 B-B 부근의 실제 DIMENSION에서 본체 두께를 읽음.
        # 청람교 양식에서 본체 두께 치수는 70~150mm 범위이며 단면 B-B 우측에 위치.
        thick_candidates=[]
        for e in dims:
            try:
                p=e.dxf.defpoint; dx=float(p.x)-tx; dy=float(p.y)-ty
            except: continue
            if 250 <= dx <= 1300 and -1450 <= dy <= -700:
                v=_dimension_measurement(e)
                if v is not None and 70 <= v <= 150:
                    # 80/90 등의 본체두께를 우선; 100 이상의 간격치수보다 작은 값을 우선
                    thick_candidates.append((abs(dx-770)+0.15*abs(dy+1060),v))
        thickness=None
        if thick_candidates:
            thick_candidates.sort(key=lambda q:q[0]); thickness=_m(thick_candidates[0][1])

        rib_length=None; rib_count=None
        if has_bottom:
            # 하면도의 리브 외곽은 CS-CONC-MINR의 닫힌 좁은 사각형.
            # 동일 리브에 내·외곽이 함께 있으므로 폭 150~300mm의 외곽만 사용.
            ribs=[]
            for cx,cy,w,h in rib_polys:
                dx,dy=cx-tx,cy-ty
                narrow=min(w,h); long=max(w,h)
                if -2200 <= dx <= -350 and -3800 <= dy <= -900 and 150 <= narrow <= 300 and 500 <= long <= 4000:
                    ribs.append((cx,cy,long))
            # 같은 중심의 중복을 제거
            uniq=[]
            for r in sorted(ribs):
                if not any(abs(r[0]-q[0])<5 and abs(r[1]-q[1])<5 for q in uniq):
                    uniq.append(r)
            if uniq:
                rib_count=len(uniq)
                rib_length=_m(sum(q[2] for q in uniq)/len(uniq))

        extra[typ]={"thickness":thickness,"deck_kind":kind,"rib_length":rib_length,"rib_count":rib_count}

    return geometry,material,all_types,extra
