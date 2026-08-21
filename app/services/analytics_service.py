"""
Analytics Service for WebVocab.
Computes authoritative mathematical statistics, detects weak words, evaluates topic-level performance,
analyzes Smart Study history (Easy/Medium/Hard) and normal Quiz attempts (Correct/Incorrect)
directly from the database. All calculations are deterministic and computed before AI interpretation.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List
from collections import defaultdict
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
    # 2. Smart Study (SRS) Historical Reviews Analytics
    # =========================================================================
    study_reviews = SmartStudyReview.query.filter_by(user_id=user_id).order_by(SmartStudyReview.timestamp.asc()).all()
    total_study_reviews = len(study_reviews)
    easy_count = sum(1 for r in study_reviews if r.rating == 'easy')
    medium_count = sum(1 for r in study_reviews if r.rating == 'medium')
    hard_count = sum(1 for r in study_reviews if r.rating == 'hard')

    # Word rating distribution in Smart Study
    word_study_counts = defaultdict(lambda: {"easy": 0, "medium": 0, "hard": 0, "term": "", "topic": "", "history": []})
    topic_study_hard_counts = defaultdict(int)

    for r in study_reviews:
        w_term = r.word.term if r.word else f"Word#{r.word_id}"
        t_name = r.topic.name if r.topic else (r.word.topic_category.name if r.word and r.word.topic_category else "Chung")
        word_study_counts[r.word_id]["term"] = w_term
        word_study_counts[r.word_id]["topic"] = t_name
        word_study_counts[r.word_id][r.rating] += 1
        word_study_counts[r.word_id]["history"].append(r.rating)
        if r.rating == 'hard':
            topic_study_hard_counts[t_name] += 1

    # Frequently marked hard and easy words
    hard_words_study = [
        {"word": v["term"], "topic": v["topic"], "hard_count": v["hard"], "total": sum([v["easy"], v["medium"], v["hard"]])}
        for v in word_study_counts.values() if v["hard"] > 0
    ]
    hard_words_study.sort(key=lambda x: (-x["hard_count"], -x["total"]))

    easy_words_study = [
        {"word": v["term"], "topic": v["topic"], "easy_count": v["easy"]}
        for v in word_study_counts.values() if v["easy"] > 0
    ]
    easy_words_study.sort(key=lambda x: -x["easy_count"])

    # Difficulty transitions (e.g. hard -> medium or medium -> easy)
    difficulty_transitions = []
    for wid, v in word_study_counts.items():
        hist = v["history"]
        if len(hist) >= 2:
            first_r, last_r = hist[0], hist[-1]
            if first_r != last_r:
                difficulty_transitions.append({
                    "word": v["term"],
                    "from_rating": first_r,
                    "to_rating": last_r,
                    "steps": len(hist)
                })

    # Hard topics in Smart Study
    hard_topics_study = sorted(topic_study_hard_counts.keys(), key=lambda t: -topic_study_hard_counts[t])

    # Recent 5 study reviews
    recent_study_reviews = [
        {
            "word": r.word.term if r.word else f"Word#{r.word_id}",
            "rating": r.rating,
            "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M") if r.timestamp else ""
        }
        for r in study_reviews[-5:]
    ]

    # =========================================================================
    # 3. Normal Quiz History Analytics
    # =========================================================================
    quiz_attempts = QuizAttempt.query.filter_by(user_id=user_id).order_by(QuizAttempt.timestamp.asc()).all()
    total_quiz_attempts = len(quiz_attempts)
    total_quiz_correct = sum(1 for a in quiz_attempts if a.is_correct)
    total_quiz_incorrect = total_quiz_attempts - total_quiz_correct
    overall_quiz_accuracy = round((total_quiz_correct / total_quiz_attempts * 100), 1) if total_quiz_attempts > 0 else 0.0

    word_quiz_stats = defaultdict(lambda: {"attempts": 0, "correct": 0, "term": "", "topic": ""})
    topic_quiz_stats = defaultdict(lambda: {"attempts": 0, "correct": 0})

    for a in quiz_attempts:
        w_term = a.word.term if a.word else f"Word#{a.word_id}"
        t_name = a.topic.name if a.topic else (a.word.topic_category.name if a.word and a.word.topic_category else "Chung")
        word_quiz_stats[a.word_id]["term"] = w_term
        word_quiz_stats[a.word_id]["topic"] = t_name
        word_quiz_stats[a.word_id]["attempts"] += 1
        if a.is_correct:
            word_quiz_stats[a.word_id]["correct"] += 1

        topic_quiz_stats[t_name]["attempts"] += 1
        if a.is_correct:
            topic_quiz_stats[t_name]["correct"] += 1

    # Categorize Quiz weak words (< 60% accuracy) and strong words (>= 80% accuracy)
    quiz_weak_words = []
    quiz_strong_words = []
    for wid, s in word_quiz_stats.items():
        acc = round(s["correct"] / s["attempts"] * 100, 1)
        entry = {"word": s["term"], "topic": s["topic"], "attempts": s["attempts"], "correct": s["correct"], "accuracy": acc}
        if acc < 60.0 or s["correct"] == 0:
            quiz_weak_words.append(entry)
        elif acc >= 80.0 and s["attempts"] >= 2:
            quiz_strong_words.append(entry)

    quiz_weak_words.sort(key=lambda x: (x["accuracy"], -x["attempts"]))
    quiz_strong_words.sort(key=lambda x: (-x["accuracy"], -x["attempts"]))

    # Categorize Quiz weak and strong topics
    quiz_weak_topics = []
    quiz_strong_topics = []
    for tname, s in topic_quiz_stats.items():
        acc = round(s["correct"] / s["attempts"] * 100, 1)
        entry = {"topic": tname, "attempts": s["attempts"], "correct": s["correct"], "accuracy": acc}
        if acc < 60.0:
            quiz_weak_topics.append(entry)
        elif acc >= 75.0:
            quiz_strong_topics.append(entry)

    quiz_weak_topics.sort(key=lambda x: x["accuracy"])
    quiz_strong_topics.sort(key=lambda x: -x["accuracy"])

    recent_mistakes = [
        {
            "word": a.word.term if a.word else f"Word#{a.word_id}",
            "topic": a.topic.name if a.topic else "Chung",
            "timestamp": a.timestamp.strftime("%Y-%m-%d %H:%M") if a.timestamp else ""
        }
        for a in quiz_attempts if not a.is_correct
    ][-5:]

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

