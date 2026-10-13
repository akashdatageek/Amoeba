# 7-yr per-truck TCO model: diesel vs BEV Class 8, Indiana. Undiscounted, no residual, net of incentives.
# NOTE: written in a run where Bash was unavailable; script NOT executed. Totals were checked with calc.
MILES_YR=60000; YEARS=7; FLEET=20; MILES=MILES_YR*YEARS  # 420,000 mi (task)
CHG_EFF=0.9
EXCISE=0.12                      # [S14] 12% federal heavy-truck excise tax, both powertrains
INCENTIVE=0                      # step 1 base case: $0/truck
# name: (low, base, high)
P_DIESEL=(150000,175000,200000)  # [S38] midpoint computed
P_BEV=(280000,340000,400000)     # [S38] midpoint computed
DIESEL_PRICE=(3.731,6.286,6.680) # [S32] low/high, [S28] base (Midwest PADD2, wk 2026-10-05)
MPG=6.5                          # [unverified] placeholder
KWH_MI=(1.2,1.5,1.9)             # base [S36]; low/high are ASSUMPTIONS
ELEC=(0.1330,0.1393,0.1407)      # [S27] Jul-2026 low, [S26] YTD base, [S27] Jul-2025 high ($/kWh)
DEMAND_ADDER=(0.0,0.0,0.10)      # ASSUMPTION, $/kWh; no sourced Indiana tariff
MAINT_D=0.18                     # $/mi ASSUMPTION [unverified]
MAINT_B=0.12                     # $/mi ASSUMPTION [unverified]
CHARGER=(80000,165000,250000)    # [S43] ends, midpoint computed; $ installed per 150 kW charger
UTILITY_UPGRADE_FLEET=0          # ASSUMPTION $0 base; sensitivity 500,000

def diesel(price=1, dp=None, p=None):
    p = P_DIESEL[1] if p is None else p; dp = DIESEL_PRICE[1] if dp is None else dp
    return p*(1+EXCISE) + MILES/MPG*dp + MAINT_D*MILES

def bev(ratio=1, price=None, kwh=None, el=None, dem=None, chg=None, upg=None, inc=None):
    price = P_BEV[1] if price is None else price
    kwh = KWH_MI[1] if kwh is None else kwh
    el = ELEC[1] if el is None else el
    dem = DEMAND_ADDER[1] if dem is None else dem
    chg = CHARGER[1] if chg is None else chg
    upg = UTILITY_UPGRADE_FLEET if upg is None else upg
    inc = INCENTIVE if inc is None else inc
    energy = MILES*kwh/CHG_EFF*(el+dem)
    infra = ((FLEET/ratio)*chg + upg)/FLEET
    return price*(1+EXCISE) - inc + energy + MAINT_B*MILES + infra

if __name__=='__main__':
    d=diesel(); print('diesel',round(d), round(d/MILES,4))
    for r in (1,2):
        b=bev(r); print('bev 1:%d'%r, round(b), round(b/MILES,4), 'diff', round(b-d))
    nonfuel=P_DIESEL[1]*(1+EXCISE)+MAINT_D*MILES
    for r in (1,2):
        print('breakeven diesel $/gal 1:%d'%r, round((bev(r)-nonfuel)/(MILES/MPG),3))
    # feasibility
    print('kWh/day grid', 250*KWH_MI[1]/CHG_EFF, 'battery', 250*KWH_MI[1])
    print('charge h @150kW', 250*KWH_MI[1]/CHG_EFF/150, 'fleet peak MW 1:1', FLEET*0.15, '1:2', FLEET/2*0.15)
