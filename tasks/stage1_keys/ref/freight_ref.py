"""Reference brute force for a truck-assignment task: every assignment of loads to trucks (unused trucks cost 0)."""
import itertools, json, sys

def solve(loads, trucks):
    names = list(trucks); best = None
    W = [w for w, m in loads.values()]; M = [m for w, m in loads.values()]; L = list(loads)
    for assign in itertools.product(range(len(names)), repeat=len(L)):
        w = [0] * len(names); mi = [0] * len(names)
        for i, t in enumerate(assign):
            w[t] += W[i]; mi[t] += M[i]
        ok = True; cost = 0.0
        for t, n in enumerate(names):
            cap, lim, fixed, rate = trucks[n]
            if w[t] > cap or mi[t] > lim: ok = False; break
            if mi[t] or w[t]: cost += fixed + rate * mi[t]
        if ok and (best is None or cost < best[0] - 1e-9):
            best = (cost, assign, list(w), list(mi))
    cost, assign, w, mi = best
    plan = {n: {"loads": [L[i] for i, t in enumerate(assign) if t == k], "weight": w[k], "miles": mi[k]}
            for k, n in enumerate(names)}
    return round(cost, 2), plan

if __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))
    print(json.dumps(solve({k: tuple(v) for k, v in spec["loads"].items()},
                           {k: tuple(v) for k, v in spec["trucks"].items()}), indent=1))
