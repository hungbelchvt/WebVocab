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
    'DictionaryAPIError'
]

