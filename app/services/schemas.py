"""
Pydantic Schema Models for AI Features in WebVocab.
Used for structured output generation and response validation.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# =====================================================================
# Phase 2: AI Vocabulary Assistant Schemas
# =====================================================================

class ExampleSentence(BaseModel):
    sentence: str = Field(
        description="Natural English example sentence demonstrating the word in context."
    )
    translation_vi: str = Field(
        description="Natural and accurate Vietnamese translation of the example sentence."
    )


class VocabularyExplanation(BaseModel):
    word: str = Field(
        description="The English word analyzed (normalized to lowercase/standard casing)."
    )
    meaning_vi: str = Field(
        description="Primary Vietnamese meaning and definition, prioritizing the most common usage."
    )
    part_of_speech: str = Field(
        description="Part of speech (e.g., noun, verb, adjective, adverb, idiom)."
    )
    pronunciation: str = Field(
        description="Standard IPA phonetic transcription (e.g., /əˈbændən/)."
    )
    examples: List[ExampleSentence] = Field(
        default_factory=list,
        description="2 to 3 practical example sentences with Vietnamese translations."
    )
    synonyms: List[str] = Field(
        default_factory=list,
        description="Up to 4-5 common English synonyms."
    )
    antonyms: List[str] = Field(
        default_factory=list,
        description="Up to 4-5 common English antonyms if applicable."
    )
    collocations: List[str] = Field(
        default_factory=list,
        description="Up to 3-5 frequent collocations or phrase combinations."
    )
    memory_tip: Optional[str] = Field(
        default="",
        description="A helpful mnemonic, association, or memory tip in Vietnamese."
    )


# =====================================================================
# Phase 3: AI Quiz Generator Schemas
# =====================================================================

class AIQuizQuestion(BaseModel):
    word: str = Field(
        description="The target English vocabulary word being tested."
    )
    type: str = Field(
        description="Question type: 'multiple_choice', 'fill_blank', or 'context'."
    )
    question: str = Field(
        description="The clear question text, sentence with blank, or contextual scenario."
    )
    options: List[str] = Field(
        description="List of 4 distinct answer choices. Exactly one must be correct."
    )
    answer: str = Field(
        description="The exact correct answer string matching one of the items in options."
    )
    explanation: str = Field(
        description="Clear explanation in Vietnamese (or bilingual) explaining why the answer is correct and reinforcing the word's meaning."
    )


class AIQuizResponse(BaseModel):
    questions: List[AIQuizQuestion] = Field(
        description="List of personalized quiz questions generated for the user's candidate vocabulary."
    )


# =====================================================================
# Phase 4: AI Learning Analysis Schemas
# =====================================================================

class WeakWordInsight(BaseModel):
    word: str = Field(
        description="The weak English vocabulary word identified."
    )
    issue: str = Field(
        description="Brief diagnosis of why the user struggles (e.g. low accuracy, repeated incorrect attempts)."
    )
    recommendation: str = Field(
        description="Concrete, actionable advice in Vietnamese to master this specific word."
    )


class WeakTopicInsight(BaseModel):
    topic_name: str = Field(
        description="Name of the topic needing improvement."
    )
    issue: str = Field(
        description="Identified pattern or weakness in this vocabulary domain."
    )
    recommendation: str = Field(
        description="Actionable study strategy in Vietnamese for this topic."
    )


class LearningInsight(BaseModel):
    title: str = Field(
        description="Catchy headline for the learning pattern or tip."
    )
    insight: str = Field(
        description="Observation of the user's learning behavior or retention pattern in Vietnamese."
    )
    action: str = Field(
        description="Actionable next step for the learner in Vietnamese."
    )


class AILearningAnalysis(BaseModel):
    summary: str = Field(
        description="A personalized, encouraging overview of the user's current progress and vocabulary retention."
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="List of 2-4 strong areas, mastered concepts, or positive learning habits."
    )
    weaknesses: List[str] = Field(
        default_factory=list,
        description="List of 2-4 key areas or vocabulary groups needing attention."
    )
    weak_words: List[WeakWordInsight] = Field(
        default_factory=list,
        description="Detailed insights and learning tips for top weak words."
    )
    weak_topics: List[WeakTopicInsight] = Field(
        default_factory=list,
        description="Targeted suggestions for low-scoring vocabulary topics."
    )
    review_priorities: List[str] = Field(
        default_factory=list,
        description="Top 3-5 high-priority words to review immediately."
    )
    learning_insights: List[LearningInsight] = Field(
        default_factory=list,
        description="General actionable cognitive & study insights to boost retention."
    )
