import itertools
import math

def dist(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def solve():
    start = (0, 0)
    # Stressed zones from previous step: Z2, Z4, Z6
    # Centers: Z1(15,15), Z2(45,15), Z3(75,15), Z4(15,45), Z5(45,45), Z6(75,45)
    centers = {
        'Z2': (45, 15),
        'Z4': (15, 45),
        'Z6': (75, 45)
    }
    
    zones = list(centers.keys())
    min_len = float('inf')
    best_route = None
    
    for p in itertools.permutations(zones):
        # Route: start -> p[0] -> p[1] -> p[2] -> start
        d = dist(start, centers[p[0]])
        d += dist(centers[p[0]], centers[p[1]])
        d += dist(centers[p[1]], centers[p[2]])
        d += dist(centers[p[2]], start)
        
        if d < min_len:
            min_len = d
            best_route = p
            
    return best_route, min_len

if __name__ == "__main__":
    route, length = solve()
    print(f"Best Route: {' -> '.join(route)}")
    print(f"Length: {length:.4f}")
