import csv
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as md
rows=list(csv.DictReader(open('eia_weekly.csv',newline='')))
d=[date.fromisoformat(r['week_date']) for r in rows]
p=[Decimal(r['price_usd_per_gal']) for r in rows]
print(len(rows), d[0], d[-1], len(set(d)))
assert all((d[i+1]-d[i]).days==7 for i in range(len(d)-1)), "gaps"
assert all(x.weekday()==0 for x in d)
s=[((x-Decimal('1.25'))/Decimal('6.2')).quantize(Decimal('0.01'),ROUND_HALF_UP) for x in p]
print('price min/max',min(p),max(p),'sur min/max',min(s),max(s))
print(rows[0]['series_id'],rows[0]['area'])
fig,ax=plt.subplots(figsize=(14,9),dpi=150)
ax.plot(d,[float(x) for x in p],color='#1f4e9c',lw=2,label='Diesel price ($/gal, left)')
ax.set_ylabel('Diesel price ($ per gallon)',color='#1f4e9c'); ax.set_xlabel('Week (Monday), EIA weekly release')
ax2=ax.twinx()
ax2.plot(d,[float(x) for x in s],color='#d9531e',lw=2,ls='--',label='Surcharge ($/mile, right)')
ax2.set_ylabel('Fuel surcharge ($ per mile) = (price - $1.25) / 6.2 mpg',color='#d9531e')
ax.xaxis.set_major_locator(md.MonthLocator()); ax.xaxis.set_major_formatter(md.DateFormatter('%b %Y'))
plt.setp(ax.get_xticklabels(),rotation=45,ha='right'); ax.grid(alpha=.3)
h1,l1=ax.get_legend_handles_labels();h2,l2=ax2.get_legend_handles_labels()
ax.legend(h1+h2,l1+l2,loc='upper left')
ttl=f"EIA Weekly Midwest (PADD 2) No 2 Diesel Retail Price (EMD_EPD2D_PTE_R20_DPG) and Fuel Surcharge\n52 weeks: {d[0]:%b %d, %Y} to {d[-1]:%b %d, %Y} (stand-in for Indiana)"
ax.set_title(ttl,fontsize=12)
fig.text(0.01,0.01,"Source: U.S. EIA, Weekly Midwest No 2 Diesel Retail Prices, series EMD_EPD2D_PTE_R20_DPG, eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMD_EPD2D_PTE_R20_DPG&f=W, retrieved 2026-10-16.\nMidwest (PADD 2) used as a stand-in for Indiana (no Indiana series confirmed). Surcharge = ROUND((price-1.25)/6.2, 2).",fontsize=7.5,va='bottom')
fig.tight_layout(rect=(0,0.07,1,1))
fig.savefig('diesel_price_surcharge.png',dpi=150)
from PIL import Image
print(Image.open('diesel_price_surcharge.png').size)
