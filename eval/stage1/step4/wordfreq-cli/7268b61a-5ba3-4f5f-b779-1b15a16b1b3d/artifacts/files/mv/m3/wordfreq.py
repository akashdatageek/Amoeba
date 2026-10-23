#!/usr/bin/env python3
"""wordfreq: print the most frequent words of a UTF-8 text file."""

import argparse
import re
import sys
import unicodedata
from collections import Counter

_TOKEN_RE = re.compile(r"(?:\w|')+")


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
    parser.add_argument("path", metavar="PATH", help="UTF-8 text file")
    parser.add_argument("-n", dest="n", type=int, default=10,
                        help="number of words to print (default 10)")
    parser.add_argument("--min-length", dest="min_length", type=int, default=1,
                        help="ignore words shorter than L characters (default 1)")
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)  # argparse errors exit with 2
    if args.n < 1:
        print("wordfreq: error: -n must be at least 1", file=sys.stderr)
        sys.exit(2)
    try:
        with open(args.path, encoding="utf-8", newline=None) as fh:
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
