from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from flask_login import UserMixin

db = SQLAlchemy()


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    # Private Gamification & Overall Progress
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    current_streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)
    last_active = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_admin = db.Column(db.Boolean, default=False)

    # Relationship to private progress entries
    all_word_progress = db.relationship('WordProgress', backref='progress_owner', lazy=True, cascade='all, delete-orphan')

    # Relationship to Smart Study reviews and Quiz attempts
    smart_study_reviews = db.relationship('SmartStudyReview', backref='user', lazy=True, cascade='all, delete-orphan')
    quiz_attempts = db.relationship('QuizAttempt', backref='user', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'


class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Creator ownership: NULL indicates system/public topic
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    date_created = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship: A public topic contains shared words
    words = db.relationship('Word', backref='topic_category', lazy=True)

    # Relationship to track who created it
    creator = db.relationship('User', backref='created_topics', lazy=True)

    def __repr__(self):
        return f'<Topic {self.name}>'


class Word(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    # Creator ownership (optional, NULL for system/public words)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Shared Vocabulary Details
    term = db.Column(db.String(100), nullable=False)
    ipa = db.Column(db.String(128))
    definition = db.Column(db.Text, nullable=False)
    example_sentence = db.Column(db.Text)
    synonyms = db.Column(db.String(200))
    antonyms = db.Column(db.String(200))

    # The creator's intended difficulty (optional default)
    difficulty = db.Column(db.String(20), default='medium')
    date_added = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Creator backref
    creator = db.relationship('User', backref='created_words', lazy=True)

    def __repr__(self):
        return f'<Word {self.term}>'


# This is the "Quizlet" private progress table
class WordProgress(db.Model):
    __tablename__ = 'word_progress'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)

    # Spaced Repetition System (SRS) Data (PRIVATE to the user)
    user_difficulty_rating = db.Column(db.String(20), default='medium')
    last_reviewed = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    next_review = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Stats for "Weak Words" and Accuracy features (PRIVATE to the user)
    times_tested = db.Column(db.Integer, default=0)
    times_correct = db.Column(db.Integer, default=0)
    is_mastered = db.Column(db.Boolean, default=False)

    date_mastered = db.Column(db.DateTime, nullable=True)

    # Junction connections
    user = db.relationship('User', backref=db.backref('word_progress_junction', lazy=True, overlaps="all_word_progress,progress_owner"), overlaps="all_word_progress,progress_owner")
    word = db.relationship('Word', backref=db.backref('progress_entries', lazy=True))

    def __repr__(self):
        return f'<WordProgress {self.word.term} for {self.user.username}>'


class SmartStudyReview(db.Model):
    """
    Historical log of every Smart Study (SRS) review event.
    Persists Easy / Medium / Hard ratings per user, word, topic over time.
    """
    __tablename__ = 'smart_study_review'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False, index=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=True, index=True)
    rating = db.Column(db.String(20), nullable=False)  # 'easy', 'medium', 'hard'
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    word = db.relationship('Word', backref=db.backref('study_reviews', lazy=True))
    topic = db.relationship('Topic', backref=db.backref('study_reviews', lazy=True))

    def __repr__(self):
        return f'<SmartStudyReview user={self.user_id} word={self.word_id} rating={self.rating}>'


class QuizAttempt(db.Model):
    """
    Historical log of every normal Quiz question attempt.
    Tracks correct / incorrect answers per user, word, topic over time.
    """
    __tablename__ = 'quiz_attempt'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False, index=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=True, index=True)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    selected_id = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    word = db.relationship('Word', backref=db.backref('quiz_attempts', lazy=True))
    topic = db.relationship('Topic', backref=db.backref('quiz_attempts', lazy=True))

    def __repr__(self):
        return f'<QuizAttempt user={self.user_id} word={self.word_id} correct={self.is_correct}>'


