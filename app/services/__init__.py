"""
Services package for WebVocab.
Contains business logic services including AI Service integration.
"""
from app.services.ai_service import (
    AIService,
    ai_service,
    AIError,
    AIConfigurationError,
    AITimeoutError,
    AIResponseError,
    AIValidationError
)

from app.services.dictionary_service import (
    DictionaryService,
    dictionary_service,
    DictionaryError,
    DictionaryNotFoundError,
    DictionaryTimeoutError,
    DictionaryAPIError
)

from app.services.daily_word_service import (
    get_daily_word,
    get_daily_word_raw,
    get_today_vn_date_str,
    clear_daily_word_cache
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

__all__ = [
    'AIService',
    'ai_service',
    'AIError',
    'AIConfigurationError',
    'AITimeoutError',
    'AIResponseError',
    'AIValidationError',
    'DictionaryService',
    'dictionary_service',
    'DictionaryError',
    'DictionaryNotFoundError',
    'DictionaryTimeoutError',
    'DictionaryAPIError',
    'get_daily_word',
    'get_daily_word_raw',
    'get_today_vn_date_str',
    'clear_daily_word_cache',
    'get_week_bounds',
    'get_user_weekly_goal',
    'get_last_set_goal',
    'set_or_update_weekly_goal',
    'calculate_new_words_learned',
    'calculate_completed_study_sessions',
    'get_weekly_goal_progress'
]

