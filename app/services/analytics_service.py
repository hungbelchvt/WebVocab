"""
Analytics Service for WebVocab.
Computes authoritative mathematical statistics, detects weak words, evaluates topic-level performance,
and prioritizes review candidates directly from the database.
All numerical calculations are deterministic and computed here before AI interpretation.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List
from app.models import db, User, Topic, Word, WordProgress


def get_user_learning_statistics(user_id: int) -> Dict[str, Any]:
    """
    Aggregate and calculate all learning statistics for a given user.
    Pure backend calculations without AI hallucination.
    """
    now = datetime.now(timezone.utc)

    # Query all WordProgress records for this user joined with Word and Topic
    progress_records = WordProgress.query.join(Word).join(Topic).filter(
        WordProgress.user_id == user_id
    ).all()

    total_enrolled = len(progress_records)
    if total_enrolled == 0:
        return {
            "has_sufficient_data": False,
            "total_words_enrolled": 0,
            "total_words_tested": 0,
            "total_tests_taken": 0,
            "total_correct_answers": 0,
            "overall_accuracy": 0.0,
            "total_mastered_words": 0,
            "mastery_percentage": 0.0,
            "total_due_reviews": 0,
            "weak_words": [],
            "topic_stats": [],
            "due_review_words": [],
            "summary_sentence": "Bạn chưa ghi danh từ vựng nào."
        }

    total_tested_words = 0
    total_tests_taken = 0
    total_correct = 0
    mastered_count = 0
    due_reviews = []
    weak_words_list = []

    # Map for topic aggregations: topic_id -> stats dict
    topic_map = {}

    for p in progress_records:
        w = p.word
        t = w.topic_category or db.session.get(Topic, w.topic_id)
        topic_name = t.name if t else "Chung"
        topic_id = t.id if t else 0

        # Initialize topic entry if needed
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

        # Test statistics
        if p.times_tested > 0:
            total_tested_words += 1
            total_tests_taken += p.times_tested
            total_correct += p.times_correct
            topic_map[topic_id]["tested_words"] += 1
            topic_map[topic_id]["total_tests"] += p.times_tested
            topic_map[topic_id]["total_correct"] += p.times_correct

        # Mastery
        if p.is_mastered:
            mastered_count += 1
            topic_map[topic_id]["mastered_words"] += 1

        # SRS Due Check (timezone-safe, mastered words not considered due)
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

        # Weak word detection rules:
        # Rule 1: Tested >= 2 times with accuracy < 60%
        # Rule 2: Tested >= 1 time with 0 correct
        # Rule 3: User difficulty rating == 'hard' with accuracy < 75%
        # Rule 4: Tested >= 3 times, not mastered, accuracy < 70%
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
            reason = "Người dùng đánh giá khó & cần củng cố"
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

    # Sort weak words by severity (lowest accuracy and highest test count first)
    weak_words_list.sort(key=lambda x: (x["accuracy"], -x["times_tested"]))

    # Overall Metrics
    overall_accuracy = round((total_correct / total_tests_taken), 2) if total_tests_taken > 0 else 0.0
    mastery_percentage = round((mastered_count / total_enrolled * 100), 1) if total_enrolled > 0 else 0.0

    # Topic Stats formatting & weak topic detection
    topic_stats_list = []
    for t_data in topic_map.values():
        t_acc = round((t_data["total_correct"] / t_data["total_tests"]), 2) if t_data["total_tests"] > 0 else 0.0
        t_mastery = round((t_data["mastered_words"] / t_data["total_words"] * 100), 1) if t_data["total_words"] > 0 else 0.0
        
        # Topic is weak if tests were taken and accuracy < 60% or weak_words_ratio >= 40%
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

    # Sort topics by accuracy ascending (weakest first)
    topic_stats_list.sort(key=lambda x: (x["accuracy"], -x["weak_words_count"]))

    has_sufficient_data = total_tests_taken >= 1 or len(weak_words_list) > 0 or total_enrolled >= 3

    return {
        "has_sufficient_data": has_sufficient_data,
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
        "weak_words": weak_words_list[:10],  # Top 10 weak words for focus
        "topic_stats": topic_stats_list,
        "due_review_words": due_reviews[:10]
    }
