SHELL := /bin/bash
COMPOSE := docker compose
-include .env
export

.PHONY: up down logs ps shell-db env fetch-ws-plugin convert-assets reset

## Bring the whole stack up (builds images, clones AtomCMS source on first run).
up: env cms/src
	@mkdir -p data/db data/emulator data/cms/storage
	$(COMPOSE) up -d --build
	@$(COMPOSE) ps

## Generate .env from .env.example (no-op if it exists). Deliberately NOT a
## `.env:` file rule — with `-include .env` above, make would silently
## regenerate a missing .env with FRESH secrets on ANY target (even `make
## logs`), desyncing them from a ./data/db that still holds the old password.
env:
	@./scripts/gen-env.sh

cms/src:
	git clone https://github.com/atom-retros/atomcms.git cms/src

## Stop containers. NEVER touches ./data — safe to run any time.
down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200

ps:
	$(COMPOSE) ps

## Root MariaDB shell into the game database.
shell-db:
	$(COMPOSE) exec db mariadb -uroot -p$(DB_ROOT_PASSWORD) $(DB_DATABASE)

## Download the NitroWebsockets plugin jar from the official Krews repo.
## Explicit on purpose: it's a compiled binary, so fetching is a knowing act.
## (Built against MS 3.x; the community runs it on 4.0.x — see artifacts/README.md.)
## Download to .part then mv: an interrupted transfer must never leave a
## truncated jar that would pass the emulator's plugin-presence check.
fetch-ws-plugin:
	@mkdir -p artifacts/arcturus/plugins
	curl -fL -o artifacts/arcturus/plugins/NitroWebsockets-3.2.jar.part \
	  https://git.krews.org/morningstar/nitrowebsockets-for-ms/-/raw/master/target/NitroWebsockets-3.2.jar
	mv artifacts/arcturus/plugins/NitroWebsockets-3.2.jar.part artifacts/arcturus/plugins/NitroWebsockets-3.2.jar
	@echo "Saved artifacts/arcturus/plugins/NitroWebsockets-3.2.jar"

## One-shot: convert ./artifacts/flash-assets SWFs (+ official furniture) into
## .nitro bundles + gamedata in ./artifacts/nitro-assets. Exits when done;
## re-running resumes (existing outputs are skipped, never overwritten).
convert-assets:
	$(COMPOSE) --profile tools build converter
	$(COMPOSE) --profile tools run --rm converter

## ─── DESTRUCTIVE ─── wipes every account, item, currency, room, upload, log.
reset:
	@echo "!!! DESTRUCTIVE RESET !!!"
	@echo "This will PERMANENTLY DELETE:"
	@echo "  - all pixelrp containers and the docker network"
	@echo "  - ./data/db          (every account, currency, item, room, progression)"
	@echo "  - ./data/emulator    (emulator config.ini and logs)"
	@echo "  - ./data/cms         (CMS storage: uploads, logs, seed marker)"
	@echo "Your ./artifacts files and .env are NOT touched."
	@read -p "Type 'yes-destroy-my-data' to proceed: " confirm && \
	  [ "$$confirm" = "yes-destroy-my-data" ] || { echo "Aborted — nothing deleted."; exit 1; }
	$(COMPOSE) down -v --remove-orphans
	rm -rf ./data
	@echo "Reset complete. Next 'make up' re-initializes the DB from ./artifacts/sql."
