# Vocabulary Trainer

Vocabulary Trainer is a self-hosted vocabulary learning app with one catalogue managed by
administrators and independent learning progress for every user. Decks can use
any two languages or, more generally, any prompt/answer pair. No vocabulary is
hardcoded into the application.

The interface supports English, Simplified Chinese, Hindi, Spanish, and German.
Anonymous visitors use their browser's preferred supported language. Each
account stores its own interface language; existing accounts initialize it on
their first login and can change it at any time in Settings. The content model,
language tags, answer aliases, sections, study directions, and matching
profiles remain deck-specific and independent from the interface language.

## What it includes

- centrally managed shared decks, sections, and cards;
- draft, published, and archived deck states;
- an administrator UI for managing users, editing content, and importing JSON manifests;
- forward, reverse, and mixed study directions;
- typing and self-assessment modes with spaced repetition;
- per-user progress, favorites, editable name and login email, settings, sessions, and review history;
- automatic browser-language detection with a persistent per-account override;
- frozen study-session content, so an administrator edit cannot change an
  answer halfway through a learner's session;
- transactional, versioned, idempotent imports with stable content IDs;
- FastAPI, React, PostgreSQL, Alembic, and a Docker Compose deployment.

## Start locally

Docker Desktop with Docker Compose is the only runtime prerequisite.

```bash
docker compose up --build -d
```

Open <http://localhost:3000>. The first registered account automatically becomes
an administrator. A fresh installation intentionally has no deck; the **Admin**
navigation item lets that account:

1. view all accounts and promote trusted users to administrators;
2. create a draft deck;
3. add optional sections and cards, or import a complete JSON manifest;
4. publish the deck for every user.

The command-line role tool remains available for administrative recovery:

```bash
docker compose exec backend python -m app.admin promote admin@example.com
```

For a quick trial, import `examples/synthetic-demo.json` in the admin UI. New
imports stay in draft until an administrator publishes them.

```text
Admin edits one shared catalogue
              |
        published decks
       /       |       \
   user A    user B    user C
  progress   progress  progress
```

Existing installations of the former Latin-only version are migrated without
discarding their catalogue, accounts, favorites, progress, or study history.
The former vocabulary becomes a published `Latin – German` deck. Fresh installs
do not receive that deck.

## Deck imports

The manifest format is documented in [docs/deck-format.md](docs/deck-format.md).
Every deck records its own side labels, BCP 47-style language tags, matching
profiles, sections, answer aliases, license, attribution, and arbitrary card
metadata.

Stable deck, section, and card keys are important: they let a newer manifest
update the shared catalogue while keeping every user's progress attached to the
same cards. Removed cards are archived instead of deleted.

Only redistribute vocabulary you are licensed to share. The MIT license in this
repository covers the software; a deck's content license belongs in its own
manifest. The included two-card example contains generated nonce strings and
does not require a separate content license.

An installation may also bundle bootstrap manifests in `data/decks/` before
building. The startup job imports a slug only if it is not already present, so a
restart never overwrites later administrator edits.

## Architecture

- `frontend/`: React, TypeScript, and Vite, served by nginx;
- `backend/`: FastAPI, SQLAlchemy, Alembic, and server-side sessions;
- `db`: PostgreSQL in a persistent Docker volume;
- nginx serves the frontend and proxies `/api/*` under the same origin.

Vocabulary Trainer does not require an OpenAI API key or an external hosted service.

## Development

To run the database while developing the two applications directly:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db
```

Backend (Python 3.12):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

Frontend (Node.js 22 or newer):

```bash
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to `http://localhost:8000` during development. Copy
`.env.example` to `.env` before changing local defaults; the database passwords
and ports in both sets of variables must match.

## Tests and checks

```bash
make test
make lint
make build
```

The automated workflows cover administrator authorization, shared catalogue
visibility, per-user isolation, deck/section scoping, both study modes, answer
matching, scheduler behavior, session snapshots, review idempotency, import
conflicts, account profile updates, and account deletion.

## Backup and restore

Create and validate a PostgreSQL backup in the ignored `backups/` directory:

```bash
make backup
```

Restore only with explicit confirmation:

```bash
make restore BACKUP_FILE=backups/vocabulary-trainer-YYYYMMDD-HHMMSS.dump CONFIRM=restore
```

To remove the local database, including all accounts, catalogue content, and
progress:

```bash
make clean-db CONFIRM=delete-all-local-data
```

`docker compose down` alone keeps the named `vocabulary_trainer_postgres` volume.

## Production checklist

- Set a long random `POSTGRES_PASSWORD` before the first database start.
- Set `ENVIRONMENT=production`, `COOKIE_SECURE=true`, the exact HTTPS origin in
  `ALLOWED_ORIGINS`, and the real host names in `ALLOWED_HOSTS`.
- Terminate TLS at a reverse proxy that replaces untrusted forwarding headers.
- Keep PostgreSQL private, back it up regularly, and test restore procedures.
- Register the installation owner first: the first account becomes an
  administrator, and all later registrations start as learners.
- Grant additional administrator access deliberately from the Admin area.
- Review each deck's license and attribution before publishing it.

## License

Vocabulary Trainer's source code is available under the [MIT License](LICENSE). See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for included third-party
notices.
