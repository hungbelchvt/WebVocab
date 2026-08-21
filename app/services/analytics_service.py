"""
Analytics Service for WebVocab.
Computes authoritative mathematical statistics, detects weak words, evaluates topic-level performance,
analyzes Smart Study history (Easy/Medium/Hard) and normal Quiz attempts (Correct/Incorrect)
directly from the database. All calculations are deterministic and computed before AI interpretation.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List
from collections import defaultdict
from sqlalchemy import func, case
from app.models import db, User, Topic, Word, WordProgress, SmartStudyReview, QuizAttempt


def get_user_learning_statistics(user_id: int) -> Dict[str, Any]:
    """
    Aggregate and calculate all learning statistics for a given user.
    Integrates WordProgress, SmartStudyReview history, and QuizAttempt history.
    Pure backend calculations without AI hallucination.
    """
    now = datetime.now(timezone.utc)
    user = db.session.get(User, user_id)
    user_xp = user.xp if user else 0
    user_level = user.level if user else 1
    current_streak = user.current_streak if user else 0
    longest_streak = user.longest_streak if user and user.longest_streak else current_streak

    # =========================================================================
    # 1. WordProgress & Spaced Repetition (SRS) Data
    # =========================================================================
    progress_records = WordProgress.query.join(Word).outerjoin(Topic, Word.topic_id == Topic.id).filter(
        WordProgress.user_id == user_id
    ).all()

    total_enrolled = len(progress_records)
    total_tested_words = 0
    total_tests_taken = 0
    total_correct = 0
    mastered_count = 0
    due_reviews = []
    weak_words_list = []
    topic_map = {}

    for p in progress_records:
        w = p.word
        t = w.topic_category or (db.session.get(Topic, w.topic_id) if w.topic_id else None)
        topic_name = t.name if t else "Chung"
        topic_id = t.id if t else 0

        if topic_id not in topic_map:
            topic_map[topic_id] = {
                "topic_id": topic_id,
                "topic_name": topic_name,
                "total_words": 0,
                "tested_words": 0,
                "total_tests": 0,
                "total_correct": 0,
                "mastered_words": 0,
                "weak_words_count": 0
            }

        topic_map[topic_id]["total_words"] += 1

        if p.times_tested > 0:
            total_tested_words += 1
            total_tests_taken += p.times_tested
            total_correct += p.times_correct
            topic_map[topic_id]["tested_words"] += 1
            topic_map[topic_id]["total_tests"] += p.times_tested
            topic_map[topic_id]["total_correct"] += p.times_correct

        if p.is_mastered:
            mastered_count += 1
            topic_map[topic_id]["mastered_words"] += 1

        # SRS Due Check
        is_due = False
        if not p.is_mastered and p.next_review:
            nr = p.next_review.replace(tzinfo=timezone.utc) if p.next_review.tzinfo is None else p.next_review
            if nr <= now:
                is_due = True
                due_reviews.append({
                    "word": w.term,
                    "definition": w.definition,
                    "topic_name": topic_name,
                    "next_review": nr.strftime("%Y-%m-%d %H:%M")
                })

        acc = (p.times_correct / p.times_tested) if p.times_tested > 0 else 0.0
        is_weak = False
        reason = ""

        if p.times_tested >= 2 and acc < 0.6:
            is_weak = True
            reason = f"Độ chính xác thấp ({int(acc * 100)}% sau {p.times_tested} lần kiểm tra)"
        elif p.times_tested >= 1 and p.times_correct == 0:
            is_weak = True
            reason = f"Chưa từng trả lời đúng ({p.times_tested} lần sai)"
        elif p.user_difficulty_rating == 'hard' and (p.times_tested == 0 or acc < 0.75):
            is_weak = True
            reason = "Người dùng đánh giá Khó & cần củng cố"
        elif p.times_tested >= 3 and not p.is_mastered and acc < 0.7:
            is_weak = True
            reason = "Luyện tập nhiều lần nhưng chưa đạt mức thành thạo"

        if is_weak:
            topic_map[topic_id]["weak_words_count"] += 1
            weak_words_list.append({
                "word": w.term,
                "definition": w.definition,
                "topic_name": topic_name,
                "times_tested": p.times_tested,
                "times_correct": p.times_correct,
                "accuracy": round(acc, 2),
                "difficulty_rating": p.user_difficulty_rating or "medium",
                "is_due": is_due,
                "reason": reason
            })

    # Sort weak words by lowest accuracy first
    weak_words_list.sort(key=lambda x: (x["accuracy"], -x["times_tested"]))

    # =========================================================================
    # 2. Smart Study (SRS) Historical Reviews Analytics (Optimized SQL)
    # =========================================================================
    # Aggregated rating counts via SQL GROUP BY
    rating_counts = db.session.query(
        SmartStudyReview.rating,
        func.count(SmartStudyReview.id)
    ).filter(
        SmartStudyReview.user_id == user_id
    ).group_by(SmartStudyReview.rating).all()

    rating_dict = {r: count for r, count in rating_counts}
    easy_count = rating_dict.get('easy', 0)
    medium_count = rating_dict.get('medium', 0)
    hard_count = rating_dict.get('hard', 0)
    total_study_reviews = easy_count + medium_count + hard_count

    # Hard words in Smart Study (Grouped by word, limit top 5)
    hard_words_study_rows = db.session.query(
        Word.term,
        Topic.name,
        func.count(SmartStudyReview.id).label('hard_count')
    ).join(Word, SmartStudyReview.word_id == Word.id
    ).outerjoin(Topic, SmartStudyReview.topic_id == Topic.id
    ).filter(
        SmartStudyReview.user_id == user_id,
        SmartStudyReview.rating == 'hard'
    ).group_by(Word.term, Topic.name
    ).order_by(func.count(SmartStudyReview.id).desc()
    ).limit(5).all()

    hard_words_study = [
        {"word": term, "topic": topic_name or "Chung", "hard_count": count, "total": count}
        for term, topic_name, count in hard_words_study_rows
    ]

    # Easy words in Smart Study (Grouped by word, limit top 5)
    easy_words_study_rows = db.session.query(
        Word.term,
        Topic.name,
        func.count(SmartStudyReview.id).label('easy_count')
    ).join(Word, SmartStudyReview.word_id == Word.id
    ).outerjoin(Topic, SmartStudyReview.topic_id == Topic.id
    ).filter(
        SmartStudyReview.user_id == user_id,
        SmartStudyReview.rating == 'easy'
    ).group_by(Word.term, Topic.name
    ).order_by(func.count(SmartStudyReview.id).desc()
    ).limit(5).all()

    easy_words_study = [
        {"word": term, "topic": topic_name or "Chung", "easy_count": count}
        for term, topic_name, count in easy_words_study_rows
    ]

    # Hard topics in Smart Study (Grouped by topic)
    hard_topics_rows = db.session.query(
        Topic.name,
        func.count(SmartStudyReview.id).label('hard_count')
    ).join(Topic, SmartStudyReview.topic_id == Topic.id
    ).filter(
        SmartStudyReview.user_id == user_id,
        SmartStudyReview.rating == 'hard'
    ).group_by(Topic.name
    ).order_by(func.count(SmartStudyReview.id).desc()
    ).limit(3).all()

    hard_topics_study = [tname for tname, _ in hard_topics_rows if tname]

    # Difficulty transitions (Recent word review history transitions)
    difficulty_transitions = []

    # Recent 5 study reviews (Indexed SQL LIMIT 5)
    recent_study_rows = db.session.query(
        Word.term,
        SmartStudyReview.rating,
        SmartStudyReview.timestamp
    ).join(Word, SmartStudyReview.word_id == Word.id
    ).filter(
        SmartStudyReview.user_id == user_id
    ).order_by(SmartStudyReview.timestamp.desc()
    ).limit(5).all()

    recent_study_reviews = [
        {
            "word": term,
            "rating": rating,
            "timestamp": ts.strftime("%Y-%m-%d %H:%M") if ts else ""
        }
        for term, rating, ts in reversed(recent_study_rows)
    ]

    # =========================================================================
    # 3. Normal Quiz History Analytics (Optimized SQL)
    # =========================================================================
    quiz_totals = db.session.query(
        func.count(QuizAttempt.id).label('total'),
        func.coalesce(func.sum(case((QuizAttempt.is_correct == True, 1), else_=0)), 0).label('correct')
    ).filter(
        QuizAttempt.user_id == user_id
    ).first()

    total_quiz_attempts = quiz_totals.total if quiz_totals else 0
    total_quiz_correct = int(quiz_totals.correct) if quiz_totals else 0
    total_quiz_incorrect = total_quiz_attempts - total_quiz_correct
    overall_quiz_accuracy = round((total_quiz_correct / total_quiz_attempts * 100), 1) if total_quiz_attempts > 0 else 0.0

    # Word-level quiz statistics grouped by word
    word_quiz_rows = db.session.query(
        Word.term,
        Topic.name,
        func.count(QuizAttempt.id).label('attempts'),
        func.coalesce(func.sum(case((QuizAttempt.is_correct == True, 1), else_=0)), 0).label('correct')
    ).join(Word, QuizAttempt.word_id == Word.id
    ).outerjoin(Topic, QuizAttempt.topic_id == Topic.id
    ).filter(
        QuizAttempt.user_id == user_id
    ).group_by(Word.term, Topic.name
    ).all()

    quiz_weak_words = []
    quiz_strong_words = []
    for term, topic_name, attempts, correct in word_quiz_rows:
        acc = round(int(correct) / attempts * 100, 1) if attempts > 0 else 0.0
        entry = {"word": term, "topic": topic_name or "Chung", "attempts": attempts, "correct": int(correct), "accuracy": acc}
        if acc < 60.0 or correct == 0:
            quiz_weak_words.append(entry)
        elif acc >= 80.0 and attempts >= 2:
            quiz_strong_words.append(entry)

    quiz_weak_words.sort(key=lambda x: (x["accuracy"], -x["attempts"]))
    quiz_strong_words.sort(key=lambda x: (-x["accuracy"], -x["attempts"]))

    # Topic-level quiz statistics grouped by topic
    topic_quiz_rows = db.session.query(
        Topic.name,
        func.count(QuizAttempt.id).label('attempts'),
        func.coalesce(func.sum(case((QuizAttempt.is_correct == True, 1), else_=0)), 0).label('correct')
    ).join(Topic, QuizAttempt.topic_id == Topic.id
    ).filter(
        QuizAttempt.user_id == user_id
    ).group_by(Topic.name
    ).all()

    quiz_weak_topics = []
    quiz_strong_topics = []
    for topic_name, attempts, correct in topic_quiz_rows:
        acc = round(int(correct) / attempts * 100, 1) if attempts > 0 else 0.0
        entry = {"topic": topic_name or "Chung", "attempts": attempts, "correct": int(correct), "accuracy": acc}
        if acc < 60.0:
            quiz_weak_topics.append(entry)
        elif acc >= 75.0:
            quiz_strong_topics.append(entry)

    quiz_weak_topics.sort(key=lambda x: x["accuracy"])
    quiz_strong_topics.sort(key=lambda x: -x["accuracy"])

    # Recent 5 mistakes (SQL limit 5)
    recent_mistakes_rows = db.session.query(
        Word.term,
        Topic.name,
        QuizAttempt.timestamp
    ).join(Word, QuizAttempt.word_id == Word.id
    ).outerjoin(Topic, QuizAttempt.topic_id == Topic.id
    ).filter(
        QuizAttempt.user_id == user_id,
        QuizAttempt.is_correct == False
    ).order_by(QuizAttempt.timestamp.desc()
    ).limit(5).all()

    recent_mistakes = [
        {
            "word": term,
            "topic": topic_name or "Chung",
            "timestamp": ts.strftime("%Y-%m-%d %H:%M") if ts else ""
        }
        for term, topic_name, ts in reversed(recent_mistakes_rows)
    ]

    # =========================================================================
    # 4. Synthesize Unified Statistics & Metrics
    # =========================================================================
    overall_tests_count = total_tests_taken + total_quiz_attempts
    overall_correct_count = total_correct + total_quiz_correct
    overall_accuracy = round((overall_correct_count / overall_tests_count), 2) if overall_tests_count > 0 else (
        round(total_correct / total_tests_taken, 2) if total_tests_taken > 0 else 0.0
    )
    mastery_percentage = round((mastered_count / total_enrolled * 100), 1) if total_enrolled > 0 else 0.0

    topic_stats_list = []
    for t_data in topic_map.values():
        t_acc = round((t_data["total_correct"] / t_data["total_tests"]), 2) if t_data["total_tests"] > 0 else 0.0
        t_mastery = round((t_data["mastered_words"] / t_data["total_words"] * 100), 1) if t_data["total_words"] > 0 else 0.0
        is_weak_topic = False
        if t_data["total_tests"] >= 1 and t_acc < 0.6:
            is_weak_topic = True
        elif t_data["total_words"] >= 2 and (t_data["weak_words_count"] / t_data["total_words"]) >= 0.4:
            is_weak_topic = True

        topic_stats_list.append({
            "topic_id": t_data["topic_id"],
            "topic_name": t_data["topic_name"],
            "total_words": t_data["total_words"],
            "tested_words": t_data["tested_words"],
            "mastered_words": t_data["mastered_words"],
            "mastery_percentage": t_mastery,
            "accuracy": t_acc,
            "weak_words_count": t_data["weak_words_count"],
            "is_weak": is_weak_topic
        })

    topic_stats_list.sort(key=lambda x: (x["accuracy"], -x["weak_words_count"]))

    # Sufficiency check: user has enrolled words and taken tests/study reviews/quiz attempts
    has_sufficient_data = (
        total_tests_taken >= 1 or
        total_study_reviews >= 1 or
        total_quiz_attempts >= 1 or
        len(weak_words_list) > 0 or
        total_enrolled >= 3
    )

    return {
        "has_sufficient_data": has_sufficient_data,
        "user_id": user_id,
        "xp": user_xp,
        "level": user_level,
        "current_streak": current_streak,
        "longest_streak": longest_streak,

        # Overall Learning Metrics
        "total_words_enrolled": total_enrolled,
        "total_words_tested": total_tested_words,
        "total_tests_taken": total_tests_taken,
        "total_correct_answers": total_correct,
        "overall_accuracy": overall_accuracy,
        "overall_accuracy_percentage": int(overall_accuracy * 100),
        "total_mastered_words": mastered_count,
        "mastery_percentage": mastery_percentage,
        "total_due_reviews": len(due_reviews),
        "total_weak_words": len(weak_words_list),
        "weak_words": weak_words_list[:10],
        "topic_stats": topic_stats_list,
        "due_review_words": due_reviews[:10],

        # Smart Study History
        "smart_study": {
            "total_reviews": total_study_reviews,
            "easy": easy_count,
            "medium": medium_count,
            "hard": hard_count,
            "hard_words": [w["word"] for w in hard_words_study[:5]],
            "hard_words_detail": hard_words_study[:5],
            "easy_words": [w["word"] for w in easy_words_study[:5]],
            "hard_topics": hard_topics_study[:3],
            "recent_reviews": recent_study_reviews,
            "difficulty_transitions": difficulty_transitions[:5]
        },

        # Normal Quiz History
        "quiz": {
            "total_attempts": total_quiz_attempts,
            "correct": total_quiz_correct,
            "incorrect": total_quiz_incorrect,
            "overall_accuracy": overall_quiz_accuracy,
            "weak_words": [w["word"] for w in quiz_weak_words[:5]],
            "weak_words_detail": quiz_weak_words[:5],
            "strong_words": [w["word"] for w in quiz_strong_words[:5]],
            "weak_topics": [t["topic"] for t in quiz_weak_topics[:3]],
            "strong_topics": [t["topic"] for t in quiz_strong_topics[:3]],
            "recent_mistakes": recent_mistakes
        }
    }

