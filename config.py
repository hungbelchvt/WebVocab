import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    # Secret key configuration
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        # Require SECRET_KEY in production environments (e.g. Render)
        if os.environ.get('RENDER') or os.environ.get('FLASK_ENV') == 'production' or os.environ.get('ENV') == 'production':
            raise ValueError("SECRET_KEY environment variable must be set in production.")
        SECRET_KEY = 'dev-insecure-secret-key-change-in-production'

    # Database URL: Read from environment, or use local SQLite fallback
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///vocab.db')

    # SQLAlchemy 1.4+ and 2.0+ require 'postgresql://' instead of legacy 'postgres://' (standard on Render)
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    is_postgres = bool(database_url and (
        database_url.startswith("postgresql://") or
        database_url.startswith("postgres://") or
        database_url.startswith("postgresql+psycopg2://")
    ))

    if is_postgres:
        # Ensure sslmode=require is set in URL if not explicitly specified
        if "sslmode=" not in database_url:
            separator = "&" if "?" in database_url else "?"
            database_url = f"{database_url}{separator}sslmode=require"

        # Production-grade PostgreSQL connection pooling for Render Free:
        # - pool_pre_ping: Discards dead/dropped connections before query execution
        # - pool_recycle: Recycles connections every 300s (5m) to avoid idle timeouts
        # - pool_size & max_overflow: Conservative limits appropriate for Render Free limits
        # - connect_args: Enforces SSL requirement on psycopg2 level
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_size": 5,
            "max_overflow": 10,
            "connect_args": {
                "sslmode": "require"
            }
        }
    else:
        # SQLite local development / test configuration
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True
        }

    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Gemini AI Configuration
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.6-flash').strip()
    AI_REQUEST_TIMEOUT = int(os.environ.get('AI_REQUEST_TIMEOUT', '30'))
