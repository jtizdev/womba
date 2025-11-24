.PHONY: install test clean build deploy docker

# Installation
install:
	pip install -r requirements-minimal.txt

install-dev:
	pip install -r requirements-minimal.txt
	pip install -e .

# Testing
test:
	pytest tests/ -v

test-integration:
	pytest tests/integration/ -v

test-unit:
	pytest tests/unit/ -v

test-coverage:
	pytest tests/ --cov=src --cov-report=html --cov-report=term

# Code quality
lint:
	flake8 src/ tests/
	black --check src/ tests/

format:
	black src/ tests/
	isort src/ tests/

# Build
build:
	python setup.py sdist bdist_wheel

clean:
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type f -name '.coverage' -delete
	rm -rf htmlcov/
	rm -f test_plan_*.json

# Docker
docker-build:
	docker build -t womba:latest .

docker-run:
	docker run --env-file .env womba:latest generate $(STORY)

docker-push:
	docker tag womba:latest plainid/womba:latest
	docker push plainid/womba:latest

# Deployment
deploy-pypi:
	twine upload dist/*

deploy-test-pypi:
	twine upload --repository-url https://test.pypi.org/legacy/ dist/*

# Usage examples
example-generate:
	python3 generate_test_plan.py PROJ-12345

example-upload:
	python3 upload_to_zephyr.py PROJ-12345

example-evaluate:
	python3 evaluate_quality.py PROJ-12345

# Development
dev:
	python3 -m pip install -e .

dev-setup:
	python3 setup_env.py

# Help
help:
	@echo "Womba - AI-Powered Test Generation"
	@echo ""
	@echo "Available commands:"
	@echo "  make install          - Install dependencies"
	@echo "  make install-dev      - Install in development mode"
	@echo "  make test             - Run all tests"
	@echo "  make test-integration - Run integration tests"
	@echo "  make test-coverage    - Run tests with coverage"
	@echo "  make lint             - Check code style"
	@echo "  make format           - Format code"
	@echo "  make build            - Build package"
	@echo "  make clean            - Clean build artifacts"
	@echo "  make docker-build     - Build Docker image"
	@echo "  make docker-run       - Run Docker container"
	@echo "  make deploy-pypi      - Deploy to PyPI"
	@echo "  make example-generate - Example: generate tests"
	@echo "  make help             - Show this help"

