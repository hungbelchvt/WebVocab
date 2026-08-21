"""
Free Dictionary API Service for WebVocab.
Integrates with https://api.dictionaryapi.dev/api/v2/entries/en/<word>
Provides clean abstraction, error handling, timeout resilience, audio extraction,
and data normalization for English vocabulary lookup.
"""

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DictionaryError(Exception):
    """Base exception for Dictionary Service errors."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DictionaryNotFoundError(DictionaryError):
    """Raised when word is not found in the dictionary."""
    def __init__(self, word: str):
        super().__init__(f"No definitions found for '{word}'.", status_code=404)
        self.word = word


class DictionaryTimeoutError(DictionaryError):
    """Raised when dictionary API request times out."""
    def __init__(self, word: str):
        super().__init__(f"Dictionary request timed out for '{word}'.", status_code=504)
        self.word = word


class DictionaryAPIError(DictionaryError):
    """Raised when external dictionary API returns an error or is unreachable."""
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message, status_code=status_code)


class DictionaryService:
    """Service layer for querying Free Dictionary API with caching & normalization."""

    BASE_URL = "https://api.dictionaryapi.dev/api/v2/entries/en"
    DEFAULT_TIMEOUT = 8  # seconds

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout

    @staticmethod
    def validate_word(raw_word: str) -> str:
        """Validate and clean word input."""
        if not raw_word or not isinstance(raw_word, str):
            raise DictionaryError("Word must be a non-empty string.", status_code=400)
        
        clean_word = raw_word.strip().lower()
        if not clean_word:
            raise DictionaryError("Word cannot be empty.", status_code=400)
        
        if len(clean_word) > 100:
            raise DictionaryError("Word length exceeds 100 characters.", status_code=400)
        
        if not re.match(r"^[a-zA-Z\s\-']+$", clean_word):
            raise DictionaryError("Word contains invalid characters.", status_code=400)
        
        return clean_word

    def fetch_raw_data(self, word: str) -> List[Dict[str, Any]]:
        """Fetch raw JSON payload from Free Dictionary API."""
        clean_word = self.validate_word(word)
        encoded_word = urllib.parse.quote(clean_word)
        url = f"{self.BASE_URL}/{encoded_word}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "WebVocab-DictionaryService/1.0",
                "Accept": "application/json"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                if "application/json" not in content_type and not content_type.startswith("application/json"):
                    # Try to parse regardless
                    pass
                raw_body = response.read().decode("utf-8")
                data = json.loads(raw_body)
                if isinstance(data, list) and len(data) > 0:
                    return data
                raise DictionaryAPIError("Unexpected response structure from dictionary API.")
                
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise DictionaryNotFoundError(clean_word)
            logger.warning(f"Dictionary API HTTP error {e.code} for word '{clean_word}'")
            raise DictionaryAPIError(f"Dictionary API returned HTTP status {e.code}.", status_code=e.code)
            
        except urllib.error.URLError as e:
            if "timed out" in str(e.reason).lower():
                logger.warning(f"Dictionary API timeout for word '{clean_word}'")
                raise DictionaryTimeoutError(clean_word)
            logger.error(f"Dictionary API connection error for '{clean_word}': {e.reason}")
            raise DictionaryAPIError(f"Unable to connect to dictionary API: {e.reason}")
            
        except TimeoutError:
            logger.warning(f"Dictionary API timeout for word '{clean_word}'")
            raise DictionaryTimeoutError(clean_word)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response for word '{clean_word}': {e}")
            raise DictionaryAPIError("Malformed response received from dictionary API.")

    def normalize_entry(self, raw_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize raw dictionary entries into a clean structured format."""
        if not raw_entries:
            return {}

        primary = raw_entries[0]
        word = primary.get("word", "").strip()

        # Extract phonetic text
        ipa = primary.get("phonetic") or ""
        audio_url = ""

        # Search phonetics list for IPA text and valid audio url
        phonetics = primary.get("phonetics", [])
        if isinstance(phonetics, list):
            for ph in phonetics:
                if not isinstance(ph, dict):
                    continue
                if not ipa and ph.get("text"):
                    ipa = ph.get("text")
                if not audio_url and ph.get("audio"):
                    audio_candidate = ph.get("audio", "").strip()
                    if audio_candidate.startswith("http://") or audio_candidate.startswith("https://"):
                        audio_url = audio_candidate
                    elif audio_candidate.startswith("//"):
                        audio_url = f"https:{audio_candidate}"

        # Clean IPA (strip slashes if needed for consistency, or keep standard /.../ format)
        if ipa:
            ipa = ipa.strip()
            if not ipa.startswith("/"):
                ipa = f"/{ipa}/"

        # Parse meanings
        meanings_list: List[Dict[str, Any]] = []
        all_synonyms: List[str] = []
        all_antonyms: List[str] = []

        primary_pos = ""
        primary_definition = ""
        primary_example = ""

        for entry in raw_entries:
            for m in entry.get("meanings", []):
                if not isinstance(m, dict):
                    continue
                pos = m.get("partOfSpeech", "").strip()
                if not primary_pos and pos:
                    primary_pos = pos

                # Top-level synonyms & antonyms
                m_synonyms = [s.strip() for s in m.get("synonyms", []) if isinstance(s, str) and s.strip()]
                m_antonyms = [a.strip() for a in m.get("antonyms", []) if isinstance(a, str) and a.strip()]
                all_synonyms.extend(m_synonyms)
                all_antonyms.extend(m_antonyms)

                defs_list = []
                for d in m.get("definitions", []):
                    if not isinstance(d, dict):
                        continue
                    def_text = d.get("definition", "").strip()
                    ex_text = d.get("example", "").strip()
                    d_syn = [s.strip() for s in d.get("synonyms", []) if isinstance(s, str) and s.strip()]
                    d_ant = [a.strip() for a in d.get("antonyms", []) if isinstance(a, str) and a.strip()]

                    all_synonyms.extend(d_syn)
                    all_antonyms.extend(d_ant)

                    if not primary_definition and def_text:
                        primary_definition = def_text
                    if not primary_example and ex_text:
                        primary_example = ex_text

                    if def_text:
                        defs_list.append({
                            "definition": def_text,
                            "example": ex_text,
                            "synonyms": d_syn[:5],
                            "antonyms": d_ant[:5]
                        })

                if defs_list:
                    meanings_list.append({
                        "part_of_speech": pos,
                        "definitions": defs_list,
                        "synonyms": m_synonyms[:5],
                        "antonyms": m_antonyms[:5]
                    })

        # Deduplicate synonyms & antonyms maintaining order
        unique_synonyms = list(dict.fromkeys(all_synonyms))
        unique_antonyms = list(dict.fromkeys(all_antonyms))

        return {
            "term": word,
            "ipa": ipa,
            "audio_url": audio_url,
            "part_of_speech": primary_pos,
            "definition": primary_definition,
            "example_sentence": primary_example,
            "synonyms": unique_synonyms[:8],
            "antonyms": unique_antonyms[:8],
            "meanings": meanings_list,
            "source": "dictionary_api"
        }

    def lookup(self, word: str) -> Dict[str, Any]:
        """Perform full lookup and normalization for a word."""
        raw_data = self.fetch_raw_data(word)
        return self.normalize_entry(raw_data)


# Global singleton instance
dictionary_service = DictionaryService()
