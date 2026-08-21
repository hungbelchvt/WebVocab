"""
Deployment & Configuration Verification Tests for WebVocab.
Validates:
1. /health endpoint behavior and security.
2. Config database_url normalization ('postgres://' -> 'postgresql://' with sslmode=require).
3. PostgreSQL connection pooling options (pool_pre_ping=True, pool_recycle=300, connect_args sslmode=require).
4. SQLite connection options compatibility (pool_pre_ping=True without PostgreSQL connect_args).
5. SECRET_KEY production enforcement.
6. PostgreSQL schema and DDL compatibility across all models.
"""

import os
import unittest
from unittest.mock import patch
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from app import create_app
from app.models import db, User, Topic, Word, WordProgress
from config import Config


class TestDeploymentConfiguration(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def tearDown(self):
        import importlib
        import config
        importlib.reload(config)

    def test_health_check_endpoint(self):
        """Verify /health returns 200 OK and valid JSON without exposing secrets."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIsNotNone(json_data)
        self.assertEqual(json_data.get('status'), 'ok')
        # Ensure no secrets or sensitive keys are leaked
        self.assertNotIn('SECRET_KEY', str(json_data))
        self.assertNotIn('DATABASE_URL', str(json_data))
        self.assertNotIn('GEMINI_API_KEY', str(json_data))

    def test_database_url_normalization_postgres_prefix(self):
        """Verify that Render postgres:// URLs are converted to postgresql:// with sslmode=require."""
        with patch.dict(os.environ, {'DATABASE_URL': 'postgres://user:pass@host:5432/dbname'}, clear=False):
            import importlib
            import config
            importlib.reload(config)
            self.assertEqual(
                config.Config.SQLALCHEMY_DATABASE_URI,
                'postgresql://user:pass@host:5432/dbname?sslmode=require'
            )

    def test_database_url_postgresql_preserved(self):
        """Verify postgresql:// URLs remain intact and include sslmode=require."""
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://user:pass@host:5432/dbname'}, clear=False):
            import importlib
            import config
            importlib.reload(config)
            self.assertEqual(
                config.Config.SQLALCHEMY_DATABASE_URI,
                'postgresql://user:pass@host:5432/dbname?sslmode=require'
            )

    def test_postgresql_connection_pool_options(self):
        """Verify pool_pre_ping, pool_recycle, and SSL connect_args are configured for PostgreSQL."""
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://user:pass@host:5432/dbname'}, clear=False):
            import importlib
            import config
            importlib.reload(config)
            engine_opts = config.Config.SQLALCHEMY_ENGINE_OPTIONS
            self.assertTrue(engine_opts.get("pool_pre_ping"))
            self.assertEqual(engine_opts.get("pool_recycle"), 300)
            self.assertEqual(engine_opts.get("pool_size"), 5)
            self.assertEqual(engine_opts.get("max_overflow"), 10)
            self.assertEqual(engine_opts.get("connect_args", {}).get("sslmode"), "require")

    def test_database_url_sqlite_fallback(self):
        """Verify SQLite is used as local development fallback when DATABASE_URL is not set."""
        env_without_db = {k: v for k, v in os.environ.items() if k != 'DATABASE_URL'}
        with patch.dict(os.environ, env_without_db, clear=True):
            import importlib
            import config
            importlib.reload(config)
            self.assertEqual(
                config.Config.SQLALCHEMY_DATABASE_URI,
                'sqlite:///vocab.db'
            )
            # Ensure SQLite engine options do not pass postgresql connect_args
            engine_opts = config.Config.SQLALCHEMY_ENGINE_OPTIONS
            self.assertTrue(engine_opts.get("pool_pre_ping"))
            self.assertNotIn("connect_args", engine_opts)

    def test_secret_key_required_in_production(self):
        """Verify SECRET_KEY is strictly required when RENDER or FLASK_ENV=production is set."""
        env_render_no_secret = {
            'RENDER': 'true',
            'SECRET_KEY': '',
            'DATABASE_URL': 'sqlite:///:memory:'
        }
        with patch.dict(os.environ, env_render_no_secret, clear=False):
            import importlib
            import config
            with self.assertRaises(ValueError) as ctx:
                importlib.reload(config)
            self.assertIn("SECRET_KEY environment variable must be set in production", str(ctx.exception))

    def test_postgresql_ddl_compilation_all_models(self):
        """Verify all SQLAlchemy models compile valid PostgreSQL DDL statements."""
        dialect = postgresql.dialect()
        models = [User, Topic, Word, WordProgress]

        for model in models:
            ddl = str(CreateTable(model.__table__).compile(dialect=dialect))
            self.assertIsInstance(ddl, str)
            self.assertGreater(len(ddl), 0)

        # Verify password_hash supports up to 256 chars on User
        user_ddl = str(CreateTable(User.__table__).compile(dialect=dialect))
        self.assertIn("VARCHAR(256)", user_ddl)


if __name__ == '__main__':
    unittest.main()

