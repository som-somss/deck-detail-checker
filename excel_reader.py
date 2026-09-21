from openpyxl import load_workbook
from models import DeckSpec

def read_excel_specs(path):
    # 수식 계산값(cached value)을 읽는다.
    wb = load_workbook(path, data_only=True, read_only=True)
    if "제원입력" not in wb.sheetnames:
        raise ValueError("Excel에서 '제원입력' 시트를 찾지 못했습니다.")
    ws = wb["제원입력"]

    out = {}
    for r in range(5, ws.max_row + 1):
        typ = ws.cell(r, 2).value
        if not isinstance(typ, str) or not typ.strip():
            continue
        typ = typ.strip()
        if not typ.upper().startswith("M"):
            continue

        # 현재 청람교 집계표 구조:
        # C=폭 시작값(경사형일 때), E=기본/끝 폭, G=길이, I=추가 끝 폭, O=DECK 수량
        c = _num(ws.cell(r, 3).value)
        e = _num(ws.cell(r, 5).value)
        g = _num(ws.cell(r, 7).value)
        i = _num(ws.cell(r, 9).value)
        qty = _int(ws.cell(r, 15).value)

        if c is not None and e is not None:
            b1, b2 = c, e
        elif e is not None and i is not None:
            b1, b2 = e, i
        else:
            b1 = e if e is not None else c
            b2 = i if i is not None else b1

        out[typ] = DeckSpec(typ, b1, b2, g, qty)
    return out

def _num(v):
    try:
        if v in (None, ""): return None
        return float(v)
    except Exception:
        return None

def _int(v):
    try:
        if v in (None, ""): return None
        return int(round(float(v)))
    except Exception:
        return None
