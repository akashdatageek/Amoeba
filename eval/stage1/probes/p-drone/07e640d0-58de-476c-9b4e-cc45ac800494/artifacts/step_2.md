I read "ndvi.png" as A colour-mapped or contrast-stretched visualisation of NDVI over the range -1 to 1.; if you meant A grayscale 8-bit image with NDVI linearly rescaled to 0-255., the answer below may not apply.

# Memo: ndvi.png (step 2)

## Confirmation
- ndvi.png was written to the workspace. I reopened it with PIL: format PNG, size 900 x 825 pixels, mode RGBA [S7]. The file is 50356 bytes [S7].
- The figure was saved at dpi=150, as set in render.py. This meets the dpi >= 100 requirement. The figure size in inches follows from the pixel size: 900 px / 150 dpi = 6 in wide, and 825 px / 150 dpi = 5.5 in tall.
- Colormap and range, read back from the image object after rendering: clim = (-1.0, 1.0), cmap = RdYlGn [S7]. The call was plt.imshow(ndvi, cmap='RdYlGn', vmin=-1, vmax=1, origin='upper'). The range is fixed, not autoscaled.
- Other elements of the figure, as set in render.py:
  - a colorbar labelled "NDVI"
  - the title "NDVI map, 40x40 field (vmin=-1, vmax=1)"
  - a black dashed vertical line at x=19.5 with the label "West | East" above it
  - x axis labelled "Column (west → east)" and y axis labelled "Row (north → south)"

## Data used
- The map is drawn from ndvi_values.csv, loaded as shape (40, 40) with minimum 0.1 and maximum 0.6 [S7]. This matches step 1: west 0.6, east 0.1.
- The data run from 0.1 to 0.6 on a -1 to 1 scale, so the colours cover only part of the colour range. That is expected with the fixed range.

## Problem and fix
- The first render failed. np.loadtxt could not parse the CSV without a delimiter (ValueError at row 0, column 1) [S7].
- I reran it with delimiter=',' and it worked [S7].
- Anyone reading ndvi_values.csv must pass delimiter=','. The CSV also keeps its leading "# col0,..." comment line from step 1.

## Files
- ndvi.png: new in this step.
- render.py: the script that makes it.
- ndvi_values.csv: unchanged.
- inputs/ was not modified.
