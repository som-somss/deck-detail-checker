
import re, math, ezdxf
TYPE_RE=re.compile(r"M\d{2}-\d{3}",re.I)
SP_RE=re.compile(r"(\d+)\s*@\s*([0-9,.]+)\s*=\s*([0-9,.]+)")
PHI5_RE=re.compile(r"(?:%%[cC]|[ØΦφ])\s*5\b")

def ttext(e):
    try:
        if e.dxftype()=="TEXT": return e.dxf.text or ""
        if e.dxftype()=="MTEXT": return e.plain_text()
        if e.dxftype()=="DIMENSION":
            s=e.dxf.text or ""
            if s and s!="<>": return s
            try:return f"{float(e.get_measurement()):g}"
            except:return ""
    except:return ""
    return ""

def ip(e):
    for k in ("insert","text_midpoint","defpoint"):
        try:
            p=getattr(e.dxf,k);return float(p.x),float(p.y)
        except:pass
    return None

def recs(msp):
    a=[]
    for e in msp:
        if e.dxftype() in ("TEXT","MTEXT","DIMENSION"):
            p=ip(e);s=ttext(e).strip()
            if p and s:a.append((p[0],p[1],s,e))
    return a

def types(rs):
    d={}
    for x,y,s,e in rs:
        m=TYPE_RE.search(s)
        if m:d.setdefault(m.group(0).upper(),(x,y))
    return d

def heading(rs,tx,ty,key,exclude=""):
    k=key.replace(" ","").upper();q=[]
    for r in rs:
        u=r[2].replace(" ","").upper()
        if k in u and (not exclude or exclude.replace(" ","").upper() not in u):
            q.append(((r[0]-tx)**2+(r[1]-ty)**2,r))
    return min(q,key=lambda z:z[0])[1] if q else None

def bbox(msp,h):
    if not h:return None
    hx,hy=h[0],h[1];q=[]
    for e in msp.query("LWPOLYLINE"):
        try:
            if not e.closed:continue
            p=[(float(v[0]),float(v[1])) for v in e.get_points()]
            xs=[v[0] for v in p];ys=[v[1] for v in p]
            b=(min(xs),max(xs),min(ys),max(ys));w=b[1]-b[0];hh=b[3]-b[2]
            cx=(b[0]+b[1])/2;cy=(b[2]+b[3])/2
            if 300<=w<=5000 and 600<=hh<=6000 and abs(cx-hx)<2500 and hy-5000<cy<hy+200:
                q.append((w*hh,b))
        except:pass
    return min(q,key=lambda z:z[0])[1] if q else None

def dpoints(e):
    pts=[]
    for k in ("defpoint","defpoint2","defpoint3","defpoint4","defpoint5"):
        try:
            p=getattr(e.dxf,k)
            pts.append((float(p.x),float(p.y)))
        except:pass
    return pts

def dimside(e,b):
    pts=dpoints(e)
    if not pts:return None
    x0,x1,y0,y1=b;cx=(x0+x1)/2;cy=(y0+y1)/2
    # Definition/extension points tell which plan edge the dimension belongs to.
    xs=[p[0] for p in pts];ys=[p[1] for p in pts]
    nearx=sum(1 for x in xs if x0-120<=x<=x1+120)
    neary=sum(1 for y in ys if y0-120<=y<=y1+120)
    avx=sum(xs)/len(xs);avy=sum(ys)/len(ys)
    if nearx>=2:
        if avy>y1:return "top"
        if avy<y0:return "bottom"
    if neary>=2:
        if avx<x0:return "left"
        if avx>x1:return "right"
    # fallback by dimension-line definition point
    try:
        p=e.dxf.defpoint
        dx=float(p.x)-cx;dy=float(p.y)-cy
        if abs(dx)>abs(dy):return "right" if dx>0 else "left"
        return "top" if dy>0 else "bottom"
    except:return None

def nums(s,minv=40):
    if "@" in s:return []
    a=[]
    for q in re.findall(r"(?<!\d)([1-9]\d{1,3})(?!\d)",s.replace(",","")):
        v=int(q)
        if minv<=v<=5000 and v not in a:a.append(v)
    return a

def sp(s):
    m=SP_RE.search(s.replace(",",""))
    return (int(m.group(1)),float(m.group(2)),float(m.group(3))) if m else None

def dim_groups(msp,b):
    g={k:[] for k in ("top","bottom","left","right")}
    if not b:return g
    x0,x1,y0,y1=b
    for e in msp.query("DIMENSION"):
        pts=dpoints(e)
        if not pts:continue
        # only dimensions whose definition points are reasonably near this plan
        if not any(x0-2500<=x<=x1+2500 and y0-2500<=y<=y1+2500 for x,y in pts):continue
        side=dimside(e,b)
        if side:g[side].append((ttext(e),e))
    return g

def phi5(rs,b):
    if not b:return 0
    x0,x1,y0,y1=b;a=[]
    for x,y,s,e in rs:
        if x0-300<=x<=x1+300 and y0-250<=y<=y1+250 and PHI5_RE.search(s):
            if not any(math.hypot(x-u,y-v)<20 for u,v in a):a.append((x,y))
    return len(a)

def vals(group,long=False):
    a=[]
    for s,e in group:
        for v in nums(s,1000 if long else 40):
            if v not in a:a.append(v)
    return a

def sps(group):
    a=[]
    for s,e in group:
        q=sp(s)
        if q and q not in a:a.append(q)
    return a

def analyze(path):
    doc=ezdxf.readfile(path);msp=doc.modelspace();rs=recs(msp);out={}
    for typ,(tx,ty) in types(rs).items():
        hv=heading(rs,tx,ty,"평면도(상면)")
        aa=heading(rs,tx,ty,"단면A-A","배근도")
        bb=heading(rs,tx,ty,"단면B-B")
        b=bbox(msp,hv);g=dim_groups(msp,b)
        top_sp=sps(g["top"]);bot_sp=sps(g["bottom"])
        left=vals(g["left"],True);right=vals(g["right"],True)

        # local A-A dimensions
        aa_sp=[]
        if aa:
            for e in msp.query("DIMENSION"):
                pts=dpoints(e)
                if pts and any(abs(x-aa[0])<2000 and aa[1]-2200<y<aa[1]+500 for x,y in pts):
                    q=sp(ttext(e))
                    if q and q not in aa_sp:aa_sp.append(q)

        # B-B LEFT dimensions: dimensions whose definition points lie left of B-B center
        bb_left=[]
        if bb:
            for e in msp.query("DIMENSION"):
                pts=dpoints(e)
                if pts and any(bb[0]-2300<x<bb[0] and bb[1]-3200<y<bb[1]+500 for x,y in pts):
                    for v in nums(ttext(e),1000):
                        if v not in bb_left:bb_left.append(v)

        # A-A vertical connector strokes
        vc=0
        if aa:
            for e in msp.query("LINE"):
                try:
                    p=e.dxf.start;q=e.dxf.end
                    x1,y1,x2,y2=float(p.x),float(p.y),float(q.x),float(q.y)
                except:continue
                L=math.hypot(x2-x1,y2-y1);mx=(x1+x2)/2;my=(y1+y2)/2
                if abs(mx-aa[0])<1700 and aa[1]-1700<my<aa[1]+400 and L>=30 and abs(x2-x1)<=max(2,.04*L):vc+=1

        p5=phi5(rs,b); base=(top_sp[0] if top_sp else (bot_sp[0] if bot_sp else None))
        out[typ]={
          "bbox":b,"top_sp":top_sp,"bottom_sp":bot_sp,
          "left_long":left,"right_long":right,
          "phi5_qty":p5,"phi5_lengths":right[-2:] if right else [],
          "phi6_lengths":left[-1:] if left else [],
          "phi6_qty":base[0]+1 if base else None,
          "aa_sp":aa_sp,"bb_left":bb_left,
          "aa_vertical_count":vc,"aa_wave":vc>=2,
          "debug_counts":{k:len(v) for k,v in g.items()}
        }
    return out
