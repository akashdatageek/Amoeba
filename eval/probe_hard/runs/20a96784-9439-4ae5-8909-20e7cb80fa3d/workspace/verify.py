loads = {
    "L1": (18000, 220),
    "L2": (12500, 340),
    "L3": (22000, 150),
    "L4": (9000, 410),
    "L5": (15500, 95),
    "L6": (7000, 280),
    "L7": (20500, 190),
    "L8": (11000, 365),
    "L9": (14000, 120),
    "L10": (8500, 255),
}

trucks = {
    "A": {"cap": 45000, "limit": 1100, "fixed": 350, "rate": 2.10},
    "B": {"cap": 45000, "limit": 1100, "fixed": 350, "rate": 2.10},
    "C": {"cap": 30000, "limit": 1100, "fixed": 500, "rate": 1.85},
    "D": {"cap": 26000, "limit": 900, "fixed": 275, "rate": 2.45},
}

assignment = {
    "A": ["L1", "L2", "L9"],
    "B": ["L5", "L7", "L10"],
    "C": ["L4", "L6", "L8"],
    "D": ["L3"],
}

total_cost = 0
all_assigned_loads = []

for truck_id, assigned_loads in assignment.items():
    t_data = trucks[truck_id]
    w_sum = sum(loads[l][0] for l in assigned_loads)
    m_sum = sum(loads[l][1] for l in assigned_loads)
    cost = t_data["fixed"] + (t_data["rate"] * m_sum)
    total_cost += cost
    all_assigned_loads.extend(assigned_loads)
    
    print(f"Truck {truck_id}:")
    print(f"  Loads: {assigned_loads}")
    print(f"  Weight: {w_sum} / {t_data['cap']} - {'OK' if w_sum <= t_data['cap'] else 'FAIL'}")
    print(f"  Miles: {m_sum} / {t_data['limit']} - {'OK' if m_sum <= t_data['limit'] else 'FAIL'}")
    print(f"  Cost: {cost:.2f}")

print(f"\nTotal Cost: {total_cost:.2f}")
print(f"All loads assigned: {sorted(all_assigned_loads) == sorted(list(loads.keys()))}")
print(f"Load count: {len(all_assigned_loads)}")
