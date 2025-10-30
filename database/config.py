# database/config.py
"""
Database configuration and connection management for PostgreSQL with NeonDB.
Handles environment variables and SQLAlchemy engine setup.
"""

import os
import logging
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import OperationalError
from typing import AsyncIterator

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Handles PostgreSQL/NeonDB configuration via .env or components."""

    def __init__(self) -> None:
        # Prefer a full DATABASE_URL
        url_from_env = os.getenv("DATABASE_URL")

        if url_from_env:
            self.database_url: str = url_from_env.strip()
        else:
            db_host = os.getenv("DB_HOST", "localhost")
            db_port = os.getenv("DB_PORT", "5432")
            db_name = os.getenv("DB_NAME", "postgres")
            db_user = os.getenv("DB_USER", "postgres")
            db_password = os.getenv("DB_PASSWORD", "")

            # Build a valid async URL
            if db_port:
                self.database_url = (
                    f"postgresql+asyncpg://{db_user}:{db_password}"
                    f"@{db_host}:{db_port}/{db_name}"
                )
            else:
                self.database_url = (
                    f"postgresql+asyncpg://{db_user}:{db_password}"
                    f"@{db_host}/{db_name}"
                )


# Global configuration instance
config = DatabaseConfig()
# print(f"✅ Using database URL: {config.database_url}")

# Create async SQLAlchemy engine
engine = create_async_engine(config.database_url, echo=True, future=True)

# Async session factory
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Dependency for async DB session management."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except OperationalError as e:
            logger.error(f"Database connection error: {e}")
            raise
