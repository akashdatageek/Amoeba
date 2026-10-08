import itertools

# Data
loads = [
    ('L1', 18000, 220),
    ('L2', 12500, 340),
    ('L3', 22000, 150),
    ('L4', 9000, 410),
    ('L5', 15500, 95),
    ('L6', 7000, 280),
    ('L7', 20500, 190),
    ('L8', 11000, 365),
    ('L9', 14000, 120),
    ('L10', 8500, 255),
]

trucks = {
    'A': {'cap': 45000, 'limit': 1100, 'fixed': 350, 'rate': 2.10},
    'B': {'cap': 45000, 'limit': 1100, 'fixed': 350, 'rate': 2.10},
    'C': {'cap': 30000, 'limit': 1100, 'fixed': 500, 'rate': 1.85},
    'D': {'cap': 26000, 'limit': 900, 'fixed': 275, 'rate': 2.45},
}

truck_names = list(trucks.keys())
num_loads = len(loads)
best_cost = float('inf')
best_assignment = None

# Pre-calculate load miles * rate for each truck to speed up
load_costs = {}
for l_idx in range(num_loads):
    l_name, l_weight, l_miles = loads[l_idx]
    for t_name in truck_names:
        load_costs[(l_idx, t_name)] = l_miles * trucks[t_name]['rate']

def solve(load_idx, truck_weights, truck_miles, truck_used, current_cost, assignment):
    global best_cost, best_assignment

    # Pruning: if current cost already exceeds best, stop
    if current_cost >= best_cost:
        return

    # Base case: all loads assigned
    if load_idx == num_loads:
        best_cost = current_cost
        best_assignment = assignment[:]
        return

    l_name, l_weight, l_miles = loads[load_idx]

    for t_name in truck_names:
        t_data = trucks[t_name]
        
        # Constraint check: Weight
        if truck_weights[t_name] + l_weight > t_data['cap']:
            continue
        
        # Constraint check: Miles
        if truck_miles[t_name] + l_miles > t_data['limit']:
            continue
        
        # Calculate cost increment
        added_cost = load_costs[(load_idx, t_name)]
        new_truck_used = truck_used[t_name]
        if not new_truck_used:
            added_cost += t_data['fixed']
            new_truck_used = True
        
        # Recurse
        truck_weights[t_name] += l_weight
        truck_miles[t_name] += l_miles
        old_used = truck_used[t_name]
        truck_used[t_name] = new_truck_used
        assignment.append(t_name)
        
        solve(load_idx + 1, truck_weights, truck_miles, truck_used, current_cost + added_cost, assignment)
        
        # Backtrack
        assignment.pop()
        truck_used[t_name] = old_used
        truck_miles[t_name] -= l_miles
        truck_weights[t_name] -= l_weight

# Initial state
initial_weights = {t: 0 for t in truck_names}
initial_miles = {t: 0 for t in truck_names}
initial_used = {t: False for t in truck_names}

solve(0, initial_weights, initial_miles, initial_used, 0, [])

print(f"Total Cost: {best_cost}")
if best_assignment:
    for t_name in truck_names:
        assigned_loads = [loads[i][0] for i, t in enumerate(best_assignment) if t == t_name]
        if assigned_loads:
            w = sum(loads[i][1] for i, t in enumerate(best_assignment) if t == t_name)
            m = sum(loads[i][2] for i, t in enumerate(best_assignment) if t == t_name)
            print(f"Truck {t_name}: Loads={assigned_loads}, Weight={w}, Miles={m}")
        else:
            print(f"Truck {t_name}: Unused")
