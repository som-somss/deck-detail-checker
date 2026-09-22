import re, ezdxf
TYPE_RE=re.compile(r"M\\d{2}-\\d{3}",re.I)
SP_RE=re.compile(r"(\\d+)\\s*@\\s*([0-9,.]+)\\s*=\\s*([0-9,.]+)")

def _text(e):
    try:
        if e.dxftype()=="TEXT": return e.dxf.text or ""
        if e.dxftype()=="MTEXT": return e.plain_text()
        if e.dxftype()=="DIMENSION":
            t=e.dxf.text or ""
            return "" if t=="<>" else t
    except: pass
    return ""

def _pt(e):
    for a in ("insert","defpoint","text_midpoint"):
        try:
            p=getattr(e.dxf,a); return float(p.x),float(p.y)
        except: pass

def analyze(path):
    doc=ezdxf.readfile(path); msp=doc.modelspace(); a=[]
    for e in msp:
        if e.dxftype() not in ("TEXT","MTEXT","DIMENSION"): continue
        t=_text(e).strip(); p=_pt(e)
        if t and p: a.append((p[0],p[1],t,getattr(e.dxf,"layer","")))
    titles={}
    for x,y,t,l in a:
        m=TYPE_RE.search(t)
        if m and ("TYPE" in t.upper() or l=="CZ-TEX0"): titles.setdefault(m.group(0).upper(),(x,y))
    out={}
    for typ,(tx,ty) in titles.items():
        local=[q for q in a if abs(q[0]-tx)<6000 and abs(q[1]-ty)<8000]
        # collect explicit spacing strings and 55 end dimensions conservatively
        spac=[]
        for x,y,t,l in local:
            m=SP_RE.search(t.replace(",",""))
            if m:
                n=int(m.group(1)); sp=float(m.group(2)); total=float(m.group(3))
                spac.append((x,y,n,sp,total,t))
        f55=[]
        for x,y,t,l in local:
            try:v=float(t.replace(",","").strip())
            except:continue
            if abs(v-55)<.5:f55.append((x,y))
        # side length candidates only; final mapping stays 확인 if ambiguous
        lengths=[]
        for x,y,t,l in local:
            try:v=float(t.replace(",","").strip())
            except:continue
            if 1000<=v<=5000 and not any(abs(v-w)<.5 for w in lengths): lengths.append(v)
        out[typ]={"spacing":spac,"phi5_55_count":min(len(f55),2),"length_candidates":sorted(lengths)}
    return out
