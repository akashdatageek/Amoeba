import csv,re,docx
from decimal import Decimal as D, ROUND_HALF_UP
def r2(x): return x.quantize(D('0.01'),ROUND_HALF_UP)
d=docx.Document('fuel_surcharge_memo.docx')
for p in d.paragraphs: print('P:',p.text)
t=d.tables[0]
pairs=[]
for r in t.rows[1:]:
    c=[x.text for x in r.cells]
    for i in range(0,len(c)-1,2): pairs.append((c[i],c[i+1]))
print('header',[x.text for x in t.rows[0].cells],'npairs',len(pairs))
bad=0
for i,(b,s) in enumerate(pairs):
    pass
exp={}
for i in range(40):
    lo=D('3.00')+D('0.05')*i; hi=lo+D('0.05')
    exp[f"${lo:.2f}–{hi:.2f}"]=f"${r2((lo+D('0.025')-D('1.25'))/D('6.2'))}"
got={b:s for b,s in pairs}
print('got',len(got))
for k,v in exp.items():
    if got.get(k)!=v: bad+=1;print('MISMATCH',k,v,got.get(k))
print('bad',bad,'extra',set(got)-set(exp))
for r in d.tables[1].rows: print('T1',[c.text for c in r.cells])
