import csv
from dxf_reader import read_dxf_specs
from excel_reader import read_excel_specs

TOL=0.0015
def close(a,b):return a is not None and b is not None and abs(a-b)<=TOL

def width_equal(a,b):
    if a is None or b is None:return False
    aa=sorted([x for x in (a.b1,a.b2) if x is not None])
    bb=sorted([x for x in (b.b1,b.b2) if x is not None])
    return len(aa)==len(bb) and all(close(x,y) for x,y in zip(aa,bb))

def run_check(dxf_path,xlsx_path):
    geo,mat=read_dxf_specs(dxf_path)
    xls=read_excel_specs(xlsx_path)
    rows=[]
    for typ in sorted(set(mat)|set(xls)):
        m=mat.get(typ); e=xls.get(typ); g=geo.get(typ)
        if not m:
            rows.append(R(typ,"데크 제원",g.size_text() if g else "인식 실패","인식 실패",e.size_text() if e else "없음","확인","DXF 재료표 제원을 인식하지 못함"))
            continue
        if not e:
            rows.append(R(typ,"데크 제원",g.size_text() if g else "확인필요",m.size_text(),"없음","X","Excel TYPE 없음"))
            continue

        me=width_equal(m,e) and close(m.length,e.length)
        if g:
            gm=width_equal(g,m) and close(g.length,m.length)
            ge=width_equal(g,e) and close(g.length,e.length)
            result="O" if (gm and ge and me) else "X"
            note="" if result=="O" else "실제 형상/재료표/Excel 중 제원이 다름"
            gd=g.size_text()
        else:
            result="O" if me else "X"
            note="실제 형상 DIMENSION 자동인식 확인필요" if me else "재료표와 Excel 제원이 다름"
            gd="확인필요"

        rows.append(R(typ,"데크 제원",gd,m.size_text(),e.size_text(),result,note))
    return rows

def R(t,i,d,m,e,r,n):
    return {"type":t,"item":i,"drawing":d,"material":m,"excel":e,"result":r,"note":n}

def export_csv(rows,path):
    cols=["type","item","drawing","material","excel","result","note"]
    with open(path,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
