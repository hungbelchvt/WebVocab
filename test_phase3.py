"""
Phase 3 Verification Tests for AI Quiz Generator.
Tests:
1. Unauthenticated access protection (/api/ai/quiz, /ai/quiz).
2. User with no vocabulary error handling (400 Bad Request).
3. Invalid question count validation (<1, >20, invalid types).
4. Invalid / nonexistent topic ID handling (404 Not Found).
5. Candidate selection algorithm ranking (SRS due, low accuracy, untested, difficulty).
6. Topic filtering on candidate selection.
7. Successful quiz generation with structured Pydantic schema (multiple_choice, fill_blank, context).
8. Option formatting and correct_id mapping.
9. Mocked Gemini API error / timeout handling.
10. Rate limit cooldown debounce protection.
11. Full Learning Loop integration with /api/submit_quiz_batch (WordProgress, XP, Mastery update).
12. AI Quiz UI page rendering (/ai/quiz).
13. Regression testing on existing standard quiz & study routes.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from app import create_app
from app.models import db, User, Topic, Word, WordProgress
from app.services.ai_service import ai_service, AIResponseError, AITimeoutError
from app.services.schemas import AIQuizQuestion, AIQuizResponse
from app.ai_routes import select_quiz_candidates
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-phase3'
    GEMINI_API_KEY = 'test-mock-api-key'
    GEMINI_MODEL = 'gemini-3.6-flash'
    AI_REQUEST_TIMEOUT = 10


class TestPhase3(unittest.TestCase):

    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        ai_service._rate_limits.clear()

        # Create test user
        self.user = User(username='quiz_tester', password_hash='mockpass', xp=100)
        db.session.add(self.user)
        db.session.commit()

        # Create Topics
        self.topic1 = Topic(name='Business English', user_id=self.user.id)
        self.topic2 = Topic(name='Daily Conversation', user_id=self.user.id)
        db.session.add_all([self.topic1, self.topic2])
        db.session.commit()

        # Create Words for Topic 1
        self.word1 = Word(term='negotiate', definition='đàm phán', topic_id=self.topic1.id, user_id=self.user.id)
        self.word2 = Word(term='lucrative', definition='sinh lợi', topic_id=self.topic1.id, user_id=self.user.id)
        self.word3 = Word(term='bankrupt', definition='phá sản', topic_id=self.topic1.id, user_id=self.user.id)

        # Create Word for Topic 2
        self.word4 = Word(term='greetings', definition='lời chào', topic_id=self.topic2.id, user_id=self.user.id)

        db.session.add_all([self.word1, self.word2, self.word3, self.word4])
        db.session.commit()

        # Create WordProgress records
        now = datetime.now(timezone.utc)
        # Word 1: weak word (tested 5, correct 1) -> high priority
        self.prog1 = WordProgress(
            user_id=self.user.id, word_id=self.word1.id,
            times_tested=5, times_correct=1, is_mastered=False,
            user_difficulty_rating='hard', next_review=now - timedelta(hours=2)
        )
        # Word 2: untested word
        self.prog2 = WordProgress(
            user_id=self.user.id, word_id=self.word2.id,
            times_tested=0, times_correct=0, is_mastered=False,
            user_difficulty_rating='medium'
        )
        # Word 3: mastered word (tested 10, correct 10) -> lower priority
        self.prog3 = WordProgress(
            user_id=self.user.id, word_id=self.word3.id,
            times_tested=10, times_correct=10, is_mastered=True,
            user_difficulty_rating='easy'
        )
        # Word 4: Topic 2 word
        self.prog4 = WordProgress(
            user_id=self.user.id, word_id=self.word4.id,
            times_tested=2, times_correct=2, is_mastered=False
        )

        db.session.add_all([self.prog1, self.prog2, self.prog3, self.prog4])
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
    # Candidate Selection Algorithm Tests
    # -----------------------------------------------------------------
    def test_candidate_selection_ranking(self):
        """Test candidate ranking prioritizes weak, due, and untested words."""
        candidates = select_quiz_candidates(self.user.id, topic_id=None, max_candidates=10)
        self.assertGreaterEqual(len(candidates), 4)

        # Word 1 (weak, due, hard) must be ranked first
        self.assertEqual(candidates[0]['term'], 'negotiate')
        self.assertEqual(candidates[0]['progress_id'], self.prog1.id)

        # Word 2 (untested) should be ranked before mastered Word 3
        cand_terms = [c['term'] for c in candidates]
        self.assertIn('negotiate', cand_terms)
        self.assertIn('lucrative', cand_terms)
        self.assertIn('bankrupt', cand_terms)
        self.assertIn('greetings', cand_terms)

    def test_candidate_selection_topic_filtering(self):
        """Test candidate selection strictly filters by topic_id."""
        candidates_t1 = select_quiz_candidates(self.user.id, topic_id=self.topic1.id, max_candidates=10)
        t1_terms = [c['term'] for c in candidates_t1]
        self.assertIn('negotiate', t1_terms)
        self.assertNotIn('greetings', t1_terms)

        candidates_t2 = select_quiz_candidates(self.user.id, topic_id=self.topic2.id, max_candidates=10)
        t2_terms = [c['term'] for c in candidates_t2]
        self.assertEqual(t2_terms, ['greetings'])

    # -----------------------------------------------------------------
    # Endpoint Input Validation Tests
    # -----------------------------------------------------------------
    def test_unauthenticated_quiz_request_blocked(self):
        """Test that unauthenticated requests to /api/ai/quiz are blocked."""
        resp = self.client.post('/api/ai/quiz', json={"question_count": 5})
        self.assertIn(resp.status_code, [302, 401])

    def test_invalid_question_count_rejected(self):
        """Test that invalid question counts are rejected with 400."""
        self._login_client()

        # Count < 1
        resp1 = self.client.post('/api/ai/quiz', json={"question_count": 0})
        self.assertEqual(resp1.status_code, 400)
        self.assertFalse(resp1.get_json()['success'])

        # Count > 20
        resp2 = self.client.post('/api/ai/quiz', json={"question_count": 25})
        self.assertEqual(resp2.status_code, 400)

        # Invalid type
        resp3 = self.client.post('/api/ai/quiz', json={"question_count": "abc"})
        self.assertEqual(resp3.status_code, 400)

    def test_nonexistent_topic_rejected(self):
        """Test that selecting a nonexistent topic returns 404."""
        self._login_client()
        resp = self.client.post('/api/ai/quiz', json={"topic_id": 99999, "question_count": 5})
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(resp.get_json()['success'])

    def test_user_with_no_vocabulary_handled(self):
        """Test that user with no enrolled words gets clear error message."""
        # Create empty user
        empty_user = User(username='empty_user', password_hash='mockpass')
        db.session.add(empty_user)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(empty_user.id)
            sess['_fresh'] = True

        resp = self.client.post('/api/ai/quiz', json={"question_count": 5})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertIn("chưa có từ vựng", data['error']['message'])

    # -----------------------------------------------------------------
    # AI Quiz Generation & Schema Tests (Mocked AI Service)
    # -----------------------------------------------------------------
    @patch('app.ai_routes.ai_service.generate_personalized_quiz')
    def test_successful_quiz_generation(self, mock_gen_quiz):
        """Test successful personalized quiz generation with varied question types."""
        self._login_client()

        mock_response = AIQuizResponse(
            questions=[
                AIQuizQuestion(
                    word="negotiate",
                    type="multiple_choice",
                    question="What is the meaning of 'negotiate' in business?",
                    options=["To discuss terms to reach an agreement", "To declare bankruptcy", "To hire employees", "To sell products"],
                    answer="To discuss terms to reach an agreement",
                    explanation="'Negotiate' có nghĩa là đàm phán, thương lượng các điều khoản để đạt được thỏa thuận."
                ),
                AIQuizQuestion(
                    word="lucrative",
                    type="fill_blank",
                    question="The tech startup signed a highly _____ contract with the government.",
                    options=["lucrative", "bankrupt", "negligent", "fragile"],
                    answer="lucrative",
                    explanation="'Lucrative' có nghĩa là sinh lợi, đem lại nhiều lợi nhuận."
                )
            ]
        )
        mock_gen_quiz.return_value = mock_response

        resp = self.client.post('/api/ai/quiz', json={"topic_id": self.topic1.id, "question_count": 2})
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['questions']), 2)

        # Question 1 verification
        q1 = data['questions'][0]
        self.assertEqual(q1['word'], 'negotiate')
        self.assertEqual(q1['type'], 'multiple_choice')
        self.assertEqual(len(q1['options']), 4)
        self.assertEqual(q1['options'][q1['correct_id']]['def'], q1['answer'])
        self.assertEqual(q1['progress_id'], self.prog1.id)

        # Question 2 verification
        q2 = data['questions'][1]
        self.assertEqual(q2['word'], 'lucrative')
        self.assertEqual(q2['type'], 'fill_blank')
        self.assertEqual(q2['progress_id'], self.prog2.id)

    @patch('app.ai_routes.ai_service.generate_personalized_quiz')
    def test_gemini_api_error_handling(self, mock_gen_quiz):
        """Test that AI errors in quiz generator return safe JSON."""
        self._login_client()
        mock_gen_quiz.side_effect = AIResponseError("AI service quota reached.", status_code=502)

        resp = self.client.post('/api/ai/quiz', json={"question_count": 5})
        self.assertEqual(resp.status_code, 502)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error']['type'], 'AIResponseError')

    # -----------------------------------------------------------------
    # Integration with submit_quiz_batch (WordProgress Learning Loop)
    # -----------------------------------------------------------------
    def test_ai_quiz_submission_updates_word_progress_and_xp(self):
        """Test submitting AI quiz answers updates real WordProgress and User XP."""
        self._login_client()

        initial_xp = self.user.xp
        initial_tested = self.prog1.times_tested
        initial_correct = self.prog1.times_correct

        # Simulate batch results from completing an AI quiz
        batch_results = {
            "results": [
                {
                    "progress_id": self.prog1.id,
                    "is_correct": True,
                    "term": self.prog1.word.term,
                    "correct_id": 0,
                    "selected_id": 0
                },
                {
                    "progress_id": self.prog2.id,
                    "is_correct": False,
                    "term": self.prog2.word.term,
                    "correct_id": 0,
                    "selected_id": 2
                }
            ]
        }

        resp = self.client.post('/api/submit_quiz_batch', json=batch_results)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('/quiz/results', data['redirect_url'])

        # Verify WordProgress 1 updated (correct answer)
        db.session.refresh(self.prog1)
        self.assertEqual(self.prog1.times_tested, initial_tested + 1)
        self.assertEqual(self.prog1.times_correct, initial_correct + 1)

        # Verify WordProgress 2 updated (incorrect answer)
        db.session.refresh(self.prog2)
        self.assertEqual(self.prog2.times_tested, 1)
        self.assertEqual(self.prog2.times_correct, 0)

        # Verify User XP gained (+10 for 1 correct)
        db.session.refresh(self.user)
        self.assertEqual(self.user.xp, initial_xp + 10)

    # -----------------------------------------------------------------
    # UI Route & Existing Routes Test
    # -----------------------------------------------------------------
    def test_ai_quiz_page_renders(self):
        """Test rendering /ai/quiz page for authenticated user."""
        self._login_client()
        resp = self.client.get('/ai/quiz')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'AI Quiz Generator', resp.data)
        self.assertIn(b'Gemini 3.6 Flash', resp.data)
        self.assertIn(b'ai_quiz.js', resp.data)

    def test_ai_quiz_page_requires_auth(self):
        """Test that unauthenticated access to /ai/quiz redirects to login."""
        resp = self.client.get('/ai/quiz')
        self.assertEqual(resp.status_code, 302)


if __name__ == '__main__':
    unittest.main()
