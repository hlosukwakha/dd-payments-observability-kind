SHELL := /bin/bash

.PHONY: up down status shell pf logs-%

up:
	docker compose run --rm ctl bash ./scripts/bootstrap.sh

down:
	docker compose run --rm ctl bash ./scripts/down.sh

status:
	docker compose run --rm ctl bash ./scripts/status.sh

shell:
	docker compose run --rm ctl bash

pf:
	@echo "Port-forwarding web-frontend => http://localhost:8080"
	docker compose run --rm --service-ports ctl bash ./scripts/port-forward.sh

logs-%:
	docker compose run --rm ctl bash ./scripts/logs.sh $*
