.PHONY: setup run worker flower test migrate train lint docker-up docker-down docker-logs mlflow ingest-rag frontend

setup:
	python -m venv venv && . venv/bin/activate && pip install -r requirements.txt

run:
	uvicorn app.main:app --reload

worker:
	celery -A app.worker.celery_app worker --loglevel=info

flower:
	celery -A app.worker.celery_app flower --port=5555

test:
	pytest tests/ -v --cov=app

migrate:
	alembic upgrade head

train:
	python scripts/generate_training_data.py && python scripts/train_models.py

lint:
	ruff check app/ && mypy app/ --ignore-missing-imports

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f api worker

mlflow:
	mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000

ingest-rag:
	curl -X POST http://localhost:8000/api/v1/rag/ingest/regulatory \
	     -H "Authorization: Bearer $$TOKEN"

frontend:
	cd frontend && npm run dev
