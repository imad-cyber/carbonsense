# Importing all models here ensures SQLAlchemy knows about them
# when Alembic scans for changes. If you forget to add a model here,
# Alembic won't include it in migrations.
from app.models.company import Company
from app.models.emission import EmissionRecord
from app.models.user import User