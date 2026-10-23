import csv
cpi={2015:237.017,2016:240.007,2017:245.120,2018:251.107,2019:255.657,2020:258.811,2021:270.970,2022:292.655,2023:304.702}
nom={}  # no ACS values were retrieved: never filled
ACS="https://api.census.gov/data/{y}/acs/acs1?get=NAME,B19013_001E,B19013_001M&for={g}"
CPIU="https://api.bls.gov/publicAPI/v2/timeserie/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true".replace("timeserie/","timeseries/")
geos={"Indiana":"state:18","United States":"us:1"}
cols="year,geography,acs_nominal_usd,acs_moe_usd,cpi_u_annual_avg,adjusted_2023_usd,nominal_pct_change_2015_2023,real_pct_change_2015_2023,note,acs_source_url,cpi_source_url,retrieved_date".split(",")
rows=[]
def adj(y,g):
    n=nom.get((y,g)); return None if n is None else n*cpi[2023]/cpi[y]
for y in range(2015,2024):
    for g,c in geos.items():
        a=adj(y,g)
        note="ACS value UNAVAILABLE (Census API returned Missing Key; not filled)"
        if y==2020: note="EXPERIMENTAL: no standard 2020 ACS 1-year release (pandemic nonresponse); "+note
        rows.append(dict(year=y,geography=g,acs_nominal_usd="" if a is None else nom[(y,g)],acs_moe_usd="",cpi_u_annual_avg="%.3f"%cpi[y],adjusted_2023_usd="" if a is None else round(a),nominal_pct_change_2015_2023="",real_pct_change_2015_2023="",note=note,acs_source_url=ACS.format(y=y,g=c),cpi_source_url=CPIU,retrieved_date="2026-10-23"))
for g,c in geos.items():
    rows.append(dict(year="2015-2023",geography=g,acs_nominal_usd="",acs_moe_usd="",cpi_u_annual_avg="",adjusted_2023_usd="",nominal_pct_change_2015_2023="",real_pct_change_2015_2023="",note="Summary: percent changes not computable because 2015 and 2023 ACS values are missing; CPI-U change 2015-2023 = %.1f%%"%((cpi[2023]/cpi[2015]-1)*100),acs_source_url="",cpi_source_url=CPIU,retrieved_date="2026-10-23"))
with open("income_cpi_adjusted.csv","w",newline="") as f:
    w=csv.DictWriter(f,cols);w.writeheader();w.writerows(rows)
print("| year | geography | nominal | CPI | factor CPI23/CPIyr | adjusted 2023 $ | Indiana % of US | gap $ | formula check |\n|---|---|---|---|---|---|---|---|---|")
for y in cpi:
    for g in geos:
        print(f"| {y} | {g} | blank | {cpi[y]:.3f} | {cpi[2023]/cpi[y]:.4f} | blank | blank | blank | n/a (no nominal) |")
