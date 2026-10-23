import csv,re,docx,subprocess,os,shutil
from decimal import Decimal as D, ROUND_HALF_UP
def r2(x): return x.quantize(D('0.01'),ROUND_HALF_UP)
rows=list(csv.DictReader(open('weekly_prices.csv')))
pr=[(r['week_ending'],D(r['price_usd_per_gal'])) for r in rows]
gal=D(80500)/D('6.2')
sc=[r2((p-D('1.25'))/D('6.2')) for _,p in pr]
cost=[p*gal for _,p in pr]
avgp=sum(p for _,p in pr)/52
print(len(pr),pr[0],pr[-1],'avgp',avgp,'avgsc',sum(sc)/52,'tot',sum(cost),'avgcost',sum(cost)/52,'fuelmi',avgp/D('6.2'))
hi=max(pr,key=lambda x:x[1]);lo=min(pr,key=lambda x:x[1])
for n,w in(('hi',hi),('lo',lo)):
    i=pr.index(w);print(n,w,sc[i],r2(cost[i]))
print('latest',pr[-1],r2((pr[-1][1]-D('1.25'))/D('6.2')),r2(cost[-1]))
d=docx.Document('fuel_surcharge_memo.docx')
txt='\n'.join(p.text for p in d.paragraphs)
print(txt)
print('----TABLES')
bands=[]
for ti,t in enumerate(d.tables):
    for r in t.rows:
        cells=[c.text for c in r.cells]
        print(ti,cells)
# expected bands
exp=[]
for i in range(40):
    lo_=D('3.00')+D('0.05')*i; mid=lo_+D('0.025')
    exp.append((lo_,r2((mid-D('1.25'))/D('6.2'))))
print('EXP',[(str(a),str(b)) for a,b in exp])
# parse band table
t=d.tables[0]; found=[]
alltxt=' '.join(c.text for r in t.rows for c in r.cells)
print('ALLBAND',alltxt[:1500])
print('sections',d.sections[0].page_width,d.sections[0].left_margin)
print('inline shapes',len(d.inline_shapes))
print(shutil.which('soffice'),shutil.which('libreoffice'))
