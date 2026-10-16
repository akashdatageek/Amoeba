import re,json,datetime as D,glob,csv
idx=json.load(open('sources/index.json'))
lst=idx if isinstance(idx,list) else idx.get('sources',[])
u10=[e.get('url') for e in lst if e.get('source')=='S10'][0]
L=open(glob.glob('sources/S10*')[0]).read().split('\n')[:476]
d={}
for l in L:
    m=re.match(r'\| (\d{4})-(\w{3}) \|(.*)',l)
    if not m: continue
    y=int(m[1]);c=[x.strip() for x in m[3].split('|')]
    for i in range(0,len(c)-1,2):
        if re.match(r'\d\d/\d\d$',c[i]) and c[i+1]:
            d[D.date(y,int(c[i][:2]),int(c[i][3:]))]=float(c[i+1])
ks=sorted(d)[-52:]
print('n',len(ks),'first',ks[0],'last',ks[-1],'gaps',sorted({(b-a).days for a,b in zip(ks,ks[1:])}),'mondays',all(k.weekday()==0 for k in ks))
sid='EMD_EPD2D_PTE_R20_DPG'
with open('eia_prices.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow(['week_date','price_usd_per_gal','series_id','source_url','retrieved_date'])
    for k in ks:w.writerow([k.isoformat(),'%.3f'%d[k],sid,u10,'2026-10-16'])
print('| week_date | price_usd_per_gal | series_id | source_url |\n|---|---|---|---|')
for k in ks:print('| %s | %.3f | %s | %s |'%(k,d[k],sid,u10))
