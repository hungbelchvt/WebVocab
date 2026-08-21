import random
from datetime import datetime, timedelta, timezone
from flask import current_app as app
from flask import jsonify
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app.forms import RegistrationForm, LoginForm
from app.forms import TopicForm, WordForm
from app.models import db, User, Topic, Word, WordProgress, SmartStudyReview, QuizAttempt
from sqlalchemy import func
from datetime import datetime, timezone
from functools import wraps
from flask import abort
import csv
import io
from flask import session
from app.services.dictionary_service import (
    dictionary_service,
    DictionaryError,
    DictionaryNotFoundError,
    DictionaryTimeoutError,
    DictionaryAPIError
)



@app.route('/register', methods=['GET', 'POST'])
def register():
    # If they are already logged in, send them to the dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # 1. Check if passwords match
        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp. Vui lòng thử lại.', 'danger')
            return redirect(url_for('register'))

        # 2. Check if username is already taken
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.', 'warning')
            return redirect(url_for('register'))

        # 3. Hash the password and create the user
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password_hash=hashed_password, xp=0, level=1, current_streak=0, longest_streak=0)
        db.session.add(new_user)
        db.session.commit()

        # 4. Flash success message and redirect to login
        flash('Đăng ký tài khoản thành công! Vui lòng đăng nhập.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không chính xác. Vui lòng thử lại.', 'danger')

    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Main app
@app.route('/')
@app.route('/dashboard')
def dashboard():
    if not current_user.is_authenticated:
        return redirect(url_for('flashcards'))

    now = datetime.now(timezone.utc)

    # 1. Spaced Repetition Stats
    words_due = WordProgress.query.filter(
        WordProgress.user_id == current_user.id,
        WordProgress.next_review <= now
    ).count()

    total_learning = WordProgress.query.filter_by(user_id=current_user.id).count()

    mastered_count = WordProgress.query.filter_by(
        user_id=current_user.id,
        is_mastered=True
    ).count()

    # 2. Dynamic Streak Logic
    today_index = now.weekday()
    active_days = [False] * 7
    if current_user.last_active:
        days_since_active = (now.date() - current_user.last_active.date()).days
        if days_since_active <= 1:
            start_index = today_index if days_since_active == 0 else today_index - 1
            for i in range(current_user.current_streak):
                day_to_light = start_index - i
                if day_to_light >= 0:
                    active_days[day_to_light] = True

    day_labels = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
    streak_data = [(label, active_days[i]) for i, label in enumerate(day_labels)]

    # 3. Leaderboard #1 — Longest Streak (Top 10)
    streak_leaderboard = db.session.query(
        User.id,
        User.username,
        func.coalesce(User.longest_streak, User.current_streak, 0).label('streak_value')
    ).order_by(
        func.coalesce(User.longest_streak, User.current_streak, 0).desc(),
        User.xp.desc()
    ).limit(10).all()

    user_streak_val = max(current_user.longest_streak or 0, current_user.current_streak or 0)
    user_streak_rank = db.session.query(func.count(User.id)).filter(
        func.coalesce(User.longest_streak, User.current_streak, 0) > user_streak_val
    ).scalar() + 1

    # 4. Leaderboard #2 — Highest EXP (Top 10)
    exp_leaderboard = db.session.query(
        User.id,
        User.username,
        User.xp.label('exp_value')
    ).order_by(
        User.xp.desc()
    ).limit(10).all()

    user_exp_val = current_user.xp or 0
    user_exp_rank = db.session.query(func.count(User.id)).filter(
        User.xp > user_exp_val
    ).scalar() + 1

    # 5. Find Weakest Topic
    weak_progress = WordProgress.query.filter(
        WordProgress.user_id == current_user.id,
        WordProgress.times_tested > 0
    ).all()

    topic_scores = {}
    for p in weak_progress:
        if p.word and p.word.topic_id:
            topic = db.session.get(Topic, p.word.topic_id)
            if topic:
                acc = p.times_correct / p.times_tested
                t_id = topic.id
                if t_id not in topic_scores:
                    topic_scores[t_id] = {'name': topic.name, 'total_acc': 0, 'count': 0}
                topic_scores[t_id]['total_acc'] += acc
                topic_scores[t_id]['count'] += 1

    weakest_topic = None
    if topic_scores:
        lowest_acc = 1.1
        for t_id, data in topic_scores.items():
            avg = data['total_acc'] / data['count']
            if avg < lowest_acc:
                lowest_acc = avg
                weakest_topic = {'id': t_id, 'name': data['name']}

    return render_template('dashboard.html',
                           words_due=words_due,
                           total_learning=total_learning,
                           mastered_count=mastered_count,
                           streak_data=streak_data,
                           streak_leaderboard=streak_leaderboard,
                           exp_leaderboard=exp_leaderboard,
                           user_streak_rank=user_streak_rank,
                           user_exp_rank=user_exp_rank,
                           user_streak_val=user_streak_val,
                           weakest_topic=weakest_topic)


@app.route('/api/leaderboard/streak', methods=['GET'])
def api_leaderboard_streak():
    """Returns Top 10 users by longest streak without sensitive private data."""
    top_users = db.session.query(
        User.id,
        User.username,
        func.coalesce(User.longest_streak, User.current_streak, 0).label('streak_value')
    ).order_by(
        func.coalesce(User.longest_streak, User.current_streak, 0).desc(),
        User.xp.desc()
    ).limit(10).all()

    results = [
        {"rank": idx + 1, "username": u.username, "streak": int(u.streak_value)}
        for idx, u in enumerate(top_users)
    ]

    user_info = None
    if current_user.is_authenticated:
        user_streak_val = max(current_user.longest_streak or 0, current_user.current_streak or 0)
        user_rank = db.session.query(func.count(User.id)).filter(
            func.coalesce(User.longest_streak, User.current_streak, 0) > user_streak_val
        ).scalar() + 1
        user_info = {
            "username": current_user.username,
            "streak": user_streak_val,
            "rank": user_rank
        }

    return jsonify({"success": True, "leaderboard": results, "current_user": user_info})


@app.route('/api/leaderboard/exp', methods=['GET'])
def api_leaderboard_exp():
    """Returns Top 10 users by EXP without sensitive private data."""
    top_users = db.session.query(
        User.id,
        User.username,
        User.xp.label('exp_value')
    ).order_by(
        User.xp.desc()
    ).limit(10).all()

    results = [
        {"rank": idx + 1, "username": u.username, "xp": int(u.exp_value)}
        for idx, u in enumerate(top_users)
    ]

    user_info = None
    if current_user.is_authenticated:
        user_exp_val = current_user.xp or 0
        user_rank = db.session.query(func.count(User.id)).filter(
            User.xp > user_exp_val
        ).scalar() + 1
        user_info = {
            "username": current_user.username,
            "xp": user_exp_val,
            "rank": user_rank
        }

    return jsonify({"success": True, "leaderboard": results, "current_user": user_info})


@app.route('/study')
@login_required
def study():
    now = datetime.now(timezone.utc)

    # Query WordProgress, filter by user, ensure it's due, and LIMIT to 15
    due_progress = WordProgress.query.join(Word).filter(
        WordProgress.user_id == current_user.id,
        WordProgress.next_review <= now
    ).limit(15).all()

    words_data = [{
        'progress_id': progress.id,
        'word_id': progress.word.id,
        'term': progress.word.term,
        'ipa': progress.word.ipa,
        'definition': progress.word.definition,
        'example': progress.word.example_sentence,
    } for progress in due_progress]

    return render_template('study.html', words=words_data)


@app.route('/api/update_srs', methods=['POST'])
@login_required
def update_srs():
    data = request.get_json()
    progress_id = data.get('progress_id')
    rating = data.get('rating')

    progress = db.session.get(WordProgress, progress_id)
    if not progress:
        return jsonify({"error": "Progress record not found"}), 404

    if progress.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    now = datetime.now(timezone.utc)
    progress.last_reviewed = now
    progress.times_tested += 1

    # SRS logic updates the Progress record
    if rating == 'easy':
        progress.next_review = now + timedelta(days=4)
        progress.user_difficulty_rating = 'easy'
        progress.times_correct += 1
        current_user.xp += 15
    elif rating == 'medium':
        progress.next_review = now + timedelta(days=1)
        progress.user_difficulty_rating = 'medium'
        progress.times_correct += 1
        current_user.xp += 10
    elif rating == 'hard':
        progress.next_review = now + timedelta(minutes=10)
        progress.user_difficulty_rating = 'hard'
        current_user.xp += 5

    # 1. Persist Smart Study review history event
    study_review = SmartStudyReview(
        user_id=current_user.id,
        word_id=progress.word_id,
        topic_id=progress.word.topic_id if progress.word else None,
        rating=rating,
        timestamp=now
    )
    db.session.add(study_review)

    # 2. Update streak & longest_streak
    if not current_user.last_active or current_user.current_streak == 0:
        current_user.current_streak = 1
    else:
        delta = now.date() - current_user.last_active.date()
        if delta.days == 1:
            current_user.current_streak += 1
        elif delta.days > 1:
            current_user.current_streak = 1

    current_user.last_active = now
    if current_user.current_streak > (current_user.longest_streak or 0):
        current_user.longest_streak = current_user.current_streak

    # Mastery check on the progress record
    if progress.times_tested >= 3 and (progress.times_correct / progress.times_tested) >= 0.8:
        if not progress.is_mastered:
            progress.is_mastered = True
            progress.date_mastered = now
            current_user.xp += 50

    db.session.commit()
    return jsonify({"status": "success", "new_xp": current_user.xp})


@app.route('/quiz', methods=['GET'])
@login_required
def quiz_setup():
    user_progress = WordProgress.query.filter_by(user_id=current_user.id).all()
    enrolled_word_ids = [p.word_id for p in user_progress]

    enrolled_topics = db.session.query(Topic).join(Word).filter(Word.id.in_(enrolled_word_ids)).distinct().all()

    return render_template('quiz_setup.html', topics=enrolled_topics)


@app.route('/quiz/run', methods=['POST'])
@login_required
def quiz_run():
    topic_ids = request.form.getlist('topic_ids')
    count = int(request.form.get('question_count', 10))

    progress_query = WordProgress.query.filter_by(user_id=current_user.id)

    if 'all' not in topic_ids and topic_ids:
        topic_ids_int = [int(t_id) for t_id in topic_ids]
        progress_query = progress_query.join(Word).filter(Word.topic_id.in_(topic_ids_int))

    available_progress = progress_query.all()

    if not available_progress:
        flash("Bạn chưa có đủ từ vựng trong các chủ đề đã chọn để tạo bài quiz.", "warning")
        return redirect(url_for('quiz_setup'))

    selected_progress = random.sample(available_progress, min(count, len(available_progress)))
    
    # Query only words from the relevant topics instead of loading entire database
    selected_topic_ids = list({p.word.topic_id for p in selected_progress if p.word and p.word.topic_id})
    relevant_words = Word.query.filter(Word.topic_id.in_(selected_topic_ids)).all() if selected_topic_ids else []

    quiz_data = []
    for p in selected_progress:
        target_word = p.word
        if not target_word:
            continue

        same_topic_words = [w for w in relevant_words if w.topic_id == target_word.topic_id and w.id != target_word.id]
        wrong_choices = random.sample(same_topic_words, min(3, len(same_topic_words)))

        options = wrong_choices + [target_word]
        random.shuffle(options)

        quiz_data.append({
            'progress_id': p.id,
            'target_term': target_word.term,
            'options': [{'id': opt.id, 'def': opt.definition} for opt in options],
            'correct_id': target_word.id
        })

    return render_template('quiz_run.html', quiz_data=quiz_data)


@app.route('/api/submit_quiz_batch', methods=['POST'])
@login_required
def submit_quiz_batch():
    data = request.get_json()
    results = data.get('results', [])

    xp_earned = 0
    now = datetime.now(timezone.utc)

    # Streak logic
    if not current_user.last_active or current_user.current_streak == 0:
        current_user.current_streak = 1
    else:
        delta = now.date() - current_user.last_active.date()
        if delta.days == 1:
            current_user.current_streak += 1
        elif delta.days > 1:
            current_user.current_streak = 1

    current_user.last_active = now
    if current_user.current_streak > (current_user.longest_streak or 0):
        current_user.longest_streak = current_user.current_streak

    detailed_results = []

    for item in results:
        progress = db.session.get(WordProgress, item['progress_id'])
        if progress and progress.user_id == current_user.id:
            progress.times_tested += 1
            is_correct = bool(item.get('is_correct'))
            if is_correct:
                progress.times_correct += 1
                xp_earned += 10

            if progress.times_tested >= 3 and (progress.times_correct / progress.times_tested) >= 0.8:
                if not progress.is_mastered:
                    progress.is_mastered = True
                    progress.date_mastered = now
                    xp_earned += 50

            detailed_results.append(item)

            # Persist normal Quiz attempt history
            quiz_attempt = QuizAttempt(
                user_id=current_user.id,
                word_id=progress.word_id,
                topic_id=progress.word.topic_id if progress.word else None,
                is_correct=is_correct,
                selected_id=item.get('selected_id'),
                timestamp=now
            )
            db.session.add(quiz_attempt)

    current_user.xp += xp_earned
    db.session.commit()

    session['last_quiz'] = {
        'xp': xp_earned,
        'details': detailed_results
    }

    return jsonify({
        "status": "success",
        "redirect_url": url_for('quiz_results_view')
    })


@app.route('/flashcards')
def flashcards():
    all_topics = Topic.query.all()

    return render_template('flashcards.html', topics=all_topics)


@app.route('/flashcards/<int:topic_id>')
def view_flashcards(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    words = Word.query.filter_by(topic_id=topic.id).all()

    # Check if the user is enrolled in this deck
    is_enrolled = False
    if current_user.is_authenticated:
        word_ids = [w.id for w in words]
        if word_ids:
            # If the user has ANY progress trackers for the words in this deck, they are enrolled
            progress_exists = WordProgress.query.filter(
                WordProgress.user_id == current_user.id,
                WordProgress.word_id.in_(word_ids)
            ).first()
            if progress_exists:
                is_enrolled = True

    return render_template('view_flashcards.html', topic=topic, words=words, is_enrolled=is_enrolled)


@app.route('/unenroll/<int:topic_id>', methods=['POST'])
@login_required
def unenroll_topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    words = Word.query.filter_by(topic_id=topic.id).all()
    word_ids = [w.id for w in words]

    if word_ids:
        # Delete all progress trackers for these specific words for the current user
        WordProgress.query.filter(
            WordProgress.user_id == current_user.id,
            WordProgress.word_id.in_(word_ids)
        ).delete(synchronize_session=False)
        db.session.commit()

        flash(f'Đã xóa chủ đề "{topic.name}" khỏi danh sách học của bạn.', 'info')
        return redirect(url_for('view_flashcards', topic_id=topic.id))



@app.route('/create_topic', methods=['GET', 'POST'])
@login_required
def create_topic():
    form = TopicForm()
    if form.validate_on_submit():
        new_topic = Topic(name=form.name.data, user_id=current_user.id)
        db.session.add(new_topic)
        db.session.commit()

        flash(f'Đã tạo chủ đề "{new_topic.name}" thành công! Hãy thêm từ vựng mới.', 'success')
        # Immediately redirect them to add words to this new deck
        return redirect(url_for('add_word', topic_id=new_topic.id))

    return render_template('create_topic.html', form=form)

@app.route('/edit_word/<int:word_id>', methods=['POST'])
@login_required
def edit_word(word_id):
    word = Word.query.get_or_404(word_id)

    # Security Check: Only the creator or an admin can edit
    if word.user_id != current_user.id and not current_user.is_admin:
        flash("Bạn không có quyền chỉnh sửa từ vựng này.", "danger")
        return redirect(url_for('flashcards'))

    topic_id = word.topic_id

    # Update the word with the new data from the form
    word.term = request.form.get('term')
    word.ipa = request.form.get('ipa')
    word.definition = request.form.get('definition')
    word.example_sentence = request.form.get('example_sentence')

    db.session.commit()
    flash(f'Đã cập nhật thành công từ vựng "{word.term}"!', 'success')

    return redirect(url_for('add_word', topic_id=topic_id))

@app.route('/add_word/<int:topic_id>', methods=['GET', 'POST'])
@login_required
def add_word(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    form = WordForm()

    if form.validate_on_submit():
        # 1. Create the public word
        new_word = Word(
            term=form.term.data,
            ipa=form.ipa.data,
            definition=form.definition.data,
            example_sentence=form.example_sentence.data,
            topic_id=topic.id,
            user_id=current_user.id
        )
        db.session.add(new_word)
        db.session.commit()

        # 2. Automatically give the creator a progress tracker for it
        progress = WordProgress(user_id=current_user.id, word_id=new_word.id)
        db.session.add(progress)
        db.session.commit()

        flash(f'Đã thêm thành công từ "{new_word.term}" vào chủ đề "{topic.name}"!', 'success')
        return redirect(url_for('add_word', topic_id=topic.id))

    # Fetch existing words to show the user what they've added so far
    words = Word.query.filter_by(topic_id=topic.id).all()
    return render_template('add_word.html', form=form, topic=topic, words=words)


@app.route('/progress')
@login_required
def progress():
    # 1. Weak Words Logic (Now querying WordProgress)
    weak_progress = WordProgress.query.filter(
        WordProgress.user_id == current_user.id,
        WordProgress.times_tested > 0
    ).all()
    actual_weak_words = [p for p in weak_progress if (p.times_correct / p.times_tested) < 0.5]

    # 2. Mastery Breakdown Logic
    mastered_count = WordProgress.query.filter_by(user_id=current_user.id, is_mastered=True).count()

    learning_count = WordProgress.query.filter(
        WordProgress.user_id == current_user.id,
        WordProgress.times_tested > 0,
        WordProgress.is_mastered == False
    ).count()

    new_count = WordProgress.query.filter_by(user_id=current_user.id, times_tested=0).count()

    # 3. Chart Data
    today = datetime.now(timezone.utc).date()
    last_7_dates = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
    chart_labels = [day.strftime('%b %d') for day in last_7_dates]
    chart_data = [0] * 7

    mastered_progress_list = WordProgress.query.filter(
        WordProgress.user_id == current_user.id,
        WordProgress.is_mastered == True,
        WordProgress.date_mastered.isnot(None)
    ).all()

    for progress in mastered_progress_list:
        word_date = progress.date_mastered.date()
        if word_date in last_7_dates:
            index = last_7_dates.index(word_date)
            chart_data[index] += 1

    return render_template('progress.html',
                           weak_words=actual_weak_words,
                           mastered_count=mastered_count,
                           learning_count=learning_count,
                           new_count=new_count,
                           chart_labels=chart_labels,
                           chart_data=chart_data)


@app.route('/enroll/<int:topic_id>', methods=['POST'])
@login_required
def enroll_topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    words = Word.query.filter_by(topic_id=topic.id).all()

    for word in words:
        existing_progress = WordProgress.query.filter_by(user_id=current_user.id, word_id=word.id).first()
        if not existing_progress:
            progress = WordProgress(user_id=current_user.id, word_id=word.id)
            db.session.add(progress)

    db.session.commit()
    flash(f'Đã thêm chủ đề "{topic.name}" vào tiến trình học của bạn!', 'success')
    return redirect(url_for('view_flashcards', topic_id=topic.id))


@app.route('/delete_word/<int:word_id>', methods=['POST'])
@login_required
def delete_word(word_id):
    word = Word.query.get_or_404(word_id)

    # ADDED the admin bypass here:
    if word.user_id != current_user.id and not current_user.is_admin:
        flash("Bạn không có quyền xóa từ vựng này.", "danger")
        return redirect(url_for('flashcards'))

    topic_id = word.topic_id

    WordProgress.query.filter_by(word_id=word.id).delete()

    db.session.delete(word)
    db.session.commit()

    flash(f'Đã xóa từ vựng "{word.term}".', 'info')
    return redirect(url_for('add_word', topic_id=topic_id))

@app.route('/delete_topic/<int:topic_id>', methods=['POST'])
@login_required
def delete_topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)

    # ADDED the admin bypass here:
    if topic.user_id != current_user.id and not current_user.is_admin:
        flash("Bạn không có quyền xóa chủ đề này.", "danger")
        return redirect(url_for('flashcards'))

    words = Word.query.filter_by(topic_id=topic.id).all()
    for word in words:
        WordProgress.query.filter_by(word_id=word.id).delete()
        db.session.delete(word)

    db.session.delete(topic)
    db.session.commit()

    flash(f'Chủ đề "{topic.name}" đã được xóa.', 'info')
    return redirect(url_for('flashcards'))


# --- ADMIN SECURITY DECORATOR ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Bạn không có quyền truy cập trang quản trị này.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated_function


# --- ADMIN ROUTES ---
@app.route('/admin')
@admin_required
def admin_panel():
    users = User.query.all()
    # We can fetch all topics to display stats in the admin panel
    topics = Topic.query.all()
    return render_template('admin.html', users=users, topics=topics)


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Bạn không thể xóa tài khoản quản trị viên của chính mình!', 'danger')
        return redirect(url_for('admin_panel'))

    # Delete their study progress first to prevent database errors
    WordProgress.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    flash(f'Người dùng {user.username} đã được xóa thành công.', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/import_csv/<int:topic_id>', methods=['POST'])
@login_required
def import_csv(topic_id):
    topic = Topic.query.get_or_404(topic_id)

    if 'file' not in request.files:
        flash('Vui lòng chọn tệp tin tải lên.', 'danger')
        return redirect(url_for('add_word', topic_id=topic.id))

    file = request.files['file']
    if file.filename == '':
        flash('Chưa có tệp tin nào được chọn.', 'danger')
        return redirect(url_for('add_word', topic_id=topic.id))

    if file and file.filename.endswith('.csv'):
        # Decode the file stream as text
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.reader(stream)

        # Skip the header row (Term, Definition, Example)
        next(csv_input, None)

        words_added = 0
        for row in csv_input:
            # We need at least a term and a definition
            if len(row) >= 2 and row[0].strip() and row[1].strip():
                term = row[0].strip()
                definition = row[1].strip()
                example = row[2].strip() if len(row) > 2 else ""

                # 1. Create the Word
                new_word = Word(term=term, definition=definition, example_sentence=example, topic_id=topic.id,
                                user_id=current_user.id)
                db.session.add(new_word)
                db.session.flush()  # Flushes to DB to generate the new_word.id immediately

                # 2. Give the creator a progress tracker
                progress = WordProgress(user_id=current_user.id, word_id=new_word.id)
                db.session.add(progress)
                words_added += 1

        db.session.commit()
        flash(f'Đã nhập thành công {words_added} từ vựng vào chủ đề "{topic.name}"!', 'success')
    else:
        flash('Vui lòng tải lên tệp tin định dạng .csv hợp lệ.', 'danger')

    return redirect(url_for('add_word', topic_id=topic.id))


@app.route('/quiz/results')
@login_required
def quiz_results_view():
    quiz_data = session.pop('last_quiz', None)

    # If they try to visit this URL without taking a quiz, kick them out
    if not quiz_data:
        return redirect(url_for('dashboard'))

    return render_template('quiz_results.html', data=quiz_data)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for deployment monitoring (Render)."""
    return jsonify({"status": "ok"}), 200


@app.route('/api/dictionary/<string:word>', methods=['GET'])
def api_dictionary_lookup(word):
    """
    Dictionary lookup endpoint.
    1. Validates the word.
    2. Checks if the word exists in PostgreSQL database.
    3. If found, returns database vocabulary data (with audio enrichment if available).
    4. If not found in DB, queries Free Dictionary API and normalizes the response.
    """
    try:
        clean_word = dictionary_service.validate_word(word)
    except DictionaryError as e:
        return jsonify({
            "success": False,
            "found": False,
            "error": e.message
        }), e.status_code

    # 1. Search in local database
    db_word = Word.query.filter(func.lower(Word.term) == func.lower(clean_word)).first()

    if db_word:
        # Try to retrieve audio if available from Free Dictionary API
        audio_url = ""
        try:
            dict_data = dictionary_service.lookup(clean_word)
            audio_url = dict_data.get("audio_url", "")
        except Exception:
            pass

        synonyms_list = [s.strip() for s in db_word.synonyms.split(",") if s.strip()] if db_word.synonyms else []
        antonyms_list = [a.strip() for a in db_word.antonyms.split(",") if a.strip()] if db_word.antonyms else []

        return jsonify({
            "success": True,
            "found": True,
            "source": "database",
            "data": {
                "id": db_word.id,
                "term": db_word.term,
                "ipa": db_word.ipa or "",
                "audio_url": audio_url,
                "definition": db_word.definition,
                "example_sentence": db_word.example_sentence or "",
                "synonyms": synonyms_list,
                "antonyms": antonyms_list,
                "difficulty": db_word.difficulty or "medium",
                "topic_id": db_word.topic_id,
                "topic_name": db_word.topic_category.name if db_word.topic_category else None,
                "in_database": True
            }
        }), 200

    # 2. Query Free Dictionary API
    try:
        dict_data = dictionary_service.lookup(clean_word)
        return jsonify({
            "success": True,
            "found": True,
            "source": "dictionary_api",
            "data": {
                "term": dict_data["term"],
                "ipa": dict_data.get("ipa", ""),
                "audio_url": dict_data.get("audio_url", ""),
                "part_of_speech": dict_data.get("part_of_speech", ""),
                "definition": dict_data.get("definition", ""),
                "example_sentence": dict_data.get("example_sentence", ""),
                "synonyms": dict_data.get("synonyms", []),
                "antonyms": dict_data.get("antonyms", []),
                "meanings": dict_data.get("meanings", []),
                "difficulty": "medium",
                "in_database": False,
                "topic_id": None,
                "topic_name": None
            }
        }), 200

    except DictionaryNotFoundError:
        return jsonify({
            "success": False,
            "found": False,
            "error": f"Không tìm thấy định nghĩa cho từ '{clean_word}' trong từ điển."
        }), 404

    except DictionaryTimeoutError:
        return jsonify({
            "success": False,
            "found": False,
            "error": "Yêu cầu tra từ điển bị quá thời gian (timeout). Vui lòng thử lại sau."
        }), 504

    except DictionaryAPIError as e:
        return jsonify({
            "success": False,
            "found": False,
            "error": f"Lỗi dịch vụ từ điển bên ngoài: {e.message}"
        }), e.status_code

    except Exception as e:
        return jsonify({
            "success": False,
            "found": False,
            "error": "Đã xảy ra lỗi không xác định khi tra cứu từ điển."
        }), 500
