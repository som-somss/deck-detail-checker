import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from checker import run_check,export_csv
class App(tk.Tk):
 def __init__(self):
  super().__init__();self.title("DECK 상세도 자동 검토기 V18");self.geometry("1250x720");self.d=tk.StringVar();self.x=tk.StringVar();self.err=tk.BooleanVar(value=True);self.rows=[];self.ui()
 def ui(self):
  f=ttk.Frame(self,padding=12);f.pack(fill="x")
  for r,(lab,var,ext) in enumerate([("상세도 DXF",self.d,"*.dxf"),("집계표 Excel",self.x,"*.xlsx")]):
   ttk.Label(f,text=lab).grid(row=r,column=0);ttk.Entry(f,textvariable=var).grid(row=r,column=1,sticky="ew",padx=8);ttk.Button(f,text="찾기",command=lambda v=var,e=ext:self.pick(v,e)).grid(row=r,column=2)
  f.columnconfigure(1,weight=1);b=ttk.Frame(self,padding=(12,0,12,8));b.pack(fill="x")
  ttk.Button(b,text="자동 검토",command=self.check).pack(side="left");ttk.Checkbutton(b,text="오류만 보기",variable=self.err,command=self.show).pack(side="left",padx=10);ttk.Button(b,text="결과 CSV 저장",command=self.save).pack(side="left");self.s=ttk.Label(b);self.s.pack(side="right")
  cs=("type","item","drawing","material","excel","result","note");fr=ttk.Frame(self,padding=12);fr.pack(fill="both",expand=True);self.t=ttk.Treeview(fr,columns=cs,show="headings")
  names=["TYPE","항목","상세도 실제 형상","상세도 재료표","집계표","판정","비고"]
  for c,n in zip(cs,names):self.t.heading(c,text=n);self.t.column(c,width=160 if c not in ("type","result") else 90)
  self.t.tag_configure("needcheck",foreground="#d00000",font=("TkDefaultFont",9,"bold"))
  self.t.tag_configure("separator",foreground="#202020",font=("TkDefaultFont",8,"bold"))
  self.scroll_y=ttk.Scrollbar(self,orient="vertical",command=self.t.yview)
  self.t.configure(yscrollcommand=self.scroll_y.set)
  self.scroll_y.pack(side="right",fill="y")
  self.t.pack(side="left",fill="both",expand=True)
 def pick(self,v,e):
  p=filedialog.askopenfilename(filetypes=[("파일",e)])
  if p:v.set(p)
 def check(self):
  try:self.rows=run_check(self.d.get(),self.x.get());self.show()
  except Exception as e:messagebox.showerror("검토 오류",str(e))
 def show(self):
  self.t.delete(*self.t.get_children());a=[r for r in self.rows if not self.err.get() or r["result"]!="O"]
  last=None
  for r in a:
   if last is not None and r["type"]!=last:
    self.t.insert("", "end",values=("━━━━━━━━","━━━━━━━━━━━━━━━━","━━━━━━━━━━━━━━━━","━━━━━━━━━━━━━━━━","━━━━━━━━━━━━━━━━","━━━━","━━━━━━━━━━━━━━━━"),tags=("separator",))
   tags=("needcheck",) if r["result"] in ("확인","X") else ()
   self.t.insert("", "end",values=tuple(r[k] for k in ("type","item","drawing","material","excel","result","note")),tags=tags)
   last=r["type"]
  self.s.config(text=f"전체 {len(self.rows)} / 오류·확인 {sum(r['result']!='O' for r in self.rows)}")
 def save(self):
  p=filedialog.asksaveasfilename(defaultextension=".csv")
  if p:export_csv(self.rows,p)
if __name__=="__main__":App().mainloop()
