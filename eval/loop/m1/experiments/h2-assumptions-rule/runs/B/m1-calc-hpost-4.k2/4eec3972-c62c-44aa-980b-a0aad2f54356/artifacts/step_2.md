Verdict: PASS
Issues: none

Verification Report:
- Distance: Pass
- Fuel: Pass
- Cost: Pass

Re-checks performed:
- Distance: `calc(22 * 2 * 5 * 46)` returned 10120. Matches Step 1.
- Fuel: `calc((10120 / 100) * 7.8)` returned 789.36. Matches Step 1.
- Cost: `calc(789.36 * 1.65)` returned 1302.444. Matches Step 1 ($1,302.44 rounded).
