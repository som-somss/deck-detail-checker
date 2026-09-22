
import re, math, ezdxf
TYPE_RE=re.compile(r"M\d{2}-\d{3}",re.I)
SP_RE=re.compile(r"(\d+)\s*@\s*([0-9,.]+)\s*=\s*([0-9,.]+)")

def txt(e):
    try:
        if e.dxftype()=="TEXT": return e.dxf.text or ""
        if e.dxftype()=="MTEXT": return e.plain_text()
        if e.dxftype()=="DIMENSION":
            t=e.dxf.text or ""
            if t and t!="<>": return t
            # actual measurement fallback only for dimensions
            try: return f"{float(e.get_measurement()):g}"
            except: return ""
    except: pass
    return ""

def pt(e):
    for a in ("insert","defpoint","text_midpoint"):
        try:
            p=getattr(e.dxf,a); return float(p.x),float(p.y)
        except: pass
    return None

def collect(msp):
    out=[]
    for e in msp:
        if e.dxftype() not in ("TEXT","MTEXT","DIMENSION"): continue
        t=txt(e).strip(); p=pt(e)
        if t and p: out.append((p[0],p[1],t,e.dxftype(),e))
    return out

def titles(a):
    d={}
    for x,y,t,k,e in a:
        m=TYPE_RE.search(t)
        if m: d.setdefault(m.group(0).upper(),(x,y))
    return d

def heading(a,tx,ty,key,exclude=None):
    kk=key.replace(" ","").upper(); cand=[]
    for q in a:
        u=q[2].replace(" ","").upper()
        if kk in u and (not exclude or exclude not in u):
            cand.append(((q[0]-tx)**2+(q[1]-ty)**2,q))
    return min(cand,key=lambda z:z[0])[1] if cand else None

def number(t):
    try:return float(t.replace(",","").strip())
    except:return None

def spacing(t):
    m=SP_RE.search(t.replace(",",""))
    if not m:return None
    return int(m.group(1)),float(m.group(2)),float(m.group(3))

def segs(msp,cx,cy,rx,ry):
    out=[]
    for e in msp.query("LINE"):
        try:
            a=e.dxf.start;b=e.dxf.end
            x1,y1,x2,y2=map(float,(a.x,a.y,b.x,b.y))
        except:continue
        mx=(x1+x2)/2;my=(y1+y2)/2
        if abs(mx-cx)<=rx and abs(my-cy)<=ry:
            L=math.hypot(x2-x1,y2-y1)
            if 8<=L<=1200:out.append((x1,y1,x2,y2,L))
    return out

def vertical_count(ss):
    return sum(1 for x1,y1,x2,y2,L in ss if abs(x2-x1)<=max(2,.05*L) and abs(y2-y1)>=25)

def truss_joints(ss):
    sl=[s for s in ss if abs(s[2]-s[0])>=10 and abs(s[3]-s[1])>=10]
    n=0
    for i,a in enumerate(sl):
        for b in sl[i+1:]:
            pa=[(a[0],a[1]),(a[2],a[3])];pb=[(b[0],b[1]),(b[2],b[3])]
            if min(math.hypot(x-u,y-v) for x,y in pa for u,v in pb)<=5:
                if (a[2]-a[0])*(b[2]-b[0])<0:n+=1
    return n

def analyze(path):
    doc=ezdxf.readfile(path);msp=doc.modelspace();a=collect(msp);tt=titles(a);out={}
    for typ,(tx,ty) in tt.items():
        top=heading(a,tx,ty,"평면도(상면)")
        aa=heading(a,tx,ty,"단면A-A","배근도")
        bb=heading(a,tx,ty,"단면B-B")
        detail=heading(a,tx,ty,"전단연결재상세")
        kinds=[]; evidence=[]
        # A-A: vertical strokes=wave; repeated /\=TRUSS
        if aa:
            ss=segs(msp,aa[0],aa[1]-650,1700,1300); v=vertical_count(ss);j=truss_joints(ss)
            if j>=2:kinds.append("TRUSS GR");evidence.append("A-A:∧/A형")
            elif v>=2:kinds.append("파형철선");evidence.append("A-A:수직 실선형")
        # B-B: explicit local label is strong; otherwise triangular zigzag=TRUSS
        if bb:
            local=[q[2] for q in a if abs(q[0]-bb[0])<1700 and abs(q[1]-(bb[1]-900))<2300]
            joined=" ".join(local).upper().replace(" ","")
            if "파형철선" in joined:kinds.append("파형철선");evidence.append("B-B:물결영역+파형철선 표기")
            elif "TRUSS" in joined:kinds.append("TRUSS GR");evidence.append("B-B:TRUSS GR 표기")
            else:
                j=truss_joints(segs(msp,bb[0],bb[1]-900,1500,2200))
                if j>=4:kinds.append("TRUSS GR");evidence.append("B-B:삼각 지그재그")
        # Detail explicit naming/geometry
        if detail:
            local=[q[2] for q in a if abs(q[0]-detail[0])<2000 and abs(q[1]-(detail[1]-450))<1500]
            joined=" ".join(local).upper().replace(" ","")
            if "TRUSS" in joined:kinds.append("TRUSS GR");evidence.append("상세:TRUSS GR")
            elif "파형철선" in joined:kinds.append("파형철선");evidence.append("상세:파형철선")
        kind=""
        if kinds and len(set(kinds))==1:kind=kinds[0]
        elif kinds:kind="불일치"

        # Top-plan connector chain and Phi5 end-55.
        top_spacing=[]; end55=[]; side_lengths=[]
        if top:
            # search around top plan only
            zone=[q for q in a if abs(q[0]-top[0])<=2200 and -3600<=q[1]-top[1]<=500]
            for q in zone:
                sp=spacing(q[2])
                if sp:top_spacing.append(sp)
                v=number(q[2])
                if v is not None:
                    if abs(v-55)<=.5:end55.append((q[0],q[1]))
                    # connector product length is side vertical dimension; practical range only.
                    if 1000<=v<=5000:side_lengths.append((q[0],q[1],v))
        # de-dup 55 positions
        e55=[]
        for x,y in end55:
            if not any(math.hypot(x-u,y-v)<15 for u,v in e55):e55.append((x,y))
        # candidate lengths, unique values. Never use L= text.
        lv=[]
        for x,y,v in side_lengths:
            if not any(abs(v-w)<.5 for w in lv):lv.append(v)
        lv=sorted(lv)

        # B-B explicit long vertical dimensions for cross-check, no L= text.
        bb_len=[]
        if bb:
            zone=[q for q in a if abs(q[0]-bb[0])<=1800 and -2600<=q[1]-bb[1]<=300]
            for q in zone:
                v=number(q[2])
                if v is not None and 1000<=v<=5000 and not any(abs(v-w)<.5 for w in bb_len):
                    bb_len.append(v)
        out[typ]={"kind":kind,"evidence":evidence,"top_spacing":top_spacing,
                  "phi5_qty":len(e55),"top_lengths":lv,"bb_lengths":sorted(bb_len)}
    return out
