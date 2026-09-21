import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from checker import run_check, export_csv

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DECK 상세도 자동 검토기 V2")
        self.geometry("1250x720")
        self.dxf_path = tk.StringVar()
        self.xlsx_path = tk.StringVar()
        self.only_errors = tk.BooleanVar(value=True)
        self.results = []
        self._ui()

    def _ui(self):
        top = ttk.Frame(self, padding=12); top.pack(fill="x")
        ttk.Label(top,text="상세도 DXF").grid(row=0,column=0,sticky="w",pady=4)
        ttk.Entry(top,textvariable=self.dxf_path).grid(row=0,column=1,sticky="ew",padx=8)
        ttk.Button(top,text="찾기",command=self.pick_dxf).grid(row=0,column=2)
        ttk.Label(top,text="집계표 Excel").grid(row=1,column=0,sticky="w",pady=4)
        ttk.Entry(top,textvariable=self.xlsx_path).grid(row=1,column=1,sticky="ew",padx=8)
        ttk.Button(top,text="찾기",command=self.pick_xlsx).grid(row=1,column=2)
        top.columnconfigure(1,weight=1)

        bar=ttk.Frame(self,padding=(12,0,12,8)); bar.pack(fill="x")
        ttk.Button(bar,text="자동 검토",command=self.check).pack(side="left")
        ttk.Checkbutton(bar,text="오류만 보기",variable=self.only_errors,command=self.refresh).pack(side="left",padx=10)
        ttk.Button(bar,text="결과 CSV 저장",command=self.save).pack(side="left")
        self.summary=ttk.Label(bar,text=""); self.summary.pack(side="right")

        cols=("type","item","drawing","material","excel","result","note")
        f=ttk.Frame(self,padding=(12,0,12,12)); f.pack(fill="both",expand=True)
        self.tree=ttk.Treeview(f,columns=cols,show="headings")
        names={"type":"TYPE","item":"항목","drawing":"상세도 실제 형상",
               "material":"상세도 재료표","excel":"집계표","result":"판정","note":"비고"}
        widths={"type":100,"item":110,"drawing":180,"material":180,"excel":180,"result":65,"note":300}
        for c in cols:
            self.tree.heading(c,text=names[c]); self.tree.column(c,width=widths[c],anchor="center" if c!="note" else "w")
        sy=ttk.Scrollbar(f,orient="vertical",command=self.tree.yview)
        sx=ttk.Scrollbar(f,orient="horizontal",command=self.tree.xview)
        self.tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        self.tree.grid(row=0,column=0,sticky="nsew"); sy.grid(row=0,column=1,sticky="ns"); sx.grid(row=1,column=0,sticky="ew")
        f.rowconfigure(0,weight=1); f.columnconfigure(0,weight=1)

    def pick_dxf(self):
        p=filedialog.askopenfilename(filetypes=[("DXF","*.dxf")])
        if p:self.dxf_path.set(p)
    def pick_xlsx(self):
        p=filedialog.askopenfilename(filetypes=[("Excel","*.xlsx")])
        if p:self.xlsx_path.set(p)
    def check(self):
        try:
            self.results=run_check(self.dxf_path.get(),self.xlsx_path.get())
            self.refresh()
        except Exception as e:
            messagebox.showerror("검토 오류",str(e))
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        rows=[r for r in self.results if not self.only_errors.get() or r["result"]!="O"]
        for r in rows:self.tree.insert("", "end", values=tuple(r[k] for k in ("type","item","drawing","material","excel","result","note")))
        self.summary.config(text=f"전체 {len(self.results)}건 / 오류·확인필요 {sum(r['result']!='O' for r in self.results)}건")
    def save(self):
        if not self.results:return
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if p: export_csv(self.results,p)

if __name__=="__main__":
    App().mainloop()
