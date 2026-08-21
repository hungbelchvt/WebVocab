"""
Phase 2 Verification Tests for AI Vocabulary Assistant.
Tests:
1. Empty input validation.
2. Invalid input / character validation.
3. Excessive length validation.
4. Unauthenticated request protection.
5. Successful AI vocabulary response generation and schema conformance.
6. Mocked Gemini API error / timeout / quota handling.
7. Topics retrieval endpoint (/api/ai/topics).
8. Add AI word to existing Topic with WordProgress creation.
9. Duplicate word prevention in same topic (409 Conflict).
10. Add AI word with new Topic creation.
11. UI template rendering (/ai/vocabulary).
12. Existing routes regression testing.
"""

import unittest
from unittest.mock import patch, MagicMock
from app import create_app
from app.models import db, User, Topic, Word, WordProgress
from app.services.ai_service import AIService, ai_service, AIResponseError, AITimeoutError
from app.services.schemas import VocabularyExplanation, ExampleSentence
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-phase2'
    GEMINI_API_KEY = 'test-mock-api-key'
    GEMINI_MODEL = 'gemini-3.6-flash'
    AI_REQUEST_TIMEOUT = 10


class TestPhase2(unittest.TestCase):

    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Reset rate limits for clean test environment
        ai_service._rate_limits.clear()

        # Create test user
        self.user = User(username='vocab_learner', password_hash='mockpass')
        db.session.add(self.user)
        db.session.commit()

        # Create a sample topic for this user
        self.topic = Topic(name='IELTS Academic', user_id=self.user.id)
        db.session.add(self.topic)
        db.session.commit()


    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login_client(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user.id)
            sess['_fresh'] = True

    # -----------------------------------------------------------------
    # Input Validation Tests
    # -----------------------------------------------------------------
    def test_empty_input_rejected(self):
        """Test that empty or whitespace-only word input is rejected with 400."""
        self._login_client()
        
        # Test 1: Empty string
        resp1 = self.client.post('/api/ai/vocabulary', json={"word": ""})
        self.assertEqual(resp1.status_code, 400)
        data1 = resp1.get_json()
        self.assertFalse(data1['success'])
        self.assertIn("Vui lòng nhập", data1['error']['message'])

        # Test 2: Whitespace string
        resp2 = self.client.post('/api/ai/vocabulary', json={"word": "   "})
        self.assertEqual(resp2.status_code, 400)

        # Test 3: Missing word field
        resp3 = self.client.post('/api/ai/vocabulary', json={})
        self.assertEqual(resp3.status_code, 400)

    def test_excessive_length_rejected(self):
        """Test that words exceeding 100 characters are rejected with 400."""
        self._login_client()
        long_word = "a" * 105
        resp = self.client.post('/api/ai/vocabulary', json={"word": long_word})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertIn("100 ký tự", data['error']['message'])

    def test_invalid_characters_rejected(self):
        """Test that inputs with non-word symbols or injection attempts are rejected."""
        self._login_client()
        resp = self.client.post('/api/ai/vocabulary', json={"word": "<script>alert(1)</script>"})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertIn("chỉ được chứa chữ cái", data['error']['message'])

    def test_unauthenticated_request_rejected(self):
        """Test that unauthenticated requests to /api/ai/vocabulary are blocked."""
        resp = self.client.post('/api/ai/vocabulary', json={"word": "abandon"})
        self.assertIn(resp.status_code, [302, 401])

    # -----------------------------------------------------------------
    # AI Vocabulary Generation Tests (Mocked AI Service)
    # -----------------------------------------------------------------
    @patch('app.ai_routes.ai_service.explain_vocabulary')
    def test_successful_vocabulary_explanation(self, mock_explain):
        """Test successful vocabulary analysis returning structured JSON."""
        self._login_client()

        mock_result = VocabularyExplanation(
            word="abandon",
            meaning_vi="từ bỏ, bỏ rơi",
            part_of_speech="verb",
            pronunciation="/əˈbændən/",
            examples=[
                ExampleSentence(
                    sentence="They had to abandon the car in the snow.",
                    translation_vi="Họ phải bỏ lại chiếc xe trong tuyết."
                )
            ],
            synonyms=["desert", "leave", "give up"],
            antonyms=["retain", "keep", "maintain"],
            collocations=["abandon hope", "abandon a plan"],
            memory_tip="Nhớ 'a band on' -> một ban nhạc đang bật nhạc rồi bỏ đi."
        )
        mock_explain.return_value = mock_result

        resp = self.client.post('/api/ai/vocabulary', json={"word": "abandon"})
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['word'], "abandon")
        self.assertEqual(data['data']['meaning_vi'], "từ bỏ, bỏ rơi")
        self.assertEqual(data['data']['part_of_speech'], "verb")
        self.assertEqual(data['data']['pronunciation'], "/əˈbændən/")
        self.assertEqual(len(data['data']['examples']), 1)
        self.assertEqual(data['data']['examples'][0]['sentence'], "They had to abandon the car in the snow.")
        self.assertIn("desert", data['data']['synonyms'])
        self.assertIn("abandon hope", data['data']['collocations'])
        self.assertIn("ban nhạc", data['data']['memory_tip'])

    @patch('app.ai_routes.ai_service.explain_vocabulary')
    def test_gemini_api_error_handling(self, mock_explain):
        """Test that AI errors return safe JSON responses with appropriate status code."""
        self._login_client()
        mock_explain.side_effect = AIResponseError("Quota exceeded or connection error.", status_code=502)

        resp = self.client.post('/api/ai/vocabulary', json={"word": "resilient"})
        self.assertEqual(resp.status_code, 502)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error']['type'], 'AIResponseError')
        self.assertNotIn('test-mock-api-key', str(data))

    @patch('app.ai_routes.ai_service.explain_vocabulary')
    def test_gemini_timeout_handling(self, mock_explain):
        """Test that AI timeout returns 504 with friendly message."""
        self._login_client()
        mock_explain.side_effect = AITimeoutError("AI request timed out.")

        resp = self.client.post('/api/ai/vocabulary', json={"word": "ubiquitous"})
        self.assertEqual(resp.status_code, 504)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error']['type'], 'AITimeoutError')

    # -----------------------------------------------------------------
    # Topics & Add to Vocabulary Tests
    # -----------------------------------------------------------------
    def test_get_user_topics(self):
        """Test fetching available topics for user."""
        self._login_client()
        resp = self.client.get('/api/ai/topics')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['topics']), 1)
        self.assertEqual(data['topics'][0]['name'], 'IELTS Academic')

    def test_add_word_to_existing_topic(self):
        """Test successfully adding an AI-analyzed word to an existing topic."""
        self._login_client()

        payload = {
            "topic_id": self.topic.id,
            "word": "diligent",
            "pronunciation": "/ˈdɪlɪdʒənt/",
            "meaning_vi": "chăm chỉ, cần cù",
            "examples": [
                {"sentence": "She is a diligent student.", "translation_vi": "Cô ấy là một học sinh chăm chỉ."}
            ],
            "synonyms": ["hardworking", "industrious"],
            "antonyms": ["lazy", "careless"]
        }

        resp = self.client.post('/api/ai/vocabulary/add-to-topic', json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertIn("thành công", data['message'])

        # Verify Word in database
        saved_word = Word.query.filter_by(term="diligent", topic_id=self.topic.id).first()
        self.assertIsNotNone(saved_word)
        self.assertEqual(saved_word.definition, "chăm chỉ, cần cù")
        self.assertEqual(saved_word.ipa, "/ˈdɪlɪdʒənt/")
        self.assertIn("hardworking", saved_word.synonyms)

        # Verify WordProgress in database
        progress = WordProgress.query.filter_by(user_id=self.user.id, word_id=saved_word.id).first()
        self.assertIsNotNone(progress)
        self.assertEqual(progress.times_tested, 0)

    def test_duplicate_word_prevention(self):
        """Test that adding an existing word to the same topic returns 409 Conflict."""
        self._login_client()

        # Add word first time
        word1 = Word(
            term="diligent",
            definition="chăm chỉ",
            topic_id=self.topic.id,
            user_id=self.user.id
        )
        db.session.add(word1)
        db.session.commit()

        # Attempt to add same word (case-insensitive)
        payload = {
            "topic_id": self.topic.id,
            "word": "Diligent",
            "meaning_vi": "cần cù",
            "pronunciation": "/ˈdɪlɪdʒənt/"
        }

        resp = self.client.post('/api/ai/vocabulary/add-to-topic', json=payload)
        self.assertEqual(resp.status_code, 409)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertTrue(data['duplicate'])
        self.assertIn("đã có sẵn", data['error'])

    def test_add_word_with_new_topic_creation(self):
        """Test creating a new topic on-the-fly and adding the word."""
        self._login_client()

        payload = {
            "new_topic_name": "TOEIC Advanced",
            "word": "ephemeral",
            "pronunciation": "/ɪˈfemərəl/",
            "meaning_vi": "ngắn ngủi, phù du",
            "examples": [{"sentence": "Fame in the world is ephemeral.", "translation_vi": "Danh tiếng là phù du."}],
            "synonyms": ["transient", "fleeting"],
            "antonyms": ["permanent", "eternal"]
        }

        resp = self.client.post('/api/ai/vocabulary/add-to-topic', json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data['success'])

        # Verify new topic created
        new_top = Topic.query.filter_by(name="TOEIC Advanced", user_id=self.user.id).first()
        self.assertIsNotNone(new_top)

        # Verify word linked to new topic
        saved_word = Word.query.filter_by(term="ephemeral", topic_id=new_top.id).first()
        self.assertIsNotNone(saved_word)

    # -----------------------------------------------------------------
    # UI Route & Existing Routes Test
    # -----------------------------------------------------------------
    def test_ai_vocabulary_page_renders(self):
        """Test rendering /ai/vocabulary page for authenticated user."""
        self._login_client()
        resp = self.client.get('/ai/vocabulary')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Tr\xe1\xbb\xa3 l\xc3\xbd T\xe1\xbb\xab v\xe1\xbb\xb1ng AI', resp.data)
        self.assertIn(b'ai-badge', resp.data)
        self.assertNotIn(b'Gemini 3.6 Flash', resp.data)
        self.assertIn(b'ai_vocabulary.js', resp.data)


    def test_ai_vocabulary_page_requires_auth(self):
        """Test that unauthenticated access to /ai/vocabulary redirects to login."""
        resp = self.client.get('/ai/vocabulary')
        self.assertEqual(resp.status_code, 302)


if __name__ == '__main__':
    unittest.main()
