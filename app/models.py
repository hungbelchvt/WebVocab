from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from flask_login import UserMixin

db = SQLAlchemy()


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    # Private Gamification & Overall Progress
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    current_streak = db.Column(db.Integer, default=0)
    last_active = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_admin = db.Column(db.Boolean, default=False)
    # Relationship to private progress entries
    all_word_progress = db.relationship('WordProgress', backref='progress_owner', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'


class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Creator ownership is kept for tracking/filtering, but content is shared [134-137]
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
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
    # Creator ownership (optional, good practice)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Shared Vocabulary Details
    term = db.Column(db.String(100), nullable=False)
    ipa = db.Column(db.String(128))
    definition = db.Column(db.Text, nullable=False)
    example_sentence = db.Column(db.Text)
    synonyms = db.Column(db.String(200))
    antonyms = db.Column(db.String(200))

    # The creator's intended difficulty (optional default) [3, 51, 129]
    difficulty = db.Column(db.String(20), default='medium')
    date_added = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Creator backref
    creator = db.relationship('User', backref='created_words', lazy=True)

    def __repr__(self):
        return f'<Word {self.term}>'


# This is the new "Quizlet" private progress table [134-137, 139-141]
class WordProgress(db.Model):
    __tablename__ = 'word_progress'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)

    # Spaced Repetition System (SRS) Data (This is PRIVATE to the user!) [2, 131]
    user_difficulty_rating = db.Column(db.String(20), default='medium')  # What they rated it [70-71, 129]
    last_reviewed = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    next_review = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Stats for "Weak Words" and Accuracy features (This is PRIVATE to the user!) [22, 93, 132-133]
    times_tested = db.Column(db.Integer, default=0)
    times_correct = db.Column(db.Integer, default=0)
    is_mastered = db.Column(db.Boolean, default=False)

    date_mastered = db.Column(db.DateTime, nullable=True)

    # Junction connections
    user = db.relationship('User', backref=db.backref('word_progress_junction', lazy=True, overlaps="all_word_progress,progress_owner"), overlaps="all_word_progress,progress_owner")
    word = db.relationship('Word', backref=db.backref('progress_entries', lazy=True))

    def __repr__(self):
        return f'<WordProgress {self.word.term} for {self.user.username}>'

