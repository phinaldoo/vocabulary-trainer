from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Password = Annotated[str, StringConstraints(min_length=10, max_length=128)]
Direction = Literal["forward", "reverse", "mixed"]
CardDirection = Literal["forward", "reverse"]
InputMode = Literal["typing", "reveal"]
SelectionMode = Literal["scheduled", "random", "adaptive"]
UiLanguage = Literal["en", "zh-Hans", "hi", "es", "de"]
DeckStatus = Literal["draft", "published", "archived"]
MatcherProfile = Literal["generic-v1", "german-v1", "latin-v1"]
CardStatus = Literal["new", "learning", "familiar", "mastered", "difficult"]
AnswerText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=250),
]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
LabelText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
StableKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
SectionKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
Slug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=80,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
LanguageTag = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=35,
        pattern=r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$",
    ),
]


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    role: Literal["user", "admin"]
    language: UiLanguage | None
    daily_goal: int
    direction: Direction
    input_mode: InputMode
    selected_deck_id: uuid.UUID | None
    selected_section_id: uuid.UUID | None
    created_at: datetime


class AdminUserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    role: Literal["user", "admin"]
    created_at: datetime


class PaginatedUsers(BaseModel):
    items: list[AdminUserPublic]
    page: int
    page_size: int
    total: int
    pages: int


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: Password
    display_name: DisplayName
    language: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=35)] = None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    language: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=35)] = None


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_goal: int = Field(ge=5, le=500)
    direction: Direction
    input_mode: InputMode
    language: UiLanguage | None = None
    selected_deck_id: uuid.UUID | None = None
    selected_section_id: uuid.UUID | None = None


class AccountProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    display_name: DisplayName


class AccountDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class LanguageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: UiLanguage


class DeckPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    description: str | None
    front_label: str
    back_label: str
    front_language: str
    back_language: str
    front_matcher: str
    back_matcher: str
    status: DeckStatus
    version: int
    license: str | None
    attribution: str | None
    sort_order: int
    section_count: int = 0
    card_count: int = 0


class DeckCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: Slug
    title: ShortText
    description: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=2_000)
    ] = None
    front_label: LabelText
    back_label: LabelText
    front_language: LanguageTag
    back_language: LanguageTag
    front_matcher: MatcherProfile = "generic-v1"
    back_matcher: MatcherProfile = "generic-v1"
    license: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=80)] = None
    attribution: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=2_000)
    ] = None


class DeckUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ShortText
    description: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=2_000)
    ] = None
    front_label: LabelText
    back_label: LabelText
    front_language: LanguageTag
    back_language: LanguageTag
    front_matcher: MatcherProfile
    back_matcher: MatcherProfile
    license: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=80)] = None
    attribution: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=2_000)
    ] = None


class DeckStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DeckStatus


class SectionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    deck_id: uuid.UUID
    stable_key: str
    title: str
    sort_order: int
    active: bool
    total: int = 0
    learned: int = 0
    mastered: int = 0
    due: int = 0
    progress_percent: int = 0


class SectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stable_key: SectionKey
    title: ShortText
    sort_order: int = Field(ge=1, le=1_000_000)


class SectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ShortText
    sort_order: int = Field(ge=1, le=1_000_000)
    active: bool = True


class CardPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    deck_id: uuid.UUID
    section_id: uuid.UUID | None
    section_title: str | None = None
    stable_key: str
    sort_order: int
    front_text: str
    back_text: str
    front_answers: list[str]
    back_answers: list[str]
    metadata: dict[str, object] = Field(default_factory=dict, validation_alias="details")
    active: bool
    favorite: bool = False
    status: CardStatus = "new"


class PaginatedCards(BaseModel):
    items: list[CardPublic]
    page: int
    page_size: int
    total: int
    pages: int


class CardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stable_key: StableKey
    section_id: uuid.UUID | None = None
    sort_order: int = Field(ge=1, le=10_000_000)
    front_text: AnswerText
    back_text: AnswerText
    front_answers: list[AnswerText] = Field(default_factory=list, max_length=100)
    back_answers: list[AnswerText] = Field(default_factory=list, max_length=100)
    metadata: dict[str, object] = Field(default_factory=dict)


class CardUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: uuid.UUID | None = None
    sort_order: int = Field(ge=1, le=10_000_000)
    front_text: AnswerText
    back_text: AnswerText
    front_answers: list[AnswerText] = Field(default_factory=list, max_length=100)
    back_answers: list[AnswerText] = Field(default_factory=list, max_length=100)
    metadata: dict[str, object] = Field(default_factory=dict)
    active: bool = True


class StudySessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deck_id: uuid.UUID
    section_id: uuid.UUID | None = None
    direction: Direction
    input_mode: InputMode
    selection_mode: SelectionMode = "scheduled"
    limit: int = Field(ge=1, le=50)


class StudyCard(BaseModel):
    item_id: uuid.UUID
    card_id: uuid.UUID
    section_id: uuid.UUID | None
    section_title: str | None
    ordinal: int
    direction: CardDirection
    prompt: str
    prompt_language: str
    answer_language: str
    metadata: dict[str, object]
    state_version: int
    is_new: bool


class StudySessionPublic(BaseModel):
    selection_mode: SelectionMode
    id: uuid.UUID
    deck_id: uuid.UUID
    deck_title: str
    section_id: uuid.UUID | None
    section_title: str | None
    front_label: str
    back_label: str
    front_language: str
    back_language: str
    direction: Direction
    input_mode: InputMode
    total: int
    reviewed: int
    correct_reviewed: int
    complete: bool
    cards: list[StudyCard]


class AnswerCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: uuid.UUID
    answer: AnswerText


class AnswerCheckResponse(BaseModel):
    correct: bool
    solution: str
    match_kind: str | None
    missing_meanings: list[str] = Field(default_factory=list)


class RevealResponse(BaseModel):
    solution: str


class TypingReview(BaseModel):
    type: Literal["typing"]
    answer: AnswerText
    rating: int = Field(ge=0, le=3)


class FlipReview(BaseModel):
    type: Literal["self_assessment"]
    known: bool


ReviewResponse = Annotated[TypingReview | FlipReview, Field(discriminator="type")]


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: uuid.UUID
    item_id: uuid.UUID
    base_version: int = Field(ge=0, le=1_000_000)
    response_ms: int | None = Field(default=None, ge=0, le=600_000)
    response: ReviewResponse


class ReviewResult(BaseModel):
    ok: bool = True
    correct: bool
    effective_rating: int
    match_kind: str | None
    solution: str
    due_at: datetime
    interval_days: float
    version: int
    reviewed: int
    correct_reviewed: int
    total: int
    complete: bool


class WeeklyActivity(BaseModel):
    date: date
    count: int
    today: bool


class DifficultCard(BaseModel):
    id: uuid.UUID
    deck_id: uuid.UUID
    section_id: uuid.UUID | None
    section_title: str | None
    front_text: str
    back_text: str
    front_language: str
    lapses: int


class DashboardData(BaseModel):
    deck: DeckPublic | None
    due_count: int
    reviewed_today: int
    learned_count: int
    mastered_count: int
    streak: int
    total_count: int
    progress_percent: int
    weekly_activity: list[WeeklyActivity]
    difficult: list[DifficultCard]


class ProgressData(BaseModel):
    deck: DeckPublic | None
    total: int
    learned: int
    secure: int
    familiar: int
    learning: int
    accuracy: int
    reviews: int
    streak: int
    sections: list[SectionPublic]


class ManifestSide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: LabelText
    language: LanguageTag
    matcher: MatcherProfile = "generic-v1"


class ManifestSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: SectionKey
    title: ShortText
    order: int = Field(ge=1, le=1_000_000)


class ManifestCardSide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: AnswerText
    answers: list[AnswerText] = Field(default_factory=list, max_length=100)


class ManifestCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StableKey
    section: SectionKey | None = None
    order: int = Field(ge=1, le=10_000_000)
    front: ManifestCardSide
    back: ManifestCardSide
    metadata: dict[str, object] = Field(default_factory=dict)


class DeckManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal[1] = Field(alias="schemaVersion")
    id: Slug
    version: int = Field(ge=1, le=1_000_000)
    title: ShortText
    description: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=2_000)
    ] = None
    license: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=80)] = None
    attribution: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=2_000)
    ] = None
    front: ManifestSide
    back: ManifestSide
    sections: list[ManifestSection] = Field(default_factory=list, max_length=10_000)
    cards: list[ManifestCard] = Field(min_length=1, max_length=100_000)

    @field_validator("sections")
    @classmethod
    def unique_sections(cls, value: list[ManifestSection]) -> list[ManifestSection]:
        keys = [section.id for section in value]
        orders = [section.order for section in value]
        if len(keys) != len(set(keys)) or len(orders) != len(set(orders)):
            raise ValueError("Section IDs and order values must be unique")
        return value

    @model_validator(mode="after")
    def validate_cards(self) -> DeckManifest:
        section_keys = {section.id for section in self.sections}
        card_keys = [card.id for card in self.cards]
        card_orders = [card.order for card in self.cards]
        if len(card_keys) != len(set(card_keys)):
            raise ValueError("Card IDs must be unique")
        if len(card_orders) != len(set(card_orders)):
            raise ValueError("Card order values must be unique")
        missing = {card.section for card in self.cards if card.section not in section_keys | {None}}
        if missing:
            raise ValueError(f"Cards reference unknown sections: {', '.join(sorted(missing))}")
        return self


class ImportResult(BaseModel):
    deck: DeckPublic
    created_sections: int = 0
    updated_sections: int = 0
    created_cards: int = 0
    updated_cards: int = 0
    archived_cards: int = 0
    unchanged: bool = False


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str | None = None
