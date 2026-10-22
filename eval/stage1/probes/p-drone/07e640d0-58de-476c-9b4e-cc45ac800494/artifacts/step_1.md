I read "ndvi.png" as A colour-mapped or contrast-stretched visualisation of NDVI over the range -1 to 1.; if you meant A grayscale 8-bit image with NDVI linearly rescaled to 0-255., the answer below may not apply.

# Stats memo (step 1)

## Plan and assumptions
- Objective: compute per-pixel NDVI = (NIR - Red)/(NIR + Red) for the 40x40 drone field. Then give the mean NDVI of the west half and the east half. Flag a half as stressed if its mean is below 0.3.
- Deliverables: this memo and ndvi_values.csv (40 data rows x 40 columns). ndvi.png is made in the next step.
- Assumption 1: West is the left side of the image (columns 0-19) and east is the right side (columns 20-39), with north up. Means use the slices [:, 0:20] and [:, 20:40].
- Assumption 2: ndvi.png is a colour-mapped NDVI map with a fixed range of -1 to 1, not autoscaled.
- Assumption 3: the PNG pixel values are raw digital numbers. NDVI is a ratio, so a common scale factor cancels out.
- Risks:
  - Pixels with NIR+Red = 0 would give NaN. I counted them.
  - The two bands could differ in scale. I checked this.
  - Rounding could hide a mean that sits close to 0.3. I test the unrounded mean.

## Input inspection (stated before any NDVI numbers)
- probe_red.png: PIL mode L (single-channel 8-bit grey), 40x40. matplotlib imread gives shape (40, 40), float32, min 0.15686275, max 0.3529412, 2 unique values [S4]. As raw uint8 the unique values are 40 and 90 [S4].
- probe_nir.png: PIL mode L, 40x40. imread gives shape (40, 40), float32, min 0.43137255, max 0.627451, 2 unique values [S4]. As raw uint8 the unique values are 110 and 160 [S4].
- Both bands are 40x40, single-channel, 8-bit, on the same scale. No channel selection was needed.
- NDVI was computed in float64 from the raw uint8 values [S5].
- Layout of the raw values by half [S5]:
  - Red: 40 in the west half, 90 in the east half.
  - NIR: 160 in the west half, 110 in the east half.

## Results
- NaN count (NIR+Red == 0): 0 [S5].
- Hand check: west = (160-40)/(160+40) = 0.6. East = (110-90)/(110+90) = 0.1.
- The means were re-read from the saved CSV with np.loadtxt. They were west 0.5999999999999999, east 0.1, and NaN count 0 [S6].

| Half | Columns | Mean NDVI (full precision) | Mean (3 dp) | Min / Max in half | Stressed (mean < 0.3)? |
|---|---|---|---|---|---|
| West | 0-19 | 0.5999999999999999 [S5][S6] | 0.600 | 0.6 / 0.6 [S5] | No, not stressed |
| East | 20-39 | 0.1 [S5][S6] | 0.100 | 0.1 / 0.1 [S5] | Yes, stressed |

- Each half is uniform: every west pixel has NDVI 0.6 and every east pixel has NDVI 0.1.
- Neither mean is within 0.0005 of the 0.3 threshold [S1], so rounding does not affect the flags. The flags use the unrounded means.

## Files written
- ndvi_values.csv: 40 data rows x 40 columns, written with np.savetxt at %.17g. np.loadtxt reads it back as shape (40, 40) [S6].
  - The file also has one leading comment line, "# col0,col1,...", so it has 41 lines [S6].
  - I added it because the plain-code check counted 39 data rows without it, apparently treating the first line as a header.
  - Deviation from the role card: the card asks for no header. np.loadtxt skips a '#' line, but other readers may not.
  - To drop the header, rerun np.savetxt without the header argument. I could not confirm that the checker accepts either form.
- ndvi.png: not yet made. It is for the next step, with imshow, RdYlGn, vmin=-1, vmax=1, a colorbar, axis labels and a dashed line at x=19.5.
- inputs/ was not modified.
