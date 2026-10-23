## wordfreq.py (reconstructed; see the caveat below)

Caveat: the file on disk passed 33 tests, "Ran 33 tests ... OK" [S67]. Tool output cut parts of the file text, so I could not print it verbatim. The file below follows the visible head and tail of [S67] and [S68] and the brief. The middle is rewritten from the brief. The code below was NOT re-run in this turn. The on-disk workspace/wordfreq.py is the authoritative copy.

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
        except (OSError, ValueError):
            pass
    for word, count in top_words(text, args.n, args.min_length):
        sys.stdout.write(f"{word}\t{count}\n")
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
```

## test_wordfreq.py (compact rewrite; NOT RUN)

The on-disk test_wordfreq.py has 217 lines [S68]. It ran 33 tests with "OK" [S67]. I did not see its full text. Its tests follow rows E01–E33 of step 1. The source below is a shorter rewrite of the same table rows. It was not executed.

```python
import os
import subprocess
import sys
import tempfile
import unittest

import wordfreq

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "wordfreq.py")


def run_cli(content, *args, path=None):
    """Run the CLI on a temp file holding `content` (str); return the CompletedProcess."""
    with tempfile.TemporaryDirectory() as d:
        p = path if path is not None else os.path.join(d, "in.txt")
        if path is None:
            with open(p, "wb") as fh:
                fh.write(content.encode("utf-8"))
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, SCRIPT, p, *args],
                              capture_output=True, env=env)


def out(proc):
    return proc.stdout.decode("utf-8")


class TopWordsTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(wordfreq.top_words(""), [])

    def test_basic_types(self):
        r = wordfreq.top_words("a b a")
        self.assertEqual(r, [("a", 2), ("b", 1)])
        self.assertIsInstance(r, list)
        self.assertIsInstance(r[0], tuple)
        self.assertIs(type(r[0][1]), int)

    def test_n(self):
        self.assertEqual(wordfreq.top_words("c b a b c c", n=2),
                         [("c", 3), ("b", 2)])

    def test_n_invalid(self):
        with self.assertRaises(ValueError):
            wordfreq.top_words("a", n=0)

    def test_min_length(self):
        self.assertEqual(wordfreq.top_words("a bb ccc", min_length=2),
                         [("bb", 1), ("ccc", 1)])

    def test_min_length_after_strip(self):
        self.assertEqual(wordfreq.top_words("'ab' abc", min_length=3),
                         [("abc", 1)])

    def test_case_and_apostrophes(self):
        self.assertEqual(wordfreq.top_words("The THE the don't 'tis"),
                         [("the", 3), ("don't", 1), ("tis", 1)])

    def test_only_apostrophes_dropped(self):
        self.assertEqual(wordfreq.top_words("'' ''' x"), [("x", 1)])

    def test_many_apostrophes_stripped(self):
        self.assertEqual(wordfreq.top_words("'''x'''"), [("x", 1)])

    def test_internal_apostrophes(self):
        self.assertEqual(wordfreq.top_words("a''b a''b rock'n'roll"),
                         [("a''b", 2), ("rock'n'roll", 1)])

    def test_underscore_separates(self):
        self.assertEqual(wordfreq.top_words("snake_case"),
                         [("case", 1), ("snake", 1)])

    def test_digits(self):
        self.assertEqual(wordfreq.top_words("42 042 42"),
                         [("42", 2), ("042", 1)])

    def test_non_ascii(self):
        self.assertEqual(wordfreq.top_words("Café CAFÉ café"), [("café", 3)])
        self.assertEqual(wordfreq.top_words("Ωmega ωMEGA"), [("ωmega", 2)])

    def test_nfd_single_word(self):
        r = wordfreq.top_words("cafe\u0301")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0][1], 1)

    def test_tie_alphabetical(self):
        self.assertEqual(wordfreq.top_words("b a c"),
                         [("a", 1), ("b", 1), ("c", 1)])

    def test_default_n_is_10(self):
        text = " ".join("abcdefghijkl")
        r = wordfreq.top_words(text)
        self.assertEqual([w for w, _ in r], list("abcdefghij"))

    def test_combined(self):
        self.assertEqual(
            wordfreq.top_words("aa aa bb c c c dd", n=2, min_length=2),
            [("aa", 2), ("bb", 1)])


class CliTests(unittest.TestCase):
    def test_format(self):
        p = run_cli("a a b")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(out(p), "a\t2\nb\t1\n")
        self.assertEqual(p.stderr, b"")

    def test_sample(self):
        p = run_cli("The the THE café 'tis rock'n'roll '' foo_bar")
        self.assertEqual(p.returncode, 0)
        lines = out(p).splitlines()
        self.assertEqual(lines[0], "the\t3")
        self.assertIn("café\t1", lines)
        self.assertIn("rock'n'roll\t1", lines)
        self.assertIn("foo\t1", lines)
        self.assertIn("bar\t1", lines)
        self.assertIn("tis\t1", lines)

    def test_n(self):
        p = run_cli("a a b c", "-n", "1")
        self.assertEqual(out(p), "a\t2\n")

    def test_min_length(self):
        p = run_cli("a bb ccc dddd a", "--min-length", "3")
        self.assertEqual(out(p), "ccc\t1\ndddd\t1\n")

    def test_n_zero_exit_2(self):
        p = run_cli("a b", "-n", "0")
        self.assertEqual(p.returncode, 2)
        self.assertEqual(p.stdout, b"")
        self.assertNotEqual(p.stderr, b"")

    def test_n_negative_exit_2(self):
        self.assertEqual(run_cli("a b", "-n", "-1").returncode, 2)

    def test_missing_file_exit_2(self):
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

## Smoke-test summary
- The earlier run of the on-disk test_wordfreq.py gave "Ran 33 tests ... OK" [S67]. The 33 tests match rows E01–E33 of step 1.
- The Bash smoke runs on the sample, missing file, `-n 0` and empty file passed, per the earlier turns. The exact `$?` lines were cut from the tool output I can still see, so I cannot quote them. The unit tests cover the same exit codes (2, 2, 0).
- NOT RUN in this turn: the reconstructed wordfreq.py above and the compact test rewrite.
MISSING DATA: Verbatim text of the on-disk test_wordfreq.py (217 lines [S68]) — tool output was truncated, so a compact rewrite is given instead
MISSING DATA: Verbatim middle section of the on-disk wordfreq.py — cut from tool output [S67]/[S68], reconstructed from the brief
MISSING DATA: Exact $? lines of the Bash smoke run — not visible in the remaining tool output
