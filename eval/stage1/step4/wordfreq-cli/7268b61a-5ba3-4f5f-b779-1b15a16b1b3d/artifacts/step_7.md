# wordfreq.py: final deliverable

**Read this first.** The 33 tests passed on the on-disk files, and both verifiers wrote Verdict: PASS. I could not copy `wordfreq.py` or `test_wordfreq.py` in full. The step outputs I received were cut in the middle. Each gap in the code blocks below is marked `[… omitted …]`, and I did not fill any gap by guessing. The complete, authoritative copies are `wordfreq.py` and `test_wordfreq.py` in the workspace. The blocks below cannot be run as pasted.

## Files delivered
- `wordfreq.py`: the tool. It holds `top_words(text, n=10, min_length=1)` and the CLI `python wordfreq.py PATH [-n N] [--min-length L]`. It has 69 lines by `wc -l` [S45].
- `test_wordfreq.py`: the unittest suite. It has 217 lines [S45] and 33 test methods, `test_E01` to `test_E33` [S43]. `CliTests` runs the CLI through `subprocess`. `TopWordsTests` calls `top_words` directly.
- Supporting files made by the team during testing and verification. They are not part of the deliverable:
  - `acc/`, `acc2/`, `v/`, `s.txt`, `e.txt`, `t.txt`, `crlf.txt`: small input and output fixture files for the manual CLI runs (Steps 2, 5, 6).
  - `acceptance_runs.sh`: the Step 5 script for the acceptance scenarios.
  - `mutation_test/`, `mv/`: copies of `wordfreq.py` and `test_wordfreq.py` with one deliberate change each, for the Step 6 mutation check.
  - `tool_results/step*_*.txt`: saved tool output. `tool_results/step4_1.txt` holds the full verbose test listing.
  - `__pycache__/test_wordfreq.cpython-311.pyc`: Python bytecode cache.

## wordfreq.py

This is the Step 2 text. Step 2 called it a reconstruction that was not re-run, and it is cut where marked. Steps 5 and 6 compared it with the real file and found these differences:
- The real file calls `open(...)` with `newline=None` at line 52 [S52]. That is the default, so behaviour is the same.
- The real error message for N < 1 reads `-n must be at least 1` [S51]. The block below says `-n must be >= 1`.

```python
#!/usr/bin/env python3
"""wordfreq: print the N most frequent words of a UTF-8 text file.

Usage: python wordfreq.py PATH [-n N] [--min-length L]
"""
import argparse
import re
import sys
import unicodedata
from collections import Counter

# A word is a maximal run of letters/digits (any script) and ASCII apostrophes.
# Underscore is excluded, so it separates words.
_TOKEN_RE = re.compile(r"(?:[^\W_]|')+")


def top_words(text, n=10, min_length=1):
    """Return the n most frequent words as [(word, count), ...].

    Sorted by count descending, then alphabetically. Raises ValueError if n < 1.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    text = unicodedata.normalize("NFC", text)
    counts = Counter()
    for token in _TOKEN_RE.findall(text):
        word = token.strip("'").lower()
        if not word or len(word) < min_length:
            continue
        counts[word] += 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="wordfreq",
        description="Print the N most frequent words of a UTF-8 text file.")
    parser.add_argument("path", metavar="PATH", help="UTF-8 text file")
    parser.add_argument("-n", dest="n", type=int, default=10,
                        help="number of words to print (default 10)")
    parser.add_argument("--min-length", dest="min_length", type=int, default=1,
                        help="ignore words shorter than this (default 1)")
    args = parser.parse_args(argv)
    if args.n < 1:
        print("wordfreq: error: -n must be >= 1", file=sys.stderr)
        sys.exit(2)
    try:
        with open(args.path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"wordfreq: error: {exc}", file=sys.stderr)
        sys.exit(2)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
[… 38 characters omitted …]
            pass
    for word, count in top_words(text, args.n, args.min_length):
        sys.stdout.write(f"{word}\t{count}\n")
[… 41 characters omitted …]
if __name__ == "__main__":
[… rest of file omitted in the supplied step output …]
```

## Tests

`test_wordfreq.py` is not in the supplied outputs in full. The fragments below are all I have. They come from Step 2's compact rewrite, and the same caveat applies. The workspace copy is the one to use.

```python
[… file header omitted; it imports os, subprocess, sys, tempfile, unittest, wordfreq …]
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "wordfreq.py")

def run_cli(content, *args, path=None):
[… omitted …]
        p = path if path is not None else os.path.join(d, "in.txt")
[… omitted …]
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
[… omitted …]
                              capture_output=True, env=env)
[… omitted …]
        r = wordfreq.top_words("a b a")
[… omitted …]
        self.assertEqual(wordfreq.top_words("c b a b c c", n=2),
[… omitted …]
            wordfreq.top_words("a", n=0)
[… omitted …]
        self.assertEqual(wordfreq.top_words("a bb ccc", min_length=2),
[… omitted …]
        self.assertEqual(wordfreq.top_words("'ab' abc", min_length=3),
[… omitted …]
        r = wordfreq.top_words("cafe\u0301")
[… omitted …]
        text = " ".join("abcdefghijkl")
        r = wordfreq.top_words(text)
[… omitted …]
            wordfreq.top_words("aa aa bb c c c dd", n=2, min_length=2),
[… omitted …]
        p = run_cli("a a b")
[… omitted …]
        p = run_cli("The the THE café 'tis rock'n'roll '' foo_bar")
[… omitted …]
        p = run_cli("a a b c", "-n", "1")
[… omitted …]
        p = run_cli("a bb ccc dddd a", "--min-length", "3")
[… omitted …]
        p = run_cli("a b", "-n", "0")
[… omitted …]
        p = run_cli("", path=os.path.join(HERE, "no_such_file_xyz.txt"))
        self.assertEqual(p.returncode, 2)
        self.assertEqual(p.stdout, b"")
        self.assertNotEqual(p.stderr, b"")

    def test_empty_file_exit_0(self):
        p = run_cli("")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, b"")

    def test_invalid_utf8_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "bad.txt")
            with open(f, "wb") as fh:
                fh.write(b"\xff\xfe\xfa")
            p = subprocess.run([sys.executable, SCRIPT, f], capture_output=True)
            self.assertEqual(p.returncode, 2)

    def test_import_has_no_side_effects(self):
        p = subprocess.run(
            [sys.executable, "-c", "import wordfreq"],
            capture_output=True, cwd=HERE)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, b"")


if __name__ == "__main__":
    unittest.main()
```

What the tests cover (from Step 3):
- Case folding, non-ASCII words, digits, underscore as a separator and apostrophe stripping.
- `--min-length`, tie ordering and the default N of 10.
- `-n 0` and `-n -1`, a missing file, an empty file and a punctuation-only file.
- The `top_words` API and the exact `word<TAB>count` output format.

E03 (decomposed "café") asserts only one output line with count 1, because the spec does not say whether the two forms must merge.

## Test result

Command: `python3 -m unittest -v`, run in the workspace (Step 4). Exact summary [S45]:

```
Ran 33 tests in 1.081s

OK
```

- **Count and result:** 33 tests, all passed, no failures, errors or skips.
- **Verifier re-runs:** Step 5 reported "Ran 33 tests in 1.148s / OK" [S51] and "Ran 33 tests in 1.113s / OK" [S52]. Step 6 reported "Ran 33 tests in 1.121s / OK" [S59] and "Ran 33 tests in 1.169s / OK" [S60].
- **Method count:** `grep -c "    def test_"` gave 33 [S52], and 33 lines ended in "... ok" [S52].
- **Not run:** the reconstructed code blocks in this memo were not run. The runs above were on the on-disk files.

## Verification

**Verdict: PASS.** Both verifiers (Step 5 and Step 6) reported PASS with "Issues: none".

The automatic check on Step 6 flagged its verdict as DISPUTED. The reason was a mismatch between timing figures (Step 5 "1.148" against a check value of "1.284"), and it was left unresolved. The test count and OK result agree in all runs. I report the flag as given and have not resolved it.

Step 6 requirement summary (the verifier's own R1–R12 mapping), all PASS:
- **R1:** CLI arguments and default N of 10. The default gives 10 lines, and `-n 2` works.
- **R2:** `word<TAB>count` output.
- **R3:** count descending, then alphabetical.
- **R4:** word definition, with underscore splitting words.
- **R5:** case-insensitive, printed in lowercase.
- **R6:** apostrophes stripped, empty words dropped.
- **R7:** `--min-length` applied after stripping.
- **R8:** non-ASCII letters.
- **R9:** `top_words` exposed with the required signature.
- **R10:** `top_words` follows the same rules.
- **R11:** missing file gives exit 2 with the error on stderr.
- **R12:** N < 1 gives exit 2 before file access. An empty file gives exit 0 with no output.

Acceptance runs (Steps 5 and 6, on the real file):
- Missing file: rc=2, stderr `wordfreq: error: [Errno 2] No such file or directory: 'nope.txt'`, stdout empty [S51][S59].
- `-n 0` and `-n -3`: rc=2, message `-n must be at least 1` [S51][S59].
- `nope.txt -n 0`: rc=2, with the -n message, so N is checked first [S51][S59].
- Empty file: rc=0, no output [S51][S59].
- Invalid UTF-8 file: rc=2, clean error [S52].
- Importing the module prints nothing [S51].

Mutation check (Step 6). Each mutant was caught by the tests:

| Mutant | Change | Result | Caught |
|---|---|---|---|
| M1 | Sort key `(-kv[1], kv[0])` → `(kv[1], kv[0])` | Ran 33 tests / FAILED (failures=14) [S59] | yes |
| M2 | Removed `.strip("'")` | FAILED (failures=4) [S59] | yes |
| M3 | Regex `[^\W_]` → `\w` | FAILED (failures=1) [S59] | yes |
| M4 | `len(word)` → `len(token)` | FAILED (failures=1) [S59] | yes |

Step 6 reported "No defects found."

## Assumptions

From Step 1 (the supplied text is partly cut, so the list may be incomplete):
- **Underscore:** `_` is not a letter, digit or apostrophe, so it separates words. `snake_case` gives `snake` and `case`.
- **Apostrophe:** only the ASCII apostrophe (U+0027 [unverified]) is handled. The curly right single quote (U+2019 [unverified]) is unspecified and untested.
  - Leading and trailing apostrophe runs are stripped completely, so `'''x'''` gives `x`.
  - Internal apostrophes are kept, including consecutive ones (`a''b`).
  - A token made only of apostrophes is dropped.
- **Lowercase:** plain `str.lower()`. Tests use only ASCII, é/É and Ω/ω. Special cases such as ß and the Turkish dotted İ are avoided.
- **Normalization:** the spec does not require NFC/NFD merging, so E03 asserts only one line with count 1. The code normalizes text to NFC, so the two forms merge. Step 6 called this an addition consistent with the spec.
- **Length:** the minimum length is measured after apostrophe stripping.
- **Argument handling:** `-n -1` is passed as two arguments. If argparse rejects it, that still exits 2.
- **Validation order:** N is validated before the file is opened.
- **Invalid UTF-8:** this is treated as an error, exit 2 with a message. The task does not specify this case.
- **Requirement ids:** the task text has no numbered requirements, so Steps 1 and 6 each defined their own ids.

## Files made
- acc/a.txt (45 bytes, made in step 5; listed by plain code)
- acc/empty.txt (0 bytes, made in step 5; listed by plain code)
- acc/err.txt (0 bytes, made in step 5; listed by plain code)
- acc/m.txt (23 bytes, made in step 5; listed by plain code)
- acc/many.txt (23 bytes, made in step 5; listed by plain code)
- acc/o.txt (21 bytes, made in step 5; listed by plain code)
- acc/out.txt (21 bytes, made in step 5; listed by plain code)
- acc/ties.txt (27 bytes, made in step 5; listed by plain code)
- acc/u.txt (19 bytes, made in step 5; listed by plain code)
- acc/us.txt (19 bytes, made in step 5; listed by plain code)
- acc2/a.txt (46 bytes, made in step 6; listed by plain code)
- acc2/empty.txt (0 bytes, made in step 6; listed by plain code)
- acc2/many.txt (52 bytes, made in step 6; listed by plain code)
- acc2/o.txt (0 bytes, made in step 6; listed by plain code)
- acc2/ties.txt (10 bytes, made in step 6; listed by plain code)
- mutation_test/orig.py (2,347 bytes, made in step 6; listed by plain code)
- mutation_test/test_wordfreq_m2.py (8,424 bytes, made in step 6; listed by plain code)
- mutation_test/wordfreq_m2.py (2,336 bytes, made in step 6; listed by plain code)
- tool_results/step2_1.txt (2,116 bytes, made in step 2; listed by plain code)
- tool_results/step2_2.txt (2,820 bytes, made in step 2; listed by plain code)
- tool_results/step2_3.txt (2,128 bytes, made in step 2; listed by plain code)
- tool_results/step2_4.txt (2,699 bytes, made in step 2; listed by plain code)
- tool_results/step2_5.txt (2,699 bytes, made in step 2; listed by plain code)
- tool_results/step2_6.txt (2,128 bytes, made in step 2; listed by plain code)
- tool_results/step2_7.txt (2,127 bytes, made in step 2; listed by plain code)
- tool_results/step2_8.txt (3,066 bytes, made in step 3; listed by plain code)
- tool_results/step3_1.txt (2,132 bytes, made in step 3; listed by plain code)
- tool_results/step3_3.txt (2,126 bytes, made in step 3; listed by plain code)
- tool_results/step3_5.txt (2,126 bytes, made in step 4; listed by plain code)
- tool_results/step5_2.txt (3,567 bytes, made in step 5; listed by plain code)
- tool_results/step5_3.txt (2,121 bytes, made in step 5; listed by plain code)
- tool_results/step5_5.txt (3,604 bytes, made in step 5; listed by plain code)
- tool_results/step5_6.txt (3,976 bytes, made in step 5; listed by plain code)
- tool_results/step6_2.txt (2,724 bytes, made in step 6; listed by plain code)
- tool_results/step6_6.txt (2,724 bytes, made in step 6; listed by plain code)
- tool_results/step6_7.txt (7,773 bytes, made in step 6; listed by plain code)
- tool_results/step6_8.txt (3,344 bytes, made in step 6; listed by plain code)
- v/a.txt (45 bytes, made in step 6; listed by plain code)

## Limitations
- **Code not complete (Steps 2 and 3):** the verbatim text of `wordfreq.py` and `test_wordfreq.py` was not available because tool output was truncated. Step 2 flagged the missing data. The code blocks above are cut where marked `[… omitted …]`. Use the workspace files.
- **Reconstruction differences:** the `wordfreq.py` block differs from the real file in the error message wording and in `newline=None` (Steps 5 and 6).
- **Step 4:** the middle of the 33-line verbose listing was cut. The full output is in `tool_results/step4_1.txt`.
- **Step 6 verdict flag:** the automatic check marked it DISPUTED over a timing figure. The verifier's text says PASS.
- **Mislabelled citations:** the automatic checks flagged several mislabelled citations in Steps 2 to 6. I copied the figures as written, with their tags.
- **Unverified figures:** the Unicode code points U+0027 and U+2019 are tagged [unverified].
BLOCKED: Complete verbatim wordfreq.py — Step 2 output was truncated, so the code block is partial
BLOCKED: Complete verbatim test_wordfreq.py — Steps 2 and 3 outputs were truncated, so only fragments are shown
MISSING DATA: Verbatim full text of wordfreq.py — Step 2 output (cut in the middle)
MISSING DATA: Verbatim full text of test_wordfreq.py (217 lines [S45]) — Steps 2 and 3 outputs (truncated)
MISSING INPUT: Complete verbatim wordfreq.py — Step 2
MISSING INPUT: Complete verbatim test_wordfreq.py — Step 3
