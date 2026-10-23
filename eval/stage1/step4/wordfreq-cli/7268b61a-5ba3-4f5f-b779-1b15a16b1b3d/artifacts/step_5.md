Verdict: PASS
Independent acceptance runs (Independent Verifier). I ran everything in the workspace with local:Bash. TABs are shown as ^I from cat -A, and "$" marks end of line.

**A. Test re-run and import check**
1. Test suite. I ran `python3 -m unittest` and `python3 -m unittest -v`.
   - Expected: all tests pass, 33 of them (E01–E33).
   - Actual: "Ran 33 tests in 1.148s / OK" [S51], and again "Ran 33 tests in 1.113s / OK" [S52].
   - `grep -c "    def test_" test_wordfreq.py` gave 33 [S52], and 33 lines ended in "... ok" [S52]. The test count matches Step 4's claim [S45].
2. Import side effects. I ran `python3 -c 'import wordfreq; print(wordfreq.top_words("a A b"))'`.
   - Expected: only `[('a', 2), ('b', 1)]`.
   - Actual: exactly `[('a', 2), ('b', 1)]` and nothing else [S51]. There are no import side effects.

**B. CLI scenarios** (each run as `python3 ../wordfreq.py ...`; stdout and stderr captured separately)
3. `a.txt -n 2`, file = `The the THE café cafe 'tis dogs' rock'n'roll`.
   - Expected, hand-derived: the=3, then a tie of 1 each with cafe before café. Output `the^I3`, `cafe^I1`, exit 0.
   - Actual: `the^I3$`, `cafe^I1$`, exit=0, stderr empty [S51]. MATCH.
4. `a.txt --min-length 4`.
   - Expected: cafe, café, dogs, rock'n'roll, each ^I1. "the" and "tis" are dropped. "dogs'" becomes "dogs" (4 characters) and is kept.
   - Actual: `cafe^I1$`, `cafM-CM-)^I1$` (é as UTF-8), `dogs^I1$`, `rock'n'roll^I1$`, exit=0 [S51]. MATCH.
5. `many.txt` (12 distinct words a–l) with default n.
   - Expected: 10 lines, a–j, each ^I1. k and l are absent. Exit 0.
   - Actual: `a^I1$` … `j^I1$` (10 lines), exit=0 [S51]. MATCH.
6. `ties.txt` = `pear apple pear fig fig zed`.
   - Expected: `fig^I2`, `pear^I2`, `apple^I1`, `zed^I1`. Count descending, then alphabetical.
   - Actual: the same four lines in the same order, exit=0 [S51]. MATCH.
7. `nope.txt` (missing file).
   - Expected: exit 2, error on stderr, empty stdout.
   - Actual: exit=2, stdout empty, stderr `wordfreq: error: [Errno 2] No such file or directory: 'nope.txt'$` [S51]. MATCH.
8. `a.txt -n 0`.
   - Expected: exit 2.
   - Actual: exit=2, stdout empty, stderr `wordfreq: error: -n must be at least 1$` [S51]. MATCH.
9. `a.txt -n -3`.
   - Expected: exit 2.
   - Actual: exit=2, same message, stdout empty [S51]. MATCH.
10. `nope.txt -n 0` (bad N together with a missing file).
    - Expected: exit 2, with N checked before the file is opened, so the message is the -n one.
    - Actual: exit=2, stderr `-n must be at least 1`, not the file error [S51]. MATCH. This shows N is validated before file access.
11. `empty.txt`.
    - Expected: stdout empty, exit 0.
    - Actual: exit=0, stdout empty, stderr empty, and `wc -c` of stdout gave "empty bytes: 0" [S51]. MATCH.
12. `us.txt --min-length 3`, file = `snake_case 'ab' abc`.
    - Expected: underscore splits words, and the apostrophe strip comes before the length test. So `'ab'` becomes ab (2 characters) and is dropped. Output `abc^I1`, `case^I1`, `snake^I1`.
    - Actual: `abc^I1$`, `case^I1$`, `snake^I1$`, exit=0 [S51]. MATCH.
13. Extra: a file with invalid UTF-8 bytes (`x\xff`).
    - Expected: a clean error, with no traceback.
    - Actual: `wordfreq: error: 'utf-8' codec can't decode byte 0xff in position 1: invalid start byte`, exit=2 [S52]. OK.
14. Extra: `printf "a b" | python3 wordfreq.py /dev/stdin -n 1`.
    - Expected: `a^I1`, exit 0.
    - Actual: `a\t1`, exit=0 [S52]. OK.

**C. Re-checks I ran**
- I re-ran the whole unittest suite twice. It gave 33 tests, OK, matching Step 4's "Ran 33 tests ... OK" [S45].
- I counted the test methods with grep and "... ok" lines. Both gave 33 [S52], so Step 4's count is right.
- I grepped the real workspace file [S11, S52]:
  - Line 10 [S11] is the regex `(?:[^\W_]|')+`, so underscore is a separator.
  - Line 26 [S11] is `token.strip("'").lower()`, which strips before the length test.
  - Line 30 [S11] is `sorted(..., key=lambda kv: (-kv[1], kv[0]))[:n]`, which is count descending, then alphabetical.
  - Line 48 [S11] is `if args.n < 1`, which runs before the `open` call at line 52 [S52].
- Step 2 discrepancy: its code block shows `open(args.path, encoding="utf-8")`. The real file has `newline=None` at line 52 [S52]. `newline=None` is the default text-mode value, so behaviour is the same and no conclusion changes. The block is a reconstruction, as Step 2 itself said. The real file has 69 lines by `wc -l` [S45]. The Step 2 count of 70 comes from the Read tool [S11] and is probably a counting difference.
- I did not re-check anything against web sources. The task has no external figures.

**D. Result**
All 12 scenarios and both extra checks match the hand-derived expectations. The missing file, `-n 0` and `-n -3` each exit with 2. The empty file exits with 0 and prints nothing. The unittest summary is "Ran 33 tests ... OK". The import has no side effects. Mutation testing and the full requirement table belong to the review step and are not part of this one.
Issues: none
