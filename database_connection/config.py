# database/config.py
"""
Database configuration and connection management for PostgreSQL with NeonDB.
Handles environment variables and SQLAlchemy engine setup.
"""

import os
import sys
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(".../")))
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import OperationalError
from typing import AsyncIterator
from sqlalchemy import text, MetaData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class DatabaseConfig:
    """
    Configuration class for database connection settings.
    Supports both direct connection strings and component-based configuration.
    """
    
    def __init__(self):
        # Primary: Use direct DATABASE_URL if provided (for NeonDB)
        self.database_url = os.getenv("DATABASE_URL")
        
        # Fallback: Construct from individual components
        if not self.database_url:
            self.db_host = os.getenv("DB_HOST", "")
            self.db_port = os.getenv("DB_PORT", "")
            self.db_name = os.getenv("DB_NAME", "")
            self.db_user = os.getenv("DB_USER", "")
            self.db_password = os.getenv("DB_PASSWORD", "")
            
            # Construct PostgreSQL connection URL
            self.database_url = f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
            
        
        # Connection pool settings
        # self.pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        # self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        # self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        # self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
        
        # Echo SQL queries for debugging (set to False in production)
        # self.echo_sql = os.getenv("DB_ECHO", "false").lower() == "true"
    
    # def get_engine_kwargs(self):
    #     """
    #     Returns dictionary of SQLAlchemy engine configuration parameters.
    #     """
    #     # For serverless databases like NeonDB, use NullPool to avoid connection pooling issues
    #     if "neon.tech" in self.database_url or os.getenv("DB_USE_NULL_POOL", "false").lower() == "true":
    #         return {
    #             "poolclass": NullPool,
    #             "echo": self.echo_sql,
    #         }
        
    #     # Standard connection pooling for traditional PostgreSQL
    #     return {
    #         "pool_size": self.pool_size,
    #         "max_overflow": self.max_overflow,
    #         "pool_timeout": self.pool_timeout,
    #         "pool_recycle": self.pool_recycle,
    #         "echo": self.echo_sql,
    #     }


# Global configuration instance
config = DatabaseConfig()

# Create SQLAlchemy engine with appropriate settings
engine = create_async_engine(
    config.database_url, # type: ignore
    echo = True,
    future = True
)


# Configure session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)

async def init_db(drop: bool = False):
    """Initialize database schema from models."""
    async with engine.begin() as conn:
        if drop:
            # ⚠️ Dangerous in prod: drops all tables in schema
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database schema initialized")