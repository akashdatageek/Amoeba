"""Stage 1 hidden tests for wordfreq-cli (frozen judge; never shown to the team). They find the delivered wordfreq.py
anywhere in the copied workspace, import it by path, and run it as a command."""
import importlib.util, subprocess, sys
from pathlib import Path
import pytest

WORK = Path(__file__).resolve().parents[1]


def _find():
    hits = sorted((p for p in WORK.rglob("wordfreq.py") if "_hidden_tests" not in p.parts),
                  key=lambda p: (len(p.parts), str(p)))
    if not hits:
        pytest.fail("no wordfreq.py delivered")
    return hits[0]


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("wordfreq_delivered", _find())
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run(tmp_path, text, *args):
    f = tmp_path / "in.txt"
    if text is not None:
        f.write_text(text, encoding="utf-8")
    return subprocess.run([sys.executable, str(_find()), str(f), *args], capture_output=True, text=True,
                          encoding="utf-8", timeout=30)


def test_counts(mod):
    assert mod.top_words("b a b c b a") == [("b", 3), ("a", 2), ("c", 1)]


def test_case_insensitive(mod):
    assert mod.top_words("The the THE cat") == [("the", 3), ("cat", 1)]


def test_ties_alphabetical(mod):
    assert mod.top_words("pear apple fig") == [("apple", 1), ("fig", 1), ("pear", 1)]


def test_n(mod):
    assert mod.top_words("a a a b b c", n=2) == [("a", 3), ("b", 2)]


def test_min_length(mod):
    assert mod.top_words("an ox and a cow ran", min_length=3) == [("and", 1), ("cow", 1), ("ran", 1)]


def test_apostrophes(mod):
    assert mod.top_words("don't 'quoted' don't ''") == [("don't", 2), ("quoted", 1)]


def test_unicode_and_digits(mod):
    assert mod.top_words("Café café 2024, naïve-2024!") == [("2024", 2), ("café", 2), ("naïve", 1)]


def test_punctuation_splits(mod):
    assert mod.top_words("x,y;x.y-x") == [("x", 3), ("y", 2)]


def test_cli_format(tmp_path):
    r = run(tmp_path, "b a b\nc b a\n", "-n", "2")
    assert r.returncode == 0
    assert r.stdout.splitlines() == ["b\t3", "a\t2"]


def test_cli_min_length(tmp_path):
    r = run(tmp_path, "aa b aa ccc", "--min-length", "2")
    assert r.returncode == 0 and r.stdout.splitlines() == ["aa\t2", "ccc\t1"]


def test_cli_missing_file(tmp_path):
    r = run(tmp_path, None)
    assert r.returncode == 2 and r.stderr.strip() and not r.stdout.strip()


def test_cli_bad_n_and_empty(tmp_path):
    assert run(tmp_path, "a b", "-n", "0").returncode == 2
    r = run(tmp_path, "")
    assert r.returncode == 0 and r.stdout == ""
