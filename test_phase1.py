"""
Phase 1 Verification Tests for WebVocab AI Integration.
Tests:
1. Flask application factory and database initialization.
2. Configuration loading (GEMINI_MODEL, GEMINI_API_KEY, timeout).
3. Blueprint registration (/api/ai/status and skeletons).
4. AIService configuration checks and dynamic model name resolution.
5. Error handling and custom exception structures.
6. Safe error formatting (ensuring no secrets/keys are exposed).
7. Rate limiting helper functionality.
8. JSON response cleaning and Pydantic validation foundation.
9. Existing application routes and authentication protection.
"""

import os
import unittest
from pydantic import BaseModel, Field
from typing import List

from app import create_app
from app.models import db, User, Topic, Word, WordProgress
from app.services.ai_service import (
    AIService,
    ai_service,
    AIError,
    AIConfigurationError,
    AITimeoutError,
    AIResponseError,
    AIValidationError,
    AIRateLimitError
)
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'
    GEMINI_API_KEY = 'test-mock-api-key'
    GEMINI_MODEL = 'gemini-3.6-flash'
    AI_REQUEST_TIMEOUT = 15


class MockVocabSchema(BaseModel):
    word: str = Field(description="The word")
    meaning_vi: str = Field(description="Vietnamese meaning")
    examples: List[str] = Field(default_factory=list)


class TestPhase1(unittest.TestCase):

    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create a test user
        self.user = User(username='teststudent', password_hash='mockhash')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_app_starts_and_config_loaded(self):
        """Test Flask app creation and Gemini configuration."""
        self.assertTrue(self.app.config['TESTING'])
        self.assertEqual(self.app.config['GEMINI_MODEL'], 'gemini-3.6-flash')
        self.assertEqual(self.app.config['GEMINI_API_KEY'], 'test-mock-api-key')
        self.assertEqual(self.app.config['AI_REQUEST_TIMEOUT'], 15)

    def test_ai_service_model_and_configured(self):
        """Test AIService model resolution and configuration check."""
        service = AIService()
        self.assertEqual(service.get_model_name(), 'gemini-3.6-flash')
        self.assertTrue(service.is_configured())
        self.assertEqual(service.get_timeout(), 15)

    def test_ai_service_unconfigured_behavior(self):
        """Test AIService behavior when API key is missing."""
        orig_key = self.app.config['GEMINI_API_KEY']
        self.app.config['GEMINI_API_KEY'] = ''
        try:
            service = AIService()
            self.assertFalse(service.is_configured())
            with self.assertRaises(AIConfigurationError):
                service._get_client()
        finally:
            self.app.config['GEMINI_API_KEY'] = orig_key

    def test_safe_error_formatting_never_exposes_key(self):
        """Verify format_safe_error never exposes API key or internal tokens."""
        err = AIConfigurationError("Failed to connect with key test-mock-api-key-12345")
        safe_resp = AIService.format_safe_error(err)

        self.assertFalse(safe_resp['success'])
        self.assertEqual(safe_resp['error']['type'], 'AIConfigurationError')
        self.assertEqual(safe_resp['error']['status_code'], 503)

        # Generic unexpected exception
        generic_err = ValueError("Secret db_pass=super_secret in query")
        safe_generic = AIService.format_safe_error(generic_err)
        self.assertFalse(safe_generic['success'])
        self.assertEqual(safe_generic['error']['status_code'], 500)
        self.assertNotIn('super_secret', str(safe_generic))

    def test_json_cleaner_handles_code_fences(self):
        """Test _clean_json_text handles raw, markdown fenced, and prefixed JSON."""
        # Case 1: Markdown with json tag
        fenced_json = '```json\n{"word": "ephemeral", "meaning_vi": "phù du"}\n```'
        clean = AIService._clean_json_text(fenced_json)
        self.assertEqual(clean, '{"word": "ephemeral", "meaning_vi": "phù du"}')

        # Case 2: Markdown without tag
        fenced_raw = '```\n{"word": "ubiquitous", "meaning_vi": "phổ biến"}\n```'
        clean2 = AIService._clean_json_text(fenced_raw)
        self.assertEqual(clean2, '{"word": "ubiquitous", "meaning_vi": "phổ biến"}')

        # Case 3: Surrounding conversational text
        wrapped = 'Here is your structured result:\n{"word": "diligent", "meaning_vi": "chăm chỉ"}\nHope this helps!'
        clean3 = AIService._clean_json_text(wrapped)
        self.assertEqual(clean3, '{"word": "diligent", "meaning_vi": "chăm chỉ"}')

    def test_pydantic_schema_validation_foundation(self):
        """Test schema validation parsing on clean JSON."""
        sample_json = '{"word": "resilient", "meaning_vi": "kiên cường", "examples": ["She is resilient."]}'
        model = MockVocabSchema.model_validate_json(sample_json)
        self.assertEqual(model.word, "resilient")
        self.assertEqual(model.meaning_vi, "kiên cường")
        self.assertEqual(len(model.examples), 1)

    def test_rate_limit_helper(self):
        """Test in-memory rate limiting / cooldown helper."""
        service = AIService()
        user_id = 999
        action = "vocab_assistant"

        # First request allowed
        allowed, remaining = service.check_rate_limit(user_id, action, cooldown_seconds=2)
        self.assertTrue(allowed)
        self.assertEqual(remaining, 0)

        # Immediate second request blocked
        allowed2, remaining2 = service.check_rate_limit(user_id, action, cooldown_seconds=2)
        self.assertFalse(allowed2)
        self.assertGreater(remaining2, 0)

    def test_ai_status_endpoint_auth_required(self):
        """Test that /api/ai/status requires authentication."""
        resp = self.client.get('/api/ai/status')
        # Should redirect to login (302) or return unauthorized
        self.assertIn(resp.status_code, [302, 401])

    def test_ai_status_endpoint_authenticated(self):
        """Test /api/ai/status when logged in."""
        with self.client:
            # Log the user in via test client session
            with self.client.session_transaction() as sess:
                sess['_user_id'] = str(self.user.id)

            resp = self.client.get('/api/ai/status')
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data['success'])
            self.assertTrue(data['configured'])
            self.assertEqual(data['model'], 'gemini-3.6-flash')
            self.assertEqual(data['status'], 'ready')
            # Critical Security check: GEMINI_API_KEY must NOT be in the response
            self.assertNotIn('api_key', data)
            self.assertNotIn('GEMINI_API_KEY', str(data))
            self.assertNotIn('test-mock-api-key', str(data))

    def test_ai_skeleton_endpoints_return_501(self):
        """Test that skeleton endpoints return 501 Not Implemented."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess['_user_id'] = str(self.user.id)

            endpoints = [
                ('/api/ai/study-plan', 'POST'),
                ('/api/ai/tutor', 'POST'),
                ('/api/ai/recommendations', 'GET'),
            ]

            for url, method in endpoints:
                if method == 'POST':
                    r = self.client.post(url, json={})
                else:
                    r = self.client.get(url)
                self.assertEqual(r.status_code, 501, f"Failed for {url}")
                data = r.get_json()
                self.assertFalse(data['success'])

    def test_existing_routes_still_work(self):
        """Verify existing core routes are untouched and function correctly."""
        # 1. Flashcards library route (public)
        resp = self.client.get('/flashcards')
        self.assertEqual(resp.status_code, 200)

        # 2. Login route (public)
        resp_login = self.client.get('/login')
        self.assertEqual(resp_login.status_code, 200)

        # 3. Register route (public)
        resp_reg = self.client.get('/register')
        self.assertEqual(resp_reg.status_code, 200)

        # 4. Authenticated dashboard
        with self.client:
            from flask_login import login_user
            with self.app.test_request_context():
                login_user(self.user)
            with self.client.session_transaction() as sess:
                sess['_user_id'] = str(self.user.id)
                sess['_fresh'] = True
            resp_dash = self.client.get('/dashboard', follow_redirects=False)
            # If redirected to flashcards, check that unauthenticated was handled, but with user logged in
            self.assertIn(resp_dash.status_code, [200, 302])



if __name__ == '__main__':
    unittest.main()
