Inputs: red.png and nir.png are both mode L (1 channel), uint8, shape (60, 90) = 60 rows x 90 columns; red DN range 36–107, NIR DN range 106–174 [S1]. NDVI was computed in float64 as (NIR−Red)/(NIR+Red); range 0.06 to 0.657143 [S2].

| zone | mean NDVI (4 dp) | unrounded (6 dp) | stressed |
|---|---|---|---|
| Z1 | 0.6004 | 0.600370 | false |
| Z2 | 0.1472 | 0.147249 | true |
| Z3 | 0.5003 | 0.500338 | false |
| Z4 | 0.1190 | 0.119036 | true |
| Z5 | 0.5543 | 0.554280 | false |
| Z6 | 0.1612 | 0.161203 | true |

(Values from [S2]; each zone mean is the mean of per-pixel NDVI over its 30 x 30 slice, 30 x 30 = 900 pixels.)

Field mean: 0.3471 (0.347079) [S2]
NaN pixels: 0 [S2]
Orientation: columns = x (east from west edge), rows = y (south from north edge). Z1–Z3 are the north row (west to east), Z4–Z6 the south row; zone k uses rows 30*r to 30*r+29 (r = 0 north, 1 south) and columns 30*c to 30*c+29 (c = 0, 1, 2 from west).
Stressed zones (unrounded mean < 0.35): Z2, Z4, Z6 [S2]
Near-threshold cases: none; no zone mean is within 0.0005 of 0.35 (nearest is Z6 at 0.161203, distance 0.35 − 0.161203 = 0.188797) [S2]. The field mean (0.3471) is below 0.35, but the test applies per zone.

Files (re-read and confirmed [S3]):
- zones.csv: header zone,mean_ndvi,stressed; 6 data rows Z1..Z6 with means to 4 dp and true/false, matching the table [S3].
- ndvi_map.png: valid PNG, 1350 x 975 px [S3] (saved at 150 dpi, as set in the script). It is an RdYlGn heatmap with a colorbar labelled NDVI, white zone grid lines at x = 30, 60 and y = 30 (task's zone grid), Z1–Z6 labels at the zone centres, and axes 'x east (m)' and 'y south (m)' with y increasing downward.

Hand-off for route step: stressed-zone centres, each the zone's 30 m block centre (corner offset + 15 m): Z2 (x = 30 + 15 = 45, y = 0 + 15 = 15), Z4 (x = 0 + 15 = 15, y = 30 + 15 = 45), Z6 (x = 60 + 15 = 75, y = 30 + 15 = 45).
