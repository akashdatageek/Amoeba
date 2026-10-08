import openpyxl

# Data from Task
loads = {
    'L1': (18000, 220), 'L2': (12500, 340), 'L3': (22000, 150),
    'L4': (9000, 410), 'L5': (15500, 95), 'L6': (7000, 280),
    'L7': (20500, 190), 'L8': (11000, 365), 'L9': (14000, 120),
    'L10': (8500, 255)
}
trucks = {
    'A': {'cap': 45000, 'limit': 1100, 'fixed': 350, 'rate': 2.10},
    'B': {'cap': 45000, 'limit': 1100, 'fixed': 350, 'rate': 2.10},
    'C': {'cap': 30000, 'limit': 1100, 'fixed': 500, 'rate': 1.85},
    'D': {'cap': 26000, 'limit': 900, 'fixed': 275, 'rate': 2.45},
}

# Assignment from Step 1/2
assignment = {
    'A': ['L1', 'L2', 'L9'],
    'B': ['L5', 'L7', 'L10'],
    'C': ['L4', 'L6', 'L8'],
    'D': ['L3'],
}

results = {}
total_cost = 0

for t_id, l_ids in assignment.items():
    w_sum = sum(loads[l][0] for l in l_ids)
    m_sum = sum(loads[l][1] for l in l_ids)
    t_data = trucks[t_id]
    
    cost = t_data['fixed'] + (m_sum * t_data['rate'])
    total_cost += cost
    
    results[t_id] = {
        'weight': w_sum,
        'weight_ok': w_sum <= t_data['cap'],
        'miles': m_sum,
        'miles_ok': m_sum <= t_data['limit'],
        'cost': cost
    }

print(f"Total Cost: {total_cost:.2f}")
for t_id, res in results.items():
    print(f"Truck {t_id}: Weight={res['weight']} (OK={res['weight_ok']}), Miles={res['miles']} (OK={res['miles_ok']}), Cost={res['cost']:.2f}")

# Check if file exists and read basic info
try:
    wb = openpyxl.load_workbook('cost_plan_xlsx.xlsx', data_only=True)
    ws = wb.active
    print("File cost_plan_xlsx.xlsx exists and is readable.")
    # Check a few cells to ensure it's not empty (e.g., Total Cost cell)
    # Based on Step 2, Total Cost is in O6 or similar (SUM(O2:O5))
    # Let's just check if the sheet has data
    if ws['A1'].value is not None:
        print("File contains data.")
except Exception as e:
    print(f"File error: {e}")

