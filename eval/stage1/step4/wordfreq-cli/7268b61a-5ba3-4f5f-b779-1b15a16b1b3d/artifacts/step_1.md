## Edge-case table (derived by hand from the task text only; no code seen)

### Note on numbers
Every count, `-n` value and `--min-length` value in the table is test data. Each expected count is hand-counted from the input shown in the same row. The numbers are not sourced facts, so they carry no [S#]. The only outside figures are the Unicode code points, which come from my own knowledge and are tagged [unverified].

### Requirement ids
The task text has no numbered requirements, so I define these ids and use them here and in the later steps.
- R1: The CLI reads a UTF-8 file and prints `word<TAB>count` lines, most frequent first.
- R2: `-n N` limits the output to N lines. The default is 10.
- R3: A word is a maximal run of letters, digits and apostrophes. Every other character separates words.
- R4: Words are compared case-insensitively and printed in lowercase.
- R5: Apostrophes at the start or end of a word are stripped. Internal apostrophes are kept. A word left empty is dropped.
- R6: `--min-length L` (default 1) ignores words shorter than L. The length is measured after stripping.
- R7: Non-ASCII letters count as letters ("café" is one word).
- R8: Sort by count descending, then alphabetically (tie rule).
- R9: `top_words(text, n=10, min_length=1) -> list[tuple[str,int]]` follows the same rules.
- R10: Error and empty paths:
  - A missing file prints a message to stderr and exits with status 2.
  - N < 1 exits with status 2.
  - An empty file prints nothing and exits with status 0.

### Assumptions
- **Underscore:** `_` is not a letter, digit or apostrophe, so it separates words. `snake_case` gives `snake` and `case`. A regex `\w` implementation would wrongly keep it.
- **Apostrophe:** Only the ASCII apostrophe (code point U+0027 [unverified]) is tested. The curly right single quote (U+2019 [unverified]) is unspecified and not tested.
  - Leading and trailing runs of apostrophes are stripped completely, so `'''x'''` gives `x`.
  - Internal apostrophes are kept, including consecutive ones (`a''b`).
  - A token made only of apostrophes becomes empty and is dropped.
- **Lowercase:** Plain `str.lower()` on the word. Tests only use ASCII, é/É and Ω/ω. Special cases such as ß and the Turkish dotted İ are avoided.
- **Normalization (NFC/NFD):** The spec does not require normalization.
  - Precomposed `café` (é is U+00E9 [unverified]) is one word, `café`.
  - NFD `café` is `cafe` followed by the combining acute accent (U+0301 [unverified]). It should be one word. The combining mark is not strictly a "letter", so a literal implementation could split it into `cafe`. This is a spec-ambiguous row (E03), and the task text expects one word.
  - E03 therefore asserts only that there is one output line with count 1 and that its NFC form equals `café`. It does not assert that NFC and NFD forms merge into one entry.
- **Tie rule (ordering):** Ties are broken by code-point order of the lowercase word, which is Python's default string sort. So `é` sorts after `z`, because its code point is higher.
- **Argument handling:** `-n -1` is passed as two arguments. If argparse rejects it, that still exits with status 2, so the expectation holds either way. `-n=-1` is not used.
- **Exit and errors:** Every case that exits with status 2 is checked for empty stdout. The missing-file case also needs a non-empty stderr.

### Table
`\t` is a TAB. "stdout" is the exact list of lines. Each CLI row writes the input to a temp file encoded as UTF-8. Rows with no args use the defaults.

| id | input (file contents / call) | args | expected stdout / exit code | req |
|---|---|---|---|---|
| E01 | `The the THE` | – | `the\t3`; exit 0 | R4 |
| E02 | `café Café CAFÉ` (precomposed é/É) | – | `café\t3`; exit 0 | R7, R4 |
| E03 | NFD `café`: `cafe` + combining acute accent, single token | – | exactly 1 line, count 1, and NFC(word) == `café`. Must not be split into `cafe`. Spec-ambiguous. Exit 0. | R7 |
| E04 | `abc123 42 abc123` | – | `abc123\t2`, `42\t1`; exit 0 | R3, R8 |
| E05 | `snake_case foo_bar` | – | `bar\t1`, `case\t1`, `foo\t1`, `snake\t1` (underscore separates; ties alphabetical); exit 0 | R3, R8 |
| E06 | `'tis dogs' 'tis` | – | `tis\t2`, `dogs\t1`; exit 0 | R5 |
| E07 | `don't rock'n'roll don't` | – | `don't\t2`, `rock'n'roll\t1`; exit 0 | R5 |
| E08 | `'' ' ''' a` (apostrophe-only tokens, then `a`) | – | `a\t1` only (the apostrophe-only tokens are dropped); exit 0 | R5 |
| E09 | `a bb ccc dddd a` | – (min-length 1) | `a\t2`, `bb\t1`, `ccc\t1`, `dddd\t1`; exit 0 | R6 |
| E10 | `a bb ccc dddd a` | `--min-length 3` | `ccc\t1`, `dddd\t1`; exit 0 | R6 |
| E11 | `'ab' abc` (`'ab'` is 4 chars raw but 2 after stripping) | `--min-length 3` | `abc\t1` only; exit 0 | R6, R5 |
| E12 | `zeta alpha beta alpha zeta mu` | – | `alpha\t2`, `zeta\t2`, `beta\t1`, `mu\t1`; exit 0 | R8 |
| E13 | `zebra élan apple` (code-point order puts é after z) | – | `apple\t1`, `zebra\t1`, `élan\t1`; exit 0 | R8, R7 |
| E14 | `a b c d e f g h i j k l` (12 distinct words, once each) | – (default n=10) | 10 lines `a\t1` … `j\t1` in that order; `k` and `l` absent; exit 0 | R2 |
| E15 | `x y x z` (3 distinct words) | `-n 50` | `x\t2`, `y\t1`, `z\t1` (3 lines, no padding); exit 0 | R2 |
| E16 | `a a a b b c` | `-n 2` | `a\t3`, `b\t2`; exit 0 | R2, R8 |
| E17 | `a a b` (valid file) | `-n 0` | exit 2; stdout empty | R10 |
| E18 | `a a b` (valid file) | `-n -1` | exit 2; stdout empty | R10 |
| E19 | path to a nonexistent file | – | exit 2; stdout empty; stderr non-empty | R10 |
| E20 | empty file (zero bytes) | – | stdout empty; exit 0 | R10 |
| E21 | `!!! ... ,,, --- ?? ()` (punctuation only) | – | stdout empty; exit 0 | R3, R10 |
| E22 | `hello, world! hello.` | – | `hello\t2`, `world\t1`; exit 0 | R3 |
| E23 | `a\nb\ta\r\nb  a` (newline, tab, CRLF and double-space separators) | – | `a\t3`, `b\t2`; exit 0 | R3 |
| E24 | `aa aa bb c c c dd` | `-n 2 --min-length 2` | `aa\t2`, `bb\t1` (`c` is excluded; `bb` beats `dd` alphabetically); exit 0 | R2, R6, R8 |
| E25 | `42 042 42` (digits-only words; a leading zero makes a different word) | – | `42\t2`, `042\t1`; exit 0 | R3 |
| E26 | `Ωmega ωMEGA` (non-ASCII, non-Latin letters) | – | `ωmega\t2`; exit 0 | R7, R4 |
| E27 | `a''b a''b` (consecutive internal apostrophes are kept) | – | `a''b\t2`; exit 0 | R5 |
| E28 | `top_words('')` | – | `== []` | R9, R10 |
| E29 | `top_words("a b a")` | – | `== [("a", 2), ("b", 1)]`; the result is a `list`, each item is a `tuple`, with `str` and `int` (not bool) members | R9 |
| E30 | `top_words("c b a b c c", n=2)` | – | `== [("c", 3), ("b", 2)]` | R9, R2 |
| E31 | `top_words("a bb ccc", min_length=2)` | – | `== [("bb", 1), ("ccc", 1)]` | R9, R6 |
| E32 | `top_words("The THE the don't 'tis")` (call with defaults) | – | `== [("the", 3), ("don't", 1), ("tis", 1)]` | R9, R4, R5 |
| E33 | CLI output format check on `a a b` | – | stdout is exactly `a\t2\nb\t1\n`, with a TAB (not spaces) and nothing on stderr; exit 0 | R1 |

### Coverage
- R1 is covered by E33, and by every CLI row through its exact stdout.
- R2 is covered by E14–E16, E24 and E30.
- R3 is covered by E04, E05, E21–E23 and E25.
- R4 is covered by E01, E02, E26 and E32.
- R5 is covered by E06–E08, E11, E27 and E32.
- R6 is covered by E09–E11, E24 and E31.
- R7 is covered by E02, E03, E13 and E26.
- R8 is covered by E04, E05, E12, E13, E16 and E24.
- R9 is covered by E28–E32.
- R10 is covered by E17–E21 and E28.

Each of R1–R10 has at least one row, and the table has 33 rows (E01–E33). The step was derived from the spec alone, so no external research was needed.
