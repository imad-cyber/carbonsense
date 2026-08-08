#!/bin/bash
# One-command setup for a new developer
set -e

echo "Setting up CarbonSense..."
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy env template
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Edit .env with your settings before continuing"
fi

# Run DB migrations
alembic upgrade head

# Seed admin user
python scripts/seed_admin.py

# Generate training data
python scripts/generate_training_data.py

# Train initial models
python scripts/train_models.py

echo "✅ Setup complete. Run: uvicorn app.main:app --reload"
