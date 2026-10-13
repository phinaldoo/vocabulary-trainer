"""Parse the five-column Latin principal-parts CSV into ordinary study cards."""
from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.deck_kinds import PRINCIPAL_PARTS_MATCHER
from app.schemas import DeckManifest, ShortText
from app.services.answer_matcher import validate_answer_spec

MAX_CSV_BYTES = 1_000_000


class VerbCsvRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ShortText
    csv_text: str = Field(min_length=1, max_length=MAX_CSV_BYTES)


class VerbRow(BaseModel):
    line: int
    infinitive: str
    present: str
    perfect: str
    supine: str
    meaning: str
    conjugation: str
    perfect_group: str


class CsvIssue(BaseModel):
    line: int
    code: str


class VerbCsvPreview(BaseModel):
    rows: list[VerbRow]
    errors: list[CsvIssue]
    duplicate_count: int = 0
    section_count: int = 0


def parse_verb_csv(text: str) -> VerbCsvPreview:
    result = VerbCsvPreview(rows=[], errors=[])
    if len(text.encode("utf-8")) > MAX_CSV_BYTES:
        result.errors.append(CsvIssue(line=1, code="too_large"))
        return result
    text = text.lstrip("\ufeff")
    if "\x00" in text or "\ufffd" in text:
        result.errors.append(CsvIssue(line=1, code="encoding"))
        return result
    # Score complete rows so a quoted semicolon in comma CSV is not mistaken
    # for a separator. Prefer semicolons on ties for the heading-heavy format.
    scores = {}
    for candidate in (";", "\t", ","):
        score = 0
        try:
            sample = csv.reader(io.StringIO(text, newline=""), delimiter=candidate, strict=True)
            for row in itertools.islice(sample, 100):
                score += len(row) == 5
        except csv.Error:
            pass  # The actual parser below reports the malformed row.
        scores[candidate] = score
    delimiter = max(scores, key=scores.get)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    conjugation = ""
    perfect_group = ""
    seen: dict[str, VerbRow] = {}
    try:
        for raw in reader:
            line = reader.line_num
            cells = [" ".join(cell.split()) for cell in raw]
            if not any(cells):
                continue
            if len(result.errors) >= 50:
                break
            if not any(cells[1:]):
                heading = cells[0]
                if len(heading) > 100:
                    result.errors.append(CsvIssue(line=line, code="heading"))
                elif "konjug" in heading.casefold() or "conjug" in heading.casefold():
                    conjugation, perfect_group = heading, ""
                elif "perfekt" in heading.casefold() or "perfect" in heading.casefold():
                    perfect_group = heading
                else:
                    result.errors.append(CsvIssue(line=line, code="required"))
                continue
            if cells[0].casefold() in {"infinitiv", "infinitive"} and len(cells) == 5:
                continue
            if len(cells) != 5:
                result.errors.append(CsvIssue(line=line, code="columns"))
                continue
            if not all(cells):
                result.errors.append(CsvIssue(line=line, code="required"))
                continue
            if len(", ".join(cells[:4])) > 250 or len(cells[4]) > 250:
                result.errors.append(CsvIssue(line=line, code="length"))
                continue
            if cells[0] in {"-", "–", "—"} or cells[1] in {"-", "–", "—"}:
                result.errors.append(CsvIssue(line=line, code="required"))
                continue
            try:
                validate_answer_spec(cells[4], [], matcher_profile="german-v1")
            except ValueError:
                result.errors.append(CsvIssue(line=line, code="answer"))
                continue
            if len(" · ".join(filter(None, [conjugation, perfect_group]))) > 120:
                result.errors.append(CsvIssue(line=line, code="heading"))
                continue
            row = VerbRow(
                line=line, infinitive=cells[0], present=cells[1], perfect=cells[2],
                supine=cells[3], meaning=cells[4], conjugation=conjugation,
                perfect_group=perfect_group,
            )
            key = row.infinitive.casefold()
            if key in seen:
                if row.model_dump(exclude={"line"}) == seen[key].model_dump(exclude={"line"}):
                    result.duplicate_count += 1
                else:
                    result.errors.append(CsvIssue(line=line, code="duplicate"))
                continue
            if len(result.rows) >= 2000:
                result.errors.append(CsvIssue(line=line, code="too_many"))
                break
            seen[key] = row
            result.rows.append(row)
    except csv.Error:
        result.errors.append(CsvIssue(line=reader.line_num, code="syntax"))
    if not result.rows and not result.errors:
        result.errors.append(CsvIssue(line=1, code="empty"))
    result.section_count = len({(row.conjugation, row.perfect_group) for row in result.rows})
    return result


def verb_manifest(title: str, rows: list[VerbRow]) -> DeckManifest:
    # Content addressing makes repeated uploads idempotent, independent of filename,
    # line endings and blank rows. Different collections never overwrite each other.
    content = json.dumps([row.model_dump(exclude={"line"}) for row in rows], sort_keys=True)
    digest = hashlib.sha256(content.encode()).hexdigest()[:32]
    sections: dict[tuple[str, str], dict] = {}
    cards = []
    for index, row in enumerate(rows, 1):
        group = (row.conjugation, row.perfect_group)
        if group not in sections:
            sections[group] = {
                "id": f"group-{len(sections) + 1}",
                "title": " · ".join(filter(None, group)) or "Stammformen",
                "order": len(sections) + 1,
            }
        cards.append({
            "id": hashlib.sha256(row.infinitive.casefold().encode()).hexdigest(),
            "section": sections[group]["id"], "order": index,
            "front": {"text": ", ".join([row.infinitive, row.present, row.perfect, row.supine])},
            "back": {"text": row.meaning},
            "metadata": {"additional_info": row.conjugation,
                         "additional_info_2": row.perfect_group},
        })
    return DeckManifest.model_validate({
        "schemaVersion": 1, "id": f"special-verbs-{digest}", "version": 1,
        "title": title,
        "front": {"label": "Latein · Stammformen", "language": "la",
                  "matcher": PRINCIPAL_PARTS_MATCHER},
        "back": {"label": "Deutsch", "language": "de", "matcher": "german-v1"},
        "sections": list(sections.values()), "cards": cards,
    })


def preview_verb_csv(payload: VerbCsvRequest) -> VerbCsvPreview:
    result = parse_verb_csv(payload.csv_text)
    if not result.errors:
        try:
            verb_manifest(payload.title, result.rows)
        except ValidationError:
            result.errors.append(CsvIssue(line=1, code="answer"))
    return result
