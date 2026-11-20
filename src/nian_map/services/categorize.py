"""Keyword categorizer (accent-insensitive). Replace with an ML classifier later;
the signature stays the same."""
from __future__ import annotations

import unicodedata

RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Incidents", ("incident", "accident", "attaque", "attack", "explosion", "fusillade", "shooting", "crash", "emeute", "riot", "incendie")),
    ("Protests", ("manif", "election", "campagne", "campaign", "greve", "strike", "protest", "marche", "presidentielle", "rassemblement", "rally")),
    ("Concerts", ("concert", "festival", "show", "musique", "music", "live set")),
    ("Tech", ("tech", "startup", "developpeur", "developer", "ia ", " ai ", "hackathon", "meetup")),
]


def _fold(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def categorize(text: str) -> str:
    t = f" {_fold(text or '')} "
    for cat, words in RULES:
        if any(w in t for w in words):
            return cat
    return "Other"  # unknown stays unknown instead of defaulting to "Tech"
