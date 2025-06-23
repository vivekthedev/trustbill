test:
	python -m pytest 

test-cov:
	python -m pytest --cov=trustbill --cov-report=term --cov-report=html

test-unit:
	python -m pytest tests/unit

install-dev:
	pip install -r requirements-dev.txt

setup: install-dev
