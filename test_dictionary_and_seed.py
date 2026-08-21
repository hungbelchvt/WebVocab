"""
Verification Tests for Dictionary Service, API Endpoint, and Database Seeder.
Tests:
1. DictionaryService word validation.
2. DictionaryService successful lookup and normalization.
3. DictionaryService 404 Word Not Found handling.
4. DictionaryService timeout and API error handling.
5. DictionaryService handling of malformed or missing optional fields.
6. /api/dictionary/<word> endpoint for database-matched words.
7. /api/dictionary/<word> endpoint for external Free Dictionary API fallback.
8. /api/dictionary/<word> endpoint 404 for nonexistent words.
9. Database seeder idempotency and duplicate prevention.
"""

import json
import unittest
from unittest.mock import patch, MagicMock
import urllib.error

from app import create_app
from app.models import db, User, Topic, Word, WordProgress
from app.services.dictionary_service import (
    DictionaryService,
    dictionary_service,
    DictionaryError,
    DictionaryNotFoundError,
    DictionaryTimeoutError,
    DictionaryAPIError
)
from config import Config
from seed import seed_database, VOCAB_DATA


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'


class TestDictionaryAndSeed(unittest.TestCase):

    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create a test user, topic, and sample word in DB
        self.user = User(username='test_user', password_hash='hash123')
        db.session.add(self.user)
        db.session.commit()

        self.topic = Topic(name='Technology & AI', user_id=self.user.id)
        db.session.add(self.topic)
        db.session.commit()

        self.word = Word(
            term='algorithm',
            ipa='ˈælɡərɪðəm',
            definition='A process or set of rules to be followed in calculations.',
            example_sentence='Search engines use complex algorithms.',
            synonyms='formula, procedure',
            antonyms='',
            difficulty='medium',
            topic_id=self.topic.id,
            user_id=self.user.id
        )
        db.session.add(self.word)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # =================================================================
    # 1. Dictionary Service Tests
    # =================================================================

    def test_word_validation(self):
        """Test word validation rejects invalid inputs and cleans valid ones."""
        service = DictionaryService()
        self.assertEqual(service.validate_word("  Resilient  "), "resilient")
        self.assertEqual(service.validate_word("cloud-computing"), "cloud-computing")
        self.assertEqual(service.validate_word("it's"), "it's")

        with self.assertRaises(DictionaryError):
            service.validate_word("")
        with self.assertRaises(DictionaryError):
            service.validate_word("   ")
        with self.assertRaises(DictionaryError):
            service.validate_word("word123")
        with self.assertRaises(DictionaryError):
            service.validate_word("drop table users;--")

    def test_normalize_entry_complete_payload(self):
        """Test normalizing raw dictionary API payload with all fields."""
        service = DictionaryService()
        raw_payload = [
            {
                "word": "resilient",
                "phonetic": "/rɪˈzɪljənt/",
                "phonetics": [
                    {
                        "text": "/rɪˈzɪljənt/",
                        "audio": "https://api.dictionaryapi.dev/media/pronunciations/en/resilient-us.mp3"
                    }
                ],
                "meanings": [
                    {
                        "partOfSpeech": "adjective",
                        "definitions": [
                            {
                                "definition": "Able to recoil or spring back into shape after bending, stretching, or being compressed.",
                                "example": "A resilient rubber ball.",
                                "synonyms": ["flexible", "elastic"],
                                "antonyms": ["rigid"]
                            }
                        ],
                        "synonyms": ["tough", "strong"],
                        "antonyms": ["fragile", "weak"]
                    }
                ]
            }
        ]

        normalized = service.normalize_entry(raw_payload)
        self.assertEqual(normalized["term"], "resilient")
        self.assertEqual(normalized["ipa"], "/rɪˈzɪljənt/")
        self.assertEqual(normalized["audio_url"], "https://api.dictionaryapi.dev/media/pronunciations/en/resilient-us.mp3")
        self.assertEqual(normalized["part_of_speech"], "adjective")
        self.assertIn("Able to recoil", normalized["definition"])
        self.assertEqual(normalized["example_sentence"], "A resilient rubber ball.")
        self.assertIn("tough", normalized["synonyms"])
        self.assertIn("flexible", normalized["synonyms"])
        self.assertIn("fragile", normalized["antonyms"])

    def test_normalize_entry_missing_optional_fields(self):
        """Test normalizing payload with missing phonetics, audio, or examples."""
        service = DictionaryService()
        raw_payload = [
            {
                "word": "minimal",
                "meanings": [
                    {
                        "partOfSpeech": "adjective",
                        "definitions": [
                            {
                                "definition": "Of a minimum amount, quantity, or degree."
                            }
                        ]
                    }
                ]
            }
        ]

        normalized = service.normalize_entry(raw_payload)
        self.assertEqual(normalized["term"], "minimal")
        self.assertEqual(normalized["ipa"], "")
        self.assertEqual(normalized["audio_url"], "")
        self.assertEqual(normalized["part_of_speech"], "adjective")
        self.assertEqual(normalized["definition"], "Of a minimum amount, quantity, or degree.")
        self.assertEqual(normalized["example_sentence"], "")
        self.assertEqual(normalized["synonyms"], [])
        self.assertEqual(normalized["antonyms"], [])

    @patch('urllib.request.urlopen')
    def test_fetch_raw_data_success(self, mock_urlopen):
        """Test fetch_raw_data with successful mock HTTP response."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([{"word": "test", "meanings": []}]).encode('utf-8')
        mock_response.headers.get.return_value = "application/json"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        service = DictionaryService()
        data = service.fetch_raw_data("test")
        self.assertIsInstance(data, list)
        self.assertEqual(data[0]["word"], "test")

    @patch('urllib.request.urlopen')
    def test_fetch_raw_data_404_not_found(self, mock_urlopen):
        """Test fetch_raw_data handles HTTP 404 as DictionaryNotFoundError."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://mock",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )

        service = DictionaryService()
        with self.assertRaises(DictionaryNotFoundError) as ctx:
            service.fetch_raw_data("nonexistentword")
        self.assertEqual(ctx.exception.status_code, 404)

    @patch('urllib.request.urlopen')
    def test_fetch_raw_data_timeout(self, mock_urlopen):
        """Test fetch_raw_data handles network timeout as DictionaryTimeoutError."""
        mock_urlopen.side_effect = TimeoutError("Request timed out")

        service = DictionaryService()
        with self.assertRaises(DictionaryTimeoutError) as ctx:
            service.fetch_raw_data("resilient")
        self.assertEqual(ctx.exception.status_code, 504)

    # =================================================================
    # 2. /api/dictionary/<word> Endpoint Tests
    # =================================================================

    def test_api_dictionary_lookup_database_hit(self):
        """Verify endpoint returns existing database word when present."""
        response = self.client.get('/api/dictionary/algorithm')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertTrue(data["success"])
        self.assertTrue(data["found"])
        self.assertEqual(data["source"], "database")
        self.assertEqual(data["data"]["term"], "algorithm")
        self.assertEqual(data["data"]["ipa"], "ˈælɡərɪðəm")
        self.assertEqual(data["data"]["topic_name"], "Technology & AI")
        self.assertTrue(data["data"]["in_database"])

    @patch('app.routes.dictionary_service.lookup')
    def test_api_dictionary_lookup_api_fallback(self, mock_lookup):
        """Verify endpoint queries Free Dictionary API when word not in database."""
        mock_lookup.return_value = {
            "term": "ubiquitous",
            "ipa": "/juːˈbɪkwɪtəs/",
            "audio_url": "https://api.dictionaryapi.dev/media/pronunciations/en/ubiquitous-us.mp3",
            "part_of_speech": "adjective",
            "definition": "Present, appearing, or found everywhere.",
            "example_sentence": "Smartphones are ubiquitous.",
            "synonyms": ["omnipresent", "everywhere"],
            "antonyms": ["rare"],
            "meanings": [],
            "source": "dictionary_api"
        }

        response = self.client.get('/api/dictionary/ubiquitous')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertTrue(data["success"])
        self.assertTrue(data["found"])
        self.assertEqual(data["source"], "dictionary_api")
        self.assertEqual(data["data"]["term"], "ubiquitous")
        self.assertEqual(data["data"]["definition"], "Present, appearing, or found everywhere.")
        self.assertFalse(data["data"]["in_database"])

    @patch('app.routes.dictionary_service.lookup')
    def test_api_dictionary_lookup_not_found(self, mock_lookup):
        """Verify endpoint returns 404 when word is in neither database nor dictionary."""
        mock_lookup.side_effect = DictionaryNotFoundError("unknownxyz")

        response = self.client.get('/api/dictionary/unknownxyz')
        self.assertEqual(response.status_code, 404)
        data = response.get_json()

        self.assertFalse(data["success"])
        self.assertFalse(data["found"])
        self.assertIn("Không tìm thấy", data["error"])

    def test_api_dictionary_lookup_invalid_input(self):
        """Verify endpoint returns 400 for invalid characters or injection attempts."""
        response = self.client.get('/api/dictionary/word<script>')
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["success"])

    # =================================================================
    # 3. Database Seeding, Idempotency & User Data Preservation Tests
    # =================================================================

    def test_database_seeder_execution_and_idempotency(self):
        """Verify database seeder populates topics and words without duplicates on repeat runs."""
        # First run: seeds fresh data using test app context
        topics_first, words_first = seed_database(app=self.app, verbose=False)
        self.assertGreaterEqual(Topic.query.count(), 15)
        self.assertGreaterEqual(Word.query.count(), 525)
        self.assertEqual(topics_first, 15)
        self.assertEqual(words_first, 525)

        # Second run: must be idempotent and insert 0 new duplicate items
        topics_second, words_second = seed_database(app=self.app, verbose=False)
        self.assertEqual(topics_second, 0)
        self.assertEqual(words_second, 0)

        # Verify key system topics exist and have user_id is None
        expected_topics = ["Daily Life", "Travel & Tourism", "Health & Medicine", "Programming & Software"]
        for t_name in expected_topics:
            t = Topic.query.filter_by(name=t_name, user_id=None).first()
            self.assertIsNotNone(t, f"System Topic '{t_name}' should exist in database.")
            self.assertEqual(len(t.words), 35)

    def test_preservation_of_user_data(self):
        """Verify database seeder does not delete or alter existing user topics or words."""
        # Check initial user word exists before seeding
        user_word = Word.query.filter_by(term='algorithm', user_id=self.user.id).first()
        self.assertIsNotNone(user_word)

        # Run database seeder
        seed_database(app=self.app, verbose=False)

        # Verify user word still exists intact
        user_word_after = Word.query.filter_by(term='algorithm', user_id=self.user.id).first()
        self.assertIsNotNone(user_word_after)
        self.assertEqual(user_word_after.definition, 'A process or set of rules to be followed in calculations.')

    def test_system_topic_and_word_nullable_user_id_regression(self):
        """
        Regression Test: Verify system topics and words can be created with user_id=None
        without violating NOT NULL constraints on PostgreSQL or SQLite.
        """
        # 1. Test direct insertion of system topic with user_id=None
        system_top = Topic(name="Regression System Topic", user_id=None)
        db.session.add(system_top)
        db.session.commit()

        self.assertIsNotNone(system_top.id)
        self.assertIsNone(system_top.user_id)

        # 2. Test direct insertion of system word with user_id=None
        system_w = Word(
            term="ubiquity",
            ipa="/juːˈbɪkwəti/",
            definition="The state of being everywhere.",
            example_sentence="The ubiquity of smartphones is undeniable.",
            synonyms="omnipresence",
            antonyms="rarity",
            difficulty="medium",
            topic_id=system_top.id,
            user_id=None
        )
        db.session.add(system_w)
        db.session.commit()

        self.assertIsNotNone(system_w.id)
        self.assertIsNone(system_w.user_id)
        self.assertEqual(system_w.topic_id, system_top.id)

    def test_ensure_schema_compatibility_and_auto_init_and_seed(self):
        """Verify ensure_schema_compatibility and auto_init_and_seed run without error."""
        from seed import ensure_schema_compatibility, auto_init_and_seed

        # ensure_schema_compatibility must execute cleanly and idempotently
        ensure_schema_compatibility(self.app)

        # auto_init_and_seed must execute cleanly and populate 15 topics / 525 words
        success = auto_init_and_seed(self.app)
        self.assertTrue(success)

        self.assertGreaterEqual(Topic.query.filter_by(user_id=None).count(), 15)
        self.assertGreaterEqual(Word.query.filter_by(user_id=None).count(), 525)


if __name__ == '__main__':
    unittest.main()


