import csv
from decimal import Decimal, ROUND_HALF_UP
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

rows = list(csv.DictReader(open("eia_prices.csv", newline="")))
dates = [datetime.strptime(r["week_date"], "%Y-%m-%d") for r in rows]
price = [Decimal(r["price_usd_per_gal"]) for r in rows]
sur = [((p - Decimal("1.25")) / Decimal("6.2")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for p in price]
assert len(dates) == 52
pf = [float(p) for p in price]; sf = [float(s) for s in sur]

fig, ax1 = plt.subplots(figsize=(11, 6.2))
l1, = ax1.plot(dates, pf, color="#1f4e79", lw=2, marker="o", ms=3.5, label="Weekly diesel price ($/gal, left axis)")
ax1.set_xlabel("Week (Monday), %s to %s" % (dates[0].strftime("%d %b %Y"), dates[-1].strftime("%d %b %Y")))
ax1.set_ylabel("Retail on-highway diesel price ($ per gallon)", color="#1f4e79")
ax1.tick_params(axis="y", labelcolor="#1f4e79")
ax1.grid(alpha=0.3)
ax2 = ax1.twinx()
l2, = ax2.plot(dates, sf, color="#c55a11", lw=2, ls="--", marker="s", ms=3.5, label="Fuel surcharge ($/mile, right axis)")
ax2.set_ylabel("Fuel surcharge ($ per mile) = ROUND((price - 1.25) / 6.2, 2)", color="#c55a11")
ax2.tick_params(axis="y", labelcolor="#c55a11")
ax1.xaxis.set_major_locator(mdates.MonthLocator())
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
plt.setp(ax1.get_xticklabels(), rotation=45, ha="right")
ax1.set_title("Weekly diesel price and fuel surcharge per mile, 52 weeks\n(EIA Midwest PADD 2 proxy for Indiana)")
ax1.legend(handles=[l1, l2], loc="upper left")
fig.text(0.01, 0.01, "Source: U.S. EIA, series EMD_EPD2D_PTE_R20_DPG, Weekly Midwest No 2 Diesel Retail Prices; page released 9/22/2026, retrieved 2026-10-16. Base $1.25, 6.2 mpg.", fontsize=7, ha="left")
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig("price_surcharge_chart.png", dpi=150)
print(len(l1.get_xdata()), len(l2.get_xdata()), min(sf), max(sf), sf[0], sf[-1])
