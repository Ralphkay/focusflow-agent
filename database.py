# database.py (Final Corrected Version)

import logging
import os
from contextlib import contextmanager
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from threading import Lock

from client_models import Base, AppConfig
from config import APP_DATA_PATH

logger = logging.getLogger(__name__)

db_lock = Lock()

DATABASE_FILE = os.path.join(APP_DATA_PATH, "duckdb.db")
DATABASE_URL = f"duckdb:///{DATABASE_FILE}"


def check_and_migrate_db(engine, metadata):
    """
    Checks if the database schema needs to be updated.
    If the 'app_configs' table is missing the 'pushed_to_central' column,
    it deletes the old database file to trigger a full recreation.
    """
    if not os.path.exists(DATABASE_FILE):
        logger.info("Database file does not exist. Will be created on startup.")
        return

    try:
        inspector = inspect(engine)
        if inspector.has_table('app_configs'):
            columns = [col['name'] for col in inspector.get_columns('app_configs')]
            if 'pushed_to_central' not in columns:
                logger.critical(
                    "Database schema is outdated. 'pushed_to_central' column is missing from 'app_configs'.")
                logger.critical("Deleting old database file to force a schema migration on next run.")
                os.remove(DATABASE_FILE)
                return

        logger.info("Database schema is up-to-date.")
    except Exception as e:
        logger.error(f"Error during database schema check: {e}", exc_info=True)
        if os.path.exists(DATABASE_FILE):
            os.remove(DATABASE_FILE)
            logger.warning("Deleted database file due to schema check error.")


engine = create_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    connect_args={'read_only': False}
)

readonly_engine = create_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    connect_args={'read_only': True}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ReadOnlySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=readonly_engine)


def init_db():
    """Initializes the database and creates tables if they don't exist."""
    try:
        logger.info("Attempting to initialize or verify local DuckDB schema.")
        with db_lock:
            check_and_migrate_db(engine, Base.metadata)
            Base.metadata.create_all(bind=engine)
        logger.info("Local DuckDB schema is initialized and verified.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise


@contextmanager
def get_db_session():
    """Provides a transactional session for the WRITER process."""
    session = SessionLocal()
    try:
        yield session
    except Exception as e:
        logger.error(f"Database session error: {e}", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_readonly_db_session():
    """Provides a read-only session for the READER process (the dashboard UI)."""
    session = ReadOnlySessionLocal()
    try:
        yield session
    except Exception as e:
        logger.error(f"Read-only database session error: {e}", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()