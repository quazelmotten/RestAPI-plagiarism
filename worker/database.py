from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from config import settings

DATABASE_URL = (
    f"postgresql+psycopg2://{settings.db_user}:{settings.db_pass}@"
    f"{settings.db_host}:{settings.db_port}/{settings.db_name}"
)
Base = declarative_base()

# Use connection pool for concurrent access
# Pool size should be >= max_workers * threads_per_worker
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=getattr(settings, 'db_pool_size', 10),
    max_overflow=getattr(settings, 'db_max_overflow', 20),
    pool_timeout=getattr(settings, 'db_pool_timeout', 30),
    pool_pre_ping=True,  # Check connections before using
)
Session = sessionmaker(engine)


@contextmanager
def get_session():
    """Get a database session as a context manager."""
    session = Session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
