"""Identify existing verb collections without changing their IDs or progress."""
from typing import Literal

DeckKind = Literal["vocabulary", "special_verbs"]
PRINCIPAL_PARTS_MATCHER = "latin-principal-parts-v1"


def deck_kind(front_matcher: str) -> DeckKind:
    return "special_verbs" if front_matcher == PRINCIPAL_PARTS_MATCHER else "vocabulary"
