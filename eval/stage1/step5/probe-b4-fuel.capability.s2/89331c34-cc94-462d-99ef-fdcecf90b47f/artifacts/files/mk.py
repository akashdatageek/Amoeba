import re,glob,csv,datetime as dt
rows={}
f=glob.glob('sources/S3_*')[0]
t=open(f).read()
for p,v in re.findall(r'"period":"(\d{4}-\d{2}-\d{2})"[^}]*?"value":"([\d.]+)"',t): rows[p]=v
ds=sorted(rows)[-52:]
d=[dt.date.fromisoformat(x) for x in ds]
assert len(ds)==52 and all((b-a).days==7 for a,b in zip(d,d[1:]))
url="https://api.eia.gov/v2/petroleum/pri/gnd/data/?frequency=weekly&data[0]=value&facets[series][]=EMD_EPD2D_PTE_R20_DPG&sort[0][column]=period&sort[0][direction]=desc&length=52 (api_key=DEMO_KEY)"
with open('weekly_prices.csv','w',newline='') as o:
    w=csv.writer(o);w.writerow(['week_ending','price_usd_per_gal','series_id','source_url','retrieved_date'])
    for x in ds: w.writerow([x,rows[x],'EMD_EPD2D_PTE_R20_DPG',url,'2026-10-23'])
open('raw_eia.txt','w').write('\n'.join(f'{x},{rows[x]}' for x in ds))
vals=[float(rows[x]) for x in ds]
print(len(ds),ds[0],ds[-1],min(vals),max(vals),sum(vals)/52, rows[ds[0]],rows[ds[-1]])
print(min(zip(vals,ds)),max(zip(vals,ds)))
