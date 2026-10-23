"""
Unit and Integration Tests for Daily Word (Từ vựng mỗi ngày) and Weekly Learning Goal (Mục tiêu học tập hằng tuần).
Tests deterministic selection, caching, API fallbacks, timezone handling (Asia/Ho_Chi_Minh),
user isolation, progress calculation without double counting, and route permissions.
"""

import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from app import create_app
from app.models import db, User, Topic, Word, WordProgress, SmartStudyReview, QuizAttempt, WeeklyGoal
from app.services.daily_word_service import (
    get_daily_word,
    get_daily_word_raw,
    get_today_vn_date_str,
    clear_daily_word_cache,
    STATIC_FALLBACK_WORD,
    get_vietnam_timezone
)
from app.services.weekly_goal_service import (
    get_week_bounds,
    get_user_weekly_goal,
    get_last_set_goal,
    set_or_update_weekly_goal,
    calculate_new_words_learned,
    calculate_completed_study_sessions,
    get_weekly_goal_progress
)
from app.services.dictionary_service import DictionaryTimeoutError, DictionaryAPIError
from config import Config


class TestFeaturesConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-daily-weekly'


class TestDailyWordAndWeeklyGoal(unittest.TestCase):

    def setUp(self):
        self.app = create_app(TestFeaturesConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        clear_daily_word_cache()

        # Create Users
        self.user_a = User(username='alice', password_hash='hash_a', xp=100, current_streak=3, longest_streak=5)
        self.user_b = User(username='bob', password_hash='hash_b', xp=200, current_streak=1, longest_streak=2)
        db.session.add_all([self.user_a, self.user_b])
        db.session.commit()

        # Create Topic
        self.topic = Topic(name='Technology', user_id=None)
        db.session.add(self.topic)
        db.session.commit()

        # Create Words with rich attributes
        self.w1 = Word(
            term='Algorithm',
            ipa='ˈælɡərɪðəm',
            definition='A process or set of rules to be followed in calculations.',
            example_sentence='Search algorithms help find relevant information.',
            synonyms='procedure, method',
            antonyms='',
            difficulty='medium',
            topic_id=self.topic.id
        )
        self.w2 = Word(
            term='Bandwidth',
            ipa='ˈbændwɪdθ',
            definition='The amount of data that can be transmitted over a network.',
            example_sentence='Streaming high-definition video requires substantial bandwidth.',
            synonyms='capacity',
            antonyms='',
            difficulty='medium',
            topic_id=self.topic.id
        )
        self.w3 = Word(
            term='Compiler',
            ipa='kəmˈpaɪlər',
            definition='A program that converts instructions into machine-code.',
            example_sentence='The compiler detected syntax errors in the source code.',
            synonyms='translator',
            antonyms='',
            difficulty='hard',
            topic_id=self.topic.id
        )
        db.session.add_all([self.w1, self.w2, self.w3])
        db.session.commit()

    def tearDown(self):
        clear_daily_word_cache()
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    # =========================================================================
    # FEATURE 1: DAILY WORD TESTS
    # =========================================================================

    def test_daily_word_deterministic_same_day(self):
        """Verifies that queries for the same date always return the identical word."""
        date_test = "2026-10-23"
        word1 = get_daily_word_raw(date_test)
        word2 = get_daily_word_raw(date_test)

        self.assertEqual(word1["term"], word2["term"])
        self.assertEqual(word1["id"], word2["id"])
        self.assertEqual(word1["date"], date_test)

    def test_daily_word_cycles_on_different_days(self):
        """Verifies that consecutive dates cycle deterministically through eligible words."""
        day1 = get_daily_word_raw("2026-10-23")
        day2 = get_daily_word_raw("2026-10-24")

        # Since we have 3 words, day1 and day2 should be different words
        self.assertNotEqual(day1["term"], day2["term"])

    def test_daily_word_caching_avoids_repeated_api_calls(self):
        """Verifies that dictionary lookup is called at most once per day due to caching."""
        with patch('app.services.daily_word_service.dictionary_service.lookup') as mock_lookup:
            mock_lookup.return_value = {
                "term": "Algorithm",
                "ipa": "/ˈælɡərɪðəm/",
                "audio_url": "https://example.com/audio/algo.mp3",
                "part_of_speech": "noun",
                "definition": "A procedure",
                "synonyms": ["method"],
                "antonyms": []
            }

            # Call multiple times for the same date
            res1 = get_daily_word(date_str="2026-11-01")
            res2 = get_daily_word(date_str="2026-11-01")
            res3 = get_daily_word(date_str="2026-11-01")

            self.assertEqual(mock_lookup.call_count, 1)
            self.assertEqual(res1["audio_url"], "https://example.com/audio/algo.mp3")
            self.assertEqual(res2["audio_url"], "https://example.com/audio/algo.mp3")
            self.assertEqual(res3["audio_url"], "https://example.com/audio/algo.mp3")

    def test_daily_word_fallback_on_dictionary_api_failure(self):
        """Verifies that when dictionary API times out or fails, DB data is used gracefully."""
        with patch('app.services.daily_word_service.dictionary_service.lookup') as mock_lookup:
            mock_lookup.side_effect = DictionaryTimeoutError("Algorithm")

            word_data = get_daily_word(date_str="2026-12-05")
            self.assertIsNotNone(word_data)
            self.assertIn(word_data["term"], ["Algorithm", "Bandwidth", "Compiler"])
            self.assertTrue(len(word_data["definition"]) > 0)
            self.assertEqual(word_data["audio_url"], "")

    def test_daily_word_fallback_empty_database(self):
        """Verifies that when database has zero words, static fallback word is provided."""
        # Delete all words
        Word.query.delete()
        db.session.commit()
        clear_daily_word_cache()

        word_data = get_daily_word(date_str="2026-10-23")
        self.assertEqual(word_data["term"], STATIC_FALLBACK_WORD["term"])
        self.assertEqual(word_data["source"], "fallback")
        self.assertIsNone(word_data["id"])

    def test_viewing_daily_word_does_not_create_progress(self):
        """CRITICAL: Verifies viewing daily word does NOT automatically enroll the user."""
        initial_progress_count = WordProgress.query.filter_by(user_id=self.user_a.id).count()
        self.assertEqual(initial_progress_count, 0)

        # Alice views daily word
        daily = get_daily_word(user_id=self.user_a.id)
        self.assertFalse(daily["is_enrolled"])

        # Check DB
        after_count = WordProgress.query.filter_by(user_id=self.user_a.id).count()
        self.assertEqual(after_count, 0, "Viewing daily word must NOT create a WordProgress record!")

    def test_daily_word_learn_enrollment_authenticated(self):
        """Verifies that POST /daily-word/learn enrolls the authenticated user."""
        self._login(self.user_a)

        daily = get_daily_word(user_id=self.user_a.id)
        word_id = daily["id"]

        resp = self.client.post('/daily-word/learn', data={'word_id': word_id}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Progress should now exist
        progress = WordProgress.query.filter_by(user_id=self.user_a.id, word_id=word_id).first()
        self.assertIsNotNone(progress)
        self.assertEqual(progress.times_tested, 0)

        # Checking daily word again shows is_enrolled = True
        daily_updated = get_daily_word(user_id=self.user_a.id)
        self.assertTrue(daily_updated["is_enrolled"])

    def test_daily_word_learn_prevents_duplicate_enrollment(self):
        """Verifies that calling learn twice does not create duplicate WordProgress records."""
        self._login(self.user_a)
        daily = get_daily_word(user_id=self.user_a.id)
        word_id = daily["id"]

        # First enrollment
        self.client.post('/daily-word/learn', data={'word_id': word_id})
        # Second enrollment
        self.client.post('/daily-word/learn', data={'word_id': word_id})

        progress_records = WordProgress.query.filter_by(user_id=self.user_a.id, word_id=word_id).all()
        self.assertEqual(len(progress_records), 1)

    def test_daily_word_learn_unauthenticated_redirects(self):
        """Verifies unauthenticated visitors attempting to learn are redirected to login."""
        resp = self.client.post('/daily-word/learn', data={'word_id': self.w1.id})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers['Location'])

    def test_api_daily_word_endpoint(self):
        """Verifies GET /api/daily-word returns 200 OK and valid JSON."""
        resp = self.client.get('/api/daily-word')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("daily_word", data)
        self.assertIn("term", data["daily_word"])
        self.assertIn("definition", data["daily_word"])

    # =========================================================================
    # FEATURE 2: WEEKLY LEARNING GOAL TESTS
    # =========================================================================

    def test_week_bounds_vietnam_timezone(self):
        """Verifies Monday to Sunday calculations in Asia/Ho_Chi_Minh and UTC conversion."""
        vn_tz = get_vietnam_timezone()
        # Create a Friday date in VN: 2026-10-23 15:30:00+07:00
        test_dt = datetime(2026, 10, 23, 15, 30, 0, tzinfo=vn_tz)
        bounds = get_week_bounds(test_dt)

        self.assertEqual(bounds["year"], 2026)
        self.assertEqual(bounds["week_number"], 43)

        # Monday of this week should be 2026-10-19
        self.assertEqual(bounds["start_vn"].date(), datetime(2026, 10, 19).date())
        # Sunday of this week should be 2026-10-25
        self.assertEqual(bounds["end_vn"].date(), datetime(2026, 10, 25).date())

        # Start UTC: Monday 00:00:00 VN -> Sunday 17:00:00 UTC
        self.assertEqual(bounds["start_utc"].hour, 17)
        self.assertEqual(bounds["start_utc"].date(), datetime(2026, 10, 18).date())

    def test_set_and_update_weekly_goal(self):
        """Verifies user can set and update their weekly goal."""
        bounds = get_week_bounds()
        year = bounds["year"]
        week_num = bounds["week_number"]

        # 1. Set goal: 20 words
        goal = set_or_update_weekly_goal(self.user_a.id, year, week_num, 'words', 20)
        self.assertEqual(goal.user_id, self.user_a.id)
        self.assertEqual(goal.goal_type, 'words')
        self.assertEqual(goal.target_value, 20)

        # 2. Update goal: change to 5 sessions
        updated_goal = set_or_update_weekly_goal(self.user_a.id, year, week_num, 'sessions', 5)
        self.assertEqual(updated_goal.id, goal.id)
        self.assertEqual(updated_goal.goal_type, 'sessions')
        self.assertEqual(updated_goal.target_value, 5)

        # Verify only 1 row exists for (user_a, year, week_num)
        all_goals = WeeklyGoal.query.filter_by(user_id=self.user_a.id, year=year, week_number=week_num).all()
        self.assertEqual(len(all_goals), 1)

    def test_weekly_goal_validation(self):
        """Verifies validation rules for goal_type and target limits."""
        bounds = get_week_bounds()
        year = bounds["year"]
        week_num = bounds["week_number"]

        # Invalid goal type
        with self.assertRaises(ValueError):
            set_or_update_weekly_goal(self.user_a.id, year, week_num, 'invalid_type', 10)

        # Out-of-bounds target for words
        with self.assertRaises(ValueError):
            set_or_update_weekly_goal(self.user_a.id, year, week_num, 'words', 0)
        with self.assertRaises(ValueError):
            set_or_update_weekly_goal(self.user_a.id, year, week_num, 'words', 600)

        # Out-of-bounds target for sessions
        with self.assertRaises(ValueError):
            set_or_update_weekly_goal(self.user_a.id, year, week_num, 'sessions', 0)
        with self.assertRaises(ValueError):
            set_or_update_weekly_goal(self.user_a.id, year, week_num, 'sessions', 150)

    def test_user_isolation(self):
        """Verifies User A and User B maintain separate isolated goals."""
        bounds = get_week_bounds()
        year = bounds["year"]
        week_num = bounds["week_number"]

        set_or_update_weekly_goal(self.user_a.id, year, week_num, 'words', 35)
        set_or_update_weekly_goal(self.user_b.id, year, week_num, 'sessions', 7)

        goal_a = get_user_weekly_goal(self.user_a.id, year, week_num)
        goal_b = get_user_weekly_goal(self.user_b.id, year, week_num)

        self.assertEqual(goal_a.goal_type, 'words')
        self.assertEqual(goal_a.target_value, 35)
        self.assertEqual(goal_b.goal_type, 'sessions')
        self.assertEqual(goal_b.target_value, 7)

    def test_new_words_learned_calculation_no_double_counting(self):
        """
        CRITICAL TEST: Verifies that:
        1. A word studied for the first time this week is counted.
        2. A word studied in a prior week is NOT counted.
        3. A word studied multiple times this week is counted ONCE.
        4. Enrolled words with zero tests/reviews are NOT counted.
        """
        bounds = get_week_bounds()
        start_utc = bounds["start_utc"]
        end_utc = bounds["end_utc"]

        # Mid-week timestamp (e.g. Wednesday of this week)
        this_week_ts = start_utc + timedelta(days=2)
        # Prior week timestamp (10 days ago)
        prior_week_ts = start_utc - timedelta(days=10)

        # Word 1 (Algorithm): First studied 10 days ago (prior week)
        r_prior = SmartStudyReview(user_id=self.user_a.id, word_id=self.w1.id, topic_id=self.topic.id, rating='easy', timestamp=prior_week_ts)
        # Word 1 studied again THIS week (should NOT be counted as new)
        r_repeat = SmartStudyReview(user_id=self.user_a.id, word_id=self.w1.id, topic_id=self.topic.id, rating='hard', timestamp=this_week_ts)

        # Word 2 (Bandwidth): Studied for the FIRST time this week
        r_new1 = SmartStudyReview(user_id=self.user_a.id, word_id=self.w2.id, topic_id=self.topic.id, rating='medium', timestamp=this_week_ts)
        # Word 2 studied a second time this week (should be deduplicated)
        r_new2 = QuizAttempt(user_id=self.user_a.id, word_id=self.w2.id, topic_id=self.topic.id, is_correct=True, timestamp=this_week_ts + timedelta(hours=1))

        # Word 3 (Compiler): Enrolled but never studied (times_tested = 0)
        p3 = WordProgress(user_id=self.user_a.id, word_id=self.w3.id, times_tested=0)

        db.session.add_all([r_prior, r_repeat, r_new1, r_new2, p3])
        db.session.commit()

        # Calculate new words learned
        new_words = calculate_new_words_learned(self.user_a.id, start_utc, end_utc)

        # Only Word 2 (Bandwidth) was learned for the first time this week!
        self.assertEqual(new_words, 1, "Expected exactly 1 new word learned (Word 2), without double counting!")

    def test_completed_study_sessions_calculation(self):
        """
        CRITICAL TEST: Verifies session counting rules:
        1. A Quiz submission batch counts as 1 completed session.
        2. A Smart Study cluster with >= 3 reviews counts as 1 completed session.
        3. A trivial single card review (<3 reviews) does NOT count as a session.
        """
        bounds = get_week_bounds()
        start_utc = bounds["start_utc"]
        end_utc = bounds["end_utc"]
        t_base = start_utc + timedelta(days=1)

        # Session 1: Quiz batch of 3 questions submitted together (same timestamp)
        q1 = QuizAttempt(user_id=self.user_a.id, word_id=self.w1.id, is_correct=True, timestamp=t_base)
        q2 = QuizAttempt(user_id=self.user_a.id, word_id=self.w2.id, is_correct=False, timestamp=t_base)
        q3 = QuizAttempt(user_id=self.user_a.id, word_id=self.w3.id, is_correct=True, timestamp=t_base)

        # Session 2: Smart Study with 4 reviews within 5 minutes
        t_study = t_base + timedelta(hours=3)
        s1 = SmartStudyReview(user_id=self.user_a.id, word_id=self.w1.id, rating='easy', timestamp=t_study)
        s2 = SmartStudyReview(user_id=self.user_a.id, word_id=self.w2.id, rating='medium', timestamp=t_study + timedelta(minutes=1))
        s3 = SmartStudyReview(user_id=self.user_a.id, word_id=self.w3.id, rating='hard', timestamp=t_study + timedelta(minutes=2))
        s4 = SmartStudyReview(user_id=self.user_a.id, word_id=self.w1.id, rating='easy', timestamp=t_study + timedelta(minutes=3))

        # Trivial review: only 1 card reviewed (does NOT meet threshold of 3)
        t_trivial = t_base + timedelta(hours=8)
        s_trivial = SmartStudyReview(user_id=self.user_a.id, word_id=self.w1.id, rating='easy', timestamp=t_trivial)

        db.session.add_all([q1, q2, q3, s1, s2, s3, s4, s_trivial])
        db.session.commit()

        sessions = calculate_completed_study_sessions(self.user_a.id, start_utc, end_utc)
        # Expected: 1 quiz session + 1 smart study session = 2 sessions
        self.assertEqual(sessions, 2)

    def test_weekly_goal_progress_completion_and_no_duplicate_rewards(self):
        """Verifies is_completed state and ensures XP/streak are not modified by goal checking."""
        bounds = get_week_bounds()
        year = bounds["year"]
        week_num = bounds["week_number"]

        set_or_update_weekly_goal(self.user_a.id, year, week_num, 'words', 1)

        initial_xp = self.user_a.xp
        initial_streak = self.user_a.current_streak

        # Alice learns 1 new word this week
        now_utc = bounds["start_utc"] + timedelta(days=2)
        r = SmartStudyReview(user_id=self.user_a.id, word_id=self.w1.id, rating='easy', timestamp=now_utc)
        db.session.add(r)
        db.session.commit()

        progress_data = get_weekly_goal_progress(self.user_a.id)

        self.assertTrue(progress_data["has_goal"])
        self.assertTrue(progress_data["is_completed"])
        self.assertEqual(progress_data["percentage"], 100)
        self.assertEqual(progress_data["remaining"], 0)

        # Verify no XP or streak was arbitrarily granted
        user_fresh = db.session.get(User, self.user_a.id)
        self.assertEqual(user_fresh.xp, initial_xp, "Checking goal completion must NOT grant unconfigured XP!")
        self.assertEqual(user_fresh.current_streak, initial_streak, "Checking goal completion must NOT alter streak!")

    def test_goal_history_preserved_across_weeks(self):
        """Verifies that goals in previous weeks remain intact as history."""
        # Set goal for prior week (e.g. week 40)
        prior_goal = WeeklyGoal(
            user_id=self.user_a.id,
            year=2026,
            week_number=40,
            goal_type='words',
            target_value=25
        )
        db.session.add(prior_goal)
        db.session.commit()

        # Query current week (which is not week 40)
        bounds = get_week_bounds()
        current_progress = get_weekly_goal_progress(self.user_a.id)

        self.assertFalse(current_progress["has_goal"], "New week must show has_goal=False until set.")
        self.assertIsNotNone(current_progress["last_goal"], "Prior week goal should be available as last_goal.")
        self.assertEqual(current_progress["last_goal"]["target_value"], 25)

    def test_api_weekly_goal_endpoints(self):
        """Verifies GET and POST /api/weekly-goal JSON endpoints."""
        self._login(self.user_a)

        # 1. GET before setting goal
        resp_get = self.client.get('/api/weekly-goal')
        self.assertEqual(resp_get.status_code, 200)
        data_get = resp_get.get_json()
        self.assertTrue(data_get["success"])
        self.assertFalse(data_get["data"]["has_goal"])

        # 2. POST to set goal: 20 words
        resp_post = self.client.post('/api/weekly-goal', json={
            'goal_type': 'words',
            'target_value': 20
        })
        self.assertEqual(resp_post.status_code, 200)
        data_post = resp_post.get_json()
        self.assertTrue(data_post["success"])
        self.assertTrue(data_post["data"]["has_goal"])
        self.assertEqual(data_post["data"]["target_value"], 20)

        # 3. POST invalid data returns 400
        resp_bad = self.client.post('/api/weekly-goal', json={
            'goal_type': 'invalid',
            'target_value': 20
        })
        self.assertEqual(resp_bad.status_code, 400)

    def test_form_weekly_goal_set(self):
        """Verifies POST /weekly-goal/set form submission."""
        self._login(self.user_a)

        resp = self.client.post('/weekly-goal/set', data={
            'goal_type': 'sessions',
            'target_value': '5'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        bounds = get_week_bounds()
        goal = get_user_weekly_goal(self.user_a.id, bounds["year"], bounds["week_number"])
        self.assertIsNotNone(goal)
        self.assertEqual(goal.goal_type, 'sessions')
        self.assertEqual(goal.target_value, 5)


if __name__ == '__main__':
    unittest.main()
