Files written in the workspace: **zones.csv** and **ndvi_map.png**. Their source data are results.json [S3] and ndvi.npy. The array has shape (60, 90), dtype float64 and 0 NaN [S4].

**ndvi_map.png** is 1000 x 750 px [S4]. It is an imshow of the NDVI array with the RdYlGn colormap, vmin -0.1 and vmax 0.8. Origin is top-left and the array is not flipped. Extent is x 0–90 m and y 60–0 m, so y is 0 at the top. The axis labels are "x (m, east from west edge)" and "y (m, south from north edge)". The colourbar is labelled NDVI. White lines are drawn at x=30, x=60 and y=30. Labels Z1–Z6 sit at the zone centres from results.json, with Z1 at the top left (15, 15), Z2 at (45, 15) and Z3 at (75, 15) on the north row, and Z4–Z6 on the south row. I did not open the PNG visually. The Z1 placement follows from the extent and the label coordinates.

**zones.csv** (header `zone,mean_ndvi,stressed`, 6 data rows) [S2]:

| zone | mean_ndvi | stressed |
|---|---|---|
| Z1 | 0.6004 | False |
| Z2 | 0.1472 | True |
| Z3 | 0.5003 | False |
| Z4 | 0.1190 | True |
| Z5 | 0.5543 | False |
| Z6 | 0.1612 | True |

**Re-read check:** I re-read zones.csv and compared it with results.json. There are 6 rows, and every mean equals zone_means_4dp and every stressed flag matches the stressed list [Z2, Z4, Z6] [S2]. The script printed `6 True` [S4]. The PNG re-opened with PIL at (1000, 750) [S4].

Field mean is 0.3471 [S3]. The convention is x east along the columns from the west edge and y south along the rows from the north edge, with north at the top.
