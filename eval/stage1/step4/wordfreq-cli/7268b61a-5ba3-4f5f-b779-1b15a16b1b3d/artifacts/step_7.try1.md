# wordfreq: final deliverable

**Overall:** The verifier's verdict is PASS, and the suite reported "Ran 33 tests … OK". Two parts of this memo are incomplete:
- The `wordfreq.py` code block is the developer's reconstruction. It is not a verbatim copy of the tested file.
- The full text of `test_wordfreq.py` was never delivered to me, so the Tests section has no code block.

## Files

The task asks for two files. Both are in the workspace root.
- `wordfreq.py`: the tool, with the CLI and `top_words`. The block below is a reconstruction. The tested file is the workspace copy.
- `test_wordfreq.py`: the unittest suite with 33 tests. Step 2 gave its size as 2884 characters [S8], which is an early draft size. Step 3 later wrote the file again. Step 3 quoted 218 lines [S44] and Step 4 gave 217 lines [S45]. I could not reconcile these two line counts.

The team also left helper files in the workspace. They are not deliverables.
- Scratch and sample inputs: `s.txt`, `t.txt`, `e.txt` (steps 2–3), `crlf.txt` (step 6), and `__pycache__/test_wordfreq.cpython-311.pyc` (step 3, compiled cache).
- Acceptance fixtures (step 5, folder `acc/`): `a.txt`, `empty.txt`, `err.txt`, `m.txt`, `many.txt`, `o.txt`, `out.txt`, `t.txt`, `ties.txt`, `u.txt`, `us.txt`. These hold input files and captured stdout/stderr. `acceptance_runs.sh` is the script that ran the scenarios.
- Acceptance fixtures (step 6, folders `acc2/` and `v/`): `acc2/a.txt`, `acc2/empty.txt`, `acc2/many.txt`, `acc2/o.txt`, `acc2/ties.txt`, `v/a.txt`. They hold the same kind of input and output captures.
- Mutation check (step 6): `mutation_test/orig.py`, `mutation_test/wordfreq_m2.py`, `mutation_test/test_wordfreq_m2.py`, plus the `mutation_test/`, `mv/` and `m2/` folders. These hold copies of the code with one deliberate bug each, and the test file run against them.
- Saved tool output (folder `tool_results/`): `step2_1.txt` to `step2_8.txt`, `step3_1.txt`, `step3_3.txt`, `step3_5.txt`, `step5_2.txt`, `step5_3.txt`, `step5_5.txt`, `step5_6.txt`, `step6_2.txt`, `step6_6.txt`, `step6_7.txt`, `step6_8.txt`. Each holds the raw output of a command in that step. `step4_1.txt` holds the full verbose test listing.

## wordfreq.py

Step 2 (Python Developer) supplied this block. Step 2 said it rewrote the middle of `main()` from a cut-off tool output, so it is a reconstruction. The workspace `wordfreq.py` is the file that was actually tested. Step 5 and Step 6 found one difference: the workspace file's `open(...)` call at line 52 also passes `newline=None`, which is the default text-mode value, so behaviour is the same. Step 5 and Step 6 give the workspace file as 69 lines by `wc -l`; Step 2 said 70. I did not diff the block against the workspace file.

```python
#!/usr/bin/env python3
"""wordfreq: print the most frequent words of a UTF-8 text file."""

import argparse
import re
import sys
import unicodedata
from collections import Counter

_TOKEN_RE = re.compile(r"(?:[^\W_]|')+")


def top_words(text, n=10, min_length=1):
    """Return the n most frequent words as (word, count) tuples.

    A word is a maximal run of letters, digits and apostrophes. Words are
    lowercased, leading/trailing apostrophes are stripped, empty words are
    dropped, and words shorter than min_length are ignored. Sorted by count
    descending, then alphabetically.
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


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="wordfreq",
        description="Print the N most frequent words of a UTF-8 text file.",
    )
    parser.add_argument("path", metavar="PATH", help="UTF-8 text file to read")
    parser.add_argument("-n", dest="n", type=int, default=10,
                        help="number of words to print (default 10)")
    parser.add_argument("--min-length", dest="min_length", type=int, default=1,
                        help="ignore words shorter than this (default 1)")
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    if args.n < 1:
        print("wordfreq: error: -n must be at least 1", file=sys.stderr)
        sys.exit(2)
    try:
        with open(args.path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        print("wordfreq: error: %s" % exc, file=sys.stderr)
        sys.exit(2)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        except (ValueError, OSError):
            pass
    for word, count in top_words(text, args.n, args.min_length):
        sys.stdout.write("%s\t%d\n" % (word, count))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
```

## Tests

**The full text of `test_wordfreq.py` is not available to me, so I cannot print it here.** Step 3 wrote the file, but its read-back was truncated mid-file, and Step 3 quoted only the structure. The complete file exists in the workspace, and this memo does not reproduce it. What Step 3 and Step 4 reported about it:

- It uses only `unittest` plus the standard modules `os`, `subprocess`, `sys`, `tempfile` and `unicodedata`.
- It finds `wordfreq.py` relative to the test file (`HERE` / `WORDFREQ`), and it adds `HERE` to `sys.path` so `from wordfreq import top_words` works.
- It has 33 test methods, `test_E01` to `test_E33`, one per row of the Step 1 edge-case table. Step 5 counted them with grep and got 33.
- The tests are in two classes. `CliTests` runs the CLI through `subprocess.run([sys.executable, WORDFREQ, path, ...])` on a UTF-8 temp file and asserts on return code, stdout and stderr. `TopWordsTests` calls `top_words` directly.
- Topics covered:
  - case folding and non-ASCII letters (E01, E02, E26, E32)
  - word characters, including digits and underscore as a separator (E04, E05, E21–E23, E25)
  - apostrophe stripping (E06–E08, E27)
  - `--min-length` (E09–E11, E24, E31)
  - tie ordering (E12, E13, E16, E24)
  - count limits (E14–E16, E24, E30)
  - error and empty paths (E17–E20): `-n 0`, `-n -1`, missing file, empty file, punctuation-only file
  - the `top_words` API (E28, E29)
  - exact output format `a\t2\nb\t1\n` (E33)
- E03 (decomposed `café`) asserts only one output line with count 1 and an NFC form equal to `café`. The spec is ambiguous on merging NFC and NFD forms.
- The file ends with `if __name__ == "__main__": unittest.main()`.

## Test result

Command: `python3 -m unittest -v`, run in the workspace by Step 4. Exact summary:

```
Ran 33 tests in 1.081s

OK
```

- Number of tests: 33. Result: all passed. There were no failures, errors or skips in the summary line.
- The verifier re-ran the suite. Step 5 reported "Ran 33 tests in 1.148s / OK" and "Ran 33 tests in 1.113s / OK". Step 6 reported "Ran 33 tests in 1.121s / OK" and "Ran 33 tests in 1.169s / OK".
- In Step 4 the middle of the 33-line verbose listing was cut from the displayed output. The full output is in `tool_results/step4_1.txt`.

## Verification

**Verdict: PASS** (Step 6, Independent Verifier). The verifier reported no defects and no issues. Its summary says "The deliverable can ship."

Step 5 had also given Verdict: PASS. It ran 12 scenarios plus 2 extra checks, and all matched the hand-derived expectations.

The verifier also checked the code by reading it:
- Line 10 [S11]: the regex `(?:[^\W_]|')+`, so underscore is a separator.
- Line 26 [S11]: `token.strip("'").lower()`. Line 27 [S59]: `if not word or len(word) < min_length`. The length test runs after stripping.
- Line 30 [S11]: the sort is count descending, then alphabetical.
- Line 48 [S11, S52]: `if args.n < 1`, which runs before the `open` call at line 52 [S52].

Per-requirement result from Step 6 (the verifier numbered its own R1–R12, and the numbers differ from the task's R-ids):

| Requirement | Verdict |
|---|---|
| CLI args, default N of 10 | PASS |
| `word<TAB>count` output | PASS |
| Count descending, ties alphabetical | PASS |
| Word definition, underscore splits | PASS |
| Case-insensitive, lowercase output | PASS |
| Apostrophe strip, empty words dropped | PASS |
| `--min-length` applied after stripping | PASS |
| Non-ASCII letters | PASS |
| `top_words` exposed with the right signature | PASS |
| `top_words` follows the same rules | PASS |
| Missing file exits 2, error on stderr | PASS |
| N < 1 exits 2 before file access; empty file exits 0 with no output | PASS |

Acceptance runs reported by the verifier:
- A missing file gave rc=2 with `wordfreq: error: [Errno 2] No such file or directory: 'nope.txt'`.
- `-n 0` and `-n -3` gave rc=2.
- `nope.txt -n 0` gave rc=2 with the `-n` message, so N is checked before the file is opened.
- An empty file gave rc=0 and no output.
- Twelve distinct words with the default N gave 10 lines.
- `import wordfreq` has no side effects.
- Step 5's extra checks: a file with invalid UTF-8 gave a clean error and exit 2, and reading from `/dev/stdin` worked.

**Mutation check (Step 6).** The verifier ran its own mutations, and the test suite caught each one. The mutation table in the Step 6 output was partly cut, and only M1–M4 are visible to me:

| Mutation | Result | Caught |
|---|---|---|
| M1: sort key `(-kv[1], kv[0])` changed to `(kv[1], kv[0])` | Ran 33 tests / FAILED (failures=14) | yes |
| M2: removed `.strip("'")` | FAILED (failures=4) | yes |
| M3: regex `[^\W_]` changed to `\w`, so underscore is a word character | FAILED (failures=1) | yes |
| M4: `len(word)` changed to `len(token)`, so the length test runs before stripping | FAILED (failures=1) | yes |

## Assumptions

From Step 1. Part of that assumptions list was cut from the output I received, so the list below is incomplete.
- **Underscore:** `_` is not a letter, digit or apostrophe, so it separates words (`snake_case` gives `snake` and `case`).
- **Apostrophe:** Only the ASCII apostrophe is tested.
  - The curly right single quote is unspecified and not tested.
  - Leading and trailing apostrophe runs are stripped completely (`'''x'''` gives `x`).
  - Internal apostrophes are kept, including consecutive ones (`a''b`).
  - A token of only apostrophes becomes empty and is dropped.
- **Lowercase:** Plain `str.lower()`. Tests use only ASCII, é/É and Ω/ω. Special cases such as ß and the Turkish dotted İ are avoided.
- **Normalization:** The spec does not require NFC/NFD normalization. The test for decomposed `café` (E03) therefore asserts only one output line with count 1 and an NFC form equal to `café`.
- **Argument handling:** `-n -1` is passed as two arguments. If argparse rejects it, that still exits with status 2. `-n=-1` is not used.
- **Min-length:** The length is measured after apostrophe stripping.
- **Expected values:** Every count, `-n` value and `--min-length` value in the tests is hand-derived test data from the task text, not a sourced fact.
- **Code behaviour beyond the spec (reported by Step 4 and Step 6):** The code normalizes the text to NFC, so decomposed and precomposed `café` merge. An undecodable file exits 2 with a clean error.

## Files made
- tool_results/step2_2.txt (2,920 bytes, made in step 3; listed by plain code)
- tool_results/step2_3.txt (2,611 bytes, made in step 3; listed by plain code)
- tool_results/step2_4.txt (3,337 bytes, made in step 3; listed by plain code)
- tool_results/step2_5.txt (2,983 bytes, made in step 3; listed by plain code)
- tool_results/step2_6.txt (2,625 bytes, made in step 3; listed by plain code)
- tool_results/step2_7.txt (2,724 bytes, made in step 3; listed by plain code)

## Limitations

- **Step 2 (partial):** The exact test count and the verbatim middle of `main()` were cut from the output the developer saw. The `wordfreq.py` block above is a reconstruction, not a verified verbatim copy. The workspace file differs at least by `newline=None` at line 52 (69 lines vs the 70 Step 2 stated).
- **Step 3 (partial):** The full text of `test_wordfreq.py` was not delivered, so the Tests section has no code block. The file is only in the workspace. Its line count is 218 [S44] in Step 3 and 217 [S45] in Step 4, and I did not resolve the difference.
- **Step 4 (partial):** The middle of the verbose 33-line test listing was cut. The full output is in `tool_results/step4_1.txt`.
- **Step 5 and Step 6 (partial):** Both were flagged for mislabelled citations. Step 6 also carries a note of an unresolved dispute on run timings ("step 5 1.148 vs check 1.284"). The test count (33) and result (OK) are the same in every run. Step 6's own verdict text is PASS.
- **Step 1:** Parts of the edge-case table and assumptions were cut from the output I received. The Unicode code points in it are tagged [unverified].
- **Step 6 mutation table:** Only M1–M4 are visible to me. Some rows were cut.
- **Missing inputs:** the complete `test_wordfreq.py` source (Step 3) and the verbatim `wordfreq.py` (Step 2).
MISSING DATA: Full text of test_wordfreq.py — Step 3 read-back was truncated; only structure quoted
MISSING DATA: Verbatim workspace wordfreq.py — Step 2 code block is a reconstruction (workspace line 52 also has newline=None)
MISSING DATA: Full mutation table and full assumptions list — parts cut in Step 6 and Step 1 outputs
MISSING INPUT: Complete test_wordfreq.py source — Step 3
MISSING INPUT: Verbatim wordfreq.py — Step 2
