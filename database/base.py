# database/base.py
from sqlalchemy.orm import declarative_base

# Global base for all models (used by Alembic)
Base = declarative_base()
