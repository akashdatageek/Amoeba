# Field NDVI summary

## Results
| zone | mean NDVI | stressed |
|---|---|---|
| Z1 | 0.6004 [S7] | false |
| Z2 | 0.1472 [S7] | true |
| Z3 | 0.5003 [S7] | false |
| Z4 | 0.1190 [S7] | true |
| Z5 | 0.5543 [S7] | false |
| Z6 | 0.1612 [S7] | true |

Whole-field mean NDVI: 0.3471 (unrounded 0.347079) [S7]

## Stressed zones
A zone is stressed when its unrounded mean NDVI is below 0.35.
- Z2 (0.1472) [S7]
- Z4 (0.1190) [S7]
- Z6 (0.1612) [S7]

## Route and battery
- Shortest route: (0,0) -> Z2 -> Z6 -> Z4 -> (0,0). The reverse direction has the same length.
- Zone centres used: Z2 (45, 15), Z6 (75, 45), Z4 (15, 45) [S9].
- Length: 197.3 m (unrounded 197.2947 m) [S9].
- The route is within the 260 m battery limit, with 62.7 m to spare [S9].
- All 6 orderings were checked. The next-best total is 219.7513 m [S9].

## Deliverables
Required files, both in the workspace:
- ndvi_map.png: the NDVI map. It is a 1350×975 px RdYlGn heatmap with a colorbar, zone grid lines and Z1–Z6 labels [S7].
- zones.csv: header `zone,mean_ndvi,stressed`, then six rows Z1 to Z6, with means to 4 dp and stressed as true/false [S7].

Supporting files made by the team (not requested deliverables):
- ndvi_step1.py (step 1): script that computes the NDVI, the zone means and the two deliverable files.
- r_route.py and r_route2.py (step 2): scripts that try all 6 orderings of the stressed zones and compute the route length.
- qa_compute.py and qa_recompute.py (step 3): the verifier's independent recomputation scripts.
- tool_results/step3_2.txt (step 3): saved output of the verifier's recomputation.

## Assumptions and caveats
- The input bands are 60 rows by 90 columns [S6]. x runs east along the columns from the west edge, and y runs south along the rows from the north edge. Zones are numbered row by row: Z1–Z3 on the north row and Z4–Z6 on the south row.
- NDVI was computed in float64 from the raw 0–255 values. Pixels with NIR + Red = 0 would be NaN. There were none (NaN pixels: 0) [S7].
- No zone is within 0.0005 of the 0.35 threshold. The closest is Z2 at 0.147249 [S7].
- The drone is assumed to fly straight Euclidean legs between points. Zone centres are at the 30 m block midpoints.
- Verifier verdict: PASS. All figures were independently recomputed and no discrepancies were found [S14].

## Limitations
- Step 1 was marked partial. Its text was truncated, so the zones were recomputed, and two citations were mislabelled. All of its figures were confirmed by step 3.
- Step 3 was marked partial because of mislabelled citations. Its verdict is PASS and no figure changed.
- The verifier checked ndvi_map.png only for a valid PNG signature and size (1350×975). It did not inspect the rendered image, so the colourmap, labels and grid lines rest on step 1's description.
