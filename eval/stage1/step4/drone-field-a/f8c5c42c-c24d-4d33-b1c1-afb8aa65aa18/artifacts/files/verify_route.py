import math
from itertools import permutations

def dist(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

depot = (0, 0)
stressed_zones = {
    'Z2': (45, 15),
    'Z4': (15, 45),
    'Z6': (75, 45),
}

zones = list(stressed_zones.keys())
coords = {z: stressed_zones[z] for z in zones}

min_len = float('inf')
best_route = None

for p in permutations(zones):
    current_len = 0
    prev = depot
    for z in p:
        current_len += dist(prev, coords[z])
        prev = coords[z]
    current_len += dist(prev, depot)
    
    if current_len < min_len:
        min_len = current_len
        best_route = p

print(f"Best Route: {best_route}")
print(f"Min Length: {min_len}")
print(f"Margin: {260 - min_len}")
