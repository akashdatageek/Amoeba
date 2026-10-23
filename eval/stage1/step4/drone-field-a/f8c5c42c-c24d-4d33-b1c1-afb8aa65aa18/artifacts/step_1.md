NDVI step complete. Inputs: red.png and nir.png are both mode L, shape (60, 90), uint8 (red 36–107, nir 106–174) [S2]. They were cast to float64 before the maths. Zero-denominator pixels: 0 [S2]. Per-pixel NDVI ranges from 0.06 to 0.6571 [S2].

Zone means (Z1–Z3 are the north row, west to east; Z4–Z6 are the south row). Slices are given as rows,cols: Z1 rows 0–30, cols 0–30; Z2 rows 0–30, cols 30–60; Z3 rows 0–30, cols 60–90; Z4 rows 30–60, cols 0–30; Z5 rows 30–60, cols 30–60; Z6 rows 30–60, cols 60–90 (all fixed by the task's 30 m x 30 m zone grid, python-style end-exclusive).

| Zone | Mean NDVI (4 dp) | Stressed (<0.35) |
|---|---|---|
| Z1 | 0.6004 | false |
| Z2 | 0.1472 | true |
| Z3 | 0.5003 | false |
| Z4 | 0.1190 | true |
| Z5 | 0.5543 | false |
| Z6 | 0.1612 | true |
| Field | 0.3471 | n/a |

All values come from [S2] and [S3].

- Unrounded means [S2]: Z1 0.60037, Z2 0.14725, Z3 0.50034, Z4 0.11904, Z5 0.55428, Z6 0.16120. Field mean 0.347079 [S2].
- Consistency check: the mean of the zone means is 0.347079, which equals the field mean [S2].
- Stressed zones, tested on unrounded values: Z2, Z4, Z6 [S2].
- Near-threshold flags (within 0.0005 of 0.35): none. The zone nearest the threshold in the stressed/unstressed split is Z6 at 0.1612 on the low side and Z3 at 0.5003 on the high side [S2].
- Orientation: x runs east along the columns from the west edge and y runs south along the rows from the north edge. Row 0 is the north edge and the map is plotted with imshow origin='upper', so north is at the top.
- Stressed zone centres (derived from the 30 m zone grid, centre = zone corner + 15 m): Z2 at x = 30 + 15 = 45, y = 0 + 15 = 15; Z4 at x = 0 + 15 = 15, y = 30 + 15 = 45; Z6 at x = 60 + 15 = 75, y = 30 + 15 = 45 (metres). These are calculated here, not script outputs.

Files written in the workspace:
- zones.csv: header zone,mean_ndvi,stressed, with 6 rows Z1..Z6 [S2][S3].
- ndvi_map.png: 1080x780 px, with colourbar, zone grid, Z1–Z6 labels and axes in metres [S2][S3].
- results.json: full-precision and 4 dp zone means, field mean, stressed list, shape (60, 90), zero-denominator count 0, and near-threshold flags [S3].
