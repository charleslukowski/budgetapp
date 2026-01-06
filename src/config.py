"""
Configuration loader for environment variables.
"""

import os
from dotenv import load_dotenv

# Load .env from project root
load_dotenv()


class Config:
    """Application configuration from environment variables."""
    
    # PostgreSQL
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
    POSTGRES_DATABASE = os.getenv('POSTGRES_DATABASE', 'budgetapp')
    POSTGRES_USER = os.getenv('POSTGRES_USER')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
    
    # Infinium DB2
    DB2_DSN = os.getenv('DB2_DSN', 'CRYSTAL-CLIENT EXPRESS')
    INFINIUM_USER = os.getenv('INFINIUM_USER')
    INFINIUM_PW = os.getenv('INFINIUM_PW')
    
    @classmethod
    def get_postgres_url(cls):
        """Get SQLAlchemy PostgreSQL connection URL."""
        return (
            f"postgresql://{cls.POSTGRES_USER}:{cls.POSTGRES_PASSWORD}"
            f"@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DATABASE}"
        )
    
    @classmethod
    def get_db2_connection_string(cls):
        """Get pyodbc DB2 connection string."""
        return f"DSN={cls.DB2_DSN};UID={cls.INFINIUM_USER};PWD={cls.INFINIUM_PW}"
