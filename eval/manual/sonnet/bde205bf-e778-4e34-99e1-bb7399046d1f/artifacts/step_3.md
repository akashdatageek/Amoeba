sed -i 's/error bar = 90% MOE/error bar = 90%% MOE/' build.py && python3 build.py && ls -la mi_income_indiana_us.csv plotted_values.json real_median_household_income.png && cat plotted_values.json && python3 -c "
import csv
for r in csv.DictReader(open('mi_income_indiana_us.csv')): print(r['geography'],'|',r['metric'],'|',r['year'],'|',r['value'])
" | head -40
