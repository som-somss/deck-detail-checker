
import re, math, ezdxf
TYPE_RE=re.compile(r"M\d{2}-\d{3}",re.I)
SP_RE=re.compile(r"(\d+)\s*@\s*([0-9,.]+)\s*=\s*([0-9,.]+)")
PHI5_RE=re.compile(r"(?:%%[cC]|[ØΦφ])\s*5\b")

def _text(e):
    try:
        if e.dxftype()=="TEXT": return e.dxf.text or ""
        if e.dxftype()=="MTEXT": return e.plain_text()
        if e.dxftype()=="DIMENSION":
            t=e.dxf.text or ""
            if t and t!="<>": return t
            try:return f"{float(e.get_measurement()):g}"
            except:return ""
    except:return ""
    return ""

def _point(e):
    for k in ("insert","defpoint","text_midpoint"):
        try:
            p=getattr(e.dxf,k); return float(p.x),float(p.y)
        except:pass
    return None

def _records(msp):
    a=[]
    for e in msp:
        if e.dxftype() in ("TEXT","MTEXT","DIMENSION"):
            t=_text(e).strip(); p=_point(e)
            if t and p:a.append((p[0],p[1],t,e.dxftype(),e))
    return a

def _types(rs):
    d={}
    for x,y,t,k,e in rs:
        m=TYPE_RE.search(t)
        if m:d.setdefault(m.group(0).upper(),(x,y))
    return d

def _heading(rs,tx,ty,key,exclude=""):
    k=key.replace(" ","").upper(); out=[]
    for r in rs:
        u=r[2].replace(" ","").upper()
        if k in u and (not exclude or exclude.replace(" ","").upper() not in u):
            out.append(((r[0]-tx)**2+(r[1]-ty)**2,r))
    return min(out,key=lambda q:q[0])[1] if out else None

def _closed_plan_bbox(msp,h):
    if not h:return None
    hx,hy=h[0],h[1]; cand=[]
    for e in msp.query("LWPOLYLINE"):
        try:
            if not e.closed:continue
            pts=[(float(p[0]),float(p[1])) for p in e.get_points()]
            xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
            x0,x1,y0,y1=min(xs),max(xs),min(ys),max(ys)
            w=x1-x0; hh=y1-y0
            cx=(x0+x1)/2; cy=(y0+y1)/2
            # Plan body is below heading, tall rectangle/trapezoid.
            if 300<=w<=5000 and 600<=hh<=6000 and abs(cx-hx)<2500 and hy-4500<cy<hy+200:
                cand.append((w*hh,(x0,x1,y0,y1)))
        except:pass
    return min(cand,key=lambda q:q[0])[1] if cand else None

def _nums(t):
    if "@" in t:return []
    s=t.replace(",","")
    vals=[]
    for q in re.findall(r"(?<!\d)([1-9]\d{2,3})(?!\d)",s):
        v=int(q)
        if 40<=v<=5000 and v not in vals:vals.append(v)
    return vals

def _spacing(t):
    m=SP_RE.search(t.replace(",",""))
    if not m:return None
    return int(m.group(1)),float(m.group(2)),float(m.group(3))

def _groups(rs,bbox):
    if not bbox:return {"top":[],"bottom":[],"left":[],"right":[]}
    x0,x1,y0,y1=bbox
    pad_x=max(500,(x1-x0)*1.3); pad_y=max(700,(y1-y0)*.45)
    g={"top":[],"bottom":[],"left":[],"right":[]}
    for r in rs:
        x,y=r[0],r[1]
        # only surrounding dimension/text bands, not the plan interior
        if x0-pad_x<=x<=x1+pad_x and y1<=y<=y1+pad_y:g["top"].append(r)
        if x0-pad_x<=x<=x1+pad_x and y0-pad_y<=y<=y0:g["bottom"].append(r)
        if x0-pad_x<=x<=x0 and y0-pad_y*.2<=y<=y1+pad_y*.2:g["left"].append(r)
        if x1<=x<=x1+pad_x and y0-pad_y*.2<=y<=y1+pad_y*.2:g["right"].append(r)
    return g

def _vals(group,long_only=False):
    a=[]
    for r in group:
        for v in _nums(r[2]):
            if long_only and v<1000:continue
            if v not in a:a.append(v)
    return a

def _sp(group):
    a=[]
    for r in group:
        v=_spacing(r[2])
        if v and v not in a:a.append(v)
    return a

def _phi5(rs,bbox):
    if not bbox:return 0
    x0,x1,y0,y1=bbox; pts=[]
    for x,y,t,k,e in rs:
        if x0-250<=x<=x1+250 and y0-200<=y<=y1+200 and PHI5_RE.search(t):
            if not any(math.hypot(x-a,y-b)<20 for a,b in pts):pts.append((x,y))
    return len(pts)

def analyze(path):
    doc=ezdxf.readfile(path);msp=doc.modelspace();rs=_records(msp);out={}
    for typ,(tx,ty) in _types(rs).items():
        topview=_heading(rs,tx,ty,"평면도(상면)")
        aa=_heading(rs,tx,ty,"단면A-A","배근도")
        bb=_heading(rs,tx,ty,"단면B-B")
        bbox=_closed_plan_bbox(msp,topview)
        g=_groups(rs,bbox)

        # "평면도(상면)" is the view. These are its four surrounding sides.
        top_sp=_sp(g["top"]); bottom_sp=_sp(g["bottom"])
        left_long=_vals(g["left"],True); right_long=_vals(g["right"],True)

        # A-A and B-B local records
        az=[]; bz=[]
        if aa:
            az=[r for r in rs if abs(r[0]-aa[0])<1900 and aa[1]-1900<r[1]<aa[1]+300]
        if bb:
            bz=[r for r in rs if abs(r[0]-bb[0])<1900 and bb[1]-2800<r[1]<bb[1]+300]
        aa_sp=_sp(az)
        bb_left=[]
        if bb:
            # B-B LEFT side only
            for r in bz:
                if r[0] < bb[0]:
                    for v in _nums(r[2]):
                        if v>=1000 and v not in bb_left:bb_left.append(v)

        # A-A wave geometry: repeated vertical LINEs in section region.
        vcount=0
        if aa:
            for e in msp.query("LINE"):
                try:
                    p=e.dxf.start;q=e.dxf.end
                    x1,y1,x2,y2=float(p.x),float(p.y),float(q.x),float(q.y)
                except:continue
                mx,my=(x1+x2)/2,(y1+y2)/2; L=math.hypot(x2-x1,y2-y1)
                if abs(mx-aa[0])<1700 and aa[1]-1500<my<aa[1]+300 and L>=30 and abs(x2-x1)<=max(2,.04*L):
                    vcount+=1

        p5=_phi5(rs,bbox)
        # User rule: left side of plan = main Φ6 length; right side = Φ5 length(s).
        p6len=left_long[-1:] if left_long else []
        p5len=right_long[-2:] if right_long else []
        base_sp=(top_sp[0] if top_sp else (bottom_sp[0] if bottom_sp else None))
        out[typ]={
          "bbox":bbox,"top_sp":top_sp,"bottom_sp":bottom_sp,
          "left_long":left_long,"right_long":right_long,
          "phi5_qty":p5,"phi5_lengths":p5len,
          "phi6_lengths":p6len,"phi6_qty":base_sp[0]+1 if base_sp else None,
          "aa_sp":aa_sp,"bb_left":bb_left,
          "aa_wave":vcount>=2,"aa_vertical_count":vcount
        }
    return out
