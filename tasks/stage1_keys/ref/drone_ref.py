"""Stage 1 reference for the drone tasks (frozen judge material, never shown to the team).

    python tasks/stage1_keys/ref/drone_ref.py make  <field.json> <out_dir>   # writes red.png and nir.png
    python tasks/stage1_keys/ref/drone_ref.py solve <field.json> <out_dir>   # prints the key numbers as JSON

field.json: {"cols", "rows", "zone_px", "seed", "zones": {"Z1": [red, nir], ...} (row-major), "threshold", "base": [x, y],
"battery_m"}. A pixel is 1 m; zone k's centre is ((c + 0.5) * zone_px, (r + 0.5) * zone_px). The drone starts and ends at
the base and visits the centre of every stressed zone (mean NDVI < threshold); the route is the shortest such tour
(every order tried)."""
import itertools, json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image


def make(f, out):
    rng = np.random.default_rng(f["seed"])
    z, R, C = f["zone_px"], f["rows"], f["cols"]
    red = np.zeros((R * z, C * z)); nir = np.zeros((R * z, C * z))
    for k, (zid, (r0, n0)) in enumerate(f["zones"].items()):
        r, c = divmod(k, C)
        red[r * z:(r + 1) * z, c * z:(c + 1) * z] = r0 + rng.integers(-6, 7, (z, z))
        nir[r * z:(r + 1) * z, c * z:(c + 1) * z] = n0 + rng.integers(-6, 7, (z, z))
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(red, 0, 255).astype(np.uint8)).save(out / "red.png")
    Image.fromarray(np.clip(nir, 0, 255).astype(np.uint8)).save(out / "nir.png")


def solve(f, out):
    red = np.asarray(Image.open(out / "red.png"), dtype=float)
    nir = np.asarray(Image.open(out / "nir.png"), dtype=float)
    ndvi = (nir - red) / np.where(nir + red == 0, 1, nir + red)
    z, C = f["zone_px"], f["cols"]
    means, centres = {}, {}
    for k, zid in enumerate(f["zones"]):
        r, c = divmod(k, C)
        means[zid] = round(float(ndvi[r * z:(r + 1) * z, c * z:(c + 1) * z].mean()), 4)
        centres[zid] = ((c + 0.5) * z, (r + 0.5) * z)
    stressed = [k for k, v in means.items() if v < f["threshold"]]
    base = tuple(f["base"])
    d = lambda a, b: math.dist(a, b)
    best = min(itertools.permutations(stressed),
               key=lambda p: sum(d(a, b) for a, b in zip((base,) + tuple(centres[s] for s in p),
                                                          tuple(centres[s] for s in p) + (base,))))
    pts = (base,) + tuple(centres[s] for s in best) + (base,)
    length = round(sum(d(a, b) for a, b in zip(pts, pts[1:])), 1)
    return {"field_mean_ndvi": round(float(ndvi.mean()), 4), "zone_mean_ndvi": means, "stressed": stressed,
            "route": list(best), "route_m": length, "battery_m": f["battery_m"],
            "within_battery": length <= f["battery_m"], "margin_m": round(f["battery_m"] - length, 1)}


if __name__ == "__main__":
    cmd, fj, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    f = json.loads(fj.read_text())
    if cmd == "make":
        make(f, out)
    else:
        print(json.dumps(solve(f, out), indent=1))
