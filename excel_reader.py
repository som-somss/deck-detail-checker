import re, zipfile, xml.etree.ElementTree as ET
from models import Spec, ExcelInfo

NS="{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

def _col(s):
    return re.match(r"[A-Z]+",s).group()

def _shared(z):
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    r=ET.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in x.iter(NS+"t")) for x in r.findall(NS+"si")]

def _sheet(z,name):
    wb=ET.fromstring(z.read("xl/workbook.xml"))
    rel=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    R="{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    rid=None
    for s in wb.find(NS+"sheets"):
        if s.attrib.get("name")==name:
            rid=s.attrib.get(R); break
    if not rid:
        raise ValueError("Excel에서 '제원입력' 시트를 찾지 못했습니다.")
    for q in rel:
        if q.attrib.get("Id")==rid:
            t=q.attrib["Target"].lstrip("/")
            return t if t.startswith("xl/") else "xl/"+t
    raise ValueError("Excel 시트 연결정보 오류")

def read_excel_specs(path):
    out={}
    with zipfile.ZipFile(path) as z:
        ss=_shared(z)
        root=ET.fromstring(z.read(_sheet(z,"제원입력")))
        for row in root.iter(NS+"row"):
            d={}
            for c in row.findall(NS+"c"):
                v=c.find(NS+"v")
                if v is None:
                    continue
                val=v.text
                if c.attrib.get("t")=="s":
                    val=ss[int(val)]
                d[_col(c.attrib["r"])]=val
            typ=str(d.get("B","")).strip()
            if not re.fullmatch(r"M\d{2}-\d+(?:-\d+)?",typ,re.I):
                continue
            def n(k):
                try: return float(d[k])
                except: return None
            c,e,g=n("C"),n("E"),n("G")
            b1=c if c is not None else e
            b2=e if e is not None else b1
            spec=Spec(typ,b1,b2,g) if b1 is not None and g is not None else None
            cnt=n("M")
            out[typ]=ExcelInfo(
                spec=spec,
                thickness=n("J"),
                rib_length=n("K"),
                rib_thickness=n("L"),
                rib_count=int(round(cnt)) if cnt is not None else None,
                deck_kind=str(d.get("P","")).strip()
            )
    return out
