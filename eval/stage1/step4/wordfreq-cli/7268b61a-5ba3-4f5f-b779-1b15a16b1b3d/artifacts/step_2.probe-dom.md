**Caveat on the code block.** The Read of the on-disk file [S39] was cut in the middle (about 1,500 characters). I saw the head and the tail of the file, including all of main()'s output and exit logic. I rebuilt the middle (the end of top_words, the argparse setup and the file reading) from the brief and from the error messages the smoke runs printed [S40]. The behaviour below is the on-disk file's behaviour, as shown in [S40]. The block may differ from the file in whitespace or comments. I did not diff the two.

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

The module imports without side effects. All work sits under the `main()` guard, and the only module-level statements are imports and the compiled regex. It uses the stdlib only and is one file.

**Smoke summary.** These are the four runs I saw in [S40]. The sample file contained `The the THE café 'tis rock'n'roll '' foo_bar`.
1. Sample (piped through `cat -A`), exit 0. The output was `the^I3`, `bar^I1`, `cafM-CM-)^I1` (this is `café`), `foo^I1`, `rock'n'roll^I1` and `tis^I1`. `^I` is a TAB. The order is count descending, then alphabetical. `foo_bar` splits at the underscore, `''` is dropped, and `'tis` becomes `tis`.
2. Missing file: stderr showed `wordfreq: error: [Errno 2] No such file or directory: 'nope.txt'`, exit 2.
3. `-n 0`: stderr showed `wordfreq: error: -n must be at least 1`, exit 2. The check runs before the file is opened.
4. Empty file: no output, exit 0.

**What the work-around does not cover.**
- I have no test count and no E01–E33 coverage. An earlier `test_wordfreq.py` run was made [S36], but its result was cut off and I did not see it.
- The unseen middle of the file is reconstructed (see the caveat above).
- Nothing beyond the four smoke runs was checked here. That includes `--min-length`, NFD input and a non-UTF-8 file.
MISSING DATA: Exact test count and E01–E33 coverage — the tool output was cut off; left to the test step
MISSING DATA: Middle ~1,500 characters of wordfreq.py as read back [S39] — cut in the tool output; reconstructed from the spec and the smoke-run messages
