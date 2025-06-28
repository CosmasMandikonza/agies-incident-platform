.PHONY: help install test lint format deploy-dev deploy-prod clean

# Default target
help:
	@echo "Available commands:"
	@echo "  make install       - Install all dependencies"
	@echo "  make test         - Run all tests"
	@echo "  make lint         - Run linting checks"
	@echo "  make format       - Format code"
	@echo "  make build        - Build SAM application"
	@echo "  make deploy-dev   - Deploy to development"
	@echo "  make deploy-prod  - Deploy to production"
	@echo "  make clean        - Clean build artifacts"
	@echo "  make local        - Start local development environment"
	@echo "  make chaos        - Run chaos experiments"

# Install dependencies
install:
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install
	@echo "Installing pre-commit hooks..."
	pre-commit install
	@echo "Installation complete!"

# Testing targets
test: test-unit test-integration

test-unit:
	@echo "Running unit tests..."
	pytest tests/unit -v --cov=src --cov-report=term-missing --cov-report=html

test-integration:
	@echo "Running integration tests..."
	pytest tests/integration -v

test-e2e:
	@echo "Running end-to-end tests..."
	pytest tests/e2e -v

# Code quality targets
lint: lint-python lint-frontend

lint-python:
	@echo "Linting Python code..."
	black --check src/ tests/
	isort --check-only src/ tests/
	flake8 src/ tests/
	mypy src/ --ignore-missing-imports
	bandit -r src/

lint-frontend:
	@echo "Linting frontend code..."
	cd frontend && npm run lint

format: format-python format-frontend

format-python:
	@echo "Formatting Python code..."
	black src/ tests/
	isort src/ tests/

format-frontend:
	@echo "Formatting frontend code..."
	cd frontend && npm run format

# Security scanning
security-scan:
	@echo "Running security scans..."
	safety check
	bandit -r src/ -f json -o bandit-report.json
	checkov -d infrastructure/
	cd frontend && npm audit

# Build targets
build: build-layers build-sam build-frontend

build-layers:
	@echo "Building Lambda layers..."
	cd infrastructure/layers && ./build-layers.sh

build-sam:
	@echo "Building SAM application..."
	sam build --template infrastructure/template.yaml

build-frontend:
	@echo "Building frontend..."
	cd frontend && npm run build

# Deployment targets
deploy-dev: build
	@echo "Deploying to development environment..."
	sam deploy \
		--config-file samconfig.toml \
		--config-env dev \
		--parameter-overrides \
			Environment=dev \
			LogLevel=DEBUG \
			EnableTracing=true

deploy-prod: test security-scan
	@echo "Deploying to production environment..."
	@read -p "Are you sure you want to deploy to production? (y/N) " confirm; \
	if [ "$$confirm" = "y" ]; then \
		sam deploy \
			--config-file samconfig.toml \
			--config-env prod \
			--parameter-overrides \
				Environment=prod \
				LogLevel=INFO \
				EnableTracing=true \
				EnableAutoScaling=true; \
	else \
		echo "Production deployment cancelled."; \
	fi

# Local development
local: local-start

local-start:
	@echo "Starting local development environment..."
	docker-compose up -d
	sam local start-api \
		--env-vars tests/local/env.json \
		--docker-network aegis-network &
	cd frontend && npm start

local-stop:
	@echo "Stopping local development environment..."
	docker-compose down
	pkill -f "sam local"

# DynamoDB local
dynamodb-local:
	@echo "Starting DynamoDB local..."
	docker run -d -p 8000:8000 \
		--name dynamodb-local \
		amazon/dynamodb-local \
		-jar DynamoDBLocal.jar -sharedDb

dynamodb-admin:
	@echo "Starting DynamoDB admin UI..."
	docker run -d -p 8001:8001 \
		--name dynamodb-admin \
		--link dynamodb-local:dynamodb \
		aaronshaf/dynamodb-admin

# Logs and monitoring
logs-dev:
	@echo "Tailing development logs..."
	sam logs --stack-name aegis-dev --tail

logs-prod:
	@echo "Tailing production logs..."
	sam logs --stack-name aegis-prod --tail

# Chaos engineering
chaos: chaos-prepare chaos-run

chaos-prepare:
	@echo "Preparing chaos experiments..."
	cd chaos-experiments && \
	pip install -r requirements.txt

chaos-run:
	@echo "Running chaos experiments..."
	cd chaos-experiments && \
	python run_experiments.py --environment dev

# Documentation
docs: docs-build

docs-build:
	@echo "Building documentation..."
	cd docs && \
	sphinx-build -b html . _build/html

docs-serve:
	@echo "Serving documentation..."
	cd docs/_build/html && \
	python -m http.server 8080

# Performance testing
perf-test:
	@echo "Running performance tests..."
	locust -f tests/performance/locustfile.py \
		--host=$$(aws cloudformation describe-stacks \
			--stack-name aegis-dev \
			--query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
			--output text)

# Cleanup
clean:
	@echo "Cleaning build artifacts..."
	rm -rf .aws-sam/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf node_modules/
	rm -rf frontend/build/
	rm -rf frontend/node_modules/
	rm -rf **