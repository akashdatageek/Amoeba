## Step 3: test_wordfreq.py written. Syntax check passed. Not yet run.

**File:** `test_wordfreq.py` in the workspace root. I wrote it with local:Write [S41] and read it back [S42, S44].

**Syntax check:** `python3 -m py_compile test_wordfreq.py` printed `SYNTAX_OK` [S43]. The file has 33 `def test_` methods [S43]: `test_E01` to `test_E33`, one per row of the step-1 edge-case table. Method names, in file order: E01-E27, then E33, then E28-E32 [S43]. I did not run the suite in this step, as instructed.

**Structure** (header and tail seen in the read-back [S44]):
- Only `unittest` is used, plus the standard modules `os`, `subprocess`, `sys`, `tempfile` and `unicodedata`.
- `HERE = os.path.dirname(os.path.abspath(__file__))` and `WORDFREQ = os.path.join(HERE, "wordfreq.py")`. The script is found relative to the test file, so the current directory does not matter. `HERE` is added to `sys.path` so that `from wordfreq import top_words` works.
- The CLI tests write a UTF-8 temp file with `tempfile`. They call `subprocess.run([sys.executable, WORDFREQ, path, ...])` and assert on `returncode`, `stdout` and `stderr`.
- The `top_words` tests (E28-E32) call the function directly.
- The file ends with `if __name__ == "__main__": unittest.main()`.

**What each group asserts** (the expected values are the hand-derived ones from the step-1 table):
- **Case folding and non-ASCII (E01, E02, E26, E32):** `The/the/THE` gives one lowercase word. Precomposed `café` is one word. `Ωmega ωMEGA` gives `ωmega\t2`. `top_words("The THE the don't 'tis")` gives `[("the",3),("don't",1),("tis",1)]` [S44].
- **NFD `café` (E03):** this case is ambiguous in the spec. The test asserts only one output line with count 1, and that its NFC form equals `café`. It does not require NFC and NFD forms to merge.
- **Word characters (E04, E05, E21-E23, E25):** digits (`abc123`, `42`), underscore as a separator, and `42 042 42` giving `42\t2` and `042\t1`.
- **Apostrophes (E06-E08, E27):** leading and trailing apostrophes stripped, internal ones kept (`don't`, `rock'n'roll`, `a''b`), and a lone `''` dropped.
- **min_length (E09-E11, E24, E31):** `--min-length` 1 vs 3. E11 checks that `'ab'` is 2 characters after stripping, so it is excluded at 3 and only `abc` is output. E31 checks `top_words("a bb ccc", min_length=2) == [("bb",1),("ccc",1)]` [S44].
- **Tie ordering (E12, E13, E16, E24):** equal counts sort alphabetically, including non-ASCII words.
- **Count limits (E14-E16, E24, E30):** default n=10 with 12 distinct words gives exactly 10 lines. n larger than the number of distinct words returns all of them. `-n 2` is also tested.
- **Error and empty paths (E17-E20):**
  - `-n 0` and `-n -1` exit 2 even with a valid file.
  - A missing file exits 2 with a stderr message and empty stdout.
  - An empty file exits 0 with empty stdout.
  - A punctuation-only file exits 0 with empty stdout.
- **API (E28, E29):** `top_words('') == []`. `top_words("a b a")` equals `[("a",2),("b",1)]`, and the test checks the result is a `list` of `tuple`s with `str` and `int` members.
- **Output format (E33):** for `a a b`, stdout is exactly `a\t2\nb\t1\n` with a real TAB and empty stderr.

**Requirement coverage:** R1-R10 each have at least one test, as in the step-1 coverage list.

**Limit:** the read-back I have is cut in the middle [S44], so I could not paste all 218 lines here. The complete code is in `test_wordfreq.py` in the workspace. Step 4 must run it from that file with `python3 -m unittest -v`.
MISSING DATA: Full text of test_wordfreq.py in this output — the read-back result [S44] was truncated mid-file, so only the structure and key assertions are quoted; the complete code is in the workspace file
