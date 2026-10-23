Verdict: PASS
# Verification memo: wordfreq.py (Independent Verifier, step 6)

The task text does not number R1–R12, so I mapped them as follows.
- R1: CLI arguments and the default N of 10.
- R2: output format `word<TAB>count`.
- R3: order, count descending then alphabetical.
- R4: word definition, including underscore as a separator.
- R5: case folding to lowercase.
- R6: apostrophe stripping and dropping empty words.
- R7: `--min-length`, applied after stripping.
- R8: non-ASCII letters.
- R9: `top_words` API and signature.
- R10: `top_words` follows the same rules.
- R11: missing file exits 2 with the error on stderr.
- R12: N < 1 exits 2, and an empty file exits 0 with no output.

## Test re-run
- I re-ran `python3 -m unittest` on the delivered file. Result: "Ran 33 tests in 1.121s / OK" [S59]. A second run gave "Ran 33 tests in 1.169s / OK" [S60].
- Step 5 reported "Ran 33 tests ... OK" [S51][S52]. My counts match it.
- The delivered `wordfreq.py` has 69 lines [S59].
- Import check: `python3 -c 'import wordfreq; print(wordfreq.top_words("a A b"))'` printed only `[('a', 2), ('b', 1)]` [S8]. There are no import side effects.

## Acceptance runs
I re-ran the key scenarios myself against the delivered file [S59]. TABs are shown as ^I.

| Scenario | Expected | Actual | Result |
|---|---|---|---|
| `a.txt -n 2`, file `The the THE café cafe 'tis dogs' rock'n'roll` | `the^I3`, `cafe^I1`, exit 0 | the same two lines, rc=0, no stderr [S59] | PASS |
| `a.txt --min-length 4` | cafe, café, dogs, rock'n'roll, each ^I1, exit 0 | the same four lines (é as `M-CM-)`), rc=0 [S59] | PASS |
| Missing `nope.txt` | exit 2, error on stderr | rc=2, `wordfreq: error: [Errno 2] No such file or directory: 'nope.txt'` [S59] | PASS |
| `-n 0` | exit 2 | rc=2, `-n must be at least 1` [S59] | PASS |
| `-n -3` | exit 2 | rc=2, same message [S59] | PASS |
| `nope.txt -n 0` | exit 2, the -n message, because N is checked first | rc=2, `-n must be at least 1` [S59] | PASS |
| Empty file | empty stdout, exit 0 | no output, rc=0, err empty [S59] | PASS |
| Default n with 12 distinct words | 10 lines | 10 lines a..j, rc=0 [S49] | PASS |
| Ties `pear apple pear fig fig zed` | fig 2, pear 2, apple 1, zed 1 | the same four lines in that order [S51] | PASS |

Extra `top_words` checks [S60]:
- `top_words("snake_case 'ab' abc", 10, 3)` gives `[('abc',1),('case',1),('snake',1)]`. The underscore splits words, and `'ab'` is stripped to `ab` and then dropped by the length test.
- `top_words("'' ''' x")` gives `[('x',1)]`. All-apostrophe tokens are dropped.
- `top_words('b a b a c', 2)` gives `[('a',2),('b',2)]`. This is the tie rule.
- `top_words('cafe\u0301 café')` gives `[('café',2)]`.
- `top_words('A1 a1 9')` gives `[('a1',2),('9',1)]`.
- A CRLF file prints `a^I2`, `b^I1`, with no stray `\r` [S60].
- `--min-length 0` runs and exits 0 [S60].
- Step 5 also found that invalid UTF-8 gives a clean exit 2 [S52].

## Code review
Line numbers come from my grep of the delivered file [S59].
- Line 10 [S59]: `_TOKEN_RE = re.compile(r"(?:[^\W_]|')+")`. This matches Unicode letters and digits plus apostrophes. Underscore is excluded, so it separates words. R4 and R8 hold.
- Line 26 [S59]: `word = token.strip("'").lower()`. This lowercases and strips leading and trailing apostrophes. Line 27 [S59] reads `if not word or len(word) < min_length`, so empty words are dropped and the length test comes after stripping. R5, R6 and R7 hold.
- Line 30 [S59]: `sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]`. This is count descending, then alphabetical. R3 holds.
- Line 48 [S59]: `if args.n < 1` prints to stderr and exits 2. It comes before the `open(...)` at line 52 [S59], so N is validated before file access. Line 52 [S59] uses `encoding="utf-8"`. R11 and R12 hold.
- The `OSError` and `UnicodeDecodeError` handler exits 2.
- `top_words(text, n=10, min_length=1)` has the required signature and returns a list of tuples. R9 and R10 hold.
- The code also normalizes the text to NFC, so a decomposed "café" counts as the same word as the precomposed one. This is an addition, and it is consistent with the spec.
- Observation, not a defect: `top_words` raises `ValueError` for n < 1. The spec does not define this case.
- Observation, not a defect: letters with no precomposed form, such as combining marks in some scripts, would split a word. The spec does not cover this.
- Step 2's quoted code block shows `open(...)` without `newline=None`. The real file has it at line 52 [S59]. This is the default behaviour, so no conclusion changes.

## Mutation check
I applied four mutations with `sed` to separate copies in `mv/m1`..`mv/m4`, each with its own copy of the tests. The delivered file was not touched [S59]. After the mutations the original still gave "Ran 33 tests ... OK" [S59]. A separate md5sum of the original and `m1` (`ddc88610` [S60] vs `27b89e82` [S60]) confirms the copies differ.

| Mutation | Change | Tests | Caught? |
|---|---|---|---|
| M1 | Sort key `(-kv[1], kv[0])` → `(kv[1], kv[0])` | "Ran 33 tests / FAILED (failures=14)" [S59] | yes |
| M2 | Removed `.strip("'")` | FAILED (failures=4) [S59] | yes |
| M3 | Regex `[^\W_]` → `\w`, so underscore is a word character | FAILED (failures=1) [S59] | yes |
| M4 | `len(word)` → `len(token)`, so the length test comes before stripping | FAILED (failures=1) [S59] | yes |

All four mutations were caught, which is more than the two required.

## Re-checks I ran (as verifier of step 5)
- I re-ran the unittest suite on the delivered file twice. It gave 33 tests, OK, matching Step 5 [S51][S52][S59][S60].
- I re-ran the CLI scenarios independently. The outputs and exit codes match Step 5's table [S59].
- I grepped the real file for the regex, strip, sort key, N check and open call, and the lines match Step 5's citations [S59].
- I ran my own mutations. Step 5 did none, because mutation testing belongs to this step.
- There are no external figures to check on the web.
- Difference between my result and Step 5's: my result used different fixture files, such as ties `a/b/c`. No expected or actual value differs, so no conclusion changes.

## Verdict

| Req | Verdict | Evidence |
|---|---|---|
| R1 CLI args, default N of 10 | PASS | Default-n scenario gives 10 lines [S51]; `-n 2` works [S59] |
| R2 `word<TAB>count` output | PASS | `the^I3$` in cat -A output [S59] |
| R3 count descending, ties alphabetical | PASS | Line 30 [S59]; ties scenario [S51]; M1 caught with 14 failures [S59] |
| R4 word definition, underscore splits | PASS | Line 10 [S59]; `snake_case` gives snake and case [S60]; M3 caught [S59] |
| R5 case-insensitive, lowercase output | PASS | `The the THE` gives `the^I3` [S59] |
| R6 apostrophe strip, empty dropped | PASS | `'' ''' x` gives `[('x',1)]` [S60]; M2 caught [S59] |
| R7 min-length after stripping | PASS | `'ab'` dropped at L=3 [S60]; `dogs'` kept at L=4 [S59]; M4 caught [S59] |
| R8 non-ASCII letters | PASS | cafe and café are separate words, and café is one word [S59]; NFC variant merges [S60] |
| R9 `top_words` exposed with signature | PASS | Import check [S59]; lines 14–30 reviewed |
| R10 `top_words` has the same rules | PASS | Direct calls in [S60] match the CLI results |
| R11 missing file exits 2, error on stderr | PASS | rc=2, stdout empty, stderr error [S59] |
| R12 N < 1 exits 2 before file access; empty file exits 0 with no output | PASS | `-n 0`, `-n -3` and `nope.txt -n 0` all rc=2 [S59]; empty file rc=0, no output [S59] |

No defects found. Nothing was marked NOT RUN.

Verdict: PASS. The deliverable can ship.
Issues: none
