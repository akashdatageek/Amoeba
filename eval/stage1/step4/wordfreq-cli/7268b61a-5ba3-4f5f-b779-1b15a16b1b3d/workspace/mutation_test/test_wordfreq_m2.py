"""Tests for wordfreq.py, derived by hand from the spec (edge-case table E01-E33).

Requirement ids: R1 output format, R2 -n, R3 word definition, R4 case folding,
R5 apostrophes, R6 --min-length, R7 non-ASCII letters, R8 tie order,
R9 top_words API, R10 error / empty paths.

Only unittest is used. wordfreq.py is located relative to this file, not the cwd.
"""
import os
import subprocess
import sys
import tempfile
import unicodedata
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
WORDFREQ = os.path.join(HERE, "wordfreq.py")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from wordfreq import top_words  # noqa: E402


def run_cli(content, *args):
    """Write `content` (str or bytes) to a temp file as UTF-8, run the CLI.

    The child runs with cwd set to the temp dir so the test never relies on the
    current directory. Returns the CompletedProcess (text mode, UTF-8).
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "input.txt")
        with open(path, "wb") as fh:
            fh.write(content)
        return run_raw(path, *args, cwd=d)


def run_raw(path, *args, cwd=None):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, WORDFREQ, path, *args],
        capture_output=True, encoding="utf-8", env=env, cwd=cwd, timeout=60,
    )


class CliTests(unittest.TestCase):
    def check(self, content, args, expected_lines):
        r = run_cli(content, *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        expected = "".join(line + "\n" for line in expected_lines)
        self.assertEqual(r.stdout, expected)
        self.assertEqual(r.stderr, "")

    # --- R4 case folding -------------------------------------------------
    def test_E01_case_folding(self):
        self.check("The the THE", [], ["the\t3"])

    # --- R7 non-ASCII ----------------------------------------------------
    def test_E02_cafe_precomposed_one_word(self):
        self.check("caf\u00e9 Caf\u00e9 CAF\u00c9", [], ["caf\u00e9\t3"])

    def test_E03_cafe_nfd_single_word(self):
        # Spec-ambiguous: only assert one line, count 1, NFC form == café.
        r = run_cli("cafe\u0301")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), 1, r.stdout)
        word, count = lines[0].split("\t")
        self.assertEqual(count, "1")
        self.assertEqual(unicodedata.normalize("NFC", word), "caf\u00e9")

    # --- R3 word definition ---------------------------------------------
    def test_E04_digits_inside_and_alone(self):
        # abc123 x2, 42 x1, x x1; "42" sorts before "x"
        self.check("abc123 abc123 42 x", [], ["abc123\t2", "42\t1", "x\t1"])

    def test_E05_underscore_is_separator(self):
        self.check("snake_case snake_case", [], ["case\t2", "snake\t2"])

    # --- R5 apostrophes --------------------------------------------------
    def test_E06_leading_trailing_apostrophes_stripped(self):
        self.check("'tis dogs' 'tis", [], ["tis\t2", "dogs\t1"])

    def test_E07_internal_apostrophes_kept(self):
        self.check("don't rock'n'roll don't", [],
                   ["don't\t2", "rock'n'roll\t1"])

    def test_E08_apostrophe_only_tokens_dropped(self):
        self.check("'' ' a '''", [], ["a\t1"])

    # --- R6 min-length ---------------------------------------------------
    def test_E09_min_length_default_keeps_all(self):
        self.check("a bb ccc dddd a", [],
                   ["a\t2", "bb\t1", "ccc\t1", "dddd\t1"])

    def test_E10_min_length_3(self):
        self.check("a bb ccc dddd a", ["--min-length", "3"],
                   ["ccc\t1", "dddd\t1"])

    def test_E11_min_length_measured_after_stripping(self):
        self.check("'ab' abc", ["--min-length", "3"], ["abc\t1"])

    # --- R8 tie order ----------------------------------------------------
    def test_E12_tie_alphabetical(self):
        self.check("pear apple pear apple fig", [],
                   ["apple\t2", "pear\t2", "fig\t1"])

    def test_E13_tie_alphabetical_non_ascii(self):
        # cafd < cafe < café (é sorts after e both by code point and locale);
        # alpha < ωmega likewise.
        self.check("caf\u00e9 cafe cafd", [],
                   ["cafd\t1", "cafe\t1", "caf\u00e9\t1"])
        self.check("\u03c9mega alpha", [],
                   ["alpha\t1", "\u03c9mega\t1"])

    # --- R2 -n -----------------------------------------------------------
    def test_E14_default_n_is_10(self):
        words = "a b c d e f g h i j k l"
        self.check(words, [], ["%s\t1" % c for c in "abcdefghij"])

    def test_E15_n_larger_than_distinct(self):
        self.check("b a b", ["-n", "100"], ["b\t2", "a\t1"])

    def test_E16_n_limits_with_tie_order(self):
        # z3, y2, then w1 and x1 tie -> w first; n=3 stops after w
        self.check("x y y z z z w", ["-n", "3"], ["z\t3", "y\t2", "w\t1"])

    # --- R10 error / empty paths ----------------------------------------
    def test_E17_n_zero_exits_2(self):
        r = run_cli("a b", "-n", "0")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")

    def test_E18_n_negative_exits_2(self):
        r = run_cli("a b", "-n", "-1")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")

    def test_E19_missing_file_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, "does_not_exist.txt")
            r = run_raw(missing, cwd=d)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertNotEqual(r.stderr.strip(), "")

    def test_E20_empty_file_exit_0_no_output(self):
        r = run_cli("")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "")

    def test_E21_only_punctuation_no_output(self):
        r = run_cli("!!! ... ,;:-- ?\n(){}[]\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "")

    # --- R3 separators ---------------------------------------------------
    def test_E22_mixed_separators(self):
        self.check("hello,world;hello-world\thello\nworld", [],
                   ["hello\t3", "world\t3"])

    def test_E23_surrounding_punctuation_and_crlf(self):
        self.check("(hi) \"hi\" hi.", [], ["hi\t3"])
        self.check(b"one\r\ntwo\r\none", [], ["one\t2", "two\t1"])

    # --- combined --------------------------------------------------------
    def test_E24_n_and_min_length_combined(self):
        self.check("aa aa bb c c c dd", ["-n", "2", "--min-length", "2"],
                   ["aa\t2", "bb\t1"])

    def test_E25_digits_only_words_leading_zero_differs(self):
        self.check("42 042 42", [], ["42\t2", "042\t1"])

    def test_E26_non_latin_case_folding(self):
        self.check("\u03a9mega \u03c9MEGA", [], ["\u03c9mega\t2"])

    def test_E27_consecutive_internal_apostrophes_kept(self):
        self.check("a''b a''b", [], ["a''b\t2"])

    # --- R1 format -------------------------------------------------------
    def test_E33_output_format_tab_separated(self):
        r = run_cli("a a b")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "a\t2\nb\t1\n")
        self.assertEqual(r.stderr, "")


class TopWordsTests(unittest.TestCase):
    def test_E28_empty_text(self):
        self.assertEqual(top_words(""), [])

    def test_E29_returns_list_of_str_int_tuples(self):
        result = top_words("a b a")
        self.assertEqual(result, [("a", 2), ("b", 1)])
        self.assertIsInstance(result, list)
        for item in result:
            self.assertIs(type(item), tuple)
            self.assertEqual(len(item), 2)
            self.assertIs(type(item[0]), str)
            self.assertIs(type(item[1]), int)

    def test_E30_n_limit(self):
        self.assertEqual(top_words("c b a b c c", n=2), [("c", 3), ("b", 2)])

    def test_E31_min_length(self):
        self.assertEqual(top_words("a bb ccc", min_length=2),
                         [("bb", 1), ("ccc", 1)])

    def test_E32_defaults_case_and_apostrophes(self):
        self.assertEqual(top_words("The THE the don't 'tis"),
                         [("the", 3), ("don't", 1), ("tis", 1)])


if __name__ == "__main__":
    unittest.main()
