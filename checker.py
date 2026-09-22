import csv
from dxf_reader import read_dxf_specs, read_v7_cross_checks, read_v8_connector_checks
from connector_v9 import read_connector_v9
from connector_v10 import analyze as read_connector_v10
from connector_shape_v11 import analyze as read_shape_v11
from connector_v13 import analyze as read_connector_v13
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
    conn=read_v8_connector_checks(dxf)
    conn9=read_connector_v9(dxf)
    conn10=read_connector_v10(dxf)
    shape11=read_shape_v11(dxf)
    conn13=read_connector_v13(dxf)
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

        # V8: connector detail / A-A / B-B / material-table cross checks.
        cc=conn.get(typ,{})
        dknd=cc.get("detail_kind",""); aknd=cc.get("aa_shape_kind",""); bknd=cc.get("bb_shape_kind","")
        mknd=cc.get("material_kind","")
        known=[v for v in (dknd,aknd,bknd,mknd) if v and v!="혼합"]
        if len(known)>=2:
            ok=len(set(known))==1
            rows.append(row(typ,"전단연결재 종류 교차검토",
                            f"A-A:{aknd or '확인'} / B-B:{bknd or '확인'}",
                            f"상세:{dknd or '확인'} / 재료표:{mknd or '확인'}","",
                            "O" if ok else "X",
                            "" if ok else "A-A/B-B/전단연결재상세/재료표 종류 불일치"))
        else:
            rows.append(row(typ,"전단연결재 종류 교차검토",
                            f"A-A:{aknd or '확인'} / B-B:{bknd or '확인'}",
                            f"상세:{dknd or '확인'} / 재료표:{mknd or '확인'}","",
                            "확인","형상/표기 중 2곳 이상 확정 필요"))

        # Diameter is never hard-coded: compare only explicitly read values.
        dphis=cc.get("truss_phi",[]) if (dknd=="TRUSS GR" or "TRUSS GR" in known) else cc.get("wave_phi",[])
        mphis=cc.get("material_truss_phi",[]) if (dknd=="TRUSS GR" or "TRUSS GR" in known) else cc.get("material_wave_phi",[])
        if dphis and mphis:
            ok=set(dphis)==set(mphis)
            rows.append(row(typ,"전단연결재 직경",
                            ", ".join("Φ"+f"{v:g}" for v in dphis),
                            ", ".join("Φ"+f"{v:g}" for v in mphis),"",
                            "O" if ok else "X","" if ok else "전단연결재 상세↔재료표 직경 불일치"))
        else:
            rows.append(row(typ,"전단연결재 직경",
                            ", ".join("Φ"+f"{v:g}" for v in dphis) if dphis else "인식 실패",
                            ", ".join("Φ"+f"{v:g}" for v in mphis) if mphis else "인식 실패","",
                            "확인","직경은 Φ12/Φ16 등 고정하지 않으며 명시값 인식 필요"))

        # TRUSS height is also variable (125/135/150 etc.) and must match material table.
        if "TRUSS GR" in known:
            dh=cc.get("truss_height"); mhs=cc.get("material_truss_heights",[])
            if dh is not None and mhs:
                ok=any(abs(dh-v)<=0.5 for v in mhs)
                rows.append(row(typ,"TRUSS GR 높이",f"{dh:g} mm",
                                ", ".join(f"{v:g} mm" for v in mhs),"",
                                "O" if ok else "X","" if ok else "전단연결재 상세 왼쪽 높이↔재료표 높이 불일치"))
            else:
                rows.append(row(typ,"TRUSS GR 높이",f"{dh:g} mm" if dh is not None else "인식 실패",
                                ", ".join(f"{v:g} mm" for v in mhs) if mhs else "인식 실패","",
                                "확인","높이는 고정하지 않으며 상세 왼쪽 치수와 재료표 명시값을 비교"))

        # V9: 전단연결재 간격→수량, 길이 교차검토.
        v9=conn9.get(typ,{})
        sps=v9.get("spacing",[])
        # Deduplicate same written spacing.
        uniq={}
        for q in sps:
            uniq[(q["n_space"],q["spacing"],q["total"])]=q
        for q in uniq.values():
            arithmetic_ok=abs(q["n_space"]*q["spacing"]-q["total"])<=0.5
            rows.append(row(typ,"전단연결재 간격/계산수량",
                f'{q["n_space"]}@{q["spacing"]:g}={q["total"]:g} mm → {q["calculated_qty"]}EA',
                "","",
                "O" if arithmetic_ok else "X",
                "" if arithmetic_ok else "간격수×간격과 총 배치길이가 불일치"))
        # Length evidence: top left/right and B-B are cross-check sources.
        tl=v9.get("top_lengths",[]); bl=v9.get("bb_lengths",[]); dl=v9.get("detail_lengths",[])
        if tl or bl or dl:
            sets=[set(x) for x in (tl,bl,dl) if x]
            common=set.intersection(*sets) if len(sets)>=2 else set()
            rows.append(row(typ,"전단연결재 길이",
                "상면 L="+(",".join(f"{x:g}" for x in tl) if tl else "확인"),
                "B-B L="+(",".join(f"{x:g}" for x in bl) if bl else "확인"),
                "상세 L="+(",".join(f"{x:g}" for x in dl) if dl else "확인"),
                "O" if len(sets)>=2 and common else "확인",
                "" if len(sets)>=2 and common else "상면 좌/우·B-B·상세의 종류/직경별 길이 연결 확인 필요"))
        # V10 - user-defined connector rules (test output)
        z10=conn10.get(typ,{})
        for _x,_y,n,sp,total,raw in z10.get("spacing",[]):
            ok=abs(n*sp-total)<=0.5
            rows.append(row(typ,"전단연결재 간격 산술검토",
                f"{n}@{sp:g}={total:g}","","","O" if ok else "X",
                "" if ok else f"{n}×{sp:g}≠{total:g}"))
        q55=z10.get("phi5_55_count",0)
        if q55:
            cand=z10.get("length_candidates",[])
            rows.append(row(typ,"Φ5 파형철선(끝단 55 기준)",
                f"끝단 55: {q55}곳 → Φ5 {q55}EA",
                "세로길이 후보: "+(", ".join(f"{v:g}" for v in cand) if cand else "인식 실패"),"",
                "확인","55로 수량 판정. 대응 좌/우 세로길이만 최종 매핑"))

        # V11 authoritative type classification: geometry first.
        sh=shape11.get(typ,{})
        vals=[sh.get("aa",""),sh.get("bb",""),sh.get("detail","")]
        known=[v for v in vals if v]
        if len(known)>=2:
            ok=len(set(known))==1
            rows.append(row(typ,"전단연결재 종류(A-A/B-B/상세)",
                f"A-A:{sh.get('aa') or '확인'} / B-B:{sh.get('bb') or '확인'}",
                f"전단연결재상세:{sh.get('detail') or '확인'}","",
                "O" if ok else "X",
                sh.get("note","")))
        else:
            rows.append(row(typ,"전단연결재 종류(A-A/B-B/상세)",
                f"A-A:{sh.get('aa') or '확인'} / B-B:{sh.get('bb') or '확인'}",
                f"전단연결재상세:{sh.get('detail') or '확인'}","",
                "확인","A-A와 B-B는 서로 다른 형상으로 판독하며, 2곳 이상에서 같은 전단연결재 종류가 확인되어야 확정 / "+sh.get("note","")))


        # V13 unified connector result
        q13=conn13.get(typ,{})
        k13=q13.get("kind","")
        rows.append(row(typ,"전단연결재 종류(V13)",
            k13 or "인식 실패"," / ".join(q13.get("evidence",[])) or "근거 인식 실패","",
            "X" if k13=="불일치" else ("O" if k13 else "확인"),
            "A-A/B-B/전단연결재 상세는 각 뷰의 고유 형상으로 종류 판독"))
        p5=q13.get("phi5_qty",0); tls=q13.get("top_lengths",[]); bls=q13.get("bb_lengths",[])
        # V14: main wave-wire row (Φ6 when Φ6 is explicitly present in detail/material evidence).
        # n@spacing means n spaces, therefore connector quantity is n+1.
        sp13=q13.get("top_spacing",[])
        matinfo=conn.get(typ,{})
        dphi=set(matinfo.get("detail",{}).get("wave_phi",[]) or [])
        mphi=set(matinfo.get("material",{}).get("wave_phi",[]) or [])
        phi6=(6 in dphi) or (6 in mphi)
        if k13=="파형철선":
            if sp13:
                n13, pitch13, total13=sp13[0]
                qty13=n13+1
                arith_ok=abs(n13*pitch13-total13)<=1.0
                name13="Φ6 파형철선 길이/수량" if phi6 else "주 전단연결재(파형철선) 길이/수량"
                len_txt=", ".join(f"{v:g}mm" for v in tls) if tls else "길이 인식 실패"
                rows.append(row(typ,name13,
                    f"{len_txt} / {n13}@{pitch13:g}={total13:g} → {qty13}EA",
                    "전단연결재 상세·재료표 Φ6 확인" if phi6 else "Φ6 직경 명시 인식 필요",
                    "B-B: "+(", ".join(f"{v:g}" for v in bls) if bls else "확인"),
                    ("O" if arith_ok and tls and phi6 else "확인"),
                    "간격 n개는 연결재 n+1EA. 길이는 상면/B-B 지정 세로치수만 사용"))
            else:
                rows.append(row(typ,
                    "Φ6 파형철선 길이/수량" if phi6 else "주 전단연결재(파형철선) 길이/수량",
                    "상면 n@간격 인식 실패",
                    "전단연결재 상세·재료표 Φ6 확인" if phi6 else "Φ6 직경 명시 인식 필요",
                    "","확인","주 파형철선 수량·길이 확인 필요"))
        if p5:
            if len(tls)==p5:
                rows.append(row(typ,"Φ5 파형철선 길이/수량",
                    " / ".join(f"{v:g}mm×1EA" for v in tls),
                    f"끝단 55 {p5}곳 → {p5}EA",
                    "B-B: "+(", ".join(f"{v:g}" for v in bls) if bls else "확인"),
                    "O","상면 좌/우 세로치수 기준"))
            else:
                rows.append(row(typ,"Φ5 파형철선 길이/수량",
                    "상면 세로치수: "+(", ".join(f"{v:g}" for v in tls) if tls else "인식 실패"),
                    f"끝단 55 {p5}곳 → {p5}EA",
                    "B-B: "+(", ".join(f"{v:g}" for v in bls) if bls else "확인"),
                    "확인","55 수량과 대응 세로길이 개수가 일치하지 않음"))
        else:
            rows.append(row(typ,"Φ5 파형철선 길이/수량",
                "끝단 55 인식 실패",
                "상면 세로치수: "+(", ".join(f"{v:g}" for v in tls) if tls else "인식 실패"),
                "B-B: "+(", ".join(f"{v:g}" for v in bls) if bls else "확인"),
                "확인","평면도(상면) 끝단 55 위치 확인 필요"))
    # V13: remove obsolete connector diagnostics from V8~V12.
    # These used nearby L= values or old A-A heuristics and can conflict with the geometry-first result.
    obsolete={
        "전단연결재 종류(A-A)",
        "전단연결재 종류 교차검토",
        "전단연결재 길이",
        "전단연결재 직경",
        "TRUSS GR 높이",
        "전단연결재 종류(A-A/B-B/상세)",
        "Φ5 파형철선(끝단 55 기준)",
    }
    rows=[r for r in rows if r["item"] not in obsolete]
    return rows

def export_csv(rows,path):
    cols=["type","item","drawing","material","excel","result","note"]
    with open(path,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(rows)
