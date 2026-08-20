install:
	python -m pip install -e .

dev:
	flask --app wsgi run

test:
	pytest

check:
	ruff check .

admin:
	flask --app wsgi create-admin
