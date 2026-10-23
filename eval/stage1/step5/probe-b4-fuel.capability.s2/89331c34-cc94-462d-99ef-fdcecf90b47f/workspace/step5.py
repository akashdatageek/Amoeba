import csv, datetime as dt
from decimal import Decimal as D, getcontext, ROUND_HALF_UP
getcontext().prec=40
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.dates as md
base,mpg,tr,mi=D('1.25'),D('6.2'),D(35),D(2300)
q=lambda x,p='0.01': x.quantize(D(p),rounding=ROUND_HALF_UP)
gal=tr*mi/mpg
rows=[]
for r in csv.DictReader(open('weekly_prices.csv',newline='')):
    p=D(r['price_usd_per_gal']); s=q((p-base)/mpg)
    rows.append((dt.date.fromisoformat(r['week_ending']),p,s,p*gal,p/mpg))
assert len(rows)==52
n=D(52)
ap=sum(r[1] for r in rows)/n; asur=sum(r[2] for r in rows)/n
tot=sum(r[3] for r in rows); avgw=tot/n; apm=sum(r[4] for r in rows)/n
hi=max(rows,key=lambda r:r[1]); lo=min(rows,key=lambda r:r[1])
atri_t,atri_x=D('2.336'),D('1.854'); atri_f=atri_t-atri_x
gap=apm-atri_f
print("Weeks:",rows[0][0],"to",rows[-1][0],"gallons/week",q(gal,'0.0001'))
print("| Metric | Value |\n|---|---|")
print(f"| Average price $/gal | {q(ap,'0.00001')} |")
print(f"| Average surcharge $/mi (mean of rounded weekly) | {q(asur,'0.0001')} |")
print(f"| Highest week | {hi[0]} price {hi[1]} surcharge {hi[2]} |")
print(f"| Lowest week | {lo[0]} price {lo[1]} surcharge {lo[2]} |")
print(f"| 52-wk total fleet fuel cost $ | {q(tot):,} |")
print(f"| Average weekly fleet fuel cost $ | {q(avgw):,} |")
print(f"| Carrier avg fuel $/mi | {q(apm,'0.0001')} |")
print(f"| ATRI total marginal $/mi (2025 data) | {atri_t} |")
print(f"| ATRI fuel $/mi (substitute 2.336-1.854) | {atri_f} |")
print(f"| ATRI fuel share | {q(atri_f/atri_t*100,'0.1')}% |")
print(f"| Gap carrier minus ATRI $/mi | {q(gap,'0.0001')} ({q(gap/atri_f*100,'0.1')}% of ATRI fuel) |")
print("\n| # | Band low | Band high | Midpoint | Surcharge $/mi |\n|---|---|---|---|---|")
for i in range(40):
    lw=D('3.00')+D('0.05')*i; h=lw+D('0.05'); m=(lw+h)/2
    print(f"| {i+1} | {lw} | {h} | {m} | {q((m-base)/mpg)} |")
fig,ax=plt.subplots(figsize=(12,6.8))
d=[r[0] for r in rows]
l1,=ax.plot(d,[float(r[1]) for r in rows],color='#1f4e79',marker='o',ms=3,lw=1.8,label='Midwest (PADD 2) diesel price ($/gal, left)')
ax.set_ylabel('Retail diesel price ($ per gallon)'); ax.set_xlabel('Week ending (Monday)')
ax2=ax.twinx()
l2,=ax2.plot(d,[float(r[2]) for r in rows],color='#c55a11',marker='s',ms=3,lw=1.8,ls='--',label='Fuel surcharge ($/mile, right)')
ax2.set_ylabel('Fuel surcharge ($ per mile)')
ax.xaxis.set_major_locator(md.WeekdayLocator(byweekday=md.MO,interval=4))
ax.xaxis.set_major_formatter(md.DateFormatter('%Y-%m-%d'))
plt.setp(ax.get_xticklabels(),rotation=45,ha='right')
ax.grid(alpha=.3)
ax.set_title(f'Midwest diesel price and fuel surcharge, 52 weeks ending {d[-1]}')
ax.legend(handles=[l1,l2],loc='upper left')
fig.text(0.01,0.025,'Source: EIA, Midwest (PADD 2) weekly retail diesel (EMD_EPD2D_PTE_R20_DPG), retrieved 2026-10-23. Surcharge = ROUND((price - 1.25)/6.2, 2).',fontsize=8)
fig.text(0.01,0.002,'Caption: the two lines look alike because the surcharge is linear in price (slope 1/6.2 per $).',fontsize=8)
fig.tight_layout(rect=(0,0.05,1,1))
fig.savefig('price_surcharge_chart.png',dpi=200)
from matplotlib.image import imread
print("PNG",imread('price_surcharge_chart.png').shape, "points",len(l1.get_xdata()),len(l2.get_xdata()))
