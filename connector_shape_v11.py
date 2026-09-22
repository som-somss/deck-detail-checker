
import math, re
import ezdxf

TYPE_RE=re.compile(r"M\d{2}-\d{3}",re.I)

def _txt(e):
    try:
        if e.dxftype()=="TEXT": return e.dxf.text or ""
        if e.dxftype()=="MTEXT": return e.plain_text()
    except: pass
    return ""

def _pt(e):
    for a in ("insert","text_midpoint"):
        try:
            p=getattr(e.dxf,a); return float(p.x),float(p.y)
        except: pass
    return None

def _texts(msp):
    a=[]
    for e in msp:
        if e.dxftype() not in ("TEXT","MTEXT"): continue
        t=_txt(e).strip(); p=_pt(e)
        if t and p: a.append((p[0],p[1],t))
    return a

def _titles(a):
    d={}
    for x,y,t in a:
        m=TYPE_RE.search(t)
        if m and "TYPE" in t.upper(): d.setdefault(m.group(0).upper(),(x,y))
    return d

def _heading(a,tx,ty,words):
    best=None
    for x,y,t in a:
        s=t.replace(" ","").upper()
        if any(w.replace(" ","").upper() in s for w in words):
            dd=(x-tx)**2+(y-ty)**2
            if best is None or dd<best[0]: best=(dd,x,y,t)
    return None if best is None else best[1:]

def _segments(msp,cx,cy,rx,ry):
    seg=[]
    for e in msp.query("LINE"):
        try:
            a=e.dxf.start; b=e.dxf.end
            x1,y1=float(a.x),float(a.y); x2,y2=float(b.x),float(b.y)
        except: continue
        mx=(x1+x2)/2; my=(y1+y2)/2
        if abs(mx-cx)<=rx and abs(my-cy)<=ry:
            L=math.hypot(x2-x1,y2-y1)
            if 8<=L<=1000: seg.append((x1,y1,x2,y2,L))
    return seg

def _truss_score(seg):
    # Count genuine /\ or \/ joints: two sloped legs sharing (nearly) one endpoint.
    sl=[]
    for s in seg:
        x1,y1,x2,y2,L=s; dx=x2-x1; dy=y2-y1
        if abs(dx)>=10 and abs(dy)>=10 and 0.15<=abs(dx/dy)<=6:
            sl.append(s)
    joints=0
    for i,a in enumerate(sl):
        ptsa=[(a[0],a[1]),(a[2],a[3])]
        for b in sl[i+1:]:
            ptsb=[(b[0],b[1]),(b[2],b[3])]
            if min(math.hypot(pa[0]-pb[0],pa[1]-pb[1]) for pa in ptsa for pb in ptsb)<=5:
                # Opposite horizontal directions = apex/valley, not two collinear HAUNCH legs.
                va=(a[2]-a[0],a[3]-a[1]); vb=(b[2]-b[0],b[3]-b[1])
                if va[0]*vb[0] < 0: joints+=1
    return joints

def _vertical_score(seg):
    n=0
    for x1,y1,x2,y2,L in seg:
        if abs(x2-x1)<=max(2,L*.05) and abs(y2-y1)>=25: n+=1
    return n

def _classify_section(seg, mode):
    tr=_truss_score(seg); ve=_vertical_score(seg)
    # A-A: repeated A/∧ geometry => TRUSS; otherwise repeated vertical connector lines => wave wire.
    # B-B: triangular zig-zag creates many connected sloped joints.
    need=2 if mode=="AA" else 4
    if tr>=need: return "TRUSS GR", f"형상: 연결된 경사 꼭짓점 {tr}개"
    if mode=="AA" and ve>=2 and tr<need: return "파형철선", f"형상: 수직 연결재 {ve}개"
    return "", f"형상 판정 부족(꼭짓점 {tr}, 수직선 {ve})"

def analyze(path):
    doc=ezdxf.readfile(path); msp=doc.modelspace()
    a=_texts(msp); titles=_titles(a); out={}
    for typ,(tx,ty) in titles.items():
        ah=_heading(a,tx,ty,["단면 A-A","단면A-A"])
        bh=_heading(a,tx,ty,["단면 B-B","단면B-B"])
        dh=_heading(a,tx,ty,["전단연결재 상세","전단연결재상세"])
        aa=("", "A-A 제목 인식 실패")
        bb=("", "B-B 제목 인식 실패")
        detail=("", "상세 제목 인식 실패")
        if ah:
            seg=_segments(msp,ah[0],ah[1]-650,1600,1300)
            aa=_classify_section(seg,"AA")
        if bh:
            seg=_segments(msp,bh[0],bh[1]-900,1400,2200)
            bb=_classify_section(seg,"BB")
        if dh:
            seg=_segments(msp,dh[0],dh[1]-500,1800,1200)
            # Detail: repeated triangular connected legs are TRUSS. Otherwise do not force a type.
            tr=_truss_score(seg)
            if tr>=2: detail=("TRUSS GR",f"상세 형상: 연결된 경사 꼭짓점 {tr}개")
            else: detail=("",f"상세 형상 판정 부족(꼭짓점 {tr})")
        known=[x[0] for x in (aa,bb,detail) if x[0]]
        final=""
        if known and len(set(known))==1 and len(known)>=2: final=known[0]
        return_note=" / ".join(x[1] for x in (aa,bb,detail))
        out[typ]={"aa":aa[0],"bb":bb[0],"detail":detail[0],
                  "final":final,"note":return_note}
    return out
