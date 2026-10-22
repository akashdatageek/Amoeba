# Final memo: two parallel machines, jobs of 4, 7 and 9 hours

## Answer
- **Minimum makespan: 11 hours** [S1].
- **Optimal assignment:**
  - Machine 1 runs jobs 4 and 7, so its load is 11 hours.
  - Machine 2 runs job 9, so its load is 9 hours.
  - The mirror assignment swaps the machine labels: Machine 1 runs job 9 (load 9) and Machine 2 runs jobs 4 and 7 (load 11). It is the same schedule, and its makespan is also 11 [S1].

## Optimality check (all 2^3 = 8 labelled assignments)

| # | Machine 1 jobs | Machine 2 jobs | Load M1 | Load M2 | Sum | Makespan |
|---|---|---|---|---|---|---|
| 1 | 4, 7, 9 | none | 20 | 0 | 20 | 20 |
| 2 | 4, 7 | 9 | 11 | 9 | 20 | **11** (optimal) |
| 3 | 4, 9 | 7 | 13 | 7 | 20 | 13 |
| 4 | 4 | 7, 9 | 4 | 16 | 20 | 16 |
| 5 | 7, 9 | 4 | 16 | 4 | 20 | 16 |
| 6 | 7 | 4, 9 | 7 | 13 | 20 | 13 |
| 7 | 9 | 4, 7 | 9 | 11 | 20 | **11** (optimal, mirror of row 2) |
| 8 | none | 4, 7, 9 | 0 | 20 | 20 | 20 |

(Source: [S1], independently recomputed in [S3]. The two sources agree row by row.)

- The smallest makespan in the table is 11, in rows 2 and 7 only. Every other row gives 13, 16 or 20. So 11 is the optimal makespan.
- Symmetry: swapping the machine labels maps rows 1↔8, 2↔7, 3↔6 and 4↔5. That leaves 4 distinct assignments, with makespans 20, 11, 13 and 16 [S1].
- Lower bound: max(longest job 9, ceil(20/2) = 10) = 10. A makespan of 10 would need a subset of {4, 7, 9} summing to 10. The subset sums are 0, 4, 7, 9, 11, 13, 16, 20, so 10 is not one of them [S3]. The optimum of 11 therefore cannot be improved, which agrees with the full enumeration.
- In every row, each job runs on exactly one of the two parallel machines. The two loads sum to 20 hours in every row (20+0, 11+9, 13+7, 4+16, 16+4, 7+13, 9+11, 0+20) [S1][S3].

## Assumptions
- The two machines are identical and run in parallel.
- Each job runs on exactly one machine and cannot be split.
- All jobs are available at time 0.
- The makespan is the larger of the two machine loads.

## Verification
Verifier verdict: **PASS**. All 8 rows match, there are no corrections, and the minimum makespan of 11 hours was confirmed [S1].

## Limitations
- Step 2 (Independent Verifier) was reported with status "partial". The cause was mislabelled citation tags in its memo, not wrong figures. The tags were '1,2', '3', '10 in sums' and '4,7,9', and none of them appeared in [S3]. The verdict was PASS, with 0 unverified figures and no corrections. The main figures affected are the table values, the makespan of 11, and the subset sums.
