import numpy as np
from PIL import Image
import itertools

def load_and_scale(path):
    img = Image.open(path).convert('L')
    return np.array(img, dtype=np.float64)

red = load_and_scale('inputs/red.png')
nir = load_and_scale('inputs/nir.png')

print(f"Red shape: {red.shape}, NIR shape: {nir.shape}")

# NDVI = (NIR - Red) / (NIR + Red)
# Handle division by zero
denom = nir + red
ndvi = np.divide((nir - red), denom, out=np.full_like(denom, np.nan), where=denom != 0)

nan_count = np.isnan(ndvi).sum()
print(f"NaN count: {nan_count}")

# Zones
# Z1: rows 0-29, cols 0-29
# Z2: rows 0-29, cols 30-59
# Z3: rows 0-29, cols 60-89
# Z4: rows 30-59, cols 0-29
# Z5: rows 30-59, cols 30-59
# Z6: rows 30-59, cols 60-89

zones_coords = {
    'Z1': (0, 30, 0, 30),
    'Z2': (0, 30, 30, 60),
    'Z3': (0, 30, 60, 90),
    'Z4': (30, 60, 0, 30),
    'Z5': (30, 60, 30, 60),
    'Z6': (30, 60, 60, 90),
}

zone_means = {}
for zone, (r1, r2, c1, c2) in zones_coords.items():
    zone_data = ndvi[r1:r2, c1:c2]
    zone_means[zone] = np.nanmean(zone_data)

field_mean = np.nanmean(ndvi)

print("\nZone Means:")
for zone in sorted(zone_means.keys()):
    print(f"{zone}: {zone_means[zone]:.6f}")
print(f"Field Mean: {field_mean:.6f}")

stressed_zones = [zone for zone, mean in zone_means.items() if mean < 0.35]
print(f"\nStressed Zones: {stressed_zones}")

# Route
centers = {
    'Z1': (15, 15),
    'Z2': (45, 15),
    'Z3': (75, 15),
    'Z4': (15, 45),
    'Z5': (45, 45),
    'Z6': (75, 45),
}

stressed_centers = [centers[z] for z in stressed_zones]
start_node = (0, 0)

def dist(p1, p2):
    return np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

min_dist = float('inf')
best_route = None

for perm in itertools.permutations(stressed_centers):
    d = 0
    curr = start_node
    for p in perm:
        d += dist(curr, p)
        curr = p
    d += dist(curr, start_node)
    if d < min_dist:
        min_dist = d
        best_route = perm

print(f"\nShortest Route Distance: {min_dist:.4f}")
print(f"Best Route Order: {best_route}")
