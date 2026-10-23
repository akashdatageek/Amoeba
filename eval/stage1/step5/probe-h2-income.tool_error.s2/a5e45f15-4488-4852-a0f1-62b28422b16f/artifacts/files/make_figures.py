import csv, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
CPI={2015:237.017,2023:304.702}
# nominal medians (survey-year dollars). 2015 US: S20 page value; others: see income_source text
N={('Indiana',2015):50532,('Indiana',2023):70051,('United States',2015):55775,('United States',2023):78538}
MOE={k:None for k in N}
f={y:CPI[2023]/CPI[y] for y in CPI}
print("factors",f)
adj={k:v*f[k[1]] for k,v in N.items()}
RET="2026-10-23"
cpis="BLS CUUR0000SA0 annual average (M13): 2015=237.017, 2023=304.702; https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true [S53][S55][S56]; BLS publication date not shown in API response; retrieved "+RET
src={('Indiana',2015):"ACS 2015 1-year B19013_001E, Indiana: 50,532 NOT confirmed from a fetched Census page (Census API returned Missing Key [S1]); value from analyst memory [unverified]; table ACSDT1Y2015.B19013 https://data.census.gov/table/ACSDT1Y2015.B19013; release date not confirmed",
('Indiana',2023):"ACS 2023 1-year B19013_001E, Indiana: 70,051 (2023 dollars) from third-party page quoting ACS (insights/indiana-median-household-income, web-search snippet, retrieved "+RET+") [unverified vs Census]; table ACSDT1Y2023.B19013 https://data.census.gov/table/ACSDT1Y2023.B19013 [S42] showed no values; release date not confirmed",
('United States',2015):"ACS 2015 1-year B19013_001E: 55,775 on data.census.gov table page [S20] (geography label not shown on page; matches US per analyst memory [unverified]); fetched "+RET+"; release date not confirmed",
('United States',2023):"ACS 2023 1-year B19013_001E, United States: 78,538 (2023 dollars) from third-party page quoting ACS (web-search snippet, retrieved "+RET+") [unverified vs Census]; table ACSDT1Y2023.B19013 [S42] showed no values; release date not confirmed"}
cols="geography,year,nominal_income_usd,income_moe_usd,cpi_u,adjustment_factor,adjusted_2023_usd,pct_change_nominal,pct_change_real,income_source,cpi_source,retrieved_date".split(",")
rows=[];chg={}
for g in ['Indiana','United States']:
    for y in (2015,2023):
        rows.append(dict(geography=g,year=y,nominal_income_usd=N[(g,y)],income_moe_usd="",cpi_u=CPI[y],adjustment_factor=repr(f[y]),adjusted_2023_usd=repr(adj[(g,y)]),pct_change_nominal="",pct_change_real="",income_source=src[(g,y)],cpi_source=cpis,retrieved_date=RET))
    pn=N[(g,2023)]/N[(g,2015)]-1; pr=adj[(g,2023)]/adj[(g,2015)]-1; chg[g]=(pn,pr)
    print(g,"adj2015",adj[(g,2015)],"adj2023",adj[(g,2023)],"nominal%",pn*100,"real%",pr*100)
    rows.append(dict(geography=g,year="2015-2023 change",nominal_income_usd="",income_moe_usd="",cpi_u="",adjustment_factor="",adjusted_2023_usd="",pct_change_nominal=repr(pn*100),pct_change_real=repr(pr*100),income_source="pct = 2023 vs 2015 from rows above; "+src[(g,2015)][:40]+" / "+src[(g,2023)][:40]+" (see rows above)",cpi_source=cpis,retrieved_date=RET))
with open("figures.csv","w",newline="") as fh:
    w=csv.DictWriter(fh,fieldnames=cols);w.writeheader();w.writerows(rows)
fig,ax=plt.subplots(figsize=(10,7))
gs=['Indiana','United States'];wd=0.35
for i,(y,c) in enumerate([(2015,'#9ecae1'),(2023,'#3182bd')]):
    xs=[j+(i-0.5)*wd for j in range(2)];vs=[adj[(g,y)] for g in gs]
    b=ax.bar(xs,vs,wd,label=str(y),color=c)
    for x,v in zip(xs,vs): ax.text(x,v+500,"${:,.0f}".format(v),ha='center',fontsize=10)
ax.set_xticks([0,1]);ax.set_xticklabels(gs);ax.set_xlabel("Geography");ax.set_ylabel("Median household income (2023 dollars)")
ax.set_ylim(0,max(adj.values())*1.15);ax.legend(title="Survey year")
ax.set_title("Real median household income, 2015 vs 2023 (2023 dollars)")
fig.text(0.5,0.01,"Sources: Census ACS 1-year B19013 (2015, 2023; values partly unverified, see note); BLS CPI-U CUUR0000SA0 annual avg (237.017, 304.702), retrieved 2026-10-23.\nReal = nominal x CPI_2023/CPI_year.",ha='center',fontsize=7.5)
fig.tight_layout(rect=(0,0.06,1,1));fig.savefig("real_income_chart.png",dpi=150)
