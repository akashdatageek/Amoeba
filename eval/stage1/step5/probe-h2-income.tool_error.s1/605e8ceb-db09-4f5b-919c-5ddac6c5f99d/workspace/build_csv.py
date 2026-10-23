import csv
RET="2026-10-23"
CPI={2015:237.017,2016:240.007,2017:245.120,2018:251.107,2019:255.657,2020:258.811,2021:270.970,2022:292.655,2023:304.702}  # BLS API v2 CUUR0000SA0 M13 [S59]/[S63]
CPI_URL="https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2015&endyear=2023&annualaverage=true"
NOM={}  # (year,geo)->(estimate,moe); NO sourced ACS values were retrieved (steps 1-5), so left empty
GEOS=[("Indiana","state:18"),("United States","us:1")]
cols=["year","geography","acs_nominal_usd","acs_moe_usd","cpi_u_annual_avg","adjusted_2023_usd","nominal_pct_change_2015_2023","real_pct_change_2015_2023","note","acs_source_url","cpi_source_url","retrieved_date"]
rows=[]
adj={}
for y in range(2015,2024):
    for g,f in GEOS:
        est,moe=NOM.get((y,g),(None,None))
        a=None if est is None else est*CPI[2023]/CPI[y]
        adj[(y,g)]=a
        note="ACS B19013 value UNAVAILABLE: Census API returned Missing Key / not retrieved; left blank, not filled"
        if y==2020: note="EXPERIMENTAL (no standard 2020 ACS 1-year release); "+note
        rows.append(dict(year=y,geography=g,acs_nominal_usd="" if est is None else est,acs_moe_usd="" if moe is None else moe,
          cpi_u_annual_avg=f"{CPI[y]:.3f}",adjusted_2023_usd="" if a is None else round(a),nominal_pct_change_2015_2023="",real_pct_change_2015_2023="",
          note=note,acs_source_url=f"https://api.census.gov/data/{y}/acs/acs1?get=NAME,B19013_001E,B19013_001M&for={f}",cpi_source_url=CPI_URL,retrieved_date=RET))
for g,f in GEOS:
    rows.append(dict(year="2015-2023",geography=g,acs_nominal_usd="",acs_moe_usd="",cpi_u_annual_avg=f"{CPI[2015]:.3f}->{CPI[2023]:.3f}",adjusted_2023_usd="",
      nominal_pct_change_2015_2023="",real_pct_change_2015_2023="",note="SUMMARY: percent changes cannot be computed; 2015 and 2023 ACS values unavailable. CPI-U change 2015->2023 = %.1f%%"%((CPI[2023]/CPI[2015]-1)*100),
      acs_source_url="https://api.census.gov/data/{2015,2023}/acs/acs1 (B19013)",cpi_source_url=CPI_URL,retrieved_date=RET))
with open("income_cpi_adjusted.csv","w",newline="") as fh:
    w=csv.DictWriter(fh,fieldnames=cols);w.writeheader();w.writerows(rows)
