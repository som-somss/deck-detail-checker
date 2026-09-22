import csv
from dxf_reader import read_dxf_specs, read_v7_cross_checks
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

def fmt_list(v,unit="mm"):
    return "인식 실패" if not v else ", ".join(f"{x:g} {unit}" for x in v)

def run_check(dxf,xlsx):
    geo,mat,dxf_types,extra=read_dxf_specs(dxf)
    cross=read_v7_cross_checks(dxf)
    xls=read_excel_specs(xlsx)
    types=sorted(dxf_types | set(mat) | set(geo) | set(xls) | set(extra) | set(cross))
    rows=[]
    for typ in types:
        g,m,xi=geo.get(typ),mat.get(typ),xls.get(typ)
        e=xi.spec if xi else None
        gd=g.size_text() if g else "인식 실패"; md=m.size_text() if m else "인식 실패"; ed=e.size_text() if e else "인식 실패"
        if not g or not m or not e:
            miss=[]
            if not g: miss.append("평면도(상면) 실제 형상")
            if not m: miss.append("상세도 재료표")
            if not e: miss.append("Excel")
            rows.append(row(typ,"데크 폭·길이",gd,md,ed,"확인"," / ".join(miss)+" 인식 필요"))
        else:
            gm,ge,me=same_spec(g,m),same_spec(g,e),same_spec(m,e)
            rows.append(row(typ,"데크 폭·길이",gd,md,ed,"O" if gm and ge and me else "X",
                            "" if gm and ge and me else "폭·길이 불일치"))

        ex=extra.get(typ,{})
        # Thickness is NOT fixed to 80. DXF detail thickness must equal Excel thickness.
        dt=ex.get("thickness"); et=xi.thickness if xi else None
        if dt is None or et is None:
            rows.append(row(typ,"데크 두께",fmt_m(dt),"고정값 없음",fmt_m(et),"확인","DXF 또는 Excel 두께 인식 필요"))
        else:
            rows.append(row(typ,"데크 두께",fmt_m(dt),"고정값 없음",fmt_m(et),"O" if close(dt,et) else "X",
                            "" if close(dt,et) else "DXF↔Excel 두께 불일치"))

        dk=ex.get("deck_kind",""); ek=(xi.deck_kind if xi else "")
        if not dk:
            rows.append(row(typ,"데크 형식","인식 실패","하면 있음=일반형 / 없음=평판형",ek or "없음","확인","형식 판정 실패"))
        else:
            rows.append(row(typ,"데크 형식",dk,"하면 있음=일반형 / 없음=평판형",ek or "없음","O" if ek==dk else "X",
                            "" if ek==dk else "DXF 판정↔Excel 비고 불일치"))

        rl=ex.get("rib_length"); rc=ex.get("rib_count")
        erl=xi.rib_length if xi else None; erc=xi.rib_count if xi else None
        if dk=="평판형":
            no_excel_rib=(erl in (None,0) and erc in (None,0))
            rows.append(row(typ,"리브 길이","없음","평판형",fmt_m(erl) if erl not in (None,0) else "없음","O" if no_excel_rib else "X",
                            "" if no_excel_rib else "평판형인데 Excel 리브 제원 존재"))
            rows.append(row(typ,"리브 수량","0 ea","평판형",f"{erc} ea" if erc is not None else "없음","O" if no_excel_rib else "X",
                            "" if no_excel_rib else "평판형인데 Excel 리브 수량 존재"))
        else:
            ok=rl is not None and erl is not None and close(rl,erl)
            rows.append(row(typ,"리브 길이",fmt_m(rl),"하면 실제 리브",fmt_m(erl),"O" if ok else ("확인" if rl is None or erl is None else "X"),
                            "" if ok else "DXF↔Excel 리브 길이 확인"))
            ok=rc is not None and erc is not None and rc==erc
            rows.append(row(typ,"리브 수량",f"{rc} ea" if rc is not None else "인식 실패","하면 실제 리브",
                            f"{erc} ea" if erc is not None else "인식 실패","O" if ok else ("확인" if rc is None or erc is None else "X"),
                            "" if ok else "DXF↔Excel 리브 수량 확인"))

        c=cross.get(typ,{})
        top=c.get("top") or g; bot=c.get("bottom"); reb=c.get("rebar")
        # Cross-check lower plan and reinforcement plan dimensions.
        if dk=="일반형":
            if top and bot:
                ok=same_spec(top,bot)
                rows.append(row(typ,"평면도(하면) 폭·길이",bot.size_text(),"평면도(상면) "+top.size_text(),ed,"O" if ok else "X",
                                "" if ok else "상면↔하면 폭·길이 불일치"))
            else:
                rows.append(row(typ,"평면도(하면) 폭·길이",bot.size_text() if bot else "인식 실패",
                                top.size_text() if top else "인식 실패",ed,"확인","하면 외곽 인식 필요"))
        if top and reb:
            ok=same_spec(top,reb)
            rows.append(row(typ,"배근도(평면) 폭·길이",reb.size_text(),"평면도(상면) "+top.size_text(),ed,"O" if ok else "X",
                            "" if ok else "상면↔배근도 폭·길이 불일치"))
        else:
            rows.append(row(typ,"배근도(평면) 폭·길이",reb.size_text() if reb else "인식 실패",
                            top.size_text() if top else "인식 실패",ed,"확인","배근도 평면 외곽 인식 필요"))

        # Section A-A width: compare with the corresponding deck width when unambiguous.
        aw=c.get("aa_width")
        if aw is None or not top:
            rows.append(row(typ,"단면 A-A 폭",fmt_m(aw),"평면도(상면)","", "확인","A-A 폭 인식 필요"))
        else:
            widths=[top.b1,top.b2]
            ok=any(close(aw,w) for w in widths if w is not None)
            rows.append(row(typ,"단면 A-A 폭",fmt_m(aw),"평면도 폭 "+top.width_text(),"","O" if ok else "X",
                            "" if ok else "A-A 폭↔평면도 폭 불일치"))

        # Section A-A slab thickness vs detail/Excel thickness.
        at=c.get("aa_thickness")
        if at is None or dt is None or et is None:
            rows.append(row(typ,"단면 A-A 두께",fmt_m(at),fmt_m(dt),fmt_m(et),"확인","A-A/상세도/Excel 두께 중 인식 필요"))
        else:
            ok=close(at,dt) and close(at,et)
            rows.append(row(typ,"단면 A-A 두께",fmt_m(at),fmt_m(dt),fmt_m(et),"O" if ok else "X",
                            "" if ok else "A-A↔상세도↔Excel 두께 불일치"))

        # Shear connector spacing: explicit n@spacing only, to avoid guessing unrelated dimensions.
        ps=c.get("top_shear_spacing",[]); aas=c.get("aa_shear_spacing",[])
        if ps and aas:
            ok=ps==aas
            rows.append(row(typ,"전단연결재 간격(A-A)",fmt_list(aas),"평면도(상면) "+fmt_list(ps),"","O" if ok else "X",
                            "" if ok else "평면도↔A-A 전단연결재 간격 불일치"))
        else:
            rows.append(row(typ,"전단연결재 간격(A-A)",fmt_list(aas),fmt_list(ps),"","확인","명시된 @ 간격 인식 필요"))

        # Reinforcement spacing: only explicit @ dimensions are auto-judged.
        rp=c.get("rebar_plan_spacing",[]); ra=c.get("rebar_aa_spacing",[])
        if rp and ra:
            ok=rp==ra
            rows.append(row(typ,"철근 간격(A-A)",fmt_list(ra),"배근도(평면) "+fmt_list(rp),"","O" if ok else "X",
                            "" if ok else "배근도 평면↔A-A 철근 간격 불일치"))
        else:
            rows.append(row(typ,"철근 간격(A-A)",fmt_list(ra),fmt_list(rp),"","확인",
                            "명시된 @ 철근간격을 찾지 못해 자동판정하지 않음"))

        # Shear connector type: section A-A label/shape family vs material table notation.
        ak=c.get("aa_shear_kind",""); mk=c.get("material_shear_kind","")
        if ak and mk and ak!="혼합" and mk!="혼합":
            ok=ak==mk
            rows.append(row(typ,"전단연결재 종류(A-A)",ak,"재료표 "+mk,"","O" if ok else "X",
                            "" if ok else "A-A 전단연결재 종류↔재료표 불일치"))
        else:
            rows.append(row(typ,"전단연결재 종류(A-A)",ak or "인식 실패",mk or "인식 실패","","확인",
                            "전단연결재 상세/재료표 종류 추가 확인 필요"))
    return rows

def export_csv(rows,path):
    cols=["type","item","drawing","material","excel","result","note"]
    with open(path,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(rows)
