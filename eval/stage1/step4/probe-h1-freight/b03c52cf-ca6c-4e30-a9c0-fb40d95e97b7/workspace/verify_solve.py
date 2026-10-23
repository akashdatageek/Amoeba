import itertools

def solve():
    loads = {
        'L1': (18000, 220), 'L2': (12500, 340), 'L3': (22000, 150),
        'L4': (9000, 410), 'L5': (15500, 95), 'L6': (7000, 280),
        'L7': (20500, 190), 'L8': (11000, 365), 'L9': (14000, 120),
        'L10': (8500, 255)
    }
    trucks = {
        'A': (45000, 1100, 350, 2.10),
        'B': (45000, 1100, 350, 2.10),
        'C': (30000, 1100, 500, 1.85),
        'D': (26000, 900, 275, 2.45)
    }

    load_ids = list(loads.keys())
    num_loads = len(load_ids)
    truck_names = list(trucks.keys())

    # Precompute feasible subsets for each truck
    feasible_subsets = {}
    for t_name in truck_names:
        cap, limit, fixed, rate = trucks[t_name]
        feasible = []
        # 2^10 subsets
        for i in range(1 << num_loads):
            subset = []
            total_w = 0
            total_m = 0
            for j in range(num_loads):
                if (i >> j) & 1:
                    subset.append(load_ids[j])
                    w, m = loads[load_ids[j]]
                    total_w += w
                    total_m += m
            
            if total_w <= cap and total_m <= limit:
                cost = fixed + rate * total_m if subset else 0
                feasible.append((i, cost, total_w, total_m, subset))
        feasible_subsets[t_name] = feasible

    memo = {}

    def find_min(t_idx, mask):
        state = (t_idx, mask)
        if state in memo:
            return memo[state]
        
        if t_idx == len(truck_names):
            return (0 if mask == 0 else float('inf'), [])

        t_name = truck_names[t_idx]
        best_cost = float('inf')
        best_assignment = []

        # Try all feasible subsets for this truck that are subsets of the remaining mask
        for sub_mask, cost, w, m, subset in feasible_subsets[t_name]:
            if (sub_mask & mask) == sub_mask:
                res_cost, res_assign = find_min(t_idx + 1, mask ^ sub_mask)
                if res_cost != float('inf'):
                    total = cost + res_cost
                    if total < best_cost:
                        best_cost = total
                        best_assignment = [(t_name, subset, w, m, cost)] + res_assign
        
        memo[state] = (best_cost, best_assignment)
        return memo[state]

    min_cost, assignment = find_min(0, (1 << num_loads) - 1)
    return min_cost, assignment

cost, assign = solve()
print(f"Min Cost: {cost}")
for entry in assign:
    print(f"Truck {entry[0]}: Loads={entry[1]}, Weight={entry[2]}, Miles={entry[3]}, Cost={entry[4]}")
