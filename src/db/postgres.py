"""
PostgreSQL database connection and session management.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from src.config import Config

# SQLAlchemy base for models
Base = declarative_base()

# Engine singleton
_engine = None


def get_engine():
    """Get or create the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            Config.get_postgres_url(),
            echo=False,  # Set True for SQL debugging
            pool_pre_ping=True
        )
    return _engine


def get_session():
    """Create a new database session."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def init_db():
    """Initialize database tables."""
    from src.models import gl_transaction  # Import models to register them
    engine = get_engine()
    Base.metadata.create_all(engine)


def test_connection():
    """Test the PostgreSQL connection."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        return True, "Connected to PostgreSQL"
    except Exception as e:
        return False, str(e)

