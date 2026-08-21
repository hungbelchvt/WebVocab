"""
AI Service Layer for WebVocab.
Provides unified integration with Google Gemini API (gemini-3.6-flash default).
Handles client initialization, dynamic model selection, structured JSON parsing,
schema validation, rate limiting, and safe error wrapping.
"""

import os
import json
import re
import time
import logging
from typing import Type, TypeVar, Optional, Tuple, Any, Dict
from pydantic import BaseModel, ValidationError
from flask import current_app

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


# =====================================================================
# Custom Exceptions
# =====================================================================

class AIError(Exception):
    """Base exception for all AI service errors."""
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AIConfigurationError(AIError):
    """Raised when Gemini API key or configuration is missing or invalid."""
    def __init__(self, message: str = "Gemini API is not configured or missing API key."):
        super().__init__(message, status_code=503)


class AITimeoutError(AIError):
    """Raised when an AI request times out."""
    def __init__(self, message: str = "AI request timed out. Please try again later."):
        super().__init__(message, status_code=504)


class AIResponseError(AIError):
    """Raised when Gemini API returns an error or malformed payload."""
    def __init__(self, message: str, status_code: int = 502, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=status_code, details=details)


class AIValidationError(AIError):
    """Raised when AI response does not match the required Pydantic schema."""
    def __init__(self, message: str = "AI response failed schema validation.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=502, details=details)


class AIRateLimitError(AIError):
    """Raised when a user triggers requests faster than allowed cooldown."""
    def __init__(self, retry_after: int, message: Optional[str] = None):
        msg = message or f"Please wait {retry_after} seconds before requesting AI again."
        super().__init__(msg, status_code=429, details={"retry_after": retry_after})
        self.retry_after = retry_after


# =====================================================================
# AI Service Implementation
# =====================================================================

class AIService:
    """
    AI Service providing Gemini API interactions for WebVocab.
    Reads configuration dynamically from environment or Flask app config.
    """

    def __init__(self):
        self._client = None
        self._rate_limits: Dict[Tuple[int, str], float] = {}

    def get_api_key(self) -> str:
        """Fetch API key from Flask config or environment."""
        try:
            if current_app and current_app.config.get('GEMINI_API_KEY'):
                return current_app.config['GEMINI_API_KEY'].strip()
        except RuntimeError:
            pass  # Outside of app context
        return os.environ.get('GEMINI_API_KEY', '').strip()

    def get_model_name(self) -> str:
        """
        Fetch model name from Flask config or environment.
        Default is gemini-3.6-flash.
        """
        try:
            if current_app and current_app.config.get('GEMINI_MODEL'):
                return current_app.config['GEMINI_MODEL'].strip()
        except RuntimeError:
            pass
        return os.environ.get('GEMINI_MODEL', 'gemini-3.6-flash').strip()

    def get_timeout(self) -> int:
        """Fetch request timeout in seconds."""
        try:
            if current_app and current_app.config.get('AI_REQUEST_TIMEOUT'):
                return int(current_app.config['AI_REQUEST_TIMEOUT'])
        except (RuntimeError, ValueError):
            pass
        return int(os.environ.get('AI_REQUEST_TIMEOUT', '30'))

    def is_configured(self) -> bool:
        """Check if a non-empty API key is present."""
        api_key = self.get_api_key()
        return bool(api_key and not api_key.startswith('your_gemini_api_key'))

    def _get_client(self):
        """
        Lazy-initialize and return the Google GenAI client.
        Raises AIConfigurationError if API key is missing.
        """
        api_key = self.get_api_key()
        if not self.is_configured():
            raise AIConfigurationError(
                "Gemini API key is not configured. Please set GEMINI_API_KEY in your .env file."
            )

        try:
            from google import genai
            return genai.Client(api_key=api_key)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {str(e)}")
            raise AIConfigurationError(f"Could not initialize Gemini client: {str(e)}")

    def check_rate_limit(self, user_id: int, action: str, cooldown_seconds: int = 5) -> Tuple[bool, int]:
        """
        Check in-memory rate limit per user and action type.
        Returns (is_allowed, remaining_seconds).
        """
        key = (user_id, action)
        now = time.time()
        last_time = self._rate_limits.get(key, 0.0)
        elapsed = now - last_time

        if elapsed < cooldown_seconds:
            remaining = int(cooldown_seconds - elapsed) + 1
            return False, remaining

        self._rate_limits[key] = now
        return True, 0

    @staticmethod
    def _clean_json_text(text: str) -> str:
        """
        Strip markdown code blocks or surrounding text to extract raw JSON.
        Handles ```json ... ``` and ``` ... ``` blocks.
        """
        text = text.strip()
        # Look for markdown JSON code block
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # If text starts with [ or {, extract until the matching bracket
        if text.startswith('{') or text.startswith('['):
            return text
            
        # Fallback: search for first { or [ to last } or ]
        first_brace = text.find('{')
        first_bracket = text.find('[')
        
        starts = [pos for pos in (first_brace, first_bracket) if pos != -1]
        if starts:
            start_pos = min(starts)
            end_brace = text.rfind('}')
            end_bracket = text.rfind(']')
            end_pos = max(end_brace, end_bracket)
            if end_pos > start_pos:
                return text[start_pos:end_pos + 1].strip()

        return text

    def generate_structured(
        self,
        prompt: str,
        schema_class: Type[T],
        system_instruction: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> T:
        """
        Generate structured JSON output adhering to a Pydantic schema model.
        
        Parameters:
            prompt: The user or task prompt.
            schema_class: Pydantic BaseModel subclass defining the output structure.
            system_instruction: Optional system instruction/persona.
            timeout: Optional override for request timeout.

        Returns:
            Validated instance of schema_class.
        """
        client = self._get_client()
        model_name = self.get_model_name()
        req_timeout = timeout or self.get_timeout()

        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema_class,
                system_instruction=system_instruction
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )

            raw_text = response.text or ""
            if not raw_text:
                raise AIResponseError("Gemini returned an empty response.")

            clean_json = self._clean_json_text(raw_text)

            try:
                # Validate with Pydantic
                return schema_class.model_validate_json(clean_json)
            except ValidationError as ve:
                logger.warning(f"Schema validation error on structured output: {ve}. Trying parsed dict...")
                try:
                    data = json.loads(clean_json)
                    return schema_class(**data)
                except Exception as inner_e:
                    logger.error(f"Failed to validate AI response into {schema_class.__name__}: {inner_e}")
                    raise AIValidationError(
                        f"AI response failed schema validation for {schema_class.__name__}.",
                        details={"errors": str(ve), "raw_sample": clean_json[:300]}
                    )

        except AIError:
            raise
        except Exception as e:
            err_str = str(e)
            logger.error(f"Gemini API request failed: {err_str}", exc_info=True)
            if "timeout" in err_str.lower() or "deadline" in err_str.lower():
                raise AITimeoutError()
            if "429" in err_str or "quota" in err_str.lower() or "resource_exhausted" in err_str.lower():
                raise AIResponseError("AI service quota or rate limit exceeded. Please try again shortly.", status_code=429)
            if "401" in err_str or "403" in err_str or "api_key" in err_str.lower():
                raise AIConfigurationError("Invalid Gemini API key or unauthorized access.")
            raise AIResponseError(f"AI generation failed: {err_str}")

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> str:
        """
        Generate freeform text response from Gemini.
        
        Parameters:
            prompt: The input message.
            system_instruction: Optional system instruction.
            timeout: Optional timeout.

        Returns:
            Generated text string.
        """
        client = self._get_client()
        model_name = self.get_model_name()

        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                system_instruction=system_instruction
            ) if system_instruction else None

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )

            raw_text = response.text or ""
            if not raw_text:
                raise AIResponseError("Gemini returned an empty response.")
            return raw_text.strip()

        except AIError:
            raise
        except Exception as e:
            err_str = str(e)
            logger.error(f"Gemini text generation failed: {err_str}", exc_info=True)
            if "timeout" in err_str.lower() or "deadline" in err_str.lower():
                raise AITimeoutError()
            if "429" in err_str or "quota" in err_str.lower() or "resource_exhausted" in err_str.lower():
                raise AIResponseError("AI quota or rate limit exceeded.", status_code=429)
            if "401" in err_str or "403" in err_str:
                raise AIConfigurationError("Invalid Gemini API key.")
            raise AIResponseError(f"AI text generation failed: {err_str}")

    def explain_vocabulary(self, word: str) -> Any:
        """
        Phase 2: AI Vocabulary Assistant.
        Analyzes an English word and returns a structured VocabularyExplanation.
        """
        from app.services.schemas import VocabularyExplanation

        clean_word = word.strip()
        system_instruction = (
            "You are an expert English vocabulary tutor specifically helping Vietnamese learners. "
            "Analyze the requested English vocabulary word and provide a clear, accurate, and concise explanation tailored for vocabulary learning.\n"
            "Guidelines:\n"
            "1. Explain the most common and practical meaning first in Vietnamese.\n"
            "2. Provide standard IPA phonetic transcription (e.g., /əˈbændən/).\n"
            "3. Provide 2-3 natural, high-quality English example sentences demonstrating real-world usage with accurate Vietnamese translations.\n"
            "4. List up to 4-5 common English synonyms, antonyms, and collocations/phrases.\n"
            "5. Provide a memorable, creative memory tip (mnemonic) in Vietnamese.\n"
            "6. Return strictly structured JSON matching the requested schema."
        )

        prompt = f"Please explain the English vocabulary word: '{clean_word}' for a Vietnamese learner."
        return self.generate_structured(
            prompt=prompt,
            schema_class=VocabularyExplanation,
            system_instruction=system_instruction
        )

    def generate_personalized_quiz(self, candidates: list, question_count: int = 5) -> Any:
        """
        Phase 3: AI Quiz Generator.
        Generates diverse, high-quality quiz questions tailored to the user's candidate vocabulary.
        """
        from app.services.schemas import AIQuizResponse

        system_instruction = (
            "You are an expert English quiz creator and vocabulary examiner for Vietnamese learners. "
            "Your task is to generate diverse, engaging, and pedagogically sound quiz questions ONLY for the candidate vocabulary words provided.\n\n"
            "Question Types to create across the test:\n"
            "1. 'multiple_choice': Direct vocabulary meaning or definition question.\n"
            "2. 'fill_blank': An English sentence with '_____' where the target word fits correctly. 4 word options must be provided.\n"
            "3. 'context': A practical usage scenario or situation testing contextual understanding of the word.\n\n"
            "Requirements:\n"
            "- Generate questions ONLY using words from the candidate list.\n"
            "- Each question MUST have exactly 4 options in the 'options' array.\n"
            "- The 'answer' string MUST match exactly one of the 4 strings in 'options'.\n"
            "- Provide a clear 'explanation' in Vietnamese explaining why the answer is correct and clarifying the word's meaning.\n"
            "- Return strictly structured JSON matching the requested schema."
        )

        candidates_summary = "\n".join([
            f"- Word: '{c.get('term')}', Definition: '{c.get('definition')}'" +
            (f", Difficulty: {c.get('difficulty')}" if c.get('difficulty') else "") +
            (f", Accuracy: {int(c.get('accuracy', 0) * 100)}%" if 'accuracy' in c else "")
            for c in candidates
        ])

        prompt = (
            f"Please generate {question_count} personalized quiz questions for these specific candidate words:\n\n"
            f"{candidates_summary}\n\n"
            f"Total questions needed: {question_count}. Distribute question types (multiple_choice, fill_blank, context) across the questions."
        )

        return self.generate_structured(
            prompt=prompt,
            schema_class=AIQuizResponse,
            system_instruction=system_instruction
        )

    def analyze_learning_data(self, stats: dict) -> Any:
        """
        Phase 4: AI Learning Analysis.
        Analyzes real learner statistics and generates comprehensive pedagogical feedback.
        """
        from app.services.schemas import AILearningAnalysis

        system_instruction = (
            "You are an expert AI English Learning Coach and Educational Data Analyst for Vietnamese students. "
            "Your task is to analyze the student's real vocabulary performance data (accuracies, weak words, topic mastery, SRS review needs) "
            "and generate insightful, encouraging, and deeply practical learning feedback in Vietnamese.\n\n"
            "Guidelines:\n"
            "1. Ground all feedback strictly on the provided data. Do NOT invent new numbers or stats.\n"
            "2. Highlight positive strengths and mastered achievements first.\n"
            "3. Identify key vocabulary weaknesses and explain the likely cognitive causes.\n"
            "4. For each weak word and weak topic, provide concrete, actionable study advice (mnemonics, root words, collocations).\n"
            "5. Clearly list review priorities so the student knows what to focus on next.\n"
            "6. Return strictly structured JSON matching the AILearningAnalysis schema."
        )

        weak_words_text = "\n".join([
            f"- '{w['word']}' ({w['definition']}): accuracy {int(w['accuracy']*100)}%, tested {w['times_tested']} times, reason: {w['reason']}"
            for w in stats.get("weak_words", [])
        ]) or "None"

        topics_text = "\n".join([
            f"- Topic '{t['topic_name']}': {t['total_words']} words, accuracy {int(t['accuracy']*100)}%, mastered {t['mastered_words']} words, weak words: {t['weak_words_count']}"
            for t in stats.get("topic_stats", [])
        ]) or "None"

        due_text = ", ".join([w['word'] for w in stats.get("due_review_words", [])]) or "None"

        prompt = (
            f"Here is the student's current vocabulary learning report:\n\n"
            f"- Total Enrolled Words: {stats.get('total_words_enrolled', 0)}\n"
            f"- Tested Words: {stats.get('total_words_tested', 0)} (Total test attempts: {stats.get('total_tests_taken', 0)})\n"
            f"- Overall Accuracy: {stats.get('overall_accuracy_percentage', 0)}%\n"
            f"- Mastered Words: {stats.get('total_mastered_words', 0)} ({stats.get('mastery_percentage', 0)}%)\n"
            f"- Weak Words Count: {stats.get('total_weak_words', 0)}\n"
            f"- Words Due for SRS Review: {stats.get('total_due_reviews', 0)}\n\n"
            f"Weak Words Details:\n{weak_words_text}\n\n"
            f"Topic Performance:\n{topics_text}\n\n"
            f"Due Review Words: {due_text}\n\n"
            f"Please produce a comprehensive, structured learning analysis in Vietnamese for this learner."
        )

        return self.generate_structured(
            prompt=prompt,
            schema_class=AILearningAnalysis,
            system_instruction=system_instruction
        )



    @staticmethod
    def format_safe_error(error: Exception) -> Dict[str, Any]:
        """
        Format any exception into a safe JSON response for frontend consumption.
        Guarantees no API key, token, or sensitive backend info is exposed.
        """
        if isinstance(error, AIError):
            return {
                "success": False,
                "error": {
                    "type": error.__class__.__name__,
                    "message": error.message,
                    "status_code": error.status_code,
                    "details": error.details
                }
            }
        return {
            "success": False,
            "error": {
                "type": "InternalServerError",
                "message": "An unexpected error occurred while processing the AI request.",
                "status_code": 500
            }
        }


# Singleton service instance
ai_service = AIService()

