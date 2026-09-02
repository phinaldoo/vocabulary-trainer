from __future__ import annotations

import itertools
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

GERMAN_ARTICLES = {
    "der",
    "die",
    "das",
    "den",
    "dem",
    "des",
    "ein",
    "eine",
    "einen",
    "einem",
    "einer",
    "eines",
}
GERMAN_CONTRACTIONS = {
    "am": ("an", "dem"),
    "ans": ("an", "das"),
    "beim": ("bei", "dem"),
    "im": ("in", "dem"),
    "ins": ("in", "das"),
    "vom": ("von", "dem"),
    "zum": ("zu", "dem"),
    "zur": ("zu", "der"),
}
OPTIONAL_LABELS = {
    "adj",
    "adv",
    "abl",
    "akk",
    "dat",
    "gen",
    "m",
    "n",
    "perf",
    "pl",
    "sg",
    "subst",
}
SENTENCE_ABBREVIATIONS = {
    "abl",
    "adj",
    "akk",
    "ca",
    "chr",
    "dat",
    "etw",
    "gen",
    "griech",
    "jdm",
    "jdn",
    "m",
    "perf",
    "pl",
    "rom",
    "sg",
    "v",
}
LATIN_REQUIRED_GROUP_STARTERS = {
    "an",
    "antequam",
    "cum",
    "donec",
    "dum",
    "ne",
    "postquam",
    "priusquam",
    "quam",
    "quamquam",
    "quamvis",
    "qui",
    "quin",
    "quod",
    "quia",
    "si",
    "ubi",
    "ut",
}
PRONOUN_ALTERNATIVES = {"er", "sie", "es"}
CLAUSE_STARTERS = {
    "aber",
    "als",
    "bevor",
    "damit",
    "dass",
    "denn",
    "nachdem",
    "ob",
    "obwohl",
    "oder",
    "sondern",
    "und",
    "während",
    "weil",
    "wenn",
}
GERMAN_CONNECTIVE_HEAD_WORDS = CLAUSE_STARTERS | {
    "auch",
    "hoffentlich",
    "nämlich",
    "sodass",
    "unter",
    "zwischen",
    "zu",
}
WORD_RE = re.compile(r"[^\W_]+|\d+", re.UNICODE)
KEYBOARD_EQUIVALENTS = {
    "ä": ("ä", "ae", "a"),
    "ö": ("ö", "oe", "o"),
    "ü": ("ü", "ue", "u"),
    "ß": ("ß", "ss"),
    "æ": ("æ", "ae"),
    "œ": ("œ", "oe"),
}
MAX_VARIANTS = 8_192


@dataclass(frozen=True)
class MatchResult:
    correct: bool
    normalized_input: str
    matched_variant: str | None = None
    article_insensitive: bool = False
    order_insensitive: bool = False
    parentheses_optional: bool = False


@dataclass(frozen=True)
class Candidate:
    display: str
    signature: tuple[str, ...]


def normalize_text(value: str) -> str:
    """Normalize visible text while retaining meaningful German umlauts."""

    value = unicodedata.normalize("NFKC", value).casefold()
    value = value.replace("ß", "ss")
    return " ".join(WORD_RE.findall(value))


def _split_top_level(value: str, delimiters: set[str]) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for character in value:
        if character in "([":
            depth += 1
        elif character in ")]":
            depth -= 1
            if depth < 0:
                raise ValueError("Unbalanced closing parenthesis in vocabulary entry")
        if character in delimiters and depth == 0:
            candidate = "".join(current).strip(" \t,;.!?")
            if candidate:
                parts.append(candidate)
            current = []
        else:
            current.append(character)
    if depth:
        raise ValueError("Unbalanced opening parenthesis in vocabulary entry")
    candidate = "".join(current).strip(" \t,;.!?")
    if candidate:
        parts.append(candidate)
    return parts


def _split_sentences(value: str) -> list[str]:
    """Split top-level utterances without mistaking catalogue labels for stops."""

    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for index, character in enumerate(value):
        if character in "([":
            depth += 1
        elif character in ")]":
            depth -= 1
            if depth < 0:
                raise ValueError("Unbalanced closing parenthesis in vocabulary entry")

        boundary = character in "!?" and depth == 0
        if character == "." and depth == 0:
            following = value[index + 1 :]
            next_character = next((item for item in following if not item.isspace()), "")
            preceding = re.search(r"([^\W_]+)\s*$", "".join(current), re.UNICODE)
            abbreviation = normalize_text(preceding.group(1)) if preceding else ""
            boundary = not next_character or (
                bool(following and following[0].isspace())
                and next_character.isupper()
                and abbreviation not in SENTENCE_ABBREVIATIONS
            )

        if boundary:
            candidate = "".join(current).strip(" \t,;.!?")
            if candidate:
                parts.append(candidate)
            current = []
        else:
            current.append(character)

    if depth:
        raise ValueError("Unbalanced opening parenthesis in vocabulary entry")
    candidate = "".join(current).strip(" \t,;.!?")
    if candidate:
        parts.append(candidate)
    return parts


def _is_sentence_entry(value: str) -> bool:
    return value.rstrip().endswith((".", "!", "?"))


def _is_latin_required_construction(value: str) -> bool:
    """Recognize comma-separated syntax that is required, not a principal part."""

    if _is_sentence_entry(value):
        return False
    groups = _split_top_level(value, {",", ";"})
    if len(groups) < 2:
        return False
    second_group = normalize_text(groups[1]).split()
    return bool(second_group and second_group[0] in LATIN_REQUIRED_GROUP_STARTERS)


def _meaning_groups(value: str, *, language: str) -> list[str]:
    """Split meanings while preserving commas that join complete clauses."""

    if _is_sentence_entry(value):
        return _split_sentences(value)

    if language == "la":
        return _split_top_level(value, {",", ";"})

    return _split_top_level(value, {",", ";"})


def _is_german_required_construction(value: str) -> bool:
    """Keep a trailing clause marker attached to its governing dictionary form."""

    if _is_sentence_entry(value):
        return False
    groups = _split_top_level(value, {",", ";"})
    if len(groups) != 2:
        return False
    head_tokens = normalize_text(groups[0]).split()
    tail_tokens = normalize_text(groups[1]).split()
    return bool(
        head_tokens
        and tail_tokens
        and tail_tokens[0] in CLAUSE_STARTERS
        and head_tokens[0] not in GERMAN_CONNECTIVE_HEAD_WORDS
    )


def _first_parenthetical(value: str) -> tuple[int, int] | None:
    opening = -1
    opening_character = ""
    for index, character in enumerate(value):
        if character in "([":
            if opening != -1:
                raise ValueError("Nested parentheses require an explicit vocabulary alias")
            opening = index
            opening_character = character
        elif character in ")]":
            if (
                opening == -1
                or (opening_character == "(" and character != ")")
                or (opening_character == "[" and character != "]")
            ):
                raise ValueError("Unbalanced parenthesis in vocabulary entry")
            return opening, index
    if opening != -1:
        raise ValueError("Unbalanced opening parenthesis in vocabulary entry")
    return None


def _expand_parentheses(value: str) -> set[str]:
    location = _first_parenthetical(value)
    if not location:
        return {value.strip()}
    start, end = location
    before = value[:start]
    inside = value[start + 1 : end]
    after = value[end + 1 :]
    inside_options = _split_top_level(inside, {",", "/"}) or [inside]

    replacements = {""}
    replacements.update(option.strip() for option in inside_options if option.strip())

    # In forms such as "er (sie, es) ist", the group replaces the preceding
    # pronoun rather than being appended to it.
    preceding = re.search(r"([^\W_]+)\s*$", before, re.UNICODE)
    if preceding:
        first = normalize_text(preceding.group(1))
        alternatives = {normalize_text(option) for option in inside_options}
        if first in PRONOUN_ALTERNATIVES and alternatives <= PRONOUN_ALTERNATIVES:
            stem = before[: preceding.start()]
            variants: set[str] = set()
            for pronoun in {preceding.group(1), *inside_options}:
                variants.update(_expand_parentheses(f"{stem}{pronoun.strip()}{after}"))
            return variants

    variants = set()
    for replacement in replacements:
        variants.update(_expand_parentheses(f"{before}{replacement}{after}"))
        if len(variants) > MAX_VARIANTS:
            raise ValueError("Vocabulary entry expands to too many answer variants")
    return {re.sub(r"\s+", " ", item).strip() for item in variants if item.strip()}


def _expand_one_slash(value: str) -> set[str]:
    parts = _split_top_level(value, {"/"})
    if len(parts) <= 1:
        return {value.strip()}
    if len(parts) > 2:
        if all(len(normalize_text(part).split()) == 1 for part in parts):
            return set(parts)
        raise ValueError("Ambiguous multi-slash vocabulary entry")

    left, right = parts
    left_tokens = left.split()
    right_tokens = right.split()
    if not left_tokens or not right_tokens:
        raise ValueError("Empty slash alternative in vocabulary entry")

    left_joined = normalize_text("".join(left_tokens))
    right_joined = normalize_text("".join(right_tokens))
    if left_joined == right_joined:
        return {left, right}
    if len(left_tokens) == 1 and len(right_tokens) == 1:
        return {left, right}
    if len(right_tokens) == 1:
        return {left, " ".join([*left_tokens[:-1], right])}
    if len(left_tokens) == 1:
        return {right, " ".join([left, *right_tokens[1:]])}
    return {left, right}


def _expand_slashes(value: str) -> set[str]:
    if "/" not in value:
        return {value.strip()}
    return _expand_one_slash(value)


def _structural_variants(value: str) -> set[str]:
    variants: set[str] = set()
    for parenthetical in _expand_parentheses(value):
        variants.update(_expand_slashes(parenthetical))
    variants.add(value.strip())
    return {item for item in variants if item}


def _keyboard_spellings(value: str) -> set[str]:
    choices: list[tuple[str, ...]] = []
    for character in unicodedata.normalize("NFKC", value).casefold():
        equivalents = KEYBOARD_EQUIVALENTS.get(character)
        if equivalents:
            choices.append(equivalents)
            continue
        decomposed = unicodedata.normalize("NFKD", character)
        base = "".join(part for part in decomposed if not unicodedata.combining(part))
        choices.append((character, base) if base and base != character else (character,))

    spellings: set[str] = set()
    for combination in itertools.product(*choices):
        spellings.add("".join(combination))
        if len(spellings) >= 512:
            break
    return spellings


def _tokenize(value: str, *, language: str, candidate: bool) -> list[tuple[str, ...]]:
    spellings = _keyboard_spellings(value) if candidate else {value}
    results: set[tuple[str, ...]] = set()
    for spelling in spellings:
        tokens = normalize_text(spelling).split()
        if language == "de":
            expanded: list[str] = []
            for token in tokens:
                expanded.extend(GERMAN_CONTRACTIONS.get(token, (token,)))
            tokens = [token for token in expanded if token not in GERMAN_ARTICLES]
            tokens = [token for token in tokens if token not in OPTIONAL_LABELS]
        if tokens:
            results.add(tuple(tokens))
    return list(results)


def _signatures(value: str, *, language: str, candidate: bool) -> set[tuple[str, ...]]:
    variants = {value, value.replace("-", ""), value.replace("-", " ")}
    return {
        tuple(sorted(tokens))
        for variant in variants
        for tokens in _tokenize(variant, language=language, candidate=candidate)
        if tokens
    }


def _candidate_groups(expected: str, *, language: str) -> list[list[Candidate]]:
    groups: list[list[Candidate]] = []
    for group in _meaning_groups(expected, language=language):
        candidates: dict[tuple[str, ...], Candidate] = {}
        for variant in _structural_variants(group):
            for signature in _signatures(variant, language=language, candidate=True):
                candidates.setdefault(signature, Candidate(variant, signature))
        if candidates:
            groups.append(list(candidates.values()))
    return groups


def _value_candidates(value: str, *, language: str) -> list[Candidate]:
    candidates: dict[tuple[str, ...], Candidate] = {}
    for variant in _structural_variants(value):
        for signature in _signatures(variant, language=language, candidate=True):
            candidates.setdefault(signature, Candidate(variant, signature))
    return list(candidates.values())


def _combined_german_candidates(groups: list[list[Candidate]]) -> list[Candidate]:
    """Accept any non-empty subset of complete German meaning groups."""

    states: dict[tuple[str, ...], str] = {(): ""}
    for group in groups:
        next_states = dict(states)
        for base_signature, base_display in states.items():
            for candidate in group:
                signature = tuple(sorted((*base_signature, *candidate.signature)))
                display = " · ".join(filter(None, (base_display, candidate.display)))
                next_states.setdefault(signature, display)
                if len(next_states) > MAX_VARIANTS:
                    raise ValueError("Vocabulary entry expands to too many answer variants")
        states = next_states
    return [Candidate(display, signature) for signature, display in states.items() if signature]


def _latin_principal_match(
    answer_signature: tuple[str, ...], groups: list[list[Candidate]]
) -> Candidate | None:
    if len(groups) < 2:
        return None
    answer = Counter(answer_signature)
    optional_signatures = [candidate.signature for group in groups[1:] for candidate in group]
    allowed_optional = Counter(token for signature in optional_signatures for token in signature)
    for core in groups[0]:
        core_counter = Counter(core.signature)
        allowed = core_counter + allowed_optional
        if core_counter <= answer <= allowed:
            return core
    return None


def match_text(answer: str, expected: str, *, language: str) -> MatchResult:
    normalized_input = normalize_text(answer)
    answer_signatures = _signatures(answer, language=language, candidate=False)
    if not answer_signatures:
        return MatchResult(correct=False, normalized_input=normalized_input)

    groups = _candidate_groups(expected, language=language)
    german_required = language == "de" and _is_german_required_construction(expected)
    latin_sentence = language == "la" and _is_sentence_entry(expected)
    latin_required = language == "la" and _is_latin_required_construction(expected)
    if german_required:
        candidates = [candidate for group in groups[:1] for candidate in group]
        candidates.extend(_value_candidates(expected, language=language))
    elif language == "de":
        candidates = _combined_german_candidates(groups)
    elif latin_sentence:
        # Complete Latin sentences and utterances are alternatives. Commas in
        # them join clauses and must never make a fragment count as correct.
        candidates = [candidate for group in groups for candidate in group]
        candidates.extend(_value_candidates(expected, language=language))
    elif latin_required:
        candidates = _value_candidates(expected, language=language)
    else:
        # Latin comma-separated forms are principal parts. Isolated conjugated
        # forms do not count without the required lemma/core.
        candidates = [candidate for group in groups[:1] for candidate in group]
        for signature in _signatures(expected, language=language, candidate=True):
            candidates.append(Candidate(expected, signature))

    by_signature = {candidate.signature: candidate for candidate in candidates}
    for answer_signature in answer_signatures:
        candidate = by_signature.get(answer_signature)
        if language == "la" and candidate is None and not latin_sentence and not latin_required:
            candidate = _latin_principal_match(answer_signature, groups)
        if candidate is None:
            continue
        raw_answer_tokens = normalize_text(answer).split()
        raw_candidate_tokens = normalize_text(candidate.display).split()
        return MatchResult(
            correct=True,
            normalized_input=normalized_input,
            matched_variant=candidate.display,
            article_insensitive=(
                language == "de"
                and tuple(sorted(raw_answer_tokens)) != tuple(sorted(raw_candidate_tokens))
            ),
            order_insensitive=(
                tuple(raw_answer_tokens) != tuple(raw_candidate_tokens)
                and tuple(sorted(raw_answer_tokens)) == tuple(sorted(raw_candidate_tokens))
            ),
            parentheses_optional="(" in expected or "[" in expected,
        )
    return MatchResult(correct=False, normalized_input=normalized_input)


def validate_expected(expected: str, *, language: str) -> None:
    """Compile an answer specification so bad catalogue syntax fails at import."""

    groups = _candidate_groups(expected, language=language)
    if not groups:
        raise ValueError("Vocabulary answer has no usable tokens")
    if language == "de":
        _combined_german_candidates(groups)


SUPPORTED_MATCHERS = {"generic-v1", "german-v1", "latin-v1"}


def _generic_match(answer: str, expected: str) -> MatchResult:
    normalized_input = normalize_text(answer)
    normalized_expected = normalize_text(expected)
    return MatchResult(
        correct=bool(normalized_input) and normalized_input == normalized_expected,
        normalized_input=normalized_input,
        matched_variant=expected if normalized_input == normalized_expected else None,
    )


def match_card_answer(
    answer: str,
    expected: str,
    accepted_answers: list[str],
    *,
    matcher_profile: str,
) -> MatchResult:
    """Match a frozen card answer using its declared, language-aware profile."""

    if matcher_profile not in SUPPORTED_MATCHERS:
        raise ValueError(f"Unsupported matcher profile: {matcher_profile}")
    candidates = [expected, *accepted_answers]
    for candidate in candidates:
        if matcher_profile == "german-v1":
            result = match_text(answer, candidate, language="de")
        elif matcher_profile == "latin-v1":
            result = match_text(answer, candidate, language="la")
        else:
            result = _generic_match(answer, candidate)
        if result.correct:
            return result
    return MatchResult(correct=False, normalized_input=normalize_text(answer))


def validate_answer_spec(
    expected: str,
    accepted_answers: list[str],
    *,
    matcher_profile: str,
) -> None:
    """Compile all configured answers so invalid imports fail before changing the catalogue."""

    if matcher_profile not in SUPPORTED_MATCHERS:
        raise ValueError(f"Unsupported matcher profile: {matcher_profile}")
    for candidate in [expected, *accepted_answers]:
        if matcher_profile == "german-v1":
            validate_expected(candidate, language="de")
        elif matcher_profile == "latin-v1":
            validate_expected(candidate, language="la")
        elif not normalize_text(candidate):
            raise ValueError("Card answer has no usable characters")
