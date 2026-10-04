import itertools

loads = [
    (18000, 220), # L1
    (12500, 340), # L2
    (22000, 150), # L3
    (9000, 410),  # L4
    (15500, 95),  # L5
    (7000, 280),  # L6
    (20500, 190), # L7
    (11000, 365), # L8
    (14000, 120), # L9
    (8500, 255),  # L10
]

trucks = {
    'A': {'cap': 45000, 'limit': 1100, 'fixed': 350, 'rate': 2.10},
    'B': {'cap': 45000, 'limit': 1100, 'fixed': 350, 'rate': 2.10},
    'C': {'cap': 30000, 'limit': 1100, 'fixed': 500, 'rate': 1.85},
    'D': {'cap': 26000, 'limit': 900, 'fixed': 275, 'rate': 2.45},
}

truck_names = list(trucks.keys())
num_loads = len(loads)
num_trucks = len(truck_names)

min_cost = float('inf')
best_assignment = None

def solve(load_idx, current_assignment, truck_stats):
    global min_cost, best_assignment
    
    if load_idx == num_loads:
        total_cost = 0
        for t_name, stats in truck_stats.items():
            if stats['miles'] > 0:
                total_cost += trucks[t_name]['fixed'] + (trucks[t_name]['rate'] * stats['miles'])
        
        if total_cost < min_cost:
            min_cost = total_cost
            best_assignment = current_assignment[:]
        return

    load_w, load_m = loads[load_idx]
    
    for t_idx in range(num_trucks):
        t_name = truck_names[t_idx]
        if (truck_stats[t_name]['weight'] + load_w <= trucks[t_name]['cap'] and 
            truck_stats[t_name]['miles'] + load_m <= trucks[t_name]['limit']):
            
            truck_stats[t_name]['weight'] += load_w
            truck_stats[t_name]['miles'] += load_m
            current_assignment.append(t_name)
            
            solve(load_idx + 1, current_assignment, truck_stats)
            
            current_assignment.pop()
            truck_stats[t_name]['weight'] -= load_w
            truck_stats[t_name]['miles'] -= load_m

initial_stats = {t: {'weight': 0, 'miles': 0} for t in truck_names}
solve(0, [], initial_stats)

print(f"Min Cost: {min_cost}")
print(f"Assignment: {best_assignment}")

final_stats = {t: {'weight': 0, 'miles': 0, 'loads': []} for t in truck_names}
for i, t_name in enumerate(best_assignment):
    final_stats[t_name]['weight'] += loads[i][0]
    final_stats[t_name]['miles'] += loads[i][1]
    final_stats[t_name]['loads'].append(f"L{i+1}")

for t_name, stats in final_stats.items():
    cost = 0
    if stats['miles'] > 0:
        cost = trucks[t_name]['fixed'] + (trucks[t_name]['rate'] * stats['miles'])
    print(f"Truck {t_name}: Loads={stats['loads']}, Weight={stats['weight']}, Miles={stats['miles']}, Cost={cost}")
