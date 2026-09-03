.PHONY: up down logs build test lint clean-db backup restore

BACKUP_DIR ?= backups
BACKUP_TIMESTAMP := $(shell date +%Y%m%d-%H%M%S)
BACKUP_FILE ?= $(BACKUP_DIR)/vocabulary-trainer-$(BACKUP_TIMESTAMP).dump

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=150

build:
	docker compose build

test:
	docker compose --profile test run --rm --no-deps backend-test pytest
	docker compose --profile test run --rm --no-deps frontend-test npm test

lint:
	docker compose --profile test run --rm --no-deps backend-test ruff check --no-cache app alembic tests
	docker compose --profile test run --rm --no-deps frontend-test npm run lint

clean-db:
	@test "$(CONFIRM)" = "delete-all-local-data" || (echo "Abbruch: erneut mit CONFIRM=delete-all-local-data ausführen."; exit 1)
	docker compose down --volumes

backup:
	mkdir -p "$(dir $(BACKUP_FILE))"
	docker compose exec -T db pg_dump -U vocabulary_trainer -d vocabulary_trainer -Fc > "$(BACKUP_FILE).partial"
	docker compose exec -T db pg_restore --list < "$(BACKUP_FILE).partial" > /dev/null
	mv "$(BACKUP_FILE).partial" "$(BACKUP_FILE)"
	@echo "Backup geprüft und gespeichert: $(BACKUP_FILE)"

restore:
	@test -n "$(BACKUP_FILE)" || (echo "BACKUP_FILE fehlt."; exit 1)
	@test "$(CONFIRM)" = "restore" || (echo "Abbruch: erneut mit BACKUP_FILE=... CONFIRM=restore ausführen."; exit 1)
	@test -f "$(BACKUP_FILE)" || (echo "Backup nicht gefunden: $(BACKUP_FILE)"; exit 1)
	docker compose up -d db
	docker compose stop backend frontend
	docker compose exec -T db pg_restore --list < "$(BACKUP_FILE)" > /dev/null
	docker compose exec -T db pg_restore --clean --if-exists --no-owner --exit-on-error --single-transaction -U vocabulary_trainer -d vocabulary_trainer < "$(BACKUP_FILE)"
	docker compose up -d backend frontend
