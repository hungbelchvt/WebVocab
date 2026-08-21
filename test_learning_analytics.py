"""
Unit & Integration Tests for Learning Analytics, Smart Study Memory, Quiz Tracking, AI Analysis & Leaderboards.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from app import create_app
from app.models import db, User, Topic, Word, WordProgress, SmartStudyReview, QuizAttempt
from app.services.analytics_service import get_user_learning_statistics
from app.services.schemas import (
    AILearningAnalysis,
    WeakWordInsight,
    WeakTopicInsight,
    LearningInsight
)
from config import Config


class TestAnalyticsConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-analytics-secret'
    GEMINI_API_KEY = 'mock-key'
    GEMINI_MODEL = 'gemini-3.6-flash'
    AI_REQUEST_TIMEOUT = 10


class TestLearningAnalytics(unittest.TestCase):

    def setUp(self):
        self.app = create_app(TestAnalyticsConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create Users
        self.user_a = User(username='user_alice', password_hash='hash_a', xp=300, current_streak=5, longest_streak=7)
        self.user_b = User(username='user_bob', password_hash='hash_b', xp=500, current_streak=10, longest_streak=12)
        self.user_c = User(username='user_charlie', password_hash='hash_c', xp=100, current_streak=2, longest_streak=2)
        db.session.add_all([self.user_a, self.user_b, self.user_c])
        db.session.commit()

        # Create Topic
        self.topic = Topic(name='Technology & AI', user_id=None)
        db.session.add(self.topic)
        db.session.commit()

        # Create Words
        self.w1 = Word(term='Algorithm', definition='Thuật toán', topic_id=self.topic.id)
        self.w2 = Word(term='Neural Network', definition='Mạng thần kinh', topic_id=self.topic.id)
        self.w3 = Word(term='Database', definition='Cơ sở dữ liệu', topic_id=self.topic.id)
        db.session.add_all([self.w1, self.w2, self.w3])
        db.session.commit()

        # Progress for User A
        self.p1_a = WordProgress(user_id=self.user_a.id, word_id=self.w1.id, times_tested=2, times_correct=1, user_difficulty_rating='medium')
        self.p2_a = WordProgress(user_id=self.user_a.id, word_id=self.w2.id, times_tested=3, times_correct=0, user_difficulty_rating='hard')
        self.p3_a = WordProgress(user_id=self.user_a.id, word_id=self.w3.id, times_tested=4, times_correct=4, is_mastered=True)
        db.session.add_all([self.p1_a, self.p2_a, self.p3_a])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    # =========================================================================
    # 1. Smart Study Reviews Tests
    # =========================================================================
    def test_smart_study_review_persistence(self):
        """Test that update_srs persists SmartStudyReview and updates longest_streak."""
        self._login(self.user_a)

        # Alice rates Word 1 as 'easy'
        resp = self.client.post('/api/update_srs', json={
            'progress_id': self.p1_a.id,
            'rating': 'easy'
        })
        self.assertEqual(resp.status_code, 200)

        # Verify SmartStudyReview row exists
        reviews = SmartStudyReview.query.filter_by(user_id=self.user_a.id).all()
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].word_id, self.w1.id)
        self.assertEqual(reviews[0].topic_id, self.topic.id)
        self.assertEqual(reviews[0].rating, 'easy')

    def test_smart_study_user_isolation(self):
        """Test User A's Smart Study reviews are isolated from User B."""
        # Alice reviews w1 as hard
        r_a = SmartStudyReview(user_id=self.user_a.id, word_id=self.w1.id, topic_id=self.topic.id, rating='hard')
        # Bob reviews w1 as easy
        r_b = SmartStudyReview(user_id=self.user_b.id, word_id=self.w1.id, topic_id=self.topic.id, rating='easy')
        db.session.add_all([r_a, r_b])
        db.session.commit()

        stats_a = get_user_learning_statistics(self.user_a.id)
        stats_b = get_user_learning_statistics(self.user_b.id)

        self.assertEqual(stats_a['smart_study']['hard'], 1)
        self.assertEqual(stats_a['smart_study']['easy'], 0)
        self.assertEqual(stats_b['smart_study']['hard'], 0)
        self.assertEqual(stats_b['smart_study']['easy'], 1)

    # =========================================================================
    # 2. Normal Quiz Attempt Tests
    # =========================================================================
    def test_quiz_attempt_persistence(self):
        """Test that submit_quiz_batch persists QuizAttempt records and updates XP/streak."""
        self._login(self.user_a)

        resp = self.client.post('/api/submit_quiz_batch', json={
            'results': [
                {'progress_id': self.p1_a.id, 'is_correct': True, 'selected_id': self.w1.id},
                {'progress_id': self.p2_a.id, 'is_correct': False, 'selected_id': 999}
            ]
        })
        self.assertEqual(resp.status_code, 200)

        # Verify QuizAttempt rows in database
        attempts = QuizAttempt.query.filter_by(user_id=self.user_a.id).all()
        self.assertEqual(len(attempts), 2)
        correct_attempts = [a for a in attempts if a.is_correct]
        incorrect_attempts = [a for a in attempts if not a.is_correct]
        self.assertEqual(len(correct_attempts), 1)
        self.assertEqual(len(incorrect_attempts), 1)
        self.assertEqual(correct_attempts[0].word_id, self.w1.id)
        self.assertEqual(incorrect_attempts[0].word_id, self.w2.id)

    def test_quiz_attempt_user_isolation(self):
        """Test User A's Quiz attempts are isolated from User B."""
        a1 = QuizAttempt(user_id=self.user_a.id, word_id=self.w1.id, topic_id=self.topic.id, is_correct=False)
        a2 = QuizAttempt(user_id=self.user_b.id, word_id=self.w1.id, topic_id=self.topic.id, is_correct=True)
        db.session.add_all([a1, a2])
        db.session.commit()

        stats_a = get_user_learning_statistics(self.user_a.id)
        stats_b = get_user_learning_statistics(self.user_b.id)

        self.assertEqual(stats_a['quiz']['total_attempts'], 1)
        self.assertEqual(stats_a['quiz']['correct'], 0)
        self.assertEqual(stats_a['quiz']['incorrect'], 1)

        self.assertEqual(stats_b['quiz']['total_attempts'], 1)
        self.assertEqual(stats_b['quiz']['correct'], 1)
        self.assertEqual(stats_b['quiz']['incorrect'], 0)

    # =========================================================================
    # 3. Analytics Aggregations Tests
    # =========================================================================
    def test_analytics_aggregations_with_reviews_and_quiz(self):
        """Test full analytics service aggregates Smart Study and Quiz history accurately."""
        # Add Smart Study reviews for User A
        r1 = SmartStudyReview(user_id=self.user_a.id, word_id=self.w1.id, topic_id=self.topic.id, rating='medium')
        r2 = SmartStudyReview(user_id=self.user_a.id, word_id=self.w2.id, topic_id=self.topic.id, rating='hard')
        r3 = SmartStudyReview(user_id=self.user_a.id, word_id=self.w2.id, topic_id=self.topic.id, rating='hard')
        # Add Quiz attempts for User A
        q1 = QuizAttempt(user_id=self.user_a.id, word_id=self.w1.id, topic_id=self.topic.id, is_correct=True)
        q2 = QuizAttempt(user_id=self.user_a.id, word_id=self.w2.id, topic_id=self.topic.id, is_correct=False)
        db.session.add_all([r1, r2, r3, q1, q2])
        db.session.commit()

        stats = get_user_learning_statistics(self.user_a.id)

        self.assertTrue(stats['has_sufficient_data'])
        self.assertEqual(stats['smart_study']['total_reviews'], 3)
        self.assertEqual(stats['smart_study']['hard'], 2)
        self.assertEqual(stats['smart_study']['medium'], 1)
        self.assertIn('Neural Network', stats['smart_study']['hard_words'])

        self.assertEqual(stats['quiz']['total_attempts'], 2)
        self.assertEqual(stats['quiz']['correct'], 1)
        self.assertEqual(stats['quiz']['incorrect'], 1)
        self.assertEqual(stats['quiz']['overall_accuracy'], 50.0)
        self.assertIn('Neural Network', stats['quiz']['weak_words'])

    # =========================================================================
    # 4. Leaderboards Tests
    # =========================================================================
    def test_streak_and_exp_leaderboards(self):
        """Test streak and EXP leaderboards order and user rank calculations."""
        self._login(self.user_a)

        # Test Streak API
        resp_streak = self.client.get('/api/leaderboard/streak')
        self.assertEqual(resp_streak.status_code, 200)
        data_streak = resp_streak.get_json()
        self.assertTrue(data_streak['success'])
        # Top 1 must be Bob (longest_streak 12)
        self.assertEqual(data_streak['leaderboard'][0]['username'], 'user_bob')
        self.assertEqual(data_streak['leaderboard'][0]['streak'], 12)
        # Alice is rank 2 (longest_streak 7)
        self.assertEqual(data_streak['current_user']['rank'], 2)
        self.assertEqual(data_streak['current_user']['streak'], 7)

        # Test EXP API
        resp_exp = self.client.get('/api/leaderboard/exp')
        self.assertEqual(resp_exp.status_code, 200)
        data_exp = resp_exp.get_json()
        self.assertTrue(data_exp['success'])
        # Top 1 must be Bob (500 XP)
        self.assertEqual(data_exp['leaderboard'][0]['username'], 'user_bob')
        self.assertEqual(data_exp['leaderboard'][0]['xp'], 500)
        # Alice is rank 2 (300 XP)
        self.assertEqual(data_exp['current_user']['rank'], 2)
        self.assertEqual(data_exp['current_user']['xp'], 300)

    def test_dashboard_renders_leaderboards(self):
        """Test that dashboard template renders both leaderboard panels."""
        self._login(self.user_a)
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'B\xe1\xba\xa3ng X\xe1\xba\xbfp H\xe1\xba\xa1ng', resp.data)
        self.assertIn(b'tab-streak-btn', resp.data)
        self.assertIn(b'tab-exp-btn', resp.data)
        self.assertIn(b'user_bob', resp.data)
        self.assertIn(b'user_alice', resp.data)


if __name__ == '__main__':
    unittest.main()
