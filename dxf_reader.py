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


def _norm_heading(t):
    return re.sub(r"\s+","",t or "")

def _find_type_titles_and_texts(msp):
    titles={}; texts=[]
    for e in msp:
        if e.dxftype() not in ("TEXT","MTEXT"): continue
        t=_txt(e)
        if not t: continue
        q=e.dxf.insert; x,y=float(q.x),float(q.y)
        texts.append((x,y,t,e.dxf.layer))
        if TYPE_RE.fullmatch(t) and e.dxf.layer=="CZ-TEX0":
            titles[t]=(x,y)
    return titles,texts

def _nearest_heading(texts, tx, ty, key, xlo=-5000, xhi=5000, ylo=-6000, yhi=1000):
    c=[]
    for x,y,t,layer in texts:
        dx,dy=x-tx,y-ty
        if xlo<=dx<=xhi and ylo<=dy<=yhi and key in _norm_heading(t):
            c.append((abs(dx)+abs(dy),x,y,t))
    return min(c)[1:] if c else None

def _poly_spec_near_heading(msp, typ, hx, hy):
    cand=[]
    for e in msp.query("LWPOLYLINE"):
        if e.dxf.layer!="CS-CONC" or not e.closed: continue
        pts=list(e.get_points("xy"))
        if len(pts)<4: continue
        xs=[float(q[0]) for q in pts]; ys=[float(q[1]) for q in pts]
        cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2
        if abs(cx-hx)>1200 or not (-3200 <= cy-hy <= -250): continue
        sp=_outline_spec(e,typ)
        if sp:
            cand.append((abs(cx-hx)+abs((cy-hy)+1850),sp))
    if not cand: return None
    cand.sort(key=lambda z:z[0])
    return cand[0][1]

def _aa_outline(msp,hx,hy):
    cand=[]
    for e in msp.query("LWPOLYLINE"):
        if e.dxf.layer!="CS-CONC" or not e.closed: continue
        pts=list(e.get_points("xy"))
        if len(pts)<4: continue
        xs=[float(q[0]) for q in pts]; ys=[float(q[1]) for q in pts]
        cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2
        w=max(xs)-min(xs); h=max(ys)-min(ys)
        if abs(cx-hx)<=1200 and -1200<=cy-hy<=100 and 300<=w<=2500 and 40<=h<=500:
            cand.append((abs(cx-hx)+abs((cy-hy)+600),e,w,h,ys))
    if not cand: return None,None
    cand.sort(key=lambda z:z[0]); _,e,w,h,ys=cand[0]
    # Slab thickness = top surface down to the dominant shoulder level.
    ymax=max(ys)
    levels={}
    for y in ys:
        k=round(float(y),1); levels[k]=levels.get(k,0)+1
    below=[(cnt,y) for y,cnt in levels.items() if y<ymax-1 and 40 <= ymax-y <= 150]
    if below:
        below.sort(reverse=True)
        thick=ymax-below[0][1]
    else:
        thick=None
    return _m(w), (_m(thick) if thick is not None else None)

def _at_spacing(s):
    if not s or "@" not in s: return None
    m=re.search(r"@\s*([0-9]+(?:\.[0-9]+)?)",s)
    return float(m.group(1)) if m else None

def _shear_kind_from_texts(texts, tx, ty, ylo, yhi, xlo=-5000, xhi=5000):
    found=set()
    for x,y,t,layer in texts:
        dx,dy=x-tx,y-ty
        if not (xlo<=dx<=xhi and ylo<=dy<=yhi): continue
        u=t.upper().replace(" ","")
        if "TRUSS" in u: found.add("TRUSS GR")
        if "파형철선" in t: found.add("파형철선")
    if len(found)==1: return next(iter(found))
    if len(found)>1: return "혼합"
    return ""

def read_v7_cross_checks(path):
    doc=ezdxf.readfile(path); msp=doc.modelspace()
    titles,texts=_find_type_titles_and_texts(msp)
    dims=list(msp.query("DIMENSION"))
    out={}
    for typ,(tx,ty) in titles.items():
        top_h=_nearest_heading(texts,tx,ty,"평면도(상면)")
        bot_h=_nearest_heading(texts,tx,ty,"평면도(하면)")
        reb_h=_nearest_heading(texts,tx,ty,"배근도(평면)")
        aa_h=_nearest_heading(texts,tx,ty,"단면A-A",xhi=0)
        rebaa_h=_nearest_heading(texts,tx,ty,"배근도(단면A-A)",xlo=0)

        top=_poly_spec_near_heading(msp,typ,top_h[0],top_h[1]) if top_h else None
        bottom=_poly_spec_near_heading(msp,typ,bot_h[0],bot_h[1]) if bot_h else None
        rebar=_poly_spec_near_heading(msp,typ,reb_h[0],reb_h[1]) if reb_h else None

        aa_width=aa_thickness=None
        if aa_h:
            aa_width,aa_thickness=_aa_outline(msp,aa_h[0],aa_h[1])

        # Shear connector spacing: explicit n@spacing dimension in top plan vs section A-A.
        top_sp=[]; aa_sp=[]
        for e in dims:
            try:
                q=e.dxf.defpoint; dx=float(q.x)-tx; dy=float(q.y)-ty
                sp=_at_spacing(e.dxf.text or "")
            except: continue
            if sp is None: continue
            if -4500<=dx<=-1500 and -1800<=dy<=-700: top_sp.append(sp)
            if -4500<=dx<=-1500 and -5000<=dy<=-4000: aa_sp.append(sp)

        # Reinforcement spacing: only accept explicit @ dimensions in reinforcement plan/A-A.
        reb_plan_sp=[]; reb_aa_sp=[]
        for e in dims:
            try:
                q=e.dxf.defpoint; dx=float(q.x)-tx; dy=float(q.y)-ty
                sp=_at_spacing(e.dxf.text or "")
            except: continue
            if sp is None: continue
            if 500<=dx<=5000 and -1800<=dy<=-700: reb_plan_sp.append(sp)
            if 500<=dx<=5000 and -5200<=dy<=-3500: reb_aa_sp.append(sp)

        aa_kind=_shear_kind_from_texts(texts,tx,ty,-4700,-4200,-4500,-1500)
        material_kind=_shear_kind_from_texts(texts,tx,ty,-5900,-5350,1500,3800)

        out[typ]={
            "top":top, "bottom":bottom, "rebar":rebar,
            "aa_width":aa_width, "aa_thickness":aa_thickness,
            "top_shear_spacing":sorted(set(top_sp)),
            "aa_shear_spacing":sorted(set(aa_sp)),
            "rebar_plan_spacing":sorted(set(reb_plan_sp)),
            "rebar_aa_spacing":sorted(set(reb_aa_sp)),
            "aa_shear_kind":aa_kind,
            "material_shear_kind":material_kind,
        }
    return out
