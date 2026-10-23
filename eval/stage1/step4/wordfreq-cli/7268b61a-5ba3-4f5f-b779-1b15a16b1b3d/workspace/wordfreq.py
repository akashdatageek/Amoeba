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


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="wordfreq",
        description="Print the N most frequent words in a UTF-8 text file.",
    )
    parser.add_argument("path", metavar="PATH", help="UTF-8 text file to read")
    parser.add_argument("-n", dest="n", type=int, default=10,
                        help="number of words to print (default 10)")
    parser.add_argument("--min-length", dest="min_length", type=int, default=1,
                        help="ignore words shorter than this (default 1)")
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)  # argparse errors exit with status 2
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
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
