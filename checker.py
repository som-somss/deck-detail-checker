import csv
from dxf_reader import read_dxf_specs
from excel_reader import read_excel_specs
T=.0015
def close(a,b):return a is not None and b is not None and abs(a-b)<=T
def weq(a,b):
    if not a or not b:return False
    x=sorted([q for q in (a.b1,a.b2) if q is not None]);y=sorted([q for q in (b.b1,b.b2) if q is not None])
    return len(x)==len(y) and all(close(i,j) for i,j in zip(x,y))
def run_check(dxf,xlsx):
    geo,mat=read_dxf_specs(dxf);xls=read_excel_specs(xlsx);rows=[]
    for typ in sorted(set(mat)|set(xls)):
        m=mat.get(typ);e=xls.get(typ);g=geo.get(typ)
        if not m or not e:
            rows.append(R(typ,"데크 제원",g.width_text() if g else "인식 실패",m.size_text() if m else "인식 실패",e.size_text() if e else "인식 실패","확인","DXF 또는 Excel 인식 확인 필요"));continue
        me=weq(m,e) and close(m.length,e.length)
        if g:
            ok=weq(g,m) and weq(g,e) and me
            rows.append(R(typ,"데크 제원",g.width_text()+" (폭 실측)",m.size_text(),e.size_text(),"O" if ok else "X","" if ok else "실제 형상 폭 / 재료표 / Excel 중 상이"))
        else:
            rows.append(R(typ,"데크 제원","확인필요",m.size_text(),e.size_text(),"O" if me else "X","실제 형상 폭 자동인식 확인필요" if me else "재료표와 Excel 제원이 다름"))
    return rows
def R(t,i,d,m,e,r,n):return {"type":t,"item":i,"drawing":d,"material":m,"excel":e,"result":r,"note":n}
def export_csv(rows,path):
    cs=["type","item","drawing","material","excel","result","note"]
    with open(path,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=cs);w.writeheader();w.writerows(rows)
