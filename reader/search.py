from __future__ import annotations

import re


def count_occurrences(full_text: str, search_term: str) -> int:
    """Count case-insensitive occurrences of search term in full article text."""
    pattern = re.compile(re.escape(search_term), flags=re.IGNORECASE)
    return len(pattern.findall(full_text))


def find_matching_paragraph_numbers(paragraphs: list[str], search_term: str) -> list[int]:
    """Return 1-based paragraph indices containing at least one match."""
    pattern = re.compile(re.escape(search_term), flags=re.IGNORECASE)
    matches: list[int] = []

    for index, paragraph in enumerate(paragraphs, start=1):
        if pattern.search(paragraph):
            matches.append(index)

    return matches
