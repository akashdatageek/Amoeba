import csv, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
rows=[r for r in csv.DictReader(open('income_cpi_adjusted.csv')) if r['year'].isdigit()]
years=list(range(2015,2024))
def val(y,g):
    for r in rows:
        if int(r['year'])==y and r['geography']==g:
            s=r['adjusted_2023_usd'].strip()
            return float(s) if s else math.nan
    return math.nan
ind=[val(y,'Indiana') for y in years]; us=[val(y,'United States') for y in years]
retr=next((r['retrieved_date'] for r in rows if r['retrieved_date']),'2026-10-23')
n_have=sum(0 if math.isnan(v) else 1 for v in ind+us)
fig,ax=plt.subplots(figsize=(12,7),dpi=150)
w=0.38; x=list(range(len(years)))
for i,y in enumerate(years):
    h='//' if y==2020 else None
    ax.bar(i-w/2,ind[i],w,color='#1f77b4',hatch=h,edgecolor='black',linewidth=0.5)
    ax.bar(i+w/2,us[i],w,color='#ff7f0e',hatch=h,edgecolor='black',linewidth=0.5)
i20=years.index(2020)
ax.axvspan(i20-0.5,i20+0.5,facecolor='none',hatch='//',edgecolor='grey',alpha=0.5)
ax.set_xticks(x); ax.set_xticklabels([str(y)+('*' if y==2020 else '') for y in years])
ax.set_ylim(0,100000)
ax.set_xlabel('Year (ACS 1-year estimate)'); ax.set_ylabel('Real median household income (2023 dollars)')
ax.set_title('Real median household income, Indiana vs United States, 2015-2023 (2023 dollars)')
if n_have==0:
    ax.text(0.5,0.55,'NO DATA PLOTTED: ACS B19013 values are blank in income_cpi_adjusted.csv\n(Census API returned "Missing Key"); nothing was estimated or filled in.',
            transform=ax.transAxes,ha='center',va='center',fontsize=12,color='darkred',bbox=dict(fc='white',ec='darkred'))
ax.legend(handles=[Patch(fc='#1f77b4',ec='black',label='Indiana'),Patch(fc='#ff7f0e',ec='black',label='United States'),
  Patch(fc='white',ec='black',hatch='//',label='2020: experimental ACS only (hatched)')],loc='upper left')
fn=('* 2020: no standard ACS 1-year release (pandemic nonresponse); only experimental estimates exist, shown hatched.\n'
 'Sources: U.S. Census Bureau, ACS 1-year, table B19013 (api.census.gov); BLS CPI-U, series CUUR0000SA0, annual average (api.bls.gov).\n'
 'Adjusted = nominal x CPI_2023 / CPI_year. Values read from income_cpi_adjusted.csv. Retrieved '+retr+'.')
fig.text(0.01,0.01,fn,fontsize=8,ha='left',va='bottom')
fig.tight_layout(rect=(0,0.10,1,1))
fig.savefig('real_income_indiana_vs_us.png',dpi=150)
import matplotlib.image as im
a=im.imread('real_income_indiana_vs_us.png'); print('px',a.shape[1],'x',a.shape[0],'plotted values',n_have,'retrieved',retr)
