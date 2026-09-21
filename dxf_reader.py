import re
import ezdxf
from models import DeckSpec

TYPE_RE = re.compile(r"^M\d{2}-\d+(?:-\d+)?$", re.I)

def _text(e):
    if e.dxftype() == "TEXT":
        return e.dxf.text.strip()
    if e.dxftype() == "MTEXT":
        return e.plain_text().strip()
    return ""

def read_dxf_material_specs(path):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    texts = []
    for e in msp:
        if e.dxftype() not in ("TEXT", "MTEXT"):
            continue
        t = _text(e)
        if not t:
            continue
        p = e.dxf.insert
        texts.append((float(p.x), float(p.y), t, e.dxf.layer))

    # 상세도 재료표의 TYPE은 CZ-DIMT 레이어에 있고,
    # 바로 아래 '제원(mm)' 및 우측 '재료표'가 함께 존재하는 앵커를 우선 사용.
    anchors = []
    for x, y, t, layer in texts:
        if not TYPE_RE.match(t):
            continue
        nearby = [z for z in texts if abs(z[0]-x) < 1200 and abs(z[1]-y) < 450]
        has_spec = any("제원" in z[2].replace(" ","") for z in nearby)
        has_material = any("재료" in z[2].replace(" ","") for z in nearby)
        if layer == "CZ-DIMT" and (has_spec or has_material):
            anchors.append((x,y,t))

    # 중복 TYPE이 있으면 재료표 제원값을 실제로 읽을 수 있는 앵커를 채택
    out = {}
    for ax, ay, typ in anchors:
        vals = []
        for x,y,t,layer in texts:
            dx, dy = x-ax, y-ay
            # 청람교 상세도 재료표의 데크 제원 행:
            # TYPE 아래 약 -112, x는 TYPE 기준 -100~+450 영역, 레이어 '데크규격'
            if layer == "데크규격" and -180 <= dy <= -60 and -120 <= dx <= 500:
                try:
                    vals.append((dx, float(t.replace(",",""))))
                except Exception:
                    pass
        vals.sort()
        nums = [v for _,v in vals]
        if len(nums) >= 2:
            # 재료표는 [폭, 길이] 또는 경사형이면 [폭1, 폭2, 길이] 가능
            if len(nums) >= 3:
                b1, b2, length = nums[0], nums[1], nums[-1]
            else:
                b1, b2, length = nums[0], nums[0], nums[1]
            candidate = DeckSpec(typ, b1, b2, length)
            out[typ] = candidate

    return out
