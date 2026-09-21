import csv
from dxf_reader import read_dxf_material_specs
from excel_reader import read_excel_specs

TOL = 0.0015  # m, 약 1.5 mm

def close(a,b):
    if a is None or b is None:
        return False
    return abs(a-b) <= TOL

def widths_equal(a1,a2,b1,b2):
    aa = sorted([x for x in (a1,a2) if x is not None])
    bb = sorted([x for x in (b1,b2) if x is not None])
    if len(aa) != len(bb): return False
    return all(close(x,y) for x,y in zip(aa,bb))

def run_check(dxf_path, xlsx_path):
    dxf = read_dxf_material_specs(dxf_path)
    xls = read_excel_specs(xlsx_path)

    results = []
    all_types = sorted(set(dxf) | set(xls))
    for typ in all_types:
        ds = dxf.get(typ)
        es = xls.get(typ)
        if ds is None:
            results.append(row(typ, "TYPE", "TYPE 존재", "", "", es.display() if es else "", "X",
                               "DXF 상세도 재료표에서 TYPE을 찾지 못함"))
            continue
        if es is None:
            results.append(row(typ, "TYPE", "TYPE 존재", "", ds.display(), "", "X",
                               "Excel 제원입력에서 TYPE을 찾지 못함"))
            continue

        ok_b = widths_equal(ds.b1, ds.b2, es.b1, es.b2)
        results.append(row(
            typ, "데크 제원", "폭(B)",
            "V1 미지원", _width(ds), _width(es),
            "O" if ok_b else "X",
            "" if ok_b else "상세도 재료표와 Excel 폭이 다름"
        ))

        ok_l = close(ds.length, es.length)
        results.append(row(
            typ, "데크 제원", "길이(L)",
            "V1 미지원", _fmt(ds.length), _fmt(es.length),
            "O" if ok_l else "X",
            "" if ok_l else "상세도 재료표와 Excel 길이가 다름"
        ))

    return results

def _width(s):
    if s.b1 is None: return ""
    if s.b2 is not None and abs(s.b1-s.b2) > TOL:
        return f"{s.b1:.3f}~{s.b2:.3f}"
    return f"{s.b1:.3f}"

def _fmt(v):
    return "" if v is None else f"{v:.3f}"

def row(t,c,i,d,mt,x,r,n):
    return {"type":t,"category":c,"item":i,"drawing":d,"table":mt,"excel":x,"result":r,"note":n}

def export_csv(results, path):
    cols = ["type","category","item","drawing","table","excel","result","note"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(results)
