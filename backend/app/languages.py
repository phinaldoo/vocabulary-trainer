from __future__ import annotations

from collections.abc import Iterable

SUPPORTED_UI_LANGUAGES = ("en", "zh-Hans", "hi", "es", "de")
DEFAULT_UI_LANGUAGE = "en"


def normalize_ui_language(value: str | None) -> str | None:
    """Map a BCP 47-style browser language to one supported UI language."""
    if not value:
        return None
    normalized = value.strip().replace("_", "-")
    if not normalized:
        return None
    primary = normalized.split("-", 1)[0].casefold()
    if primary == "zh":
        return "zh-Hans"
    if primary in {"en", "hi", "es", "de"}:
        return primary
    return None


def negotiate_ui_language(values: Iterable[str]) -> str:
    for value in values:
        if language := normalize_ui_language(value):
            return language
    return DEFAULT_UI_LANGUAGE


def parse_accept_language(value: str | None) -> list[str]:
    if not value:
        return []
    weighted: list[tuple[float, int, str]] = []
    for order, item in enumerate(value.split(",")):
        parts = [part.strip() for part in item.split(";")]
        language = parts[0]
        if not language or language == "*":
            continue
        quality = 1.0
        for parameter in parts[1:]:
            if parameter.casefold().startswith("q="):
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0
        if quality > 0:
            weighted.append((quality, -order, language))
    weighted.sort(reverse=True)
    return [language for _, _, language in weighted]


def request_ui_language(requested: str | None, accept_language: str | None) -> str:
    candidates = [requested] if requested else []
    candidates.extend(parse_accept_language(accept_language))
    return negotiate_ui_language(candidates)


def ai_response_language(user_language: str | None) -> str:
    """Canonical language for authenticated AI-facing copy and instructions."""
    return normalize_ui_language(user_language) or DEFAULT_UI_LANGUAGE
