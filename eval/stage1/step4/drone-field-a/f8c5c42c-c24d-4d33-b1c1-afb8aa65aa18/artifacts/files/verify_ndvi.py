from PIL import Image

def get_pixels(path):
    img = Image.open(path).convert('L')
    return list(img.getdata())

red_pixels = get_pixels('inputs/red.png')
nir_pixels = get_pixels('inputs/nir.png')

width = 90
height = 60

ndvi = []
zero_den = 0
for r, n in zip(red_pixels, nir_pixels):
    den = n + r
    if den == 0:
        ndvi.append(float('nan'))
        zero_den += 1
    else:
        ndvi.append((n - r) / den)

# Reshape to 2D (y, x)
ndvi_2d = [ndvi[i * width : (i + 1) * width] for i in range(height)]

zones = {
    "Z1": (0, 30, 0, 30), # y_start, y_end, x_start, x_end
    "Z2": (0, 30, 30, 60),
    "Z3": (0, 30, 60, 90),
    "Z4": (30, 60, 0, 30),
    "Z5": (30, 60, 30, 60),
    "Z6": (30, 60, 60, 90),
}

zone_means = {}
for z, (ys, ye, xs, xe) in zones.items():
    vals = []
    for y in range(ys, ye):
        for x in range(xs, xe):
            v = ndvi_2d[y][x]
            if not (v != v): # not nan
                vals.append(v)
    zone_means[z] = sum(vals) / len(vals) if vals else float('nan')

field_mean = sum(ndvi) / len(ndvi) if not zero_den else sum([v for v in ndvi if not (v != v)]) / (len(ndvi) - zero_den)

print(f"Zero denominators: {zero_den}")
print(f"Field mean: {field_mean:.6f}")
for z in sorted(zone_means.keys()):
    print(f"{z}: {zone_means[z]:.6f}")
