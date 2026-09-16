from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentAuth, CurrentAuthWithCsrf, Database
from app.errors import ApiError
from app.models import ReviewEvent, StudySessionItem, UserCardProgress
from app.schemas import (
    AnswerCheckRequest,
    AnswerCheckResponse,
    RevealResponse,
    ReviewRequest,
    ReviewResult,
    StudySessionCreate,
    StudySessionPublic,
)
from app.services.answer_matcher import MatchResult, match_card_answer
from app.services.scheduler import SchedulerState, schedule_review
from app.services.study import (
    create_study_session,
    get_owned_item,
    get_study_session,
)

router = APIRouter(prefix="/study-sessions", tags=["study"])


def answer_fingerprint(answer: str) -> str:
    return hashlib.sha256(answer.encode("utf-8")).hexdigest()


def match_kind(result: MatchResult) -> str | None:
    if not result.correct:
        return None
    if result.order_insensitive:
        return "reordered"
    if result.parentheses_optional:
        return "parentheses_optional"
    if result.article_insensitive:
        return "article_optional"
    return "exact"


async def replay_review(
    db: Database,
    user_id: uuid.UUID,
    idempotency_key: uuid.UUID,
    request_hash: str,
) -> ReviewResult | None:
    existing = await db.scalar(
        select(ReviewEvent).where(
            ReviewEvent.user_id == user_id,
            ReviewEvent.idempotency_key == idempotency_key,
        )
    )
    if not existing:
        return None
    if existing.request_hash != request_hash:
        raise ApiError(
            409,
            "idempotency_mismatch",
            "Diese Wiederholungs-ID wurde bereits anders verwendet.",
        )
    return ReviewResult.model_validate(existing.response_json)


@router.post("", response_model=StudySessionPublic)
async def start_session(
    payload: StudySessionCreate,
    auth: CurrentAuthWithCsrf,
    db: Database,
    response: Response,
) -> StudySessionPublic:
    response.headers["Cache-Control"] = "private, no-store"
    return await create_study_session(db, auth.user, payload)


@router.get("/{session_id}", response_model=StudySessionPublic)
async def resume_session(
    session_id: uuid.UUID,
    auth: CurrentAuth,
    db: Database,
    response: Response,
) -> StudySessionPublic:
    response.headers["Cache-Control"] = "private, no-store"
    return await get_study_session(db, auth.user.id, session_id)


@router.post("/{session_id}/check", response_model=AnswerCheckResponse)
async def check_answer(
    session_id: uuid.UUID,
    payload: AnswerCheckRequest,
    auth: CurrentAuthWithCsrf,
    db: Database,
    response: Response,
) -> AnswerCheckResponse:
    study_session, item = await get_owned_item(
        db, auth.user.id, session_id, payload.item_id, for_update=True
    )
    if study_session.input_mode != "typing":
        raise ApiError(409, "wrong_study_mode", "Diese Lerneinheit verwendet den Aufdeckmodus.")
    if item.reviewed_at is not None:
        raise ApiError(409, "already_reviewed", "Diese Karte wurde bereits bewertet.")
    result = match_card_answer(
        payload.answer,
        item.solution_snapshot,
        item.accepted_answers_snapshot,
        matcher_profile=item.matcher_profile,
    )
    item.revealed_at = datetime.now(UTC)
    item.checked_answer_hash = answer_fingerprint(payload.answer)
    item.checked_correct = result.correct
    await db.commit()
    response.headers["Cache-Control"] = "private, no-store"
    return AnswerCheckResponse(
        correct=result.correct,
        solution=item.solution_snapshot,
        match_kind=match_kind(result),
        missing_meanings=list(result.missing_meanings),
    )


@router.post("/{session_id}/items/{item_id}/reveal", response_model=RevealResponse)
async def reveal_answer(
    session_id: uuid.UUID,
    item_id: uuid.UUID,
    auth: CurrentAuthWithCsrf,
    db: Database,
    response: Response,
) -> RevealResponse:
    study_session, item = await get_owned_item(
        db, auth.user.id, session_id, item_id, for_update=True
    )
    if study_session.input_mode != "reveal":
        raise ApiError(409, "wrong_study_mode", "Diese Lerneinheit verwendet den Tippmodus.")
    if item.reviewed_at is not None:
        raise ApiError(409, "already_reviewed", "Diese Karte wurde bereits bewertet.")
    item.revealed_at = datetime.now(UTC)
    await db.commit()
    response.headers["Cache-Control"] = "private, no-store"
    return RevealResponse(solution=item.solution_snapshot)


@router.post("/{session_id}/reviews", response_model=ReviewResult)
async def review(
    session_id: uuid.UUID,
    payload: ReviewRequest,
    auth: CurrentAuthWithCsrf,
    db: Database,
    response: Response,
) -> ReviewResult:
    user_id = auth.user.id
    request_data = payload.model_dump(mode="json")
    request_hash = hashlib.sha256(
        json.dumps(request_data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    replay = await replay_review(db, user_id, payload.idempotency_key, request_hash)
    if replay:
        return replay

    study_session, item = await get_owned_item(
        db, user_id, session_id, payload.item_id, for_update=True
    )
    if item.reviewed_at is not None:
        replay = await replay_review(db, user_id, payload.idempotency_key, request_hash)
        if replay:
            return replay
        raise ApiError(409, "already_reviewed", "Diese Karte wurde bereits bewertet.")
    if item.base_version != payload.base_version:
        replay = await replay_review(db, user_id, payload.idempotency_key, request_hash)
        if replay:
            return replay
        raise ApiError(409, "stale_review", "Die Karte wurde bereits an anderer Stelle verändert.")

    progress = await db.scalar(
        select(UserCardProgress)
        .where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.card_id == item.card_id,
            UserCardProgress.direction == item.direction,
        )
        .with_for_update()
    )
    current_version = progress.version if progress else 0
    if current_version != payload.base_version:
        replay = await replay_review(db, user_id, payload.idempotency_key, request_hash)
        if replay:
            return replay
        raise ApiError(409, "stale_review", "Die Karte wurde bereits an anderer Stelle bewertet.")

    if payload.response.type == "typing":
        if study_session.input_mode != "typing":
            raise ApiError(409, "wrong_study_mode", "Diese Lerneinheit verwendet den Aufdeckmodus.")
        fingerprint = answer_fingerprint(payload.response.answer)
        if not item.checked_answer_hash or not hmac.compare_digest(
            fingerprint, item.checked_answer_hash
        ):
            raise ApiError(
                409,
                "answer_not_checked",
                "Bitte prüfe diese Antwort zuerst.",
            )
        matched = match_card_answer(
            payload.response.answer,
            item.solution_snapshot,
            item.accepted_answers_snapshot,
            matcher_profile=item.matcher_profile,
        )
        correct = matched.correct
        effective_rating = payload.response.rating if correct else 0
        answer = payload.response.answer
        kind = match_kind(matched)
        mode = "typing"
    else:
        if study_session.input_mode != "reveal":
            raise ApiError(409, "wrong_study_mode", "Diese Lerneinheit verwendet den Tippmodus.")
        if item.revealed_at is None:
            raise ApiError(409, "answer_not_revealed", "Bitte drehe die Karte zuerst um.")
        correct = payload.response.known
        effective_rating = 2 if correct else 0
        answer = None
        kind = "self_assessment"
        mode = "self_assessment"

    previous_state = (
        SchedulerState(
            phase=progress.phase,
            ease=progress.ease,
            interval_days=progress.interval_days,
            repetitions=progress.repetitions,
            lapses=progress.lapses,
        )
        if progress
        else None
    )
    now = datetime.now(UTC)
    scheduled = schedule_review(previous_state, effective_rating, now)
    next_version = current_version + 1

    if progress:
        progress.phase = scheduled.phase
        progress.ease = scheduled.ease
        progress.interval_days = scheduled.interval_days
        progress.repetitions = scheduled.repetitions
        progress.lapses = scheduled.lapses
        progress.due_at = scheduled.due_at
        progress.last_reviewed_at = now
        progress.last_rating = effective_rating
        progress.version = next_version
    else:
        db.add(
            UserCardProgress(
                user_id=user_id,
                card_id=item.card_id,
                direction=item.direction,
                phase=scheduled.phase,
                ease=scheduled.ease,
                interval_days=scheduled.interval_days,
                repetitions=scheduled.repetitions,
                lapses=scheduled.lapses,
                due_at=scheduled.due_at,
                last_reviewed_at=now,
                last_rating=effective_rating,
                version=next_version,
            )
        )
    item.reviewed_at = now
    await db.flush()
    reviewed = int(
        await db.scalar(
            select(func.count())
            .select_from(StudySessionItem)
            .where(
                StudySessionItem.session_id == session_id,
                StudySessionItem.reviewed_at.is_not(None),
            )
        )
        or 0
    )
    total = int(
        await db.scalar(
            select(func.count())
            .select_from(StudySessionItem)
            .where(StudySessionItem.session_id == session_id)
        )
        or 0
    )
    complete = reviewed == total
    if complete:
        study_session.completed_at = now

    previous_correct = int(
        await db.scalar(
            select(func.count())
            .select_from(ReviewEvent)
            .join(StudySessionItem, StudySessionItem.id == ReviewEvent.session_item_id)
            .where(
                StudySessionItem.session_id == session_id,
                ReviewEvent.was_correct.is_(True),
            )
        )
        or 0
    )
    result = ReviewResult(
        correct=correct,
        effective_rating=effective_rating,
        match_kind=kind,
        solution=item.solution_snapshot,
        due_at=scheduled.due_at,
        interval_days=scheduled.interval_days,
        version=next_version,
        reviewed=reviewed,
        correct_reviewed=previous_correct + int(correct),
        total=total,
        complete=complete,
    )
    db.add(
        ReviewEvent(
            session_item_id=item.id,
            idempotency_key=payload.idempotency_key,
            request_hash=request_hash,
            user_id=user_id,
            card_id=item.card_id,
            direction=item.direction,
            base_version=current_version,
            rating=effective_rating,
            mode=mode,
            was_correct=correct,
            response_ms=payload.response_ms,
            answer=answer,
            next_due_at=scheduled.due_at,
            response_json=result.model_dump(mode="json"),
        )
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        replay = await replay_review(db, user_id, payload.idempotency_key, request_hash)
        if replay:
            return replay
        raise ApiError(409, "review_conflict", "Diese Karte wurde gleichzeitig bewertet.") from exc

    response.headers["Cache-Control"] = "private, no-store"
    return result
