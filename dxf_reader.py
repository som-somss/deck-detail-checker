import re
from collections import Counter
import ezdxf
from models import Spec
TR=re.compile(r"^M\d{2}-\d+(?:-\d+)?$",re.I)
def txt(e):
    try:return (e.dxf.text if e.dxftype()=="TEXT" else e.plain_text()).strip()
    except:return ""
def read_dxf_specs(path):
    doc=ezdxf.readfile(path);m=doc.modelspace();ts=[]
    for e in m:
        if e.dxftype() in ("TEXT","MTEXT"):
            t=txt(e)
            if t:
                p=e.dxf.insert;ts.append((float(p.x),float(p.y),t,e.dxf.layer))
    tables={t:(x,y) for x,y,t,l in ts if TR.fullmatch(t) and l=="CZ-DIMT"}
    titles={t:(x,y) for x,y,t,l in ts if TR.fullmatch(t) and l=="CZ-TEX0"}
    material={}
    for typ,(ax,ay) in tables.items():
        cells=[]
        for x,y,t,l in ts:
            if l=="데크규격" and -100<=x-ax<=500 and -200<=y-ay<=-40:
                try:cells.append((x,y,float(t.replace(",",""))))
                except:pass
        if len(cells)>=2:
            groups=[]
            for c in cells:
                g=sorted([q for q in cells if abs(q[1]-c[1])<8],key=lambda q:q[0])
                ky=round(sum(q[1] for q in g)/len(g),1)
                if not any(abs(ky-a)<1 for a,_ in groups):groups.append((ky,g))
            two=[g for _,g in groups if len(g)>=2];one=[g for _,g in groups if len(g)==1]
            if len(cells)>=3 and two and one:
                material[typ]=Spec(typ,two[0][0][2],two[0][1][2],one[0][0][2],ax,ay)
            else:
                s=sorted(cells,key=lambda q:q[0]);material[typ]=Spec(typ,s[0][2],s[0][2],s[1][2],ax,ay)
    geometry={};dims=list(m.query("DIMENSION"))
    for typ,(tx,ty) in titles.items():
        vals=[]
        for e in dims:
            try:
                p=e.dxf.defpoint
                if abs(float(p.x)-tx)>6000 or abs(float(p.y)-ty)>5000:continue
                v=round(float(e.get_measurement())/1000,3)
                if .25<=v<=2.5:vals.append(v)
            except:pass
        mat=material.get(typ)
        if vals and mat:
            cnt=Counter(vals)
            def near(target):
                c=[v for v in cnt if abs(v-target)<=.25]
                return max(c,key=lambda v:(cnt[v],-abs(v-target))) if c else None
            b1=near(mat.b1);b2=near(mat.b2 if mat.b2 is not None else mat.b1)
            if b1 is not None:geometry[typ]=Spec(typ,b1,b2 if b2 is not None else b1,None,tx,ty)
    return geometry,material
