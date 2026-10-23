Both files were written to the workspace and pytest was run for real. All 10 tests passed on the first run, so no fixes were needed.

**slug.py** (standard library only) [S4]
```python
"""Slug helper."""
import re


def slugify(text):
    """Lowercase text, collapse runs of non [a-z0-9] chars into one '-', strip edge hyphens.

    Alphanumeric means ASCII [a-z0-9] after lowercasing, so 'é' is a separator.
    """
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
```

**test_slug.py** [S3]
```python
import pytest

from slug import slugify


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Hello World", "hello-world"),
        ("  Hello,   World!!  ", "hello-world"),
        ("a---b___c", "a-b-c"),
        ("---abc---", "abc"),
        ("", ""),
        ("!!!", ""),
        ("Python 3.12 Release", "python-3-12-release"),
        ("Café Münch", "caf-m-nch"),
        ("ALLCAPS", "allcaps"),
        ("already-a-slug", "already-a-slug"),
    ],
)
def test_slugify(text, expected):
    assert slugify(text) == expected
```
I worked out the expected values by hand from the spec. For example, 'Café Münch' becomes 'caf-m-nch' because 'é' and 'ü' are separators.

The tests cover these cases:
- mixed case
- runs of punctuation and spaces
- leading and trailing separators
- an empty string
- an all-symbol string
- digits
- non-ASCII input
- input that is already a slug

**Command run:** `python3 -m pytest -v test_slug.py`

**Verbatim pytest output** [S3]
```
============================= test session starts ==============================
platform linux -- Python 3.11.17, pytest-9.1.1, pluggy-1.7.0 -- /usr/local/bin/python3
cachedir: .pytest_cache
rootdir: /out/probes/runs/p-software/479eb6fa-7382-4621-acf4-e32b62a67086/workspace
plugins: anyio-4.15.1
collecting ... collected 10 items

test_slug.py::test_slugify[Hello World-hello-world] PASSED               [ 10%]
test_slug.py::test_slugify[  Hello,   World!!  -hello-world] PASSED      [ 20%]
test_slug.py::test_slugify[a---b___c-a-b-c] PASSED                       [ 30%]
test_slug.py::test_slugify[---abc----abc] PASSED                         [ 40%]
test_slug.py::test_slugify[-] PASSED                                     [ 50%]
test_slug.py::test_slugify[!!!-] PASSED                                  [ 60%]
test_slug.py::test_slugify[Python 3.12 Release-python-3-12-release] PASSED [ 70%]
test_slug.py::test_slugify[Caf\xe9 M\xfcnch-caf-m-nch] PASSED            [ 80%]
test_slug.py::test_slugify[ALLCAPS-allcaps] PASSED                       [ 90%]
test_slug.py::test_slugify[already-a-slug-already-a-slug] PASSED         [100%]

============================== 10 passed in 0.01s ==============================
```

**Result: 10 passed, 0 failed**
