Enumeration of all 2^3 = 8 assignments of jobs 4, 7, 9 (hours) to two parallel machines, each job on exactly one machine. Computed with python3 itertools.product; asserts passed (each job once, loads sum to 20) [S1].

| # | Machine 1 jobs | Machine 2 jobs | Load M1 | Load M2 | Makespan |
|---|---|---|---|---|---|
| 1 | 4, 7, 9 | none | 20 | 0 | 20 |
| 2 | 4, 7 | 9 | 11 | 9 | 11 |
| 3 | 4, 9 | 7 | 13 | 7 | 13 |
| 4 | 4 | 7, 9 | 4 | 16 | 16 |
| 5 | 7, 9 | 4 | 16 | 4 | 16 |
| 6 | 7 | 4, 9 | 7 | 13 | 13 |
| 7 | 9 | 4, 7 | 9 | 11 | 11 |
| 8 | none | 4, 7, 9 | 0 | 20 | 20 |

- **Minimum makespan: 11 hours** (rows 2 and 7) [S1]. Every other row is worse: 13, 16 or 20.
- **Optimal assignment:** jobs 4 and 7 on one machine (load 11) and job 9 on the other (load 9). Row 2 puts 4+7 on M1 and 9 on M2. Row 7 is its mirror, with the machine labels swapped. The two rows are the same schedule.
- **Symmetry:** swapping the machine labels maps row 1↔8, 2↔7, 3↔6 and 4↔5. That leaves 4 distinct assignments up to symmetry, with makespans 20, 11, 13 and 16.
- **Lower bound:** max(longest job 9, ceil(20/2) = 10) = 10. The optimum, 11, does not meet it, because no subset of {4, 7, 9} sums to 10 (the subset sums are 0, 4, 7, 9, 11, 13, 16, 20). So a makespan of 10 is impossible, and 11 is optimal. This agrees with the full enumeration.
- **Check:** every job runs on exactly one machine in every row, and each row's loads sum to 20 (20+0, 11+9, 13+7, 4+16, 16+4, 7+13, 9+11, 0+20). The table has exactly 8 rows, including the two rows with all jobs on a single machine.
