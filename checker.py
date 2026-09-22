import csv
from dxf_reader import read_dxf_specs
from excel_reader import read_excel_specs

TOL=0.0015
def close(a,b,tol=TOL):
    return a is not None and b is not None and abs(a-b)<=tol

def same_spec(a,b):
    if not a or not b: return False
    direct=close(a.b1,b.b1) and close(a.b2,b.b2)
    reverse=close(a.b1,b.b2) and close(a.b2,b.b1)
    return (direct or reverse) and close(a.length,b.length)

def row(t,item,drawing,material,excel,result,note=""):
    return {"type":t,"item":item,"drawing":drawing,"material":material,"excel":excel,"result":result,"note":note}

def fmt_m(v):
    return "인식 실패" if v is None else f"{v:.3f} m"

def run_check(dxf,xlsx):
    geo,mat,dxf_types,extra=read_dxf_specs(dxf)
    xls=read_excel_specs(xlsx)
    types=sorted(dxf_types | set(mat) | set(geo) | set(xls) | set(extra))
    rows=[]
    for typ in types:
        g,m,xi=geo.get(typ),mat.get(typ),xls.get(typ)
        e=xi.spec if xi else None
        gd=g.size_text() if g else "인식 실패"; md=m.size_text() if m else "인식 실패"; ed=e.size_text() if e else "인식 실패"
        if not g or not m or not e:
            miss=[]
            if not g: miss.append("평면도 실제 형상")
            if not m: miss.append("상세도 재료표")
            if not e: miss.append("Excel")
            rows.append(row(typ,"데크 폭·길이",gd,md,ed,"확인"," / ".join(miss)+" 인식 필요"))
        else:
            gm,ge,me=same_spec(g,m),same_spec(g,e),same_spec(m,e)
            if gm and ge and me: rows.append(row(typ,"데크 폭·길이",gd,md,ed,"O"))
            else:
                diff=[]
                if not gm: diff.append("실제형상↔재료표")
                if not ge: diff.append("실제형상↔Excel")
                if not me: diff.append("재료표↔Excel")
                rows.append(row(typ,"데크 폭·길이",gd,md,ed,"X"," / ".join(diff)+" 불일치"))

        ex=extra.get(typ,{})
        # 두께: DXF 실제 치수와 80mm 기준, Excel J열도 함께 확인
        dt=ex.get("thickness"); et=xi.thickness if xi else None
        if dt is None:
            rows.append(row(typ,"데크 두께","인식 실패","기준 0.080 m",fmt_m(et),"확인","DXF 본체 두께 치수 인식 필요"))
        else:
            ok80=close(dt,0.080); oke=(et is not None and close(dt,et) and close(et,0.080))
            note=[] 
            if not ok80: note.append("DXF 두께가 80mm 아님")
            if et is None: note.append("Excel 두께 없음")
            elif not close(et,0.080): note.append("Excel 두께가 80mm 아님")
            elif not close(dt,et): note.append("DXF↔Excel 두께 불일치")
            rows.append(row(typ,"데크 두께",fmt_m(dt),"기준 0.080 m",fmt_m(et),"O" if ok80 and oke else "X"," / ".join(note)))

        # 형식: 하면 존재 여부로 일반형/평판형 판정 후 Excel P열과 비교
        dk=ex.get("deck_kind",""); ek=(xi.deck_kind if xi else "")
        if not dk:
            rows.append(row(typ,"데크 형식","인식 실패","하면 있음=일반형 / 없음=평판형",ek or "없음","확인","형식 판정 실패"))
        else:
            rows.append(row(typ,"데크 형식",dk,"하면 있음=일반형 / 없음=평판형",ek or "없음","O" if ek==dk else "X","" if ek==dk else "DXF 판정↔Excel 비고 불일치"))

        # 리브 길이/수량: 일반형에서만 실제 하면 형상과 Excel K/M열 비교
        rl=ex.get("rib_length"); rc=ex.get("rib_count")
        erl=xi.rib_length if xi else None; erc=xi.rib_count if xi else None
        if dk=="평판형":
            # 평판형은 리브가 없어야 정상. Excel 값이 비어 있거나 0이면 O.
            no_excel_rib=(erl in (None,0) and erc in (None,0))
            rows.append(row(typ,"리브 길이","없음","평판형",fmt_m(erl) if erl not in (None,0) else "없음","O" if no_excel_rib else "X","" if no_excel_rib else "평판형인데 Excel 리브 제원 존재"))
            rows.append(row(typ,"리브 수량","0 ea","평판형",f"{erc} ea" if erc is not None else "없음","O" if no_excel_rib else "X","" if no_excel_rib else "평판형인데 Excel 리브 수량 존재"))
        else:
            rows.append(row(typ,"리브 길이",fmt_m(rl),"하면 실제 리브",fmt_m(erl),
                            "O" if rl is not None and erl is not None and close(rl,erl) else ("확인" if rl is None or erl is None else "X"),
                            "" if rl is not None and erl is not None and close(rl,erl) else "DXF↔Excel 리브 길이 확인"))
            rows.append(row(typ,"리브 수량",f"{rc} ea" if rc is not None else "인식 실패","하면 실제 리브",f"{erc} ea" if erc is not None else "인식 실패",
                            "O" if rc is not None and erc is not None and rc==erc else ("확인" if rc is None or erc is None else "X"),
                            "" if rc is not None and erc is not None and rc==erc else "DXF↔Excel 리브 수량 확인"))
    return rows

def export_csv(rows,path):
    cols=["type","item","drawing","material","excel","result","note"]
    with open(path,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(rows)
