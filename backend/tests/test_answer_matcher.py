import pytest

from app.services.answer_matcher import (
    match_text,
    validate_answer_spec,
    validate_expected,
)

# These examples are purpose-written test fixtures. The Latin-looking forms are
# nonce words; they exercise catalogue syntax without reproducing a real deck.


@pytest.mark.parametrize(
    ("expected", "answer"),
    [
        ("unter (der) Kristallbrücke warten", "warten unter Kristallbrücke"),
        ("unter (der) Kristallbrücke warten", "unter der Kristallbrücke warten"),
        ("Mira (die Hüterin der Sterne)", "Mira"),
        ("Mira (die Hüterin der Sterne)", "Hüterin Sterne Mira"),
        ("die Wolkenlaterne, das Himmelslicht", "Himmelslicht Wolkenlaterne"),
        ("er (sie, es) glimmt", "er glimmt"),
        ("er (sie, es) glimmt", "sie glimmt"),
        ("er (sie, es) glimmt", "es glimmt"),
        ("der (die) Pilot(in)", "Pilotin"),
        ("im Atelier schlafen", "in Atelier schlafen"),
        ("das Rätsel", "Raetsel"),
        ("das Rätsel", "Ratsel"),
        ("die Süßtorte", "Suesstorte"),
        ("die Süßtorte", "Susstorte"),
        ("Nova Aurelia Äon", "Aeon Nova Aurelia"),
    ],
)
def test_german_user_friendly_answers(expected: str, answer: str) -> None:
    assert match_text(answer, expected, language="de").correct


@pytest.mark.parametrize(
    ("expected", "answer"),
    [
        ("das Rätsel", ""),
        ("das Rätsel", "das"),
        ("das Rätsel", "Rät"),
        ("das Rätsel", "Raetselx"),
        ("Mira (die Hüterin der Sterne)", "Hüterin der Sterne"),
        ("leuchte(t) hell!, blinke rot / blau!", "blau"),
        ("er (sie, es) glimmt", "sie"),
        ("leise summen", "summen"),
        ("Funken zählen", "viele Funken zählen"),
        ("funkelnd funkelnd", "funkelnd"),
        (
            "Der silberne Automat stoppt (pausiert), während drei Lampen blinken.",
            "während drei Lampen blinken",
        ),
        ("losen", "lösen"),
    ],
)
def test_german_missing_or_extra_content_is_rejected(expected: str, answer: str) -> None:
    assert not match_text(answer, expected, language="de").correct


@pytest.mark.parametrize(
    ("expected", "answer"),
    [
        ("mirelare, mirelo, mirelavi, mirelatum", "mirelare"),
        ("mirelare, mirelo, mirelavi, mirelatum", "mirelo mirelare"),
        (
            "mirelare, mirelo, mirelavi, mirelatum",
            "mirelatum mirelavi mirelare mirelo",
        ),
        ("zorum, zori (Gen. Pl. -orum)", "zori zorum"),
        ("sena tora / senatora", "sena tora"),
        ("sena tora / senatora", "senatora"),
        ("nostra zorat / nostra velat", "nostra zorat"),
        ("nostra zorat / nostra velat", "nostra velat"),
        ("sub / trans velum mirelare", "sub velum mirelare"),
        ("sub / trans velum mirelare", "trans velum mirelare"),
        ("Zori / zorum reminiscor.", "reminiscor zori"),
        ("Zori / zorum reminiscor.", "reminiscor zorum"),
        ("tal(e)ra", "talera"),
    ],
)
def test_latin_structural_answers(expected: str, answer: str) -> None:
    assert match_text(answer, expected, language="la").correct


@pytest.mark.parametrize(
    ("expected", "answer"),
    [
        ("mirelare, mirelo, mirelavi, mirelatum", "mirelo"),
        ("mirelare, mirelo, mirelavi, mirelatum", "mirelo mirelatum"),
        ("mirelare, mirelo, mirelavi, mirelatum", "mirelare falsum"),
        ("mirelare, mirelo, mirelavi, mirelatum", "mirelare mirelare"),
        ("zorum, zori (Gen. Pl. -orum)", "zori"),
        ("sub", "der sub"),
    ],
)
def test_latin_requires_the_lemma_and_no_unknown_tokens(expected: str, answer: str) -> None:
    assert not match_text(answer, expected, language="la").correct


@pytest.mark.parametrize(
    ("expected", "answer"),
    [
        ("Der Würfel leuchtet. Das Papierboot dreht sich.", "Der Würfel"),
        ("Sobald drei Lampen blinken, startet die Maschine.", "Sobald drei Lampen blinken"),
        ("Sobald drei Lampen blinken, startet die Maschine.", "startet die Maschine"),
        (
            "Die blaue Kugel darf schweben. Das rote Dreieck kann schweben.",
            "Die blaue Kugel",
        ),
    ],
)
def test_german_sentence_fragments_are_rejected(expected: str, answer: str) -> None:
    assert not match_text(answer, expected, language="de").correct


@pytest.mark.parametrize(
    "expected",
    [
        "vermuten, dass",
        "dafür sorgen, dass",
        "(sicher)stellen, dass",
        "es überrascht mich, dass",
        "ich bestreite nicht, dass",
    ],
)
def test_german_structural_clause_markers_are_not_standalone(expected: str) -> None:
    assert not match_text("dass", expected, language="de").correct


def test_german_required_construction_core_remains_user_friendly() -> None:
    assert match_text("vermuten", "vermuten, dass", language="de").correct
    assert match_text("vermuten dass", "vermuten, dass", language="de").correct


@pytest.mark.parametrize(
    ("expected", "answer"),
    [
        ("luma! lumate!", "luma"),
        ("luma! lumate!", "lumate"),
        ("sora! sorate!", "sora"),
        ("sora! sorate!", "sorate"),
        ("Mirelum vidi, priusquam zora fulsit.", "Mirelum vidi priusquam zora fulsit"),
        ("Quaero, an talum resonet.", "Quaero an talum resonet"),
        ("Paratus es, qui zoram vertas.", "Paratus es qui zoram vertas"),
    ],
)
def test_complete_latin_utterances_are_accepted(expected: str, answer: str) -> None:
    assert match_text(answer, expected, language="la").correct


@pytest.mark.parametrize(
    ("expected", "answer"),
    [
        ("Mirelum vidi, priusquam zora fulsit.", "Mirelum vidi"),
        ("Mirelum vidi, priusquam zora fulsit.", "priusquam zora fulsit"),
        ("Talum verte, ne zora cadat!", "Talum verte"),
        ("Quaero, an talum resonet.", "Quaero"),
        ("Paratus es, qui zoram vertas.", "Paratus es"),
    ],
)
def test_latin_sentence_fragments_are_rejected(expected: str, answer: str) -> None:
    assert not match_text(answer, expected, language="la").correct


@pytest.mark.parametrize(
    ("expected", "answer"),
    [
        ("mirelare, ne", "mirelare ne"),
        ("zoram servare, ne", "zoram servare ne"),
        ("non talo, quin", "non talo quin"),
        ("accidit, ut", "accidit ut"),
        ("paratus, qui", "paratus qui"),
    ],
)
def test_latin_required_constructions_are_accepted(expected: str, answer: str) -> None:
    assert match_text(answer, expected, language="la").correct


@pytest.mark.parametrize(
    ("expected", "answer"),
    [
        ("mirelare, ne", "mirelare"),
        ("zoram servare, ne", "zoram servare"),
        ("non talo, quin", "non talo"),
        ("accidit, ut", "accidit"),
        ("paratus, qui", "paratus"),
    ],
)
def test_latin_required_construction_fragments_are_rejected(expected: str, answer: str) -> None:
    assert not match_text(answer, expected, language="la").correct


def test_latin_pronoun_principal_parts_remain_optional() -> None:
    assert match_text("zui", "zui, zua, zuod", language="la").correct
    assert not match_text("zua", "zui, zua, zuod", language="la").correct


def test_malformed_parentheses_fail_catalogue_validation() -> None:
    with pytest.raises(ValueError):
        validate_expected("nexa (tor", language="de")


@pytest.mark.parametrize(
    ("text", "answers", "profile"),
    [
        ("mirelum", ["mirelum, mireli"], "latin-v1"),
        ("das Funkelrad", ["Funkelrad", "das Funkelrad"], "german-v1"),
        ("nuvexa-47", ["nuvexa47", "nuvexa 47"], "generic-v1"),
    ],
)
def test_deck_answer_specs_compile(text: str, answers: list[str], profile: str) -> None:
    validate_answer_spec(text, answers, matcher_profile=profile)


@pytest.mark.parametrize(
    ("expected", "answer"),
    [
        ("funkeln (bei Nacht), schimmern", "funkeln"),
        ("funkeln (bei Nacht), schimmern", "bei Nacht funkeln"),
        ("funkeln (bei Nacht), schimmern", "schimmern"),
        ("die (Sternen-)Karte, das Leuchtbild", "Karte"),
        ("die (Sternen-)Karte, das Leuchtbild", "Sternenkarte"),
        ("die (Sternen-)Karte, das Leuchtbild", "Leuchtbild"),
        ("leuchte(t) hell!, blinke rot / blau!", "leuchte hell"),
        ("leuchte(t) hell!, blinke rot / blau!", "leuchtet hell"),
        ("leuchte(t) hell!, blinke rot / blau!", "blinke rot"),
        ("leuchte(t) hell!, blinke rot / blau!", "blinke blau"),
        ("der Mondstein, das Nachtjuwel", "Mondstein"),
        ("der Mondstein, das Nachtjuwel", "das Nachtjuwel"),
        ("drehen, kippen, stapeln, sortieren", "drehen stapeln"),
        ("Zähle die Monde! Ordne die Sterne (nach Farben)!", "Ordne die Sterne"),
        ("Der Würfel leuchtet. Das Papierboot dreht sich.", "Der Würfel leuchtet"),
        ("Der Würfel leuchtet. Das Papierboot dreht sich.", "Das Papierboot dreht sich"),
        (
            "Ich zählte Monde, bevor der Roboter erwachte. "
            "Die Laterne summte früher, als der Würfel landete.",
            "Die Laterne summte früher als der Würfel landete",
        ),
        ("dreh links!, dreht rechts!", "dreh links"),
        ("dreh links!, dreht rechts!", "dreht rechts"),
        ("sondern, aber", "sondern"),
        ("denn, aber, nämlich", "nämlich"),
        ("dass, weil", "weil"),
        ("obwohl, auch wenn", "auch wenn"),
        ("als, nachdem", "nachdem"),
        ("zwischen, während, unter", "unter"),
        ("und auch, und", "und"),
        ("weil, nachdem, obwohl, als", "obwohl"),
        ("ob nicht, ob", "ob"),
        ("wenn doch, hoffentlich", "hoffentlich"),
        ("wenn auch, aber, obwohl", "obwohl"),
        ("oder wenn, oder", "oder"),
        ("zu (m. Inf.), dass", "dass"),
        ("zu (m. Inf.), dass", "zu"),
        ("dass keinesfalls, keinesfalls zu (m. Inf.)", "keinesfalls zu"),
        ("sodass, damit, um zu (m. Inf.), dass", "damit"),
        ("wirklich, tatsächlich, aber", "tatsächlich"),
    ],
)
def test_all_german_meanings_are_required(expected: str, answer: str) -> None:
    assert not match_text(answer, expected, language="de").correct


@pytest.mark.parametrize(
    "answer",
    [
        "funkeln schimmern",
        "schimmern, funkeln!",
        "  funkeln   schimmern  ",
        "funkeln bei Nacht; schimmern",
    ],
)
def test_all_meanings_preserve_optional_formatting(answer: str) -> None:
    assert match_text(answer, "funkeln (bei Nacht), schimmern", language="de").correct


def test_missing_meanings_feedback_requires_complete_known_groups() -> None:
    expected = "funkeln (bei Nacht), leise schimmern, glimmen"
    result = match_text("glimmen funkeln", expected, language="de")
    assert not result.correct
    assert result.missing_meanings == ("leise schimmern",)
    for answer in ["schimmern", "funkeln falsch", "funkelnschimmern", ""]:
        assert not match_text(answer, expected, language="de").missing_meanings


def test_slash_alternatives_still_require_other_meanings() -> None:
    expected = "rot / blau, hell"
    assert match_text("hell blau", expected, language="de").correct
    assert match_text("rot hell", expected, language="de").correct
    assert not match_text("blau", expected, language="de").correct


def test_repeated_words_cannot_satisfy_multiple_meanings() -> None:
    expected = "leise funkeln, leise schimmern"
    assert not match_text("leise funkeln schimmern", expected, language="de").correct
    assert match_text("leise funkeln leise schimmern", expected, language="de").correct
