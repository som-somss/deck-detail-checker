
import re, math, ezdxf
TYPE_RE=re.compile(r"M\d{2}-\d{3}",re.I)
SP_RE=re.compile(r"(\d+)\s*@\s*([0-9,.]+)\s*=\s*([0-9,.]+)")
NUM_RE=re.compile(r"(?<![@\d])([1-9]\d{2,3})(?!\d)")

def text(e):
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

def point(e):
    for k in ("insert","defpoint","text_midpoint"):
        try:
            p=getattr(e.dxf,k); return float(p.x),float(p.y)
        except:pass
    return None

def records(msp):
    out=[]
    for e in msp:
        if e.dxftype() in ("TEXT","MTEXT","DIMENSION"):
            t=text(e).strip(); p=point(e)
            if t and p:out.append((p[0],p[1],t,e))
    return out

def types(rs):
    d={}
    for x,y,t,e in rs:
        m=TYPE_RE.search(t)
        if m:d.setdefault(m.group(0).upper(),(x,y))
    return d

def head(rs,tx,ty,key,exclude=""):
    k=key.replace(" ","").upper(); a=[]
    for r in rs:
        u=r[2].replace(" ","").upper()
        if k in u and (not exclude or exclude.replace(" ","").upper() not in u):
            a.append(((r[0]-tx)**2+(r[1]-ty)**2,r))
    return min(a,key=lambda q:q[0])[1] if a else None

def zone(rs,h,rx,up,down):
    if not h:return []
    x,y=h[0],h[1]
    return [r for r in rs if abs(r[0]-x)<=rx and -down<=r[1]-y<=up]

def spacing_vals(z):
    a=[]
    for x,y,t,e in z:
        m=SP_RE.search(t.replace(",",""))
        if m:
            v=(int(m.group(1)),float(m.group(2)),float(m.group(3)))
            if v not in a:a.append(v)
    return a

def nums_from_text(t):
    # supports 1750(2,000), 1750,2000, etc.; ignores spacing expressions
    if "@" in t:return []
    vals=[]
    for m in NUM_RE.finditer(t.replace(",","")):
        v=int(m.group(1))
        if 1000<=v<=5000 and v not in vals:vals.append(v)
    return vals

def vertical_dimension_candidates(z, center_x):
    left=[];right=[]
    for x,y,t,e in z:
        vals=nums_from_text(t)
        if not vals:continue
        # DIMENSION preferred; text override still allowed because some CADs store displayed dim as text.
        target=left if x<center_x else right
        for v in vals:
            if v not in target:target.append(v)
    return left,right

def phi5_count(z):
    pts=[]
    for x,y,t,e in z:
        if re.search(r"(?:%%[cC]|[ØΦφ])\s*5\b",t):
            if not any(math.hypot(x-a,y-b)<25 for a,b in pts):pts.append((x,y))
    return len(pts)

def line_segments(msp,h,rx,up,down):
    if not h:return []
    cx,cy=h[0],h[1]; a=[]
    for e in msp.query("LINE"):
        try:
            p=e.dxf.start;q=e.dxf.end
            x1,y1,x2,y2=float(p.x),float(p.y),float(q.x),float(q.y)
        except:continue
        mx,my=(x1+x2)/2,(y1+y2)/2
        if abs(mx-cx)<=rx and -down<=my-cy<=up:
            L=math.hypot(x2-x1,y2-y1)
            if 20<=L<=1500:a.append((x1,y1,x2,y2,L))
    return a

def aa_wave(msp,h):
    ss=line_segments(msp,h,1700,300,1500)
    vert=sum(1 for x1,y1,x2,y2,L in ss if abs(x2-x1)<=max(2,.04*L) and abs(y2-y1)>=30)
    # only use shape; no layer/linetype dependency
    return vert>=2,vert

def analyze(path):
    doc=ezdxf.readfile(path);msp=doc.modelspace();rs=records(msp);out={}
    for typ,(tx,ty) in types(rs).items():
        top=head(rs,tx,ty,"평면도(상면)")
        aa=head(rs,tx,ty,"단면A-A","배근도")
        bb=head(rs,tx,ty,"단면B-B")
        tz=zone(rs,top,2300,500,3900)
        az=zone(rs,aa,1900,300,1800)
        bz=zone(rs,bb,1900,300,2800)

        p5=phi5_count(tz)
        top_sp=spacing_vals(tz)
        aa_sp=spacing_vals(az)
        left,right=vertical_dimension_candidates(tz,top[0] if top else tx)
        # Rule supplied by user:
        # left vertical dimension = main Φ6 wave-wire length
        # right vertical dimension = Φ5 length(s), e.g. 1750(2000)
        phi6_lengths=left[-1:] if left else []
        phi5_lengths=right[-2:] if right else []

        bb_lengths=[]
        for r in bz:
            for v in nums_from_text(r[2]):
                if v not in bb_lengths:bb_lengths.append(v)

        wave,vc=aa_wave(msp,aa)
        out[typ]={
          "phi5_qty":p5,
          "phi5_lengths":phi5_lengths,
          "phi6_lengths":phi6_lengths,
          "phi6_qty":(top_sp[0][0]+1 if top_sp else None),
          "top_spacing":top_sp[0] if top_sp else None,
          "aa_spacing":aa_sp[0] if aa_sp else None,
          "aa_wave":wave,"aa_vertical_count":vc,
          "bb_lengths":bb_lengths,
        }
    return out
