FROM python:3.12.11-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv

RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /build
COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

FROM builder AS test

COPY backend/requirements-dev.txt ./requirements-dev.txt
RUN pip install -r requirements-dev.txt

WORKDIR /srv/app
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY backend/tests ./tests
COPY backend/pyproject.toml ./pyproject.toml
COPY data/decks ./data/decks
COPY examples ./examples

CMD ["pytest"]

FROM python:3.12.11-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --system --gid 10001 vocabulary_trainer \
    && useradd --system --uid 10001 --gid vocabulary_trainer --home-dir /srv/app --shell /usr/sbin/nologin vocabulary_trainer

WORKDIR /srv/app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=vocabulary_trainer:vocabulary_trainer backend/app ./app
COPY --chown=vocabulary_trainer:vocabulary_trainer backend/alembic ./alembic
COPY --chown=vocabulary_trainer:vocabulary_trainer backend/alembic.ini ./alembic.ini
COPY --chown=vocabulary_trainer:vocabulary_trainer data/decks ./data/decks

USER vocabulary_trainer
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
