# Final report: slugify

## Summary
I wrote `slug.py` with `slugify(text)`. It lowercases the text, turns each run of non-alphanumeric characters into one hyphen, and strips leading and trailing hyphens. I also wrote `test_slug.py`, which has 10 pytest cases. The test result is **10 passed, 0 failed** [S3]. The QA reviewer's independent rerun also gave 10 passed, 0 failed [S10].

## Files produced
Files the task asks for:
- `slug.py` (step 1): the module with `slugify(text)`. Full contents are below.
- `test_slug.py` (step 1): the pytest tests, one parametrised test with 10 cases. Full contents are below.

Other files the team made along the way. The task does not ask for them:
- `.pytest_cache/.gitignore`, `.pytest_cache/CACHEDIR.TAG`, `.pytest_cache/README.md` (step 1): pytest cache files created automatically by the run.
- `.pytest_cache/v/cache/nodeids` (steps 1 and 2): pytest's cache of test IDs, rewritten by the reviewer's rerun.
- `probe_qa.py` (step 2): the reviewer's probe script. It compares `slugify` with a hand-written character-loop reference on 10 inputs that are not in the tests.
- `tool_results/step2_6.txt` (step 2): the reviewer's saved tool output.

## slug.py
```python
"""Slug helper."""
import re


def slugify(text):
    """Lowercase text, collapse runs of non [a-z0-9] chars into one '-', strip edge hyphens.

    Alphanumeric means ASCII [a-z0-9] after lowercasing, so 'é' is a separator.
    """
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
```
[S4]

## test_slug.py
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
[S3]

The cases cover mixed case, runs of punctuation and spaces, leading and trailing separators, an empty string, an all-symbol string, digits, non-ASCII input and input that is already a slug. The developer worked out the expected values by hand from the spec.

## Test result
Command: `python3 -m pytest -v test_slug.py`

Verbatim pytest output from the developer's run [S3]:
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

Result: **10 passed, 0 failed** [S3].

The reviewer's rerun of the same command (authoritative) gave `10 passed in 0.02s`, with no failures or errors [S10].

## Verification
- **QA verdict: PASS.** The reviewer found no issues that would change a number or a conclusion.
- **Discrepancy check:** The two runs agree. Both give 10 passed, 0 failed. Only the run time differs, 0.01s for the developer [S3] and 0.02s for the reviewer [S10]. This does not affect the result.
- **File review [S9]:** The reviewer read both files. The function name and the import are correct, and every expected value in the tests is correct by hand check.
- **Probe run [S10]:** The reviewer checked 10 inputs that are not in the tests against a hand-written reference. All 10 matched. For example, 'Ünïcode' gives 'n-code', and 'a\nb\tc' gives 'a-b-c'.
- **Mutant check [S10]:** The tests caught all faulty variants the reviewer tried.
  - No strip failed 3 cases.
  - No collapse failed 3 cases.
  - No lowercase failed 5 cases.
  - The variant that keeps A-Z also failed 5 cases.
- **Minor gaps the reviewer noted, which do not change the verdict:**
  - There is no test for non-string input such as None, which raises AttributeError. The spec does not cover it.
  - There is no test for tabs or newlines. The reviewer's probe covers them and they pass.
  - Non-ASCII behaviour is tested only through 'Café Münch'.
  - The 'İ' probe is a quirk of Python's `lower()`. It gives 'i' plus a combining dot. The combining dot is treated as a separator and stripped. This is consistent with the ASCII-only spec.

## Assumptions
- "Alphanumeric" means ASCII `[a-z0-9]` after lowercasing. Accented and other non-ASCII letters count as separators, so 'Café Münch' becomes 'caf-m-nch'.
- Input is a `str`. Non-string input such as None is not handled and raises AttributeError.
- Empty input and input made only of symbols return `''`.
- The module uses the standard library only (`re`).
