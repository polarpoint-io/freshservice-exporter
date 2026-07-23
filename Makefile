.PHONY: install test lint run scrape docker-build docker-up

install:
	python3 -m pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check .

run:
	freshservice-exporter

scrape:
	PYTHONPATH=. python3 scripts/scrape_once.py

docker-build:
	docker build -t freshservice-exporter:local .

docker-up:
	docker compose up --build
