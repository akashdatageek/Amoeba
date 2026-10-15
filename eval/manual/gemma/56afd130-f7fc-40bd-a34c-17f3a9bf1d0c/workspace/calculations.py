# Inputs from Market Data Sheet
diesel_price_gal = 5.64  # [S25]
diesel_mpg_min = 6.0     # [S1, S4, S6]
diesel_mpg_max = 8.0     # [S1, S4, S6]
diesel_mpg_avg = (diesel_mpg_min + diesel_mpg_max) / 2

bev_elec_rate_kwh = 14.15 / 100  # [S20]
bev_eff_min = 1.8                # [S1, S4]
bev_eff_max = 2.2                # [S1, S4]
bev_eff_avg = (bev_eff_min + bev_eff_max) / 2

diesel_price_min = 139000  # [S6, S12]
diesel_price_max = 180000  # [S6, S12]
diesel_price_avg = (diesel_price_min + diesel_price_max) / 2

bev_price_sticker = 400000  # [S12]
fed_incentive = 40000       # [S26, S28]
state_incentive = 0         # [S31]

miles_per_year = 60000
years = 7
fleet_size = 20

# Diesel Calculations
diesel_cost_per_mile = diesel_price_gal / diesel_mpg_avg
diesel_7yr_energy = diesel_cost_per_mile * miles_per_year * years
diesel_net_purchase = diesel_price_avg

# BEV Calculations
bev_cost_per_mile = bev_elec_rate_kwh * bev_eff_avg
bev_7yr_energy = bev_cost_per_mile * miles_per_year * years
bev_net_purchase = bev_price_sticker - fed_incentive - state_incentive

print(f"Diesel Cost/Mile: {diesel_cost_per_mile:.4f}")
print(f"Diesel 7yr Energy: {diesel_7yr_energy:.2f}")
print(f"Diesel Net Purchase: {diesel_net_purchase:.2f}")
print(f"BEV Cost/Mile: {bev_cost_per_mile:.4f}")
print(f"BEV 7yr Energy: {bev_7yr_energy:.2f}")
print(f"BEV Net Purchase: {bev_net_purchase:.2f}")
