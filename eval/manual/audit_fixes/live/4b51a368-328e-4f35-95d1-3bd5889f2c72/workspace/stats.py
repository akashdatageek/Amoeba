import csv, json
from decimal import Decimal as D, ROUND_HALF_UP
q=lambda x,p='0.01': x.quantize(D(p),rounding=ROUND_HALF_UP)
T,M,MPG,BASE=D(35),D(2300),D('6.2'),D('1.25')
rows=[(r['week_date'],D(r['price_usd_per_gal'])) for r in csv.DictReader(open('eia_prices.csv'))]
assert len(rows)==52
gal=T*M/MPG
wk=[]
for d,p in rows:
    wk.append(dict(week=d,price=str(p),surcharge=str(q((p-BASE)/MPG)),gallons=str(q(gal,'0.01')),fleet_cost=str(q(gal*p))))
tot=sum(gal*p for _,p in rows)
avg=sum(p for _,p in rows)/52
hi=max(rows,key=lambda r:r[1]); lo=min(rows,key=lambda r:r[1])
avgsur=q((avg-BASE)/MPG)
avg_cpm=avg/MPG
atri_t,atri_f=D('2.336'),D('0.482')
bands=[]
for i in range(41):
    lb=D('3.00')+D('0.05')*i
    lab='$5.00 and above' if i==40 else f"${lb:.2f}-{lb+D('0.049'):.3f}"
    bands.append(dict(lower=str(lb),label=lab,surcharge=str(q((lb-BASE)/MPG))))
st=dict(window=dict(first=rows[0][0],last=rows[-1][0],n=52,as_of_latest_week=rows[-1][0]),
 avg_price=str(q(avg,'0.0001')),avg_price_week_surcharge=str(avgsur),
 highest=dict(week=hi[0],price=str(hi[1]),surcharge=str(q((hi[1]-BASE)/MPG)),fleet_cost=str(q(gal*hi[1]))),
 lowest=dict(week=lo[0],price=str(lo[1]),surcharge=str(q((lo[1]-BASE)/MPG)),fleet_cost=str(q(gal*lo[1]))),
 fleet_gallons_per_week=str(q(gal,'0.01')),annual_gallons=str(q(gal*52,'0.01')),
 annual_fleet_fuel_cost=str(q(tot)),avg_weekly_fleet_fuel_cost=str(q(tot/52)),
 avg_fuel_cost_per_mile=str(q(avg_cpm,'0.0001')),
 atri=dict(edition='ATRI An Analysis of the Operational Costs of Trucking: 2026 Update (2025 cost year), released 15 July 2026',
  total_per_mile=str(atri_t),fuel_per_mile=str(atri_f),fuel_share_pct=str(q(atri_f/atri_t*100,'0.1')),
  carrier_minus_atri_fuel_per_mile=str(q(avg_cpm-atri_f,'0.0001')),
  carrier_over_atri_fuel_pct=str(q((avg_cpm/atri_f-1)*100,'0.1')),
  carrier_fuel_share_of_atri_total_pct=str(q(avg_cpm/atri_t*100,'0.1')),
  caveat="ATRI uses its own survey fuel price and fleet mpg (not 6.2 mpg, not Midwest PADD 2); 2025 cost year vs carrier 52 weeks to 2026-09-21",
  missing=[]),
 missing=["EIA weeks after 2026-09-21 not fetched (newer releases 9/29, 10/6 exist per S5); Indiana state series not found - Midwest PADD 2 proxy used"],
 weekly=wk,bands=bands)
json.dump(st,open('stats.json','w'),indent=1)
print("BANDS");[print(b['label'],b['surcharge']) for b in bands]
for k in ['window','avg_price','avg_price_week_surcharge','highest','lowest','annual_gallons','annual_fleet_fuel_cost','avg_weekly_fleet_fuel_cost','avg_fuel_cost_per_mile','atri']:
    print(k,st[k])
print(sum(1 for w in wk if D(w['surcharge'])>0), min(w['surcharge'] for w in wk), max(w['surcharge'] for w in wk))
