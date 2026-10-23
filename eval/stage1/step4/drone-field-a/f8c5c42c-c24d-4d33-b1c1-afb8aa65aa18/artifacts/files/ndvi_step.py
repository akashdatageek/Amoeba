import json
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def load(n):
    im = Image.open("inputs/%s.png" % n)
    a = np.array(im)
    print(n, "mode", im.mode, "shape", a.shape, "dtype", a.dtype, "min", a.min(), "max", a.max())
    if a.ndim == 3:
        ch = [np.array_equal(a[..., 0], a[..., i]) for i in range(1, a.shape[2])]
        print(n, "channels identical to ch0:", ch)
        a = a[..., 0]
    return a

r8 = load("red"); n8 = load("nir")
assert r8.shape == (60, 90) and n8.shape == (60, 90), (r8.shape, n8.shape)
red = r8.astype(np.float64); nir = n8.astype(np.float64)
if red.max() <= 1.0 and nir.max() <= 1.0 and r8.dtype.kind == "f":
    print("float 0-1 data")
den = nir + red
zero = den == 0
nz = int(zero.sum())
ndvi = np.full(red.shape, np.nan)
np.divide(nir - red, den, out=ndvi, where=~zero)
print("zero-denominator count", nz, "ndvi min/max", np.nanmin(ndvi), np.nanmax(ndvi))

sl = {"Z1": (slice(0,30), slice(0,30)), "Z2": (slice(0,30), slice(30,60)), "Z3": (slice(0,30), slice(60,90)),
      "Z4": (slice(30,60), slice(0,30)), "Z5": (slice(30,60), slice(30,60)), "Z6": (slice(30,60), slice(60,90))}
means = {z: float(np.nanmean(ndvi[s])) for z, s in sl.items()}
field = float(np.nanmean(ndvi))
stressed = {z: bool(m < 0.35) for z, m in means.items()}
near = {z: bool(abs(m - 0.35) <= 0.0005) for z, m in means.items()}
print("mean of zone means", np.mean(list(means.values())), "field", field)

with open("zones.csv", "w") as f:
    f.write("zone,mean_ndvi,stressed\n")
    for z in sl:
        f.write("%s,%.4f,%s\n" % (z, means[z], "true" if stressed[z] else "false"))

fig, ax = plt.subplots(figsize=(9, 6.5), dpi=120)
im = ax.imshow(ndvi, origin="upper", extent=(0, 90, 60, 0), cmap="RdYlGn", interpolation="nearest")
cb = fig.colorbar(im, ax=ax); cb.set_label("NDVI")
for x in (30, 60): ax.axvline(x, color="k", lw=1.5)
ax.axhline(30, color="k", lw=1.5)
for i, z in enumerate(sl):
    cx = 15 + 30 * (i % 3); cy = 15 + 30 * (i // 3)
    ax.text(cx, cy, "%s\n%.4f" % (z, means[z]), ha="center", va="center", fontsize=10,
            bbox=dict(fc="white", alpha=0.7, ec="none"))
ax.set_xlabel("x (m, east)"); ax.set_ylabel("y (m, south)")
ax.set_title("NDVI map (north at top)")
fig.tight_layout(); fig.savefig("ndvi_map.png", dpi=120); plt.close(fig)

res = {"zone_means_full": means, "zone_means_4dp": {z: round(m, 4) for z, m in means.items()},
       "field_mean_full": field, "field_mean_4dp": round(field, 4),
       "stressed": [z for z in sl if stressed[z]], "image_shape": list(ndvi.shape),
       "zero_denominator_count": nz, "near_threshold_flags": near,
       "orientation": "x east along columns, y south along rows; row 0 = north"}
json.dump(res, open("results.json", "w"), indent=2)

# verify
print(open("zones.csv").read())
im2 = Image.open("ndvi_map.png"); print("png", im2.size)
print("| Zone | Mean NDVI | Stressed |\n|---|---|---|")
for z in sl: print("| %s | %.4f | %s |" % (z, means[z], stressed[z]))
print("| Field | %.4f | |" % field)
print("full:", means, "stressed:", res["stressed"], "near:", [z for z in near if near[z]])
