import csv
cpi={2015:237.017,2023:304.702}
base=cpi[2023]
print("factor 2015 =",base/cpi[2015],"factor 2023 =",base/cpi[2023])
acs="https://api.census.gov/data/{y}/acs/acs1 table B19013_001E (ACS 1-year, {y}) - NOT RETRIEVED (Missing Key)"
cs="https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0 series CUUR0000SA0 annual avg (M13), CPI-U NSA 1982-84=100; BLS cross-check table (released 2026)"
cols=["geography","year","nominal_median_household_income","cpi_u_annual_avg","cpi_base_2023","adjusted_2023_dollars","nominal_pct_change_2015_2023","real_pct_change_2015_2023","acs_source","cpi_source","retrieval_date"]
with open("figures.csv","w",newline="") as f:
    w=csv.writer(f);w.writerow(cols)
    for g in ["Indiana","United States"]:
        for y in (2015,2023):
            w.writerow([g,y,"NOT RETRIEVED",cpi[y],base,"NOT COMPUTED","NOT COMPUTED","NOT COMPUTED",acs.format(y=y),cs,"2026-10-22"])
rows=list(csv.DictReader(open("figures.csv")))
print(len(rows),"data rows;",list(rows[0].keys()))
