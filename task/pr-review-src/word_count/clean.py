import re
from typing import Dict, List


def _words(text: str) -> List[str]:
    return re.findall(r"[A-Za-z']+", text)


def _key(word: str) -> str:
    return word.lower()


def count_words(text: str) -> Dict[str, int]:
    """Count how often each word appears in text, ignoring case.

    Keys are lowercase words. Punctuation and digits separate words.
    """
    counts: Dict[str, int] = {}
    for word in _words(text):
        key = _key(word)
        counts[key] = counts.get(key, 0) + 1
    return counts
