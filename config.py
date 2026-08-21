import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    # Use an environment variable for security, with a fallback
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-secret-key'

    # Get the database URL from the environment, or use local SQLite
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///vocab.db')

    # SQLAlchemy 1.4+ requires 'postgresql://' instead of 'postgres://'
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Gemini AI Configuration
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.6-flash').strip()
    AI_REQUEST_TIMEOUT = int(os.environ.get('AI_REQUEST_TIMEOUT', '30'))