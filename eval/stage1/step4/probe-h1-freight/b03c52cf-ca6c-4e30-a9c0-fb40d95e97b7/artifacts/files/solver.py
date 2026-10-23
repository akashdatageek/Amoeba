import itertools

def solve():
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

    # Precompute feasible subsets for each truck
    # A subset is represented as a bitmask
    feasible_subsets = {}
    for t_name, t_data in trucks.items():
        feasible = []
        for i in range(1 << 10):
            weight = 0
            miles = 0
            for j in range(10):
                if (i >> j) & 1:
                    weight += loads[j][0]
                    miles += loads[j][1]
            if weight <= t_data['cap'] and miles <= t_data['limit']:
                cost = 0
                if i > 0:
                    cost = t_data['fixed'] + t_data['rate'] * miles
                feasible.append((i, cost))
        feasible_subsets[t_name] = feasible

    # We need to partition the 10 loads (mask (1 << 10) - 1) among trucks A, B, C, D
    # Some trucks might be unused (mask 0)
    
    min_total_cost = float('inf')
    best_assignment = None

    # To avoid redundant calculations for A and B (they are identical), 
    # we can optimize, but with only 4 trucks, a simple search is fine.
    # However, the number of feasible subsets can be up to 1024 per truck.
    # 1024^4 is too large. We need a better search.
    
    # Recursive search with pruning
    memo = {}

    def find_min(truck_idx, remaining_mask):
        state = (truck_idx, remaining_mask)
        if state in memo:
            return memo[state]
        
        if truck_idx == 4:
            return (0, {}) if remaining_mask == 0 else (float('inf'), {})
        
        t_names = ['A', 'B', 'C', 'D']
        t_name = t_names[truck_idx]
        
        best_cost = float('inf')
        best_mapping = {}
        
        # Try all feasible subsets for this truck that are subsets of remaining_mask
        for mask, cost in feasible_subsets[t_name]:
            if (mask & remaining_mask) == mask:
                res_cost, res_mapping = find_min(truck_idx + 1, remaining_mask ^ mask)
                if cost + res_cost < best_cost:
                    best_cost = cost + res_cost
                    best_mapping = res_mapping.copy()
                    best_mapping[t_name] = mask
        
        memo[state] = (best_cost, best_mapping)
        return memo[state]

    total_cost, assignment_masks = find_min(0, (1 << 10) - 1)
    
    # Convert masks to load lists
    final_assignment = {}
    for t_name, mask in assignment_masks.items():
        loads_in_truck = []
        for j in range(10):
            if (mask >> j) & 1:
                loads_in_truck.append(f"L{j+1}")
        final_assignment[t_name] = loads_in_truck

    return total_cost, final_assignment

cost, assignment = solve()
print(f"Min Cost: {cost}")
print(f"Assignment: {assignment}")
