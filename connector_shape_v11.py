
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
        if m: d.setdefault(m.group(0).upper(),(x,y))
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


def _section_heading(a,tx,ty,sec):
    # Use the actual structural section heading, not "배근도 (단면 ...)".
    key=("단면 "+sec).replace(" ","").upper()
    cand=[]
    for x,y,t in a:
        u=t.replace(" ","").upper()
        if key in u and "배근도" not in t:
            cand.append(((x-tx)**2+(y-ty)**2,x,y,t))
    if not cand: return None
    cand.sort()
    return cand[0][1:]

def _near_labels(a,cx,cy,rx,ry):
    return [t for x,y,t in a if abs(x-cx)<=rx and abs(y-cy)<=ry]

def _semantic_from_labels(labels):
    joined=" ".join(labels).upper().replace(" ","")
    has_truss="TRUSS" in joined
    has_wave="파형철선" in joined
    if has_truss and not has_wave: return "TRUSS GR"
    if has_wave and not has_truss: return "파형철선"
    return ""

def analyze(path):
    doc=ezdxf.readfile(path); msp=doc.modelspace()
    a=_texts(msp); titles=_titles(a); out={}
    for typ,(tx,ty) in titles.items():
        ah=_section_heading(a,tx,ty,"A-A")
        bh=_section_heading(a,tx,ty,"B-B")
        dh=_heading(a,tx,ty,["전단연결재 상세","전단연결재상세"])

        aa_kind=""; aa_note="A-A 제목 인식 실패"
        bb_kind=""; bb_note="B-B 제목 인식 실패"
        de_kind=""; de_note="상세 제목 인식 실패"

        if ah:
            # A-A: straight repeated vertical connector strokes = wave wire;
            # repeated connected /\ geometry = TRUSS GR.
            seg=_segments(msp,ah[0],ah[1]-650,1600,1300)
            tr=_truss_score(seg); ve=_vertical_score(seg)
            if tr>=2:
                aa_kind="TRUSS GR"; aa_note=f"A-A ∧/A형 꼭짓점 {tr}개"
            elif ve>=2:
                aa_kind="파형철선"; aa_note=f"A-A 수직 실선형 연결재 {ve}개"
            else:
                aa_note=f"A-A 형상 부족(꼭짓점 {tr}, 수직 {ve})"

        if bh:
            # B-B has a DIFFERENT shape from A-A.
            # Use both its own geometry and the nearby explicit left-side label.
            labels=_near_labels(a,bh[0],bh[1]-900,1700,2300)
            labkind=_semantic_from_labels(labels)
            seg=_segments(msp,bh[0],bh[1]-900,1500,2200)
            tr=_truss_score(seg)
            if labkind=="파형철선":
                bb_kind="파형철선"; bb_note="B-B 물결형 영역 + '(파형철선)' 표기"
            elif labkind=="TRUSS GR":
                bb_kind="TRUSS GR"; bb_note="B-B 영역 + 'TRUSS GR' 표기"
            elif tr>=4:
                bb_kind="TRUSS GR"; bb_note=f"B-B 삼각 지그재그 꼭짓점 {tr}개"
            else:
                bb_note=f"B-B 종류 표기/형상 확인 필요(지그재그 꼭짓점 {tr})"

        if dh:
            # Detail: text is strong evidence, geometry supports TRUSS.
            labels=_near_labels(a,dh[0],dh[1]-450,2000,1500)
            labkind=_semantic_from_labels(labels)
            seg=_segments(msp,dh[0],dh[1]-500,1800,1300)
            tr=_truss_score(seg)
            if labkind:
                de_kind=labkind; de_note=f"전단연결재 상세 표기: {labkind}"
            elif tr>=2:
                de_kind="TRUSS GR"; de_note=f"전단연결재 상세 트러스 형상 꼭짓점 {tr}개"
            else:
                de_note="전단연결재 상세 종류 확인 필요"

        # Geometry is allowed to differ by view. Compare only the semantic TYPE.
        known=[v for v in (aa_kind,bb_kind,de_kind) if v]
        final=""
        conflict=False
        if len(known)>=2:
            if len(set(known))==1: final=known[0]
            else: conflict=True
        out[typ]={"aa":aa_kind,"bb":bb_kind,"detail":de_kind,
                  "final":final,"conflict":conflict,
                  "note":" / ".join((aa_note,bb_note,de_note))}
    return out
