"""
AI Routes Blueprint for WebVocab.
Provides dedicated /api/ai/* endpoints and UI routes with authentication, validation,
error handling, and security protection.
"""

import re
from flask import Blueprint, jsonify, request, render_template, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import db, Topic, Word, WordProgress
from app.services.ai_service import (
    ai_service,
    AIError,
    AIConfigurationError,
    AITimeoutError,
    AIResponseError,
    AIValidationError,
    AIRateLimitError
)

# API Blueprint (prefix /api/ai)
ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')

# UI Blueprint for AI Pages (prefix /ai)
ai_ui_bp = Blueprint('ai_ui', __name__, url_prefix='/ai')


# =====================================================================
# Error Handlers for AI Blueprint
# =====================================================================

@ai_bp.errorhandler(AIError)
def handle_ai_error(error: AIError):
    """Format and return standard JSON error response for AI errors."""
    return jsonify(ai_service.format_safe_error(error)), error.status_code


@ai_bp.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
    """Catch-all for any unhandled exceptions in AI routes."""
    current_app.logger.error(f"Unexpected AI route error: {str(error)}", exc_info=True)
    return jsonify(ai_service.format_safe_error(error)), 500


# =====================================================================
# UI Route: AI Vocabulary Assistant Page
# =====================================================================

@ai_ui_bp.route('/vocabulary', methods=['GET'])
@login_required
def vocabulary_page():
    """Render the AI Vocabulary Assistant interface."""
    return render_template('ai_vocabulary.html')


# =====================================================================
# Phase 1: Status & Health Check
# =====================================================================

@ai_bp.route('/status', methods=['GET'])
@login_required
def ai_status():
    """
    Check AI configuration status for the authenticated user.
    Never exposes GEMINI_API_KEY.
    """
    is_configured = ai_service.is_configured()
    model_name = ai_service.get_model_name()

    return jsonify({
        "success": True,
        "configured": is_configured,
        "model": model_name,
        "status": "ready" if is_configured else "unconfigured",
        "user": current_user.username
    }), 200


# =====================================================================
# Phase 2: AI Vocabulary Assistant Endpoints
# =====================================================================

@ai_bp.route('/vocabulary', methods=['POST'])
@login_required
def ai_vocabulary():
    """
    Analyze an English word using Gemini 3.6 Flash.
    Returns structured JSON explanation tailored for Vietnamese learners.
    """
    data = request.get_json(silent=True) or {}
    raw_word = data.get('word', '')

    if not isinstance(raw_word, str):
        return jsonify({
            "success": False,
            "error": {
                "type": "ValidationError",
                "message": "Trường 'word' phải là một chuỗi văn bản.",
                "status_code": 400
            }
        }), 400

    word = raw_word.strip()

    # Input validation: reject empty or excessively long inputs
    if not word:
        return jsonify({
            "success": False,
            "error": {
                "type": "ValidationError",
                "message": "Vui lòng nhập từ vựng tiếng Anh cần giải thích.",
                "status_code": 400
            }
        }), 400

    if len(word) > 100:
        return jsonify({
            "success": False,
            "error": {
                "type": "ValidationError",
                "message": "Từ vựng nhập vào không được vượt quá 100 ký tự.",
                "status_code": 400
            }
        }), 400

    # Reject words containing invalid characters (allow letters, hyphens, spaces, apostrophes)
    if not re.match(r"^[a-zA-Z\s\-']+$", word):
        return jsonify({
            "success": False,
            "error": {
                "type": "ValidationError",
                "message": "Từ vựng chỉ được chứa chữ cái tiếng Anh, dấu gạch nối hoặc khoảng trắng.",
                "status_code": 400
            }
        }), 400

    # Rate limiting check: 2 seconds cooldown per user for vocabulary lookups
    allowed, remaining = ai_service.check_rate_limit(current_user.id, "vocab_assistant", cooldown_seconds=2)
    if not allowed:
        raise AIRateLimitError(retry_after=remaining)

    # Call AI Service with Gemini 3.6 Flash structured output
    result = ai_service.explain_vocabulary(word)

    return jsonify({
        "success": True,
        "data": result.model_dump()
    }), 200


@ai_bp.route('/topics', methods=['GET'])
@login_required
def get_user_topics():
    """
    Get all topics available for the current user to add vocabulary into.
    Returns user-created topics and any shared topics.
    """
    # Fetch topics created by current user
    user_topics = Topic.query.filter_by(user_id=current_user.id).order_by(Topic.name.asc()).all()
    
    # Also fetch all other topics in case user wants to add to them
    all_topics = Topic.query.order_by(Topic.name.asc()).all()
    
    # Combine uniquely with user's topics first
    seen_ids = set()
    topics_list = []
    
    for t in user_topics:
        seen_ids.add(t.id)
        topics_list.append({
            "id": t.id,
            "name": t.name,
            "is_owner": True,
            "word_count": len(t.words)
        })
        
    for t in all_topics:
        if t.id not in seen_ids:
            seen_ids.add(t.id)
            topics_list.append({
                "id": t.id,
                "name": t.name,
                "is_owner": False,
                "word_count": len(t.words)
            })

    return jsonify({
        "success": True,
        "topics": topics_list
    }), 200


@ai_bp.route('/vocabulary/add-to-topic', methods=['POST'])
@login_required
def add_vocabulary_to_topic():
    """
    Add an AI-generated vocabulary word into a specified Topic.
    Supports selecting an existing topic or creating a new topic if none exists.
    Checks for duplicate words before insertion.
    """
    data = request.get_json(silent=True) or {}
    
    topic_id = data.get('topic_id')
    new_topic_name = (data.get('new_topic_name') or '').strip()
    term = (data.get('word') or '').strip()
    ipa = (data.get('pronunciation') or '').strip()
    definition = (data.get('meaning_vi') or '').strip()
    
    # Extract first example sentence if available
    example_sentence = ""
    examples = data.get('examples', [])
    if isinstance(examples, list) and examples:
        first_ex = examples[0]
        if isinstance(first_ex, dict):
            sentence = first_ex.get('sentence', '')
            trans = first_ex.get('translation_vi', '')
            example_sentence = f"{sentence} ({trans})" if trans else sentence
        elif isinstance(first_ex, str):
            example_sentence = first_ex

    # Format synonyms and antonyms as comma-separated strings
    synonyms_raw = data.get('synonyms', [])
    if isinstance(synonyms_raw, list):
        synonyms_str = ", ".join(synonyms_raw[:5])
    else:
        synonyms_str = str(synonyms_raw or '')[:200]

    antonyms_raw = data.get('antonyms', [])
    if isinstance(antonyms_raw, list):
        antonyms_str = ", ".join(antonyms_raw[:5])
    else:
        antonyms_str = str(antonyms_raw or '')[:200]

    # Validation
    if not term:
        return jsonify({
            "success": False,
            "error": "Thiếu thông tin từ vựng."
        }), 400

    if not definition:
        return jsonify({
            "success": False,
            "error": "Thiếu định nghĩa / nghĩa tiếng Việt của từ."
        }), 400

    # Resolve or create Topic
    target_topic = None
    if new_topic_name:
        if len(new_topic_name) < 2 or len(new_topic_name) > 100:
            return jsonify({
                "success": False,
                "error": "Tên danh mục mới phải từ 2 đến 100 ký tự."
            }), 400

        # Check if topic with this name already exists for current user
        existing_topic = Topic.query.filter(
            Topic.user_id == current_user.id,
            func.lower(Topic.name) == func.lower(new_topic_name)
        ).first()

        if existing_topic:
            target_topic = existing_topic
        else:
            target_topic = Topic(name=new_topic_name, user_id=current_user.id)
            db.session.add(target_topic)
            db.session.commit()
    elif topic_id:
        try:
            topic_id_int = int(topic_id)
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "Mã danh mục không hợp lệ."
            }), 400

        target_topic = db.session.get(Topic, topic_id_int)
        if not target_topic:
            return jsonify({
                "success": False,
                "error": "Không tìm thấy danh mục được chọn."
            }), 404
    else:
        return jsonify({
            "success": False,
            "error": "Vui lòng chọn một danh mục hoặc nhập tên danh mục mới."
        }), 400

    # Duplicate check: check if word already exists in this topic
    existing_word = Word.query.filter(
        Word.topic_id == target_topic.id,
        func.lower(Word.term) == func.lower(term)
    ).first()

    if existing_word:
        return jsonify({
            "success": False,
            "duplicate": True,
            "error": f'Từ "{term}" đã có sẵn trong danh mục "{target_topic.name}".'
        }), 409

    # Create new Word
    new_word = Word(
        term=term,
        ipa=ipa or None,
        definition=definition,
        example_sentence=example_sentence or None,
        synonyms=synonyms_str or None,
        antonyms=antonyms_str or None,
        topic_id=target_topic.id,
        user_id=current_user.id
    )
    db.session.add(new_word)
    db.session.flush()

    # Automatically add WordProgress for current user (matching existing WebVocab design)
    existing_progress = WordProgress.query.filter_by(
        user_id=current_user.id,
        word_id=new_word.id
    ).first()

    if not existing_progress:
        progress = WordProgress(user_id=current_user.id, word_id=new_word.id)
        db.session.add(progress)

    db.session.commit()

    return jsonify({
        "success": True,
        "message": f'Đã thêm thành công từ "{new_word.term}" vào danh mục "{target_topic.name}"!',
        "word_id": new_word.id,
        "topic_id": target_topic.id,
        "topic_name": target_topic.name
    }), 201


# =====================================================================
# UI Route: AI Quiz Generator Page
# =====================================================================

@ai_ui_bp.route('/quiz', methods=['GET'])
@login_required
def quiz_page():
    """Render the AI Quiz Generator interface."""
    return render_template('ai_quiz.html')


# =====================================================================
# Candidate Selection Algorithm for AI Quiz
# =====================================================================

def select_quiz_candidates(user_id: int, topic_id: int = None, max_candidates: int = 15):
    """
    Select and rank candidate vocabulary for personalized quiz generation.
    Priority scoring:
    1. Words due for SRS review (+50)
    2. Words with low accuracy < 50% (+40), < 80% (+20)
    3. Words untested times_tested == 0 (+30)
    4. Words not mastered (+15)
    5. High user difficulty rating 'hard' (+20), 'medium' (+10)
    """
    from datetime import datetime, timezone

    query = WordProgress.query.join(Word).filter(WordProgress.user_id == user_id)
    if topic_id:
        query = query.filter(Word.topic_id == topic_id)

    progresses = query.all()
    if not progresses:
        return []

    now = datetime.now(timezone.utc)
    scored = []

    for p in progresses:
        score = 0
        # SRS due check (timezone-safe comparison)
        if p.next_review:
            nr = p.next_review.replace(tzinfo=timezone.utc) if p.next_review.tzinfo is None else p.next_review
            if nr <= now:
                score += 50


        # Accuracy & testing history
        if p.times_tested > 0:
            acc = p.times_correct / p.times_tested
            if acc < 0.5:
                score += 40
            elif acc < 0.8:
                score += 20
        else:
            score += 30  # Untested words need initial assessment

        # Mastery status
        if not p.is_mastered:
            score += 15

        # User difficulty rating
        if p.user_difficulty_rating == 'hard':
            score += 20
        elif p.user_difficulty_rating == 'medium':
            score += 10

        scored.append((score, p))

    # Sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)

    candidates = []
    for _, p in scored[:max_candidates]:
        acc = (p.times_correct / p.times_tested) if p.times_tested > 0 else 0.0
        candidates.append({
            'progress_id': p.id,
            'word_id': p.word.id,
            'term': p.word.term,
            'definition': p.word.definition,
            'difficulty': p.user_difficulty_rating or p.word.difficulty,
            'accuracy': acc,
            'times_tested': p.times_tested,
            'times_correct': p.times_correct
        })

    return candidates


# =====================================================================
# Phase 3: AI Quiz Generator Endpoint
# =====================================================================

@ai_bp.route('/quiz', methods=['POST'])
@login_required
def ai_quiz():
    """
    Generate personalized quiz questions using Gemini 3.6 Flash
    based on the user's real vocabulary and learning history.
    """
    data = request.get_json(silent=True) or {}

    raw_topic_id = data.get('topic_id')
    raw_count = data.get('question_count', 5)

    # Validate question_count
    try:
        count = int(raw_count)
        if count < 1 or count > 20:
            return jsonify({
                "success": False,
                "error": {
                    "type": "ValidationError",
                    "message": "Số lượng câu hỏi phải từ 1 đến 20 câu.",
                    "status_code": 400
                }
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": {
                "type": "ValidationError",
                "message": "Số lượng câu hỏi không hợp lệ.",
                "status_code": 400
            }
        }), 400

    # Validate topic_id if provided
    topic_id = None
    if raw_topic_id and raw_topic_id != 'all':
        try:
            topic_id = int(raw_topic_id)
            target_topic = db.session.get(Topic, topic_id)
            if not target_topic:
                return jsonify({
                    "success": False,
                    "error": {
                        "type": "NotFoundError",
                        "message": "Không tìm thấy danh mục được chọn.",
                        "status_code": 404
                    }
                }), 404
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": {
                    "type": "ValidationError",
                    "message": "Mã danh mục không hợp lệ.",
                    "status_code": 400
                }
            }), 400

    # Select candidates from user's real vocabulary data
    max_cands = max(10, count * 2)
    candidates = select_quiz_candidates(current_user.id, topic_id=topic_id, max_candidates=max_cands)

    if not candidates:
        msg = "Bạn chưa có từ vựng nào trong danh mục đã chọn." if topic_id else "Bạn chưa có từ vựng nào được ghi danh học. Hãy thêm từ vựng hoặc đăng ký danh mục để bắt đầu làm quiz."
        return jsonify({
            "success": False,
            "error": {
                "type": "NoVocabularyError",
                "message": msg,
                "status_code": 400
            }
        }), 400

    # Rate limiting: 3-second cooldown for quiz generation
    allowed, remaining = ai_service.check_rate_limit(current_user.id, "ai_quiz_generation", cooldown_seconds=3)
    if not allowed:
        raise AIRateLimitError(retry_after=remaining)

    # Call AI Service with candidate vocabulary
    result = ai_service.generate_personalized_quiz(candidates, question_count=min(count, len(candidates)))

    # Format questions and map back to WordProgress & Word records
    formatted_questions = []
    for q in result.questions:
        # Match candidate by term
        matched_cand = next(
            (c for c in candidates if c['term'].lower() == q.word.strip().lower()),
            candidates[0]
        )

        options = list(q.options) if isinstance(q.options, list) else []
        # Ensure answer is in options
        if q.answer not in options:
            options.append(q.answer)

        # Truncate/Pad to 4 options
        options = options[:4]
        while len(options) < 4:
            options.append("None of the above")

        # Find correct index
        try:
            correct_index = options.index(q.answer)
        except ValueError:
            correct_index = 0
            options[0] = q.answer

        options_list = [{"id": i, "def": opt} for i, opt in enumerate(options)]

        formatted_questions.append({
            "word": q.word,
            "type": q.type,
            "question": q.question,
            "options": options_list,
            "correct_id": correct_index,
            "answer": q.answer,
            "explanation": q.explanation,
            "progress_id": matched_cand['progress_id'],
            "word_id": matched_cand['word_id'],
            "target_term": matched_cand['term']
        })

    return jsonify({
        "success": True,
        "questions": formatted_questions,
        "total": len(formatted_questions)
    }), 200


# =====================================================================
# UI Route: AI Learning Analysis Page
# =====================================================================

@ai_ui_bp.route('/learning-analysis', methods=['GET'])
@login_required
def learning_analysis_page():
    """Render the AI Learning Analysis interface."""
    return render_template('ai_analysis.html')


# =====================================================================
# Phase 4: AI Learning Analysis Endpoint
# =====================================================================

@ai_bp.route('/learning-analysis', methods=['GET'])
@login_required
def ai_learning_analysis():
    """
    Perform deep learning analysis using Gemini 3.6 Flash
    grounded strictly on the user's real database learning statistics.
    """
    from app.services.analytics_service import get_user_learning_statistics

    # 1. Authoritative Backend Statistics Calculation
    stats = get_user_learning_statistics(current_user.id)

    # 2. Check if user has sufficient data
    if not stats["has_sufficient_data"]:
        return jsonify({
            "success": True,
            "has_data": False,
            "stats": stats,
            "message": "Chưa có đủ dữ liệu học tập để phân tích AI. Hãy làm ít nhất một bài quiz hoặc học thêm từ vựng để AI có thể đánh giá năng lực của bạn."
        }), 200

    # 3. Rate limiting: 3 seconds cooldown
    allowed, remaining = ai_service.check_rate_limit(current_user.id, "ai_learning_analysis", cooldown_seconds=3)
    if not allowed:
        raise AIRateLimitError(retry_after=remaining)

    # 4. Call AI Service with deterministic backend stats
    analysis_result = ai_service.analyze_learning_data(stats)

    return jsonify({
        "success": True,
        "has_data": True,
        "stats": stats,
        "analysis": analysis_result.model_dump()
    }), 200


# =====================================================================
# Phase 5+ Skeleton Handlers (To be implemented in subsequent phases)
# =====================================================================



@ai_bp.route('/study-plan', methods=['POST'])
@login_required
def ai_study_plan_skeleton():
    """Skeleton endpoint for AI Personalized Study Plan (Phase 5)."""
    return jsonify({
        "success": False,
        "message": "AI Personalized Study Plan endpoint is scheduled for Phase 5."
    }), 501


@ai_bp.route('/tutor', methods=['POST'])
@login_required
def ai_tutor_skeleton():
    """Skeleton endpoint for AI English Tutor (Phase 6)."""
    return jsonify({
        "success": False,
        "message": "AI English Tutor endpoint is scheduled for Phase 6."
    }), 501


@ai_bp.route('/recommendations', methods=['GET'])
@login_required
def ai_recommendations_skeleton():
    """Skeleton endpoint for AI Review Recommendation (Phase 7)."""
    return jsonify({
        "success": False,
        "message": "AI Review Recommendation endpoint is scheduled for Phase 7."
    }), 501

