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
