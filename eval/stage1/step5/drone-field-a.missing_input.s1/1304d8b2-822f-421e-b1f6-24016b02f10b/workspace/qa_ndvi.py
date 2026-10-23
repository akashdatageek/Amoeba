import matplotlib.image as mpimg
import numpy as np

def compute_ndvi():
    red = mpimg.imread('inputs/red.png')
    nir = mpimg.imread('inputs/nir.png')
    
    # Ensure 8-bit (0-255)
    red = (red * 255).astype(np.float64) if red.max() <= 1.0 else red.astype(np.float64)
    nir = (nir * 255).astype(np.float64) if nir.max() <= 1.0 else nir.astype(np.float64)
    
    # Handle potential alpha channel or RGB
    if len(red.shape) == 3:
        red = red[:, :, 0]
    if len(nir.shape) == 3:
        nir = nir[:, :, 0]

    # NDVI = (NIR - Red) / (NIR + Red)
    denom = nir + red
    # Count where red + nir == 0
    zero_denom_count = np.sum(denom == 0)
    
    with np.errstate(divide='ignore', invalid='ignore'):
        ndvi = (nir - red) / denom
        ndvi[denom == 0] = np.nan

    # Zones: 3x2 grid, 30x30 each.
    # Z1: y 0-29, x 0-29
    # Z2: y 0-29, x 30-59
    # Z3: y 0-29, x 60-89
    # Z4: y 30-59, x 0-29
    # Z5: y 30-59, x 30-59
    # Z6: y 30-59, x 60-89
    
    zone_means = []
    for row_block in range(2):
        for col_block in range(3):
            y_start, y_end = row_block * 30, (row_block + 1) * 30
            x_start, x_end = col_block * 30, (col_block + 1) * 30
            zone_data = ndvi[y_start:y_end, x_start:x_end]
            zone_means.append(np.nanmean(zone_data))
            
    field_mean = np.nanmean(ndvi)
    
    return zone_means, field_mean, zero_denom_count

if __name__ == "__main__":
    zm, fm, zd = compute_ndvi()
    print(f"Zone Means: {[f'{m:.4f}' for m in zm]}")
    print(f"Field Mean: {fm:.4f}")
    print(f"Zero Denom Count: {zd}")
