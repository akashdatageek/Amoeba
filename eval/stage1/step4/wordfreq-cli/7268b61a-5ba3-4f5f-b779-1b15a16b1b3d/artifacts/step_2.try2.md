## wordfreq.py (workspace file, 70 lines [S11])

The code block below is my reconstruction of the file. Tool output [S11] and [S12] showed the file's header, `top_words`, the stdout and exit tail, and the error messages. The middle of `main()` was cut from what I could see. I rewrote that part to match the brief and the messages seen in the smoke run. The workspace `wordfreq.py` is the file that was tested. Diff the block against it before relying on it.

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

The code uses `argparse`, `sys.exit`, UTF-8 reading, `strip("'")`, `lower()`, `Counter` and `min_length`, as the brief asks. It uses only the stdlib, and the main guard keeps it importable without side effects.

## Smoke-test summary (from run [S12])
1. **Sample file.** Input: `The the THE café 'tis rock'n'roll '' foo_bar`. Output with `cat -A` was `the^I3`, `bar^I1`, `cafM-CM-)^I1`, `foo^I1`, `rock'n'roll^I1`, `tis^I1`. All words are lowercase, each line is `word<TAB>count`, ties are alphabetical, `''` is dropped, and `foo_bar` is split at the underscore. The `rc=0` in that run came from the pipe, but the second, unpiped run also gave `rc=0`.
2. **Error paths.** A missing file printed `wordfreq: error: [Errno 2] No such file or directory: 'nope.txt'` and exited with `rc=2`. `-n 0` printed `wordfreq: error: -n must be at least 1` and exited with `rc=2`.
3. **Empty file and import.** An empty file wrote 0 bytes to stdout and exited with `rc=0`. `import wordfreq` printed `import ok`, so there are no import side effects.

I also wrote `test_wordfreq.py` (2884 characters [S8]) in the workspace. It is a unittest suite covering the Step 1 edge cases. Its run ended in `OK` [S12]. The test count was cut from the output I saw, so I don't state it. I did not confirm that every one of the 33 rows (E01–E33) is in that suite. The independent tests are still to come.
MISSING DATA: Exact number of tests in test_wordfreq.py and whether all of E01–E33 are covered — the count was cut from the displayed output of the tool result [S12]
MISSING DATA: Verbatim middle of main() in the workspace file — cut from the displayed output of [S11]/[S12]; the code block reconstructs it
