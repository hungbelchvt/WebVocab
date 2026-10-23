"""
Daily Word Service for WebVocab.
Selects and enriches a deterministic daily featured vocabulary item in Asia/Ho_Chi_Minh timezone.
Stable within the same day, cached to avoid repeated external Dictionary API calls,
with reliable fallbacks and zero automatic enrollment upon viewing.
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, Any, Optional, List
from app.models import db, Word, WordProgress, Topic
from app.services.dictionary_service import dictionary_service

logger = logging.getLogger(__name__)

# In-memory daily word cache: {date_str: enriched_word_dict}
_daily_word_cache: Dict[str, Dict[str, Any]] = {}

# Part of speech Vietnamese translation mapping
POS_VIETNAMESE_MAP = {
    "noun": "Danh từ",
    "verb": "Động từ",
    "adjective": "Tính từ",
    "adverb": "Trạng từ",
    "preposition": "Giới từ",
    "conjunction": "Liên từ",
    "pronoun": "Đại từ",
    "interjection": "Thán từ"
}

# Static emergency fallback word if database has zero words
STATIC_FALLBACK_WORD = {
    "id": None,
    "term": "Resilient",
    "ipa": "/rɪˈzɪliənt/",
    "part_of_speech": "adjective",
    "part_of_speech_vi": "Tính từ",
    "definition": "Có khả năng kiên cường phục hồi nhanh chóng từ khó khăn hoặc nghịch cảnh.",
    "example_sentence": "She remained resilient in the face of adversity.",
    "synonyms": ["tenacious", "hardy", "buoyant", "strong"],
    "antonyms": ["fragile", "vulnerable"],
    "audio_url": "https://api.dictionaryapi.dev/media/pronunciations/en/resilient-us.mp3",
    "topic_id": None,
    "topic_name": "Từ vựng nổi bật",
    "source": "fallback"
}


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


def get_today_vn_date_str() -> str:
    """Returns today's date formatted as YYYY-MM-DD in Asia/Ho_Chi_Minh timezone."""
    vn_tz = get_vietnam_timezone()
    return datetime.now(vn_tz).strftime("%Y-%m-%d")


def clear_daily_word_cache():
    """Clears the daily word in-memory cache (primarily used in unit testing)."""
    global _daily_word_cache
    _daily_word_cache.clear()


def _select_db_word_for_date(date_str: str) -> Optional[Word]:
    """
    Deterministically selects one eligible Word from the database based on the date.
    Uses date ordinal modulo total eligible words so that:
    1. Within the same date, the same word is always returned.
    2. Across consecutive dates, words cycle predictably.
    3. Independent of request randomness or server reloads.
    """
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        d = datetime.now(get_vietnam_timezone()).date()

    day_ordinal = d.toordinal()

    # Prioritize words with full details (definition and example sentence)
    eligible_words = Word.query.filter(
        Word.example_sentence.isnot(None),
        Word.example_sentence != '',
        Word.definition.isnot(None),
        Word.definition != ''
    ).order_by(Word.id.asc()).all()

    if not eligible_words:
        # Fallback to any words in database
        eligible_words = Word.query.order_by(Word.id.asc()).all()

    if not eligible_words:
        return None

    selected_index = day_ordinal % len(eligible_words)
    return eligible_words[selected_index]


def get_daily_word_raw(date_str: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieves and caches the raw daily word data for a given date (defaults to today in VN time).
    Enriches with Free Dictionary API (audio, part of speech) at most once per day.
    """
    if not date_str:
        date_str = get_today_vn_date_str()

    global _daily_word_cache
    if date_str in _daily_word_cache and _daily_word_cache[date_str] is not None:
        return _daily_word_cache[date_str].copy()

    db_word = _select_db_word_for_date(date_str)

    if not db_word:
        # Fallback if DB has no words
        data = STATIC_FALLBACK_WORD.copy()
        data["date"] = date_str
        _daily_word_cache[date_str] = data
        return data.copy()

    # Base payload extracted from the database
    ipa = db_word.ipa or ""
    if ipa and not ipa.startswith("/"):
        ipa = f"/{ipa}/"

    synonyms_list = [s.strip() for s in db_word.synonyms.split(",") if s.strip()] if db_word.synonyms else []
    antonyms_list = [a.strip() for a in db_word.antonyms.split(",") if a.strip()] if db_word.antonyms else []

    word_data: Dict[str, Any] = {
        "id": db_word.id,
        "term": db_word.term,
        "ipa": ipa,
        "definition": db_word.definition,
        "example_sentence": db_word.example_sentence or "",
        "synonyms": synonyms_list,
        "antonyms": antonyms_list,
        "difficulty": db_word.difficulty or "medium",
        "topic_id": db_word.topic_id,
        "topic_name": db_word.topic_category.name if db_word.topic_category else "Chung",
        "part_of_speech": "",
        "part_of_speech_vi": "",
        "audio_url": "",
        "date": date_str,
        "source": "database"
    }

    # Enrich once with Dictionary API (audio URL & part of speech)
    try:
        dict_data = dictionary_service.lookup(db_word.term)
        if dict_data:
            if dict_data.get("audio_url"):
                word_data["audio_url"] = dict_data["audio_url"]
            if not word_data["ipa"] and dict_data.get("ipa"):
                word_data["ipa"] = dict_data["ipa"]
            pos = (dict_data.get("part_of_speech") or "").lower().strip()
            if pos:
                word_data["part_of_speech"] = pos
                word_data["part_of_speech_vi"] = POS_VIETNAMESE_MAP.get(pos, pos.capitalize())
            if not word_data["synonyms"] and dict_data.get("synonyms"):
                word_data["synonyms"] = dict_data["synonyms"][:5]
    except Exception as e:
        logger.debug(f"Daily word dictionary enrichment skipped for '{db_word.term}': {e}")

    # If part of speech is still empty, derive a sensible default or leave blank
    if not word_data["part_of_speech_vi"] and word_data["part_of_speech"]:
        word_data["part_of_speech_vi"] = POS_VIETNAMESE_MAP.get(word_data["part_of_speech"], word_data["part_of_speech"].capitalize())

    # Cache for this date
    _daily_word_cache[date_str] = word_data
    return word_data.copy()


def get_daily_word(date_str: Optional[str] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Public entry point for Daily Word.
    Includes user enrollment status (is_enrolled) if user_id is provided.
    Does NOT automatically enroll the user.
    """
    word_data = get_daily_word_raw(date_str)

    is_enrolled = False
    if user_id and word_data.get("id"):
        progress = WordProgress.query.filter_by(
            user_id=user_id,
            word_id=word_data["id"]
        ).first()
        if progress:
            is_enrolled = True

    word_data["is_enrolled"] = is_enrolled
    word_data["is_authenticated"] = bool(user_id)
    return word_data
