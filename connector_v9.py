
import re, math
import ezdxf

TYPE_RE=re.compile(r"M\d{2}-\d{3}",re.I)
SP_RE=re.compile(r"(\d+)\s*@\s*([0-9,.]+)\s*=\s*([0-9,.]+)")
PHI_RE=re.compile(r"[ΦφØ]\s*([0-9]+(?:\.[0-9]+)?)")

def _txt(e):
    try:
        if e.dxftype()=="TEXT": return e.dxf.text or ""
        if e.dxftype()=="MTEXT": return e.plain_text()
        if e.dxftype()=="DIMENSION":
            t=e.dxf.text or ""
            return "" if t=="<>" else t
    except: pass
    return ""

def _xy(e):
    for a in ("insert","defpoint","text_midpoint"):
        try:
            p=getattr(e.dxf,a)
            return float(p.x),float(p.y)
        except: pass
    return None

def _texts(msp):
    out=[]
    for e in msp:
        if e.dxftype() not in ("TEXT","MTEXT","DIMENSION"): continue
        t=_txt(e).strip()
        p=_xy(e)
        if t and p: out.append((p[0],p[1],t,getattr(e.dxf,"layer","")))
    return out

def _titles(texts):
    out={}
    for x,y,t,l in texts:
        m=TYPE_RE.search(t)
        if m and ("TYPE" in t.upper() or l=="CZ-TEX0"):
            out.setdefault(m.group(0).upper(),(x,y))
    return out

def _zone(texts,tx,ty,x1,x2,y1,y2):
    return [(x,y,t,l) for x,y,t,l in texts if x1<=x-tx<=x2 and y1<=y-ty<=y2]

def _phis(t):
    return [float(x) for x in PHI_RE.findall(t)]

def _kind(t):
    u=t.upper().replace(" ","")
    if "TRUSS" in u: return "TRUSS GR"
    if "파형철선" in t or "전단연결재" in t: return "파형철선"
    return ""

def _spacing_candidates(zone):
    a=[]
    for x,y,t,l in zone:
        for m in SP_RE.finditer(t.replace(",","")):
            n=int(m.group(1)); sp=float(m.group(2)); total=float(m.group(3))
            # n@spacing is n spaces, hence n+1 connector locations.
            a.append({"n_space":n,"spacing":sp,"total":total,
                      "calculated_qty":n+1,"raw":m.group(0),"x":x,"y":y})
    return a

def _material_rows(zone):
    """Conservative explicit material-table reader."""
    rows=[]
    for x,y,t,l in zone:
        k=_kind(t); ps=_phis(t)
        if not k or not ps: continue
        for p in ps:
            rows.append({"kind":k,"phi":p,"label":t,"x":x,"y":y})
    # attach nearby explicit integer qty and plausible length if found
    nums=[]
    for x,y,t,l in zone:
        raw=t.replace(",","").strip()
        if re.fullmatch(r"\d+(?:\.\d+)?",raw):
            nums.append((x,y,float(raw),t))
    for r in rows:
        near=sorted(nums,key=lambda q:abs(q[1]-r["y"])*3+abs(q[0]-r["x"]))
        r["numbers"]=[q[2] for q in near[:8]]
    return rows

def _length_candidates(zone):
    """Read only explicit L=... labels; do not invent a length from unrelated dimensions."""
    vals=[]
    for x,y,t,l in zone:
        for m in re.finditer(r"\bL\s*=\s*([0-9,.]+)",t,re.I):
            vals.append(float(m.group(1).replace(",","")))
    return sorted(set(vals))

def read_connector_v9(path):
    doc=ezdxf.readfile(path); msp=doc.modelspace()
    texts=_texts(msp); titles=_titles(texts); out={}
    for typ,(tx,ty) in titles.items():
        # Broad zones intentionally overlap only as evidence sources; uncertain values stay 확인.
        top=_zone(texts,tx,ty,-5200,5200,-4700,600)
        bb=_zone(texts,tx,ty,-5200,5200,-7000,-1200)
        detail=_zone(texts,tx,ty,-5200,5200,-7600,-4300)
        material=_zone(texts,tx,ty,700,5400,-7600,-4300)
        out[typ]={
            "spacing":_spacing_candidates(top+bb),
            "top_lengths":_length_candidates(top),
            "bb_lengths":_length_candidates(bb),
            "detail_lengths":_length_candidates(detail),
            "material_rows":_material_rows(material),
        }
    return out
