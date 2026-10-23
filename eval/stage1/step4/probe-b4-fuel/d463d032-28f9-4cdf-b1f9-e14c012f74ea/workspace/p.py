import re,datetime,csv
t=open('sources/S6_Weekly_Midwest_No_2_Diesel_Retail_Prices.txt').read()
rows=[]
for l in t.splitlines():
    m=re.match(r'\|\s*(\d{4})-([A-Za-z]{3})\s*\|(.*)',l)
    if not m: continue
    y=int(m.group(1))
    c=[x.strip() for x in m.group(3).split('|')]
    for i in range(0,len(c)-1,2):
        if re.match(r'\d\d/\d\d',c[i]) and c[i+1]:
            mo,d=map(int,c[i].split('/'))
            rows.append((datetime.date(y,mo,d),float(c[i+1])))
rows=sorted(set(rows))
last=rows[-52:]
print(len(rows),rows[-1],last[0])
ok=all((last[i+1][0]-last[i][0]).days==7 for i in range(51))
mon=all(d.weekday()==0 for d,_ in last)
print('spacing7',ok,'allMonday',mon)
sid='EMD_EPD2D_PTE_R20_DPG'
url='https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=emd_epd2d_pte_r20_dpg&f=W'
with open('eia_weekly_diesel.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow(['week_date','price_usd_per_gal','series_id','source_url','retrieved_date'])
    for d,p in last:w.writerow([d.isoformat(),f'{p:.3f}',sid,url,'2026-10-22'])
print(sum(p for _,p in last)/52,min(last,key=lambda x:x[1]),max(last,key=lambda x:x[1]))
for d,p in last:print(d,p,end='; ')
