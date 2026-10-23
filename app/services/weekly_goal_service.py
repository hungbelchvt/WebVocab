"""
Weekly Learning Goal Service for WebVocab.
Handles goal configuration, historical tracking across weeks, and deterministic progress calculation
in the Asia/Ho_Chi_Minh timezone (Monday to Sunday).
Strictly prevents double counting of words or events.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy import func
from app.models import db, User, WeeklyGoal, WordProgress, SmartStudyReview, QuizAttempt


def get_vietnam_timezone():
    """
    Returns timezone for Asia/Ho_Chi_Minh (UTC+7).
    Resilient across Linux (Render) and Windows without crashing if tzdata package is missing.
    """
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Asia/Ho_Chi_Minh")
    except Exception:
        pass
    try:
        from dateutil import tz
        t = tz.gettz("Asia/Ho_Chi_Minh")
        if t is not None:
            return t
    except Exception:
        pass
    return timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")


def normalize_to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures a datetime object is timezone-aware UTC for safe comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_week_bounds(target_date: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Computes Monday 00:00:00 to Sunday 23:59:59.999999 for the given date in Asia/Ho_Chi_Minh timezone.
    Converts boundaries to UTC for querying UTC database timestamps.
    Returns ISO year, ISO week number, and human-readable Vietnamese week label.
    """
    vn_tz = get_vietnam_timezone()
    if target_date is None:
        target_date = datetime.now(vn_tz)
    elif target_date.tzinfo is None:
        target_date = target_date.replace(tzinfo=timezone.utc).astimezone(vn_tz)
    else:
        target_date = target_date.astimezone(vn_tz)

    # Monday is weekday 0, Sunday is weekday 6
    weekday = target_date.weekday()
    monday_date = target_date.date() - timedelta(days=weekday)
    sunday_date = monday_date + timedelta(days=6)

    start_vn = datetime.combine(monday_date, datetime.min.time(), tzinfo=vn_tz)
    end_vn = datetime.combine(sunday_date, datetime.max.time(), tzinfo=vn_tz)

    start_utc = start_vn.astimezone(timezone.utc)
    end_utc = end_vn.astimezone(timezone.utc)

    iso_year, iso_week, _ = target_date.isocalendar()

    week_label = f"Tuần {iso_week} ({monday_date.strftime('%d/%m')} - {sunday_date.strftime('%d/%m/%Y')})"

    return {
        "year": iso_year,
        "week_number": iso_week,
        "start_vn": start_vn,
        "end_vn": end_vn,
        "start_utc": start_utc,
        "end_utc": end_utc,
        "week_label": week_label
    }


def get_user_weekly_goal(user_id: int, year: int, week_number: int) -> Optional[WeeklyGoal]:
    """Retrieves the WeeklyGoal record for a user in a specific ISO week."""
    return WeeklyGoal.query.filter_by(
        user_id=user_id,
        year=year,
        week_number=week_number
    ).first()


def get_last_set_goal(user_id: int) -> Optional[WeeklyGoal]:
    """
    Retrieves the most recent WeeklyGoal set by this user across any week.
    Useful for suggesting or inheriting previous goal settings.
    """
    return WeeklyGoal.query.filter_by(
        user_id=user_id
    ).order_by(
        WeeklyGoal.year.desc(),
        WeeklyGoal.week_number.desc(),
        WeeklyGoal.updated_at.desc()
    ).first()


def set_or_update_weekly_goal(
    user_id: int,
    year: int,
    week_number: int,
    goal_type: str,
    target_value: int
) -> WeeklyGoal:
    """
    Sets or updates the weekly goal for a user for a given ISO week.
    Validates goal_type and target_value bounds.
    Does NOT award gamification XP or streak.
    """
    if goal_type not in ('words', 'sessions'):
        raise ValueError("Loại mục tiêu không hợp lệ. Vui lòng chọn 'words' hoặc 'sessions'.")

    try:
        target_value = int(target_value)
    except (ValueError, TypeError):
        raise ValueError("Giá trị mục tiêu phải là một số nguyên dương hợp lệ.")

    if goal_type == 'words':
        if target_value < 1 or target_value > 500:
            raise ValueError("Mục tiêu số từ mới phải nằm trong khoảng từ 1 đến 500 từ.")
    elif goal_type == 'sessions':
        if target_value < 1 or target_value > 100:
            raise ValueError("Mục tiêu số buổi học phải nằm trong khoảng từ 1 đến 100 buổi.")

    goal = get_user_weekly_goal(user_id, year, week_number)
    now_utc = datetime.now(timezone.utc)

    if goal:
        goal.goal_type = goal_type
        goal.target_value = target_value
        goal.updated_at = now_utc
    else:
        goal = WeeklyGoal(
            user_id=user_id,
            year=year,
            week_number=week_number,
            goal_type=goal_type,
            target_value=target_value,
            created_at=now_utc,
            updated_at=now_utc
        )
        db.session.add(goal)

    db.session.commit()
    return goal


def calculate_new_words_learned(user_id: int, start_utc: datetime, end_utc: datetime) -> int:
    """
    Calculates the number of distinct words learned FOR THE FIRST TIME in the given week interval.
    Criteria:
    - A word is learned when the user first interacted with it via SmartStudyReview or QuizAttempt.
    - If the earliest interaction timestamp across all history falls within [start_utc, end_utc],
      it counts as a new word learned in this week.
    - If the word was studied in any prior week, it is NOT counted (no double counting).
    - If the word is studied multiple times this week, it is counted exactly ONCE.
    - Enrolled words that have never been tested/reviewed are NOT counted.
    """
    # 1. Earliest SmartStudyReview per word for this user
    study_earliest = db.session.query(
        SmartStudyReview.word_id,
        func.min(SmartStudyReview.timestamp).label('min_time')
    ).filter(
        SmartStudyReview.user_id == user_id
    ).group_by(SmartStudyReview.word_id).all()

    # 2. Earliest QuizAttempt per word for this user
    quiz_earliest = db.session.query(
        QuizAttempt.word_id,
        func.min(QuizAttempt.timestamp).label('min_time')
    ).filter(
        QuizAttempt.user_id == user_id
    ).group_by(QuizAttempt.word_id).all()

    # Combine earliest interaction per word
    word_first_interaction: Dict[int, datetime] = {}

    for word_id, min_time in study_earliest:
        t_utc = normalize_to_utc(min_time)
        if t_utc:
            word_first_interaction[word_id] = t_utc

    for word_id, min_time in quiz_earliest:
        t_utc = normalize_to_utc(min_time)
        if t_utc:
            if word_id not in word_first_interaction or t_utc < word_first_interaction[word_id]:
                word_first_interaction[word_id] = t_utc

    # Fallback for WordProgress records where times_tested > 0 but review log table is absent
    tested_progress = WordProgress.query.filter(
        WordProgress.user_id == user_id,
        WordProgress.times_tested > 0
    ).all()

    for p in tested_progress:
        if p.word_id not in word_first_interaction and p.last_reviewed:
            t_utc = normalize_to_utc(p.last_reviewed)
            if t_utc:
                word_first_interaction[p.word_id] = t_utc

    # Count distinct words whose very first interaction falls strictly within the week
    new_words_count = 0
    start_utc_norm = normalize_to_utc(start_utc)
    end_utc_norm = normalize_to_utc(end_utc)

    for word_id, first_time in word_first_interaction.items():
        if start_utc_norm <= first_time <= end_utc_norm:
            new_words_count += 1

    return new_words_count


def calculate_completed_study_sessions(user_id: int, start_utc: datetime, end_utc: datetime) -> int:
    """
    Calculates completed study sessions in the week interval.
    Criteria:
    1. Quiz batches: Distinct Quiz submissions (attempts submitted together within 2 minutes).
    2. Smart Study sessions: Clusters of SmartStudyReviews where time gap between reviews is <= 15 minutes,
       and the cluster has at least 3 reviews (to prevent trivial 1-click fake sessions).
    Total sessions = Quiz sessions + Smart Study sessions.
    Strictly partitions events so no session is double counted.
    """
    start_utc_norm = normalize_to_utc(start_utc)
    end_utc_norm = normalize_to_utc(end_utc)

    # =========================================================================
    # A. Quiz Sessions (Batch Submissions)
    # =========================================================================
    quiz_attempts = QuizAttempt.query.filter(
        QuizAttempt.user_id == user_id,
        QuizAttempt.timestamp >= start_utc_norm,
        QuizAttempt.timestamp <= end_utc_norm
    ).order_by(QuizAttempt.timestamp.asc()).all()

    quiz_session_count = 0
    if quiz_attempts:
        last_quiz_time: Optional[datetime] = None
        for attempt in quiz_attempts:
            att_time = normalize_to_utc(attempt.timestamp)
            if att_time:
                if last_quiz_time is None or (att_time - last_quiz_time).total_seconds() > 120:
                    quiz_session_count += 1
                last_quiz_time = att_time

    # =========================================================================
    # B. Smart Study Sessions (Reviews with gap <= 15 min, cluster size >= 3)
    # =========================================================================
    study_reviews = SmartStudyReview.query.filter(
        SmartStudyReview.user_id == user_id,
        SmartStudyReview.timestamp >= start_utc_norm,
        SmartStudyReview.timestamp <= end_utc_norm
    ).order_by(SmartStudyReview.timestamp.asc()).all()

    study_session_count = 0
    if study_reviews:
        current_cluster_count = 0
        last_review_time: Optional[datetime] = None

        for rev in study_reviews:
            r_time = normalize_to_utc(rev.timestamp)
            if not r_time:
                continue

            if last_review_time is None:
                current_cluster_count = 1
                last_review_time = r_time
            elif (r_time - last_review_time).total_seconds() <= 900:  # <= 15 minutes
                current_cluster_count += 1
                last_review_time = r_time
            else:
                # Previous cluster finished, check if it met the minimum threshold
                if current_cluster_count >= 3:
                    study_session_count += 1
                current_cluster_count = 1
                last_review_time = r_time

        if current_cluster_count >= 3:
            study_session_count += 1

    return quiz_session_count + study_session_count


def get_weekly_goal_progress(user_id: int, target_date: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Synthesizes the complete weekly goal status and progress for a user.
    Returns goal parameters, current completion, percentage, remaining, suggestions, and history.
    """
    bounds = get_week_bounds(target_date)
    year = bounds["year"]
    week_number = bounds["week_number"]
    week_label = bounds["week_label"]
    start_utc = bounds["start_utc"]
    end_utc = bounds["end_utc"]

    goal = get_user_weekly_goal(user_id, year, week_number)
    last_goal = get_last_set_goal(user_id)

    # Compute both metrics so user can see actual activity regardless of goal status
    words_completed = calculate_new_words_learned(user_id, start_utc, end_utc)
    sessions_completed = calculate_completed_study_sessions(user_id, start_utc, end_utc)

    suggestions = {
        "words": [10, 20, 35, 50],
        "sessions": [3, 5, 7, 10]
    }

    last_goal_data = None
    if last_goal and (last_goal.year != year or last_goal.week_number != week_number):
        last_goal_data = {
            "year": last_goal.year,
            "week_number": last_goal.week_number,
            "goal_type": last_goal.goal_type,
            "target_value": last_goal.target_value,
            "type_label": "từ mới" if last_goal.goal_type == "words" else "buổi học"
        }

    if not goal:
        return {
            "has_goal": False,
            "goal_id": None,
            "year": year,
            "week_number": week_number,
            "week_label": week_label,
            "goal_type": "words",
            "target_value": 0,
            "current_value": 0,
            "percentage": 0,
            "is_completed": False,
            "remaining": 0,
            "unit": "",
            "current_words": words_completed,
            "current_sessions": sessions_completed,
            "last_goal": last_goal_data,
            "suggestions": suggestions
        }

    goal_type = goal.goal_type
    target_value = goal.target_value
    current_value = words_completed if goal_type == "words" else sessions_completed
    unit = "từ mới" if goal_type == "words" else "buổi học"

    percentage = min(100, int((current_value / target_value) * 100)) if target_value > 0 else 0
    is_completed = current_value >= target_value
    remaining = max(0, target_value - current_value)

    return {
        "has_goal": True,
        "goal_id": goal.id,
        "year": year,
        "week_number": week_number,
        "week_label": week_label,
        "goal_type": goal_type,
        "target_value": target_value,
        "current_value": current_value,
        "percentage": percentage,
        "is_completed": is_completed,
        "remaining": remaining,
        "unit": unit,
        "current_words": words_completed,
        "current_sessions": sessions_completed,
        "last_goal": last_goal_data,
        "suggestions": suggestions
    }
