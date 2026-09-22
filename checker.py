import csv
from dxf_reader import read_dxf_specs
from excel_reader import read_excel_specs

TOL=0.0015
def close(a,b):
    return a is not None and b is not None and abs(a-b)<=TOL

def same_spec(a,b):
    if not a or not b:
        return False
    # 방향을 유지해서 위폭/아래폭을 비교하되, 재료표의 표기 순서가 반대인 도면도 허용
    direct=close(a.b1,b.b1) and close(a.b2,b.b2)
    reverse=close(a.b1,b.b2) and close(a.b2,b.b1)
    return (direct or reverse) and close(a.length,b.length)

def R(t,d,m,e,r,n):
    return {"type":t,"item":"데크 제원","drawing":d,"material":m,"excel":e,"result":r,"note":n}

def run_check(dxf,xlsx):
    geo,mat,dxf_types=read_dxf_specs(dxf)
    xls=read_excel_specs(xlsx)
    # 어떤 인식이 실패해도 TYPE 자체가 결과에서 사라지지 않게 전체 합집합 사용
    types=sorted(dxf_types | set(mat) | set(geo) | set(xls))
    rows=[]
    for typ in types:
        g,m,e=geo.get(typ),mat.get(typ),xls.get(typ)
        gd=g.size_text() if g else "인식 실패"
        md=m.size_text() if m else "인식 실패"
        ed=e.size_text() if e else "인식 실패"

        if not g or not m or not e:
            missing=[]
            if not g: missing.append("평면도 실제 형상")
            if not m: missing.append("상세도 재료표")
            if not e: missing.append("Excel")
            rows.append(R(typ,gd,md,ed,"확인"," / ".join(missing)+" 인식 필요"))
            continue

        gm=same_spec(g,m)
        ge=same_spec(g,e)
        me=same_spec(m,e)
        if gm and ge and me:
            rows.append(R(typ,gd,md,ed,"O",""))
        else:
            diff=[]
            if not gm: diff.append("실제형상↔재료표")
            if not ge: diff.append("실제형상↔Excel")
            if not me: diff.append("재료표↔Excel")
            rows.append(R(typ,gd,md,ed,"X"," / ".join(diff)+" 불일치"))
    return rows

def export_csv(rows,path):
    cols=["type","item","drawing","material","excel","result","note"]
    with open(path,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
