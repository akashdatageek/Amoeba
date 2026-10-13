cd sources; grep -n -o -E ".{300}232\.957 236\.736 237\.017.{200}" S11_*.txt | head -3; cd ..; cat > income_inputs.json <<'EOF'
{"note":"Step 1 retrieved no ACS B19013 values; fill from Census with cited URL before rerunning build.py. Do not use memory.",
 "United States":{"2015":{"est":null,"moe":null},"2023":{"est":null,"moe":null}},
 "Indiana":{"2015":{"est":null,"moe":null},"2023":{"est":null,"moe":null}}}
EOF
cat > build.py <<'EOF'
import json, re, csv, math
from decimal import Decimal, getcontext
getcontext().prec = 50
RD = "2026-10-13"
s11 = open("sources/S11_Monthly_Energy_Review_September_2026.txt").read()
m = re.search(r"((?:\d{3}\.\d{3}\s+){3})(232\.957)\s+(236\.736)\s+(237\.017)\s+(240\.007)\s+(245\.120)\s+(251\.107)\s+(255\.657)\s+(258.811)\s+(270\.970)\s+(292\.655)\s+(304\.702)", s11)
assert m, "CPI row not found"
# anchors: 2013=232.957 (S10, BLS series per CPSC), 2023=304.702 (S10): positions 2013..2023 in row
vals = [m.group(i) for i in range(2, 13)]
cpi = {2013 + i: v for i, v in enumerate(vals)}
assert cpi[2013] == "232.957" and cpi[2023] == "304.702"
c15, c23 = cpi[2015], cpi[2023]
factor_f = float(c23) / float(c15)
factor_d = Decimal(c23) / Decimal(c15)
assert abs(Decimal(factor_f) - factor_d) < Decimal("1e-12")
inc = json.load(open("income_inputs.json"))
rows = []
def add(g, metric, yr, val, unit, basis, url, name, formula=""):
    rows.append([g, metric, yr, val, unit, basis, url, name, RD, formula])
S11U = "https://www.eia.gov/totalenergy/data/monthly/pdf/mer.pdf"
S10U = "https://www.cpsc.gov/s3fs-public/Decisional-Package-Draft-Proposed-Rule-to-Establish-a-Safety-Standard-for-Lit"
add("United States","CPI-U annual avg (CUUR0000SA0)",2015,c15,"index 1982-84=100","n/a",S11U,"EIA Monthly Energy Review Sept 2026 [S11] (secondary; reproduces BLS CPI-U; not a BLS page)")
add("United States","CPI-U annual avg (CUUR0000SA0)",2023,c23,"index 1982-84=100","n/a",S11U,"EIA Monthly Energy Review Sept 2026 [S11]; 2023 also in CPSC doc [S10] (secondary); BLS pages not retrieved")
add("United States","CPI-U annual avg (CUUR0000SA0)",2013,cpi[2013],"index 1982-84=100","n/a",S10U,"CPSC document citing BLS CUUR0000SA0 [S10] (anchor: matches S11 position for 2013)")
add("United States","CPI factor 2015->2023",2023,repr(factor_f),"ratio","n/a","","derived","CPI2023 / CPI2015 = %s / %s" % (c23, c15))
tot = {}
for g in ["Indiana","United States"]:
    e15, m15 = inc[g]["2015"]["est"], inc[g]["2015"]["moe"]
    e23, m23 = inc[g]["2023"]["est"], inc[g]["2023"]["moe"]
    if None in (e15, m15, e23, m23):
        for y in (2015, 2023):
            add(g,"Median household income (B19013_001E)",y,"NOT RETRIEVED","USD","as published","https://data.census.gov/table/ACSDT1Y%d.B19013" % y,"ACS 1-year B19013; Step 1 failed (no API key; grid not rendered) [S1][S2][S7]")
            add(g,"Margin of error (B19013_001M)",y,"NOT RETRIEVED","USD","as published","https://data.census.gov/table/ACSDT1Y%d.B19013" % y,"ACS 1-year B19013; Step 1 failed [S1][S2][S7]")
        continue
    adj = e15 * factor_f; madj = m15 * factor_f
    nom = e23 / e15 - 1; real = e23 / adj - 1
    sig = abs(e23 - adj) > math.hypot(madj, m23)
    tot[g] = dict(e15=e15, adj=adj, e23=e23, nom=nom, real=real, m15=m15, madj=madj, m23=m23, sig=sig)
    add(g,"Median household income",2015,e15,"USD","2015 dollars","https://data.census.gov/table/ACSDT1Y2015.B19013","ACS 1-year B19013")
    add(g,"Median household income",2023,e23,"USD","2023 dollars","https://data.census.gov/table/ACSDT1Y2023.B19013","ACS 1-year B19013")
    add(g,"MOE",2015,m15,"USD","2015 dollars","https://data.census.gov/table/ACSDT1Y2015.B19013","ACS 1-year B19013")
    add(g,"MOE",2023,m23,"USD","2023 dollars","https://data.census.gov/table/ACSDT1Y2023.B19013","ACS 1-year B19013")
    add(g,"Income 2015 in 2023$",2015,round(adj,2),"USD","2023 dollars","","derived","nominal2015 x factor")
    add(g,"Nominal % change",2023,nom*100,"percent","nominal","","derived","nominal2023/nominal2015-1")
    add(g,"Real % change",2023,real*100,"percent","2023 dollars","","derived","nominal2023/adj2015-1")
    add(g,"Adjusted 2015 MOE",2015,madj,"USD","2023 dollars","","derived","MOE2015 x factor")
    add(g,"Significant real change",2023,str(sig),"flag","2023 dollars","","derived","|e23-adj15|>sqrt(madj^2+m23^2)")
with open("mi_income_indiana_us.csv","w",newline="") as f:
    w = csv.writer(f)
    w.writerow(["geography","metric","year","value","unit","dollar_basis","source_url","source_name","retrieval_date","formula"])
    w.writerows(rows)
if len(tot) == 2:
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    geos = ["Indiana","United States"]; labels = ["2015 nominal","2015 in 2023 dollars","2023"]
    fig, ax = plt.subplots(figsize=(9,6)); wd = 0.25; pv = {}
    for j, lab in enumerate(labels):
        ys = [tot[g][["e15","adj","e23"][j]] for g in geos]
        bars = ax.bar([i + (j-1)*wd for i in range(2)], ys, wd, label=lab)
        for b, y in zip(bars, ys): ax.text(b.get_x()+b.get_width()/2, y, "${:,.0f}".format(y), ha="center", va="bottom", fontsize=8)
        pv[lab] = dict(zip(geos, ys))
    for i, g in enumerate(geos):
        ax.text(i, max(tot[g]["e15"], tot[g]["adj"], tot[g]["e23"])*1.07, "Real change %+.1f%%" % (tot[g]["real"]*100), ha="center", fontweight="bold")
    ax.set_xticks(range(2)); ax.set_xticklabels(geos); ax.set_ylabel("Median household income (USD)")
    ax.set_title("Median household income, 2015 vs 2023, in 2023 dollars"); ax.legend(loc="lower right")
    ax.set_ylim(0, max(max(t["e15"], t["adj"], t["e23"]) for t in tot.values())*1.2)
    fig.text(0.01, 0.01, "Source: ACS 1-year B19013; BLS CPI-U CUUR0000SA0 annual average (via EIA MER [S11]).", fontsize=7)
    fig.savefig("real_median_household_income.png", dpi=150, bbox_inches="tight")
    json.dump(dict(plotted=pv, real_pct={g: tot[g]["real"]*100 for g in geos}), open("plotted_values.json","w"), indent=1)
    print("chart written")
else:
    json.dump({"plotted": None, "reason": "income inputs not retrieved"}, open("plotted_values.json","w"))
    print("chart NOT drawn: income inputs missing")
print("CPI", cpi); print("factor float", repr(factor_f), "decimal", factor_d)
EOF
python3 build.py; echo; cat mi_income_indiana_us.csv | cut -c1-220; ls</parameter>
