"""Slug helper."""
import re


def slugify(text):
    """Lowercase text, collapse runs of non [a-z0-9] chars into one '-', strip edge hyphens.

    Alphanumeric means ASCII [a-z0-9] after lowercasing, so 'é' is a separator.
    """
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
