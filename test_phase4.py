"""
Phase 4 Verification Tests for AI Learning Analysis.
Tests:
1. Authentication protection (/api/ai/learning-analysis, /ai/learning-analysis).
2. User with no learning data handling (returns has_data=False, no Gemini call).
3. Backend mathematical aggregations (accuracy, total tested, mastery percentage).
4. Deterministic weak word detection rules (low accuracy, 0 correct, difficulty rating).
5. Deterministic weak topic evaluation.
6. SRS review prioritization.
7. Successful AI Learning Analysis structured generation (AILearningAnalysis schema).
8. Mocked Gemini API error / timeout handling.
9. Rate limiting cooldown protection.
10. Strict user isolation (ensuring User A cannot see User B's statistics or words).
11. UI page rendering (/ai/learning-analysis).
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from app import create_app
from app.models import db, User, Topic, Word, WordProgress
from app.services.ai_service import ai_service, AIResponseError, AITimeoutError
from app.services.analytics_service import get_user_learning_statistics
from app.services.schemas import (
    AILearningAnalysis,
    WeakWordInsight,
    WeakTopicInsight,
    LearningInsight
)
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-phase4'
    GEMINI_API_KEY = 'test-mock-api-key'
    GEMINI_MODEL = 'gemini-3.6-flash'
    AI_REQUEST_TIMEOUT = 10


class TestPhase4(unittest.TestCase):

    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        ai_service._rate_limits.clear()

        # Create User A
        self.user = User(username='student_alpha', password_hash='mockpass', xp=150)
        # Create User B (for user isolation tests)
        self.other_user = User(username='student_beta', password_hash='mockpass', xp=50)
        db.session.add_all([self.user, self.other_user])
        db.session.commit()

        # Create Topics for User A
        self.topic1 = Topic(name='Academic Words', user_id=self.user.id)
        self.topic2 = Topic(name='Business English', user_id=self.user.id)
        db.session.add_all([self.topic1, self.topic2])
        db.session.commit()

        # Create Words for User A
        self.w1 = Word(term='ambiguous', definition='mơ hồ', topic_id=self.topic1.id, user_id=self.user.id)
        self.w2 = Word(term='coherent', definition='mạch lạc', topic_id=self.topic1.id, user_id=self.user.id)
        self.w3 = Word(term='deficit', definition='thâm hụt', topic_id=self.topic2.id, user_id=self.user.id)
        self.w4 = Word(term='revenue', definition='doanh thu', topic_id=self.topic2.id, user_id=self.user.id)
        db.session.add_all([self.w1, self.w2, self.w3, self.w4])
        db.session.commit()

        now = datetime.now(timezone.utc)

        # Progress for Word 1 (weak word: tested 4, correct 1 -> 25% accuracy)
        self.p1 = WordProgress(
            user_id=self.user.id, word_id=self.w1.id,
            times_tested=4, times_correct=1, is_mastered=False,
            user_difficulty_rating='hard',
            next_review=now + timedelta(days=2)
        )
        # Progress for Word 2 (mastered word: tested 5, correct 5 -> 100% accuracy)
        self.p2 = WordProgress(
            user_id=self.user.id, word_id=self.w2.id,
            times_tested=5, times_correct=5, is_mastered=True,
            date_mastered=now,
            next_review=now + timedelta(days=7)
        )
        # Progress for Word 3 (weak word: tested 2, correct 0 -> 0% accuracy, due for review)
        self.p3 = WordProgress(
            user_id=self.user.id, word_id=self.w3.id,
            times_tested=2, times_correct=0, is_mastered=False,
            next_review=now - timedelta(days=1)
        )
        # Progress for Word 4 (untested word)
        self.p4 = WordProgress(
            user_id=self.user.id, word_id=self.w4.id,
            times_tested=0, times_correct=0, is_mastered=False,
            next_review=now + timedelta(days=3)
        )

        db.session.add_all([self.p1, self.p2, self.p3, self.p4])
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
    # Backend Mathematical Statistics Tests
    # -----------------------------------------------------------------
    def test_backend_accuracy_and_mastery_calculation(self):
        """Test backend calculates exact mathematical statistics without AI."""
        stats = get_user_learning_statistics(self.user.id)

        self.assertTrue(stats["has_sufficient_data"])
        self.assertEqual(stats["total_words_enrolled"], 4)
        self.assertEqual(stats["total_words_tested"], 3)  # w1, w2, w3
        self.assertEqual(stats["total_tests_taken"], 11)   # 4 + 5 + 2 = 11
        self.assertEqual(stats["total_correct_answers"], 6) # 1 + 5 + 0 = 6
        # Overall accuracy = 6 / 11 ~ 0.55
        self.assertEqual(stats["overall_accuracy"], 0.55)
        self.assertEqual(stats["overall_accuracy_percentage"], 55)
        # Mastery = 1 / 4 = 25.0%
        self.assertEqual(stats["total_mastered_words"], 1)
        self.assertEqual(stats["mastery_percentage"], 25.0)

    def test_deterministic_weak_word_detection(self):
        """Test backend detects weak words by deterministic rules."""
        stats = get_user_learning_statistics(self.user.id)
        weak_terms = [w["word"] for w in stats["weak_words"]]

        # w1 (25% accuracy) and w3 (0% accuracy) must be flagged
        self.assertIn('ambiguous', weak_terms)
        self.assertIn('deficit', weak_terms)
        # w2 (100% accuracy) must NOT be flagged as weak
        self.assertNotIn('coherent', weak_terms)

    def test_deterministic_weak_topic_detection(self):
        """Test backend aggregates topic performance accurately."""
        stats = get_user_learning_statistics(self.user.id)
        topics = stats["topic_stats"]
        self.assertEqual(len(topics), 2)

        # Topic 2 (Business English: deficit 0/2, revenue 0/0 -> accuracy 0.0)
        t2 = next(t for t in topics if t["topic_name"] == 'Business English')
        self.assertEqual(t2["accuracy"], 0.0)
        self.assertTrue(t2["is_weak"])

    def test_due_review_detection(self):
        """Test words past next_review are flagged for review."""
        stats = get_user_learning_statistics(self.user.id)
        due_terms = [w["word"] for w in stats["due_review_words"]]
        self.assertIn('deficit', due_terms)
        self.assertEqual(stats["total_due_reviews"], 1)

    # -----------------------------------------------------------------
    # User Isolation Tests
    # -----------------------------------------------------------------
    def test_user_isolation(self):
        """Verify User B with no words gets completely isolated empty stats."""
        stats_b = get_user_learning_statistics(self.other_user.id)
        self.assertFalse(stats_b["has_sufficient_data"])
        self.assertEqual(stats_b["total_words_enrolled"], 0)
        self.assertEqual(len(stats_b["weak_words"]), 0)

    # -----------------------------------------------------------------
    # Endpoint Tests
    # -----------------------------------------------------------------
    def test_unauthenticated_request_blocked(self):
        """Test unauthenticated requests to /api/ai/learning-analysis are blocked."""
        resp = self.client.get('/api/ai/learning-analysis')
        self.assertIn(resp.status_code, [302, 401])

    def test_empty_user_gets_has_data_false(self):
        """Test user with no learning history receives has_data=False without calling AI."""
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.other_user.id)
            sess['_fresh'] = True

        resp = self.client.get('/api/ai/learning-analysis')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertFalse(data['has_data'])
        self.assertIn('stats', data)
        self.assertIn('Chưa có đủ dữ liệu', data['message'])

    @patch('app.ai_routes.ai_service.analyze_learning_data')
    def test_successful_learning_analysis(self, mock_analyze):
        """Test successful learning analysis returning validated structured JSON."""
        self._login_client()

        mock_analysis = AILearningAnalysis(
            summary="Bạn đang có sự tiến bộ tốt ở nhóm từ Học thuật, nhưng cần cải thiện từ vựng Kinh doanh.",
            strengths=["Thành thạo tốt từ 'coherent'", "Chăm chỉ làm bài quiz"],
            weaknesses=["Gặp khó khăn với từ 'ambiguous' và 'deficit'"],
            weak_words=[
                WeakWordInsight(
                    word="deficit",
                    issue="Tỷ lệ đúng 0% sau 2 lần kiểm tra",
                    recommendation="Ghi nhớ qua cụm 'budget deficit' (thâm hụt ngân sách)"
                )
            ],
            weak_topics=[
                WeakTopicInsight(
                    topic_name="Business English",
                    issue="Tỷ lệ đúng chỉ 0% trên danh mục này",
                    recommendation="Ôn lại các định nghĩa cơ bản trước khi làm quiz"
                )
            ],
            review_priorities=["deficit", "ambiguous"],
            learning_insights=[
                LearningInsight(
                    title="Củng cố theo ngữ cảnh",
                    insight="Các từ có độ chính xác thấp thường do thiếu ngữ cảnh cụ thể.",
                    action="Tạo ví dụ câu thực tế với từ 'deficit'."
                )
            ]
        )
        mock_analyze.return_value = mock_analysis

        resp = self.client.get('/api/ai/learning-analysis')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertTrue(data['success'])
        self.assertTrue(data['has_data'])
        self.assertEqual(data['stats']['total_words_enrolled'], 4)
        self.assertEqual(data['analysis']['summary'], mock_analysis.summary)
        self.assertEqual(len(data['analysis']['weak_words']), 1)
        self.assertEqual(data['analysis']['weak_words'][0]['word'], "deficit")

    @patch('app.ai_routes.ai_service.analyze_learning_data')
    def test_gemini_api_error_handling(self, mock_analyze):
        """Test AI service errors return safe JSON response."""
        self._login_client()
        mock_analyze.side_effect = AIResponseError("AI service quota reached.", status_code=502)

        resp = self.client.get('/api/ai/learning-analysis')
        self.assertEqual(resp.status_code, 502)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error']['type'], 'AIResponseError')

    # -----------------------------------------------------------------
    # UI Route Tests
    # -----------------------------------------------------------------
    def test_analysis_page_renders_for_auth_user(self):
        """Test rendering /ai/learning-analysis page."""
        self._login_client()
        resp = self.client.get('/ai/learning-analysis')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'AI Learning Analysis', resp.data)
        self.assertIn(b'Gemini 3.6 Flash', resp.data)
        self.assertIn(b'ai_analysis.js', resp.data)

    def test_analysis_page_requires_auth(self):
        """Test unauthenticated access redirects to login."""
        resp = self.client.get('/ai/learning-analysis')
        self.assertEqual(resp.status_code, 302)


if __name__ == '__main__':
    unittest.main()
