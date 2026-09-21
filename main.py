import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from checker import run_check, export_csv


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DECK 상세도 자동 검토기 V1")
        self.geometry("1180x720")
        self.minsize(980, 620)
        self.dxf_path = tk.StringVar()
        self.xlsx_path = tk.StringVar()
        self.only_errors = tk.BooleanVar(value=True)
        self.results = []
        self._build()

    def _build(self):
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")

        ttk.Label(top, text="상세도 DXF").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Entry(top, textvariable=self.dxf_path).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Button(top, text="찾기", command=self.pick_dxf).grid(row=0, column=2, padx=6)

        ttk.Label(top, text="집계표 Excel").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Entry(top, textvariable=self.xlsx_path).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Button(top, text="찾기", command=self.pick_xlsx).grid(row=1, column=2, padx=6)

        top.columnconfigure(1, weight=1)

        btns = ttk.Frame(self, padding=(12, 0, 12, 8))
        btns.pack(fill="x")
        ttk.Button(btns, text="자동 검토", command=self.check).pack(side="left")
        ttk.Checkbutton(btns, text="오류만 보기", variable=self.only_errors, command=self.refresh).pack(side="left", padx=12)
        ttk.Button(btns, text="결과 CSV 저장", command=self.save_csv).pack(side="left")
        self.summary = ttk.Label(btns, text="")
        self.summary.pack(side="right")

        cols = ("type", "category", "item", "drawing", "table", "excel", "result", "note")
        frame = ttk.Frame(self, padding=(12, 0, 12, 12))
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        headings = {
            "type":"TYPE", "category":"검토구분", "item":"항목",
            "drawing":"상세도", "table":"상세도 재료표", "excel":"집계표",
            "result":"판정", "note":"비고"
        }
        widths = {"type":95,"category":100,"item":150,"drawing":135,"table":150,"excel":150,"result":70,"note":260}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="center" if c!="note" else "w")
        y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        x = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        note = ttk.Label(
            self,
            text="V1: DXF 재료표 제원 ↔ Excel 제원 자동 비교. CAD 실제 형상 치수 자동판독은 다음 단계에서 추가합니다.",
            padding=(12,0,12,10)
        )
        note.pack(fill="x")

    def pick_dxf(self):
        p = filedialog.askopenfilename(filetypes=[("DXF","*.dxf")])
        if p: self.dxf_path.set(p)

    def pick_xlsx(self):
        p = filedialog.askopenfilename(filetypes=[("Excel","*.xlsx")])
        if p: self.xlsx_path.set(p)

    def check(self):
        if not Path(self.dxf_path.get()).exists() or not Path(self.xlsx_path.get()).exists():
            messagebox.showwarning("파일 확인", "DXF와 Excel 파일을 모두 선택해주세요.")
            return
        try:
            self.results = run_check(self.dxf_path.get(), self.xlsx_path.get())
            self.refresh()
        except Exception as e:
            messagebox.showerror("검토 오류", str(e))

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        rows = [r for r in self.results if (not self.only_errors.get() or r["result"] != "O")]
        for r in rows:
            self.tree.insert("", "end", values=(
                r["type"], r["category"], r["item"], r["drawing"],
                r["table"], r["excel"], r["result"], r["note"]
            ))
        total = len(self.results)
        bad = sum(r["result"] != "O" for r in self.results)
        self.summary.config(text=f"검토 {total}건 / 오류·확인필요 {bad}건")

    def save_csv(self):
        if not self.results:
            messagebox.showinfo("안내", "먼저 자동 검토를 실행해주세요.")
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if p:
            export_csv(self.results, p)
            messagebox.showinfo("저장 완료", p)


if __name__ == "__main__":
    App().mainloop()
