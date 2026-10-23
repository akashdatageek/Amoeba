## Route report: scouting drone, stressed zones Z2, Z4, Z6

Stressed zones and centres (from results.json [S5]; x east, y south, origin at the NW corner): Z2 (45,15), Z4 (15,45), Z6 (75,45).

I enumerated all 3! = 6 orders with itertools. Legs are straight-line Euclidean, starting and ending at (0,0) [S5].

**Best route: Home -> Z2 -> Z6 -> Z4 -> Home**

| Leg | Length (m) |
|---|---|
| Home (0,0) -> Z2 (45,15) | 47.4342 (sqrt(45²+15²)) [S5] |
| Z2 -> Z6 (75,45) | 42.4264 (sqrt(30²+30²)) [S5] |
| Z6 -> Z4 (15,45) | 60.0000 [S5] |
| Z4 -> Home | 47.4342 (sqrt(15²+45²)) [S5] |
| **Total** | **197.3 m** (full precision 197.2947366762442) [S5] |

The leg lengths sum to the total: 47.4342 + 42.4264 + 60.0 + 47.4342 = 197.2948, which matches the full-precision total within rounding.

**Battery verdict:** the route is **within** the 260 m battery limit by **62.7 m**. Margin = 260 − 197.2947 = 62.7053 m, or 62.7 m to 1 decimal.

**Tie:** the reverse order (Home -> Z4 -> Z6 -> Z2 -> Home) has the same length, 197.2947 m [S5]. I list the lexicographically first order, Z2 -> Z6 -> Z4.

**Sanity checks:**
- The upper bound of 218.64 m comes from the step instructions [unverified]. The total of 197.3 m is below it: 218.64 − 197.2947 = 21.35 m of slack.
- The lower bound is twice the distance to the farthest stressed centre. Z6 is 87.4643 m from home [S5], so twice that is 174.93 m [S5]. We have 197.3 ≥ 174.9, so the check passes.

**Alternatives (all 6 orders evaluated; each reverse pair ties, so there are 3 distinct lengths) [S2]:**
- 1st (best): Home -> Z2 -> Z6 -> Z4 -> Home, 197.3 m (197.2947). It is within the 260 m battery limit by 62.7 m. The reverse, Z4 -> Z6 -> Z2, ties.
- 2nd: Home -> Z4 -> Z2 -> Z6 -> Home, 219.8 m (219.7513 [S5]). It is within the limit by 260 − 219.7513 = 40.2487 m, or 40.2 m. It is 219.7513 − 197.2947 = 22.4566 m (22.5 m) longer than the best. The reverse, Z6 -> Z2 -> Z4, ties.
- 3rd: Home -> Z2 -> Z4 -> Z6 -> Home, 237.3 m (237.3249 [S5]). It is within the limit by 260 − 237.3249 = 22.6751 m, or 22.7 m. It is 237.3249 − 197.2947 = 40.0302 m (40.0 m) longer than the best. The reverse, Z6 -> Z4 -> Z2, ties.

All orders are within the 260 m battery limit. The best is the shortest, and it leaves the most margin.
