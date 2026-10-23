
import numpy as np
from PIL import Image
import itertools
import math

def solve():
    # Load images
    red_im = Image.open('inputs/red.png').convert('L')
    nir_im = Image.open('inputs/nir.png').convert('L')
    
    red = np.array(red_im, dtype=np.float64)
    nir = np.array(nir_im, dtype=np.float64)
    
    # Compute NDVI
    # NDVI = (NIR - Red) / (NIR + Red)
    denom = nir + red
    # Handle division by zero if any
    ndvi = np.divide((nir - red), denom, out=np.full_like(nir, np.nan), where=denom != 0)
    
    field_mean = np.nanmean(ndvi)
    
    # Zones: 3x2 grid, 30x30 each
    # Z1: (0:30, 0:30), Z2: (0:30, 30:60), Z3: (0:30, 60:90)
    # Z4: (30:60, 0:30), Z5: (30:60, 30:60), Z6: (30:60, 60:90)
    zones_coords = [
        (0, 30, 0, 30), # Z1
        (0, 30, 30, 60), # Z2
        (0, 30, 60, 90), # Z3
        (30, 60, 0, 30), # Z4
        (30, 60, 30, 60), # Z5
        (30, 60, 60, 90), # Z6
    ]
    
    zone_means = []
    stressed = []
    for r1, r2, c1, c2 in zones_coords:
        z_mean = np.nanmean(ndvi[r1:r2, c1:c2])
        zone_means.append(z_mean)
        stressed.append(z_mean < 0.35)
        
    # Route
    # Centres: Z1(15,15), Z2(45,15), Z3(75,15), Z4(15,45), Z5(45,45), Z6(75,45)
    centres = {
        'Z1': (15, 15), 'Z2': (45, 15), 'Z3': (75, 15),
        'Z4': (15, 45), 'Z5': (45, 45), 'Z6': (75, 45)
    }
    
    stressed_zones = [f'Z{i+1}' for i, s in enumerate(stressed) if s]
    stressed_pts = [centres[z] for z in stressed_zones]
    
    start_node = (0, 0)
    
    def dist(p1, p2):
        return math.hypot(p1[0]-p2[0], p1[1]-p2[1])
    
    min_len = float('inf')
    best_route = None
    
    for perm in itertools.permutations(stressed_pts):
        current_len = 0
        prev = start_node
        for p in perm:
            current_len += dist(prev, p)
            prev = p
        current_len += dist(prev, start_node)
        
        if current_len < min_len:
            min_len = current_len
            best_route = perm
            
    # Output results
    print(f"Field Mean: {field_mean:.6f}")
    for i, m in enumerate(zone_means):
        print(f"Z{i+1}: {m:.6f}, Stressed: {stressed[i]}")
    
    print(f"Stressed Zones: {stressed_zones}")
    print(f"Shortest Route Length: {min_len:.6f}")
    
    # To identify the order, map points back to zone names
    pt_to_zone = {v: k for k, v in centres.items()}
    route_order = [pt_to_zone[p] for p in best_route]
    print(f"Route Order: {route_order}")

solve()
