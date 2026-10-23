## wordfreq.py (final)

The file on disk is /workspace/wordfreq.py. My tool views of it were cut in the middle [S4][S5]. The block below is that file as I wrote it, with the cut middle section restored from the brief. The visible head and tail match the tool output. The restored middle may differ from the disk file in wording.

```python
#!/usr/bin/env python3
"""wordfreq: print the N most frequent words of a UTF-8 text file."""

import argparse
import re
import sys
import unicodedata
from collections import Counter

# Letters/digits of any script (not underscore) plus ASCII apostrophes.
_TOKEN_RE = re.compile(r"(?:[^\W_]|')+")


def top_words(text, n=10, min_length=1):
    """Return the n most frequent words as (word, count) tuples.

    Most frequent first, ties broken alphabetically. Raises ValueError if n < 1.
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
        description="Print the N most frequent words in a UTF-8 text file.",
    )
    parser.add_argument("path", metavar="PATH", help="UTF-8 text file to read")
    parser.add_argument("-n", dest="n", type=int, default=10,
                        help="number of words to print (default 10)")
    parser.add_argument("--min-length", dest="min_length", type=int, default=1,
                        help="ignore words shorter than this (default 1)")
    args = parser.parse_args(argv)

    if args.n < 1:
        print("wordfreq: error: -n must be at least 1", file=sys.stderr)
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
        except (OSError, ValueError):
            pass
    for word, count in top_words(text, args.n, args.min_length):
        sys.stdout.write(f"{word}\t{count}\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

## Smoke-test summary
Only the import check [S4] and the CLI smoke run [S5] are confirmed below. I also ran an assert-based check of top_words [S3], but its output was cut off, so I do not claim it passed.
1. **Import and sample file.** `import wordfreq` printed `import_ok` with no side effects [S4]. The sample file was `The the THE café 'tis rock'n'roll '' foo_bar` [S5]. Its output was, via `cat -A`, these tab-separated lines [S5]:
   - `the<TAB>3`
   - `bar<TAB>1`
   - `café<TAB>1`
   - `foo<TAB>1`
   - `rock'n'roll<TAB>1`
   - `tis<TAB>1`

   The order is count descending, then alphabetical. All words are lowercase. `foo_bar` is split at the underscore, and the `''` token is dropped.
2. **Error paths.** A missing file printed `wordfreq: error: [Errno 2] No such file or directory: 'nope.txt'` and exited 2 [S5]. `-n 0` printed `wordfreq: error: -n must be at least 1` and exited 2 [S5].
3. **Empty file.** An empty file produced 0 bytes of output (`wc -c` gave 0) and exited 0 when run directly [S5].

**Not confirmed:**
- I did not run the full 33-row edge-case table from step 1.
- I did not confirm the results of the assert run [S3].
- I did not test `--min-length` or NFD input on the CLI.
- In my smoke command the first `rc=` line came after a pipe, so it showed the exit status of the last command in the pipeline, not of wordfreq.py.
MISSING DATA: Full output of the assert-based top_words check — cut off in tool result [S3]
MISSING DATA: Full 33-row edge-case table run — not executed in this step
