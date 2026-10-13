import re, json, csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RET = "2026-10-13"
CPI_URL = "https://data.bls.gov/timeseries/CUUR0000SA0?years_option=all_years&include_graphs=false&annual_averages=true"
CPI_NAME = "BLS CPI-U CUUR0000SA0 (US city avg, all items, NSA, 1982-84=100), Data Viewer [S16]"
ACS_URL = "https://data.census.gov/table/ACSDT1Y2023.B19013?tid=ACSDT1Y2023.B19013"
ACS_NAME = "Census ACS 2023 1-year B19013, data.census.gov table page [S2]"

t = open("sources/S16_Bureau_of_Labor_Statistics_Data.txt", errors="ignore").read()
def row(y):
    m = re.search(r"\|\s*%d\s*\|([^\n]*)" % y, t)
    return [float(x) for x in re.findall(r"\d+\.\d+", m.group(1))]
r15, r23 = row(2015), row(2023)
m15, m23 = r15[:12], r23[:12]
cpi15 = round(sum(m15) / 12, 3)
cpi23 = round(sum(m23) / 12, 3)
# cross-check with HALF1/HALF2 columns shown in the BLS table
chk15 = round((r15[12] + r15[13]) / 2, 3)
chk23 = round((r23[12] + r23[13]) / 2, 3)
assert cpi15 == chk15 and cpi23 == chk23, (cpi15, chk15, cpi23, chk23)
factor = cpi23 / cpi15

US23, US23_MOE = 77719, 186   # S2, 1-year, United States column
rows = []
def add(g, metric, yr, val, unit, basis, url, name, formula=""):
    rows.append(dict(geography=g, metric=metric, year=yr, value=val, unit=unit, dollar_basis=basis,
                     source_url=url, source_name=name, retrieval_date=RET, formula=formula))
add("US", "CPI-U annual average (mean of 12 monthly values)", 2015, cpi15, "index 1982-84=100", "n/a", CPI_URL, CPI_NAME,
    "mean of Jan-Dec 2015 monthly values in S16: %s; equals mean of HALF1/HALF2 columns" % m15)
add("US", "CPI-U annual average (mean of 12 monthly values)", 2023, cpi23, "index 1982-84=100", "n/a", CPI_URL, CPI_NAME,
    "mean of Jan-Dec 2023 monthly values in S16: %s; equals mean of HALF1/HALF2 columns" % m23)
add("US", "CPI adjustment factor 2015->2023", "2015->2023", factor, "ratio", "n/a", CPI_URL, CPI_NAME,
    "CPI2023 / CPI2015 = %s / %s" % (cpi23, cpi15))
add("US", "price level change 2015->2023", "2015->2023", factor - 1, "fraction", "n/a", CPI_URL, CPI_NAME, "factor - 1")
add("US", "median household income (B19013_001E)", 2023, US23, "USD", "2023 dollars", ACS_URL, ACS_NAME)
add("US", "margin of error 90% (B19013_001M)", 2023, US23_MOE, "USD", "2023 dollars", ACS_URL, ACS_NAME)
NR = "NOT RETRIEVED"
for g in ("US", "Indiana"):
    for yr in (2015, 2023):
        if g == "US" and yr == 2023:
            continue
        add(g, "median household income (B19013_001E)", yr, NR, "USD", "not confirmed", "", "No source retrieved (Census API Missing Key [S1][S7]; table grid not rendered [S2])")
        add(g, "margin of error 90% (B19013_001M)", yr, NR, "USD", "not confirmed", "", "No source retrieved")
for g in ("US", "Indiana"):
    for m in ("2015 income in 2023 dollars", "nominal % change", "real % change"):
        add(g, m, "2015-2023", NR, "USD" if "dollars" in m else "percent", "2023 dollars", "", "Derived metric: inputs missing",
            "needs 2015 and 2023 income for %s" % g)
for m in ("real % change gap (IN - US)", "Indiana share of US 2015 (2023$)", "Indiana share of US 2023", "level difference IN-US with MOE"):
    add("IN vs US", m, "2015-2023", NR, "", "2023 dollars", "", "Derived metric: inputs missing", "needs Indiana and US incomes")
with open("mi_income_indiana_us.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

plotted = {"plotted": {"US": {"2023": US23}},
           "not_plotted_because_not_retrieved": ["US 2015", "Indiana 2015", "Indiana 2023"],
           "cpi15": cpi15, "cpi23": cpi23, "factor": factor, "us2023_moe": US23_MOE}
json.dump(plotted, open("plotted_values.json", "w"), indent=2)

fig, ax = plt.subplots(figsize=(10, 6.5))
labels = ["2015 nominal", "2015 in 2023 dollars", "2023 (2023 dollars)"]
cols = ["#9ecae1", "#3182bd", "#08519c"]
w = 0.25
for gi, g in enumerate(["Indiana", "United States"]):
    for k in range(3):
        x = gi + (k - 1) * w
        val = US23 if (g == "United States" and k == 2) else None
        if val is not None:
            ax.bar(x, val, w, color=cols[k], label=labels[k], yerr=US23_MOE, capsize=4)
            ax.text(x, val + 1500, "${:,.0f}".format(val), ha="center", fontsize=9)
        else:
            ax.text(x, 2500, "not\nretrieved", ha="center", fontsize=8, color="firebrick")
    ax.text(gi, 90000, "real % change: not computable\n(inputs not retrieved)", ha="center", fontsize=9)
ax.set_xticks([0, 1]); ax.set_xticklabels(["Indiana", "United States"])
ax.set_ylim(0, 100000)
ax.set_ylabel("Median household income (US dollars)")
ax.set_xlabel("Geography")
ax.set_title("Median household income, 2015 vs 2023, in 2023 dollars")
h, l = ax.get_legend_handles_labels()
from matplotlib.patches import Patch
ax.legend([Patch(color=c) for c in cols], labels, loc="lower right")
fig.text(0.01, 0.01, "Source: ACS 1-year B19013 (2023 US only retrieved, error bar = 90%% MOE); BLS CPI-U CUUR0000SA0 annual average "
         "(2015 = %s, 2023 = %s, factor %.6f). Other values not retrieved." % (cpi15, cpi23, factor), fontsize=7, wrap=True)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig("real_median_household_income.png", dpi=150)
print(cpi15, cpi23, repr(factor), chk15, chk23)
