.PHONY: help up down logs restart prod-up prod-down test lint format typecheck register-webhook

COMPOSE_DEV  := docker compose
COMPOSE_PROD := docker compose -f docker-compose.yml -f docker-compose.prod.yml

help:  ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

up:  ## bring up dev stack
	$(COMPOSE_DEV) up -d --build

down:  ## stop dev stack
	$(COMPOSE_DEV) down

logs:  ## tail all services
	$(COMPOSE_DEV) logs -f --tail=100

restart:  ## restart api + worker
	$(COMPOSE_DEV) restart api worker

prod-up:  ## bring up prod stack (with Caddy)
	$(COMPOSE_PROD) up -d --build

prod-down:  ## stop prod stack
	$(COMPOSE_PROD) down

test:  ## run pytest
	pytest -q

lint:  ## ruff check
	ruff check src tests
	ruff format --check src tests

format:  ## ruff format
	ruff check --fix src tests
	ruff format src tests

typecheck:  ## mypy strict
	mypy src

register-webhook:  ## set Telegram webhook (reads .env)
	@./scripts/register_webhook.sh
