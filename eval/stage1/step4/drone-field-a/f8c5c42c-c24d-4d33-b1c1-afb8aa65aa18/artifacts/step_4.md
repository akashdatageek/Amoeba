# Field NDVI summary

## Results
The verifier (Step 3) independently recomputed all means and returned PASS. Figures come from [S2], [S3] and [S17].

| Zone | Mean NDVI (4 dp) | Stressed (<0.35) |
|---|---|---|
| Z1 | 0.6004 | no |
| Z2 | 0.1472 | yes |
| Z3 | 0.5003 | no |
| Z4 | 0.1190 | yes |
| Z5 | 0.5543 | no |
| Z6 | 0.1612 | yes |
| Whole field | 0.3471 | n/a |

## Stressed zones
Z2, Z4 and Z6 [S1]. No zone is within 0.0005 of the 0.35 threshold [S2].

## Scouting route
- Order: **Home -> Z2 -> Z6 -> Z4 -> Home**. The reverse direction has the same length.
- Length: **197.3 m** (unrounded 197.2947) [S5].
- Battery limit: 260 m. The route is **within the limit by 62.7 m** [S5].
- The next-best order, Home -> Z4 -> Z2 -> Z6 -> Home, is 219.8 m, so there is no tie [S17].

## Assumptions
- A zone mean is the mean of the per-pixel NDVI.
- The 90 x 60 m field is split into six 30 m x 30 m zones in a 3 x 2 grid, numbered row by row (Z1–Z3 north, west to east; Z4–Z6 south).
- x runs east along the columns and y runs south along the rows. The origin (0,0) is the NW corner and north is at the top of the map.
- Stressed-zone centres, in metres: Z2 (45,15), Z4 (15,45), Z6 (75,45).
- Legs are straight lines between these points. All 6 visiting orders were enumerated.
- There were no zero-denominator (NaN) pixels [S2].

## Deliverables
- ndvi_map.png: NDVI map with colourbar, zone grid and Z1–Z6 labels, north at the top.
- zones.csv: columns zone, mean_ndvi, stressed; 6 rows, Z1–Z6.
- This summary.
- Supporting files:
  - ndvi_step.py: the NDVI and zone-mean script.
  - results.json: full-precision and 4 dp means, stressed list.
  - route.py and route.json: route enumeration and result.
  - tool_results/step1_2.txt: Step 1 tool output.
  - tool_results/step3_1.txt, step3_2.txt, step3_3.txt, step3_4.txt, step3_6.txt: verifier tool outputs.
  - v2.py, ver2.py, ver_check.py, verify_ndvi.py, verify_route.py: verifier scripts.

## Limitations
- Steps 2 and 3 were flagged "partial" only because some citation labels did not match their sources. The verifier found no numeric issues.
- The `runner_up` field in route.json wrongly lists the reverse of the best route (Home-Z4-Z6-Z2-Home, 197.3 m). The correct runner-up is the 219.8 m order above. No reported number is affected.

- Mislabelled citation: step 2 cites S5 for '45,15', which S5 does not contain (added by plain code)
- Mislabelled citation: step 2 cites S5 for '75,45', which S5 does not contain (added by plain code)
- Mislabelled citation: step 2 cites S5 for '15,45', which S5 does not contain (added by plain code)
- Mislabelled citation: step 2 cites S5 for '219.7513', which S5 does not contain (added by plain code)
- Mislabelled citation: step 2 cites S5 for '219.8', which S5 does not contain (added by plain code)
- Mislabelled citation: step 3 cites S17 for '29', which S17 does not contain (added by plain code)
- Mislabelled citation: step 3 cites S17 for '59', which S17 does not contain; it is in S11 (added by plain code)
- Mislabelled citation: step 3 cites S17 for '89', which S17 does not contain (added by plain code)
- Mislabelled citation: step 3 cites S18 for '35,152,80', which S18 does not contain (added by plain code)
- Mislabelled citation: step 3 cites S18 for '204,43,43', which S18 does not contain (added by plain code)
- Mislabelled citation: step 4 cites S2 for '0.0005', which S2 does not contain; it is in S1 (added by plain code)

