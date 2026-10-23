# Summary memo

## Result
| Zone | Mean NDVI | Stressed |
|---|---|---|
| Z1 | 0.6004 | No |
| Z2 | 0.1472 | Yes |
| Z3 | 0.5003 | No |
| Z4 | 0.1190 | Yes |
| Z5 | 0.5543 | No |
| Z6 | 0.1612 | Yes |

Whole-field mean NDVI: 0.3471 [S2].

## Stressed zones
Z2, Z4, Z6 (mean NDVI below 0.35) [S2].

## Scouting route
Home (0,0) → Z2 (45,15) → Z6 (75,45) → Z4 (15,45) → Home. Length 197.3 m [S5]. The reverse order ties. Battery: within the 260 m limit by 62.7 m [S5].

## Deliverables
- ndvi_map.png: NDVI map, 1000 x 750 px, north at top [S4].
- zones.csv: columns zone, mean_ndvi, stressed; 6 rows [S2].
- Supporting files: results.json (zone means, field mean, stressed list, centres), ndvi.npy (60×90 NDVI array), mk.py (script that built the map and CSV), qa_ndvi.py and qa_route.py (QA recomputation scripts).

## Assumptions and flags
- Metre coordinates from the NW corner, x east, y south. Centres are at x = 15, 45, 75 and y = 15, 45.
- Undefined pixels: 0 [S2].
- No zone mean is within 0.0005 of 0.35. The field mean is below 0.35, but the rule applies to zones only.
- QA verdict: PASS, no discrepancies; no corrections needed.

## Limitations
- Steps 1–3 were partial (mislabelled citation tags); steps 2 and 3 were stale (built before step 1's rework). QA's recomputation matched their values.
- Step 4 was disputed over a battery-limit tag (260 vs 62.7); its PASS verdict and the 62.7 m margin are consistent.
- The PNG was not inspected visually; Z1 placement is inferred from the plot extent and label coordinates.

- NOT MET: R3 — Find the shortest route that starts at the NW corner (0,0), flies in straight lines over the centre of every stressed zone and lands back at (0,0). Give the vis (the final answer does not cover it; checked by plain code on the final answer)

