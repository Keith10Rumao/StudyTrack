"""
StudyTrack — College Study & Academics Tracker
=================================================
A Flask web app for tracking subjects, assignments, study sessions
and progress, styled in a neo-brutalist design.

Run with:
    pip install -r requirements.txt
    python app.py

Then open http://127.0.0.1:5000 in your browser.
"""

import os
import re
import csv
import io
import json
import uuid
import time
import secrets
import tempfile
import shutil
import calendar as calendar_module
from collections import defaultdict
from datetime import datetime, date, timedelta

from flask import Flask, render_template, redirect, url_for, request, flash, send_file, session, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, login_required,
    logout_user, current_user
)
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_or_create_secret_key():
    """Keeps the same signing key across restarts (so login sessions and
    flash messages don't get invalidated every time the server restarts),
    while still letting an env var override it for real deployments.

    On a read-only filesystem (e.g. Vercel's serverless functions) writing
    .secret_key isn't possible — we fall back to a per-process random key
    instead of crashing. That's fine for local dev, but on a real serverless
    deployment it means the signing key changes on every cold start, which
    silently logs everyone out at random. Set STUDYTRACK_SECRET_KEY as an
    environment variable in production to avoid that entirely — see README.
    """
    env_key = os.environ.get('STUDYTRACK_SECRET_KEY')
    if env_key:
        return env_key
    key_path = os.path.join(BASE_DIR, '.secret_key')
    try:
        if os.path.exists(key_path):
            with open(key_path, 'r') as f:
                existing = f.read().strip()
                if existing:
                    return existing
        new_key = secrets.token_hex(32)
        with open(key_path, 'w') as f:
            f.write(new_key)
        return new_key
    except OSError:
        # Read-only filesystem (serverless). Not persisted across cold
        # starts, but this at least lets the app boot instead of crashing.
        return secrets.token_hex(32)


def get_database_uri():
    """Use a real hosted database when DATABASE_URL (or POSTGRES_URL) is
    set -- required for serverless hosts like Vercel, where a local SQLite
    file can't persist or be shared across function instances. Falls back
    to a local SQLite file for local development, where a real filesystem
    is available.

    If no hosted database is configured AND we're running on Vercel
    (detected via Vercel's own auto-set VERCEL env var), BASE_DIR is
    read-only, so writing SQLite there crashes on every signup/write. In
    that case we fall back to /tmp so the app still works with zero extra
    setup. Note: /tmp is scratch space, not permanent storage -- Vercel can
    wipe it between invocations, so signed-up accounts aren't guaranteed to
    survive. Set DATABASE_URL (e.g. a free Neon/Vercel Postgres database)
    for real, permanent data.
    """
    db_url = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
    if db_url:
        # Some providers (Heroku-style, older Postgres add-ons) hand out
        # "postgres://" URLs, but SQLAlchemy 1.4+ requires "postgresql://".
        if db_url.startswith('postgres://'):
            db_url = 'postgresql://' + db_url[len('postgres://'):]
        return db_url
    if os.environ.get('VERCEL'):
        tmp_db_path = os.path.join(tempfile.gettempdir(), 'study_tracker.db')
        bundled_db_path = os.path.join(BASE_DIR, 'study_tracker.db')
        # Seed /tmp with the bundled demo database on a fresh instance --
        # BASE_DIR can still be *read* even though it can't be written to,
        # so this makes any demo account bundled in the repo reachable.
        if not os.path.exists(tmp_db_path) and os.path.exists(bundled_db_path):
            shutil.copy(bundled_db_path, tmp_db_path)
        return 'sqlite:///' + tmp_db_path
    return 'sqlite:///' + os.path.join(BASE_DIR, 'study_tracker.db')


app = Flask(__name__)
app.config['SECRET_KEY'] = get_or_create_secret_key()
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

csrf = CSRFProtect(app)
app.jinja_env.globals['csrf_token'] = generate_csrf

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
if os.environ.get('VERCEL'):
    # Read-only filesystem on Vercel -- route uploads to /tmp instead.
    # If demo attachments are bundled with the deployment, seed them into
    # /tmp on a fresh instance so they're reachable (BASE_DIR itself can
    # still be *read*, just not written to or created fresh).
    tmp_upload_folder = os.path.join(tempfile.gettempdir(), 'studytrack_uploads')
    if not os.path.isdir(tmp_upload_folder):
        if os.path.isdir(UPLOAD_FOLDER):
            shutil.copytree(UPLOAD_FOLDER, tmp_upload_folder)
        else:
            os.makedirs(tmp_upload_folder, exist_ok=True)
    UPLOAD_FOLDER = tmp_upload_folder
else:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB per request

ALLOWED_NOTE_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'png', 'jpg', 'jpeg'}

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your dashboard.'
login_manager.login_message_category = 'error'

GMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@gmail\.com$', re.IGNORECASE)

YEAR_LEVELS = ['1st Year', '2nd Year', '3rd Year', '4th Year']
PRIORITIES = ['Low', 'Medium', 'High']
CARD_COLORS = ['blue', 'orange', 'green', 'pink', 'yellow', 'purple']
CARD_HEX = {
    'blue': '#4D96FF', 'orange': '#FF9F43', 'green': '#3DDC84',
    'pink': '#FF5FA2', 'yellow': '#FFC940', 'purple': '#B084F5',
}



# ----------------------------------------------------------------------
# MODELS
# ----------------------------------------------------------------------

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), default='')
    year_level = db.Column(db.String(20), default='1st Year')
    branch = db.Column(db.String(120), default='')
    university = db.Column(db.String(150), default='')
    bio = db.Column(db.String(255), default='Building the future, one algorithm at a time')
    theme = db.Column(db.String(10), default='dark')  # 'dark' or 'light'

    # Account recovery — lets a user reset a forgotten password without
    # needing real email infrastructure. The answer is hashed, never stored
    # in plain text, same as the password itself.
    security_question = db.Column(db.String(200), default='')
    security_answer_hash = db.Column(db.String(255), default='')

    gpa_current = db.Column(db.Float, default=0.0)
    gpa_target = db.Column(db.Float, default=9.0)
    attendance = db.Column(db.Float, default=0.0)
    weekly_study_target = db.Column(db.Float, default=15.0)  # hours
    next_milestone_title = db.Column(db.String(150), default='')
    next_milestone_date = db.Column(db.Date, nullable=True)

    # Live study-session timer state (one active session per user)
    active_subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    active_started_at = db.Column(db.DateTime, nullable=True)
    active_stopped_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subjects = db.relationship('Subject', backref='owner', cascade='all, delete-orphan',
                                foreign_keys='Subject.user_id')
    assignments = db.relationship('Assignment', backref='owner', cascade='all, delete-orphan')
    study_sessions = db.relationship('StudySession', backref='owner', cascade='all, delete-orphan')


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), default='CORE')
    credits = db.Column(db.Integer, default=0)
    year_level = db.Column(db.String(20), default='1st Year')

    assignments = db.relationship('Assignment', backref='subject', cascade='all, delete-orphan')
    study_sessions = db.relationship('StudySession', backref='subject', cascade='all, delete-orphan')
    notes = db.relationship('SubjectNote', backref='subject', cascade='all, delete-orphan',
                             foreign_keys='SubjectNote.subject_id')


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    priority = db.Column(db.String(10), default='Medium')
    status = db.Column(db.String(20), default='Pending')  # Pending / Completed


class StudySession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    session_date = db.Column(db.Date, default=date.today)
    start_time = db.Column(db.String(10), default='')
    end_time = db.Column(db.String(10), default='')
    duration_minutes = db.Column(db.Integer, default=0)
    effectiveness = db.Column(db.Integer, default=3)  # 1-5


class SubjectNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ----------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------

def parse_date(value, default=None):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return default


def normalize_answer(text):
    """Security answers are matched case/whitespace-insensitively so a user
    isn't locked out by capitalization or stray spaces."""
    return (text or '').strip().lower()


# ---- Simple in-memory rate limiting (login + password reset attempts) ----
# Resets on server restart — fine for a personal/local app. Keyed by email
# so it doesn't depend on a single IP, which matters less for this use case.
_FAILED_ATTEMPTS = defaultdict(list)
MAX_ATTEMPTS = 6
LOCKOUT_SECONDS = 5 * 60


def is_locked_out(key):
    now = time.time()
    recent = [t for t in _FAILED_ATTEMPTS[key] if now - t < LOCKOUT_SECONDS]
    _FAILED_ATTEMPTS[key] = recent
    return len(recent) >= MAX_ATTEMPTS


def record_failed_attempt(key):
    _FAILED_ATTEMPTS[key].append(time.time())


def clear_attempts(key):
    _FAILED_ATTEMPTS.pop(key, None)


def seconds_until_unlocked(key):
    if not _FAILED_ATTEMPTS[key]:
        return 0
    oldest_relevant = sorted(_FAILED_ATTEMPTS[key])[0]
    remaining = LOCKOUT_SECONDS - (time.time() - oldest_relevant)
    return max(0, int(remaining))


def compute_duration_minutes(start_str, end_str):
    try:
        t1 = datetime.strptime(start_str, '%H:%M')
        t2 = datetime.strptime(end_str, '%H:%M')
        diff = (t2 - t1).total_seconds() / 60
        if diff < 0:
            diff += 24 * 60
        return int(diff)
    except (ValueError, TypeError):
        return 0


def fmt_hm(total_minutes):
    total_minutes = int(total_minutes or 0)
    h, m = divmod(total_minutes, 60)
    return f"{h}h {m}m"


def days_with_sessions(user_id):
    rows = db.session.query(StudySession.session_date).filter(
        StudySession.user_id == user_id
    ).distinct().all()
    return set(r[0] for r in rows if r[0] is not None)


def calculate_current_streak(day_set):
    if not day_set:
        return 0
    streak = 0
    cur = date.today()
    while cur in day_set:
        streak += 1
        cur -= timedelta(days=1)
    return streak


def calculate_longest_streak(day_set):
    if not day_set:
        return 0
    days = sorted(day_set)
    longest = 1
    cur = 1
    for i in range(1, len(days)):
        if (days[i] - days[i - 1]).days == 1:
            cur += 1
        else:
            cur = 1
        longest = max(longest, cur)
    return longest


def get_badges(user, subjects_count, longest_streak, total_hours):
    badges = [
        {'name': '7-Day Streak', 'icon': '🔥', 'unlocked': longest_streak >= 7},
        {'name': 'Bookworm', 'icon': '📚', 'unlocked': subjects_count >= 10},
        {'name': 'Speed Learner', 'icon': '⚡', 'unlocked': total_hours >= 50},
        {'name': 'Early Bird', 'icon': '🌅', 'unlocked': StudySession.query.filter(
            StudySession.user_id == user.id, StudySession.start_time != '',
            StudySession.start_time < '07:00'
        ).first() is not None},
        {'name': 'Goal Getter', 'icon': '🎯', 'unlocked': user.gpa_current >= user.gpa_target and user.gpa_current > 0},
        {'name': 'Centurion', 'icon': '💯', 'unlocked': total_hours >= 100},
    ]
    return badges


def allowed_note_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_NOTE_EXTENSIONS


def human_filesize(num_bytes):
    num_bytes = float(num_bytes or 0)
    for unit in ['B', 'KB', 'MB']:
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}" if unit == 'B' else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"


app.jinja_env.filters['filesize'] = human_filesize


def save_subject_notes(subject, files):
    """Save uploaded note files (PDFs, docs, etc.) for a subject. Skips
    anything with a disallowed extension and flashes a warning instead."""
    saved = 0
    for f in files:
        if not f or not f.filename:
            continue
        if not allowed_note_file(f.filename):
            flash(f'Skipped "{f.filename}" — unsupported file type.', 'error')
            continue
        ext = f.filename.rsplit('.', 1)[1].lower()
        stored_name = f"{uuid.uuid4().hex}.{ext}"
        user_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(subject.user_id))
        try:
            os.makedirs(user_dir, exist_ok=True)
            path = os.path.join(user_dir, stored_name)
            f.save(path)
            file_size = os.path.getsize(path)
        except OSError:
            # Read-only or non-persistent filesystem (e.g. serverless
            # hosting without object storage configured). Don't 500 the
            # whole request over a file save -- just tell the person.
            flash(f'Couldn\'t save "{f.filename}" — file storage isn\'t configured on this deployment.', 'error')
            continue
        note = SubjectNote(
            subject_id=subject.id,
            user_id=subject.user_id,
            original_filename=os.path.basename(f.filename),
            stored_filename=stored_name,
            file_size=file_size,
        )
        db.session.add(note)
        saved += 1
    if saved:
        db.session.commit()
    return saved


@app.context_processor
def inject_active_timer():
    """Makes a running-session badge available in the nav on every page."""
    if current_user.is_authenticated and current_user.active_subject_id \
            and current_user.active_started_at and not current_user.active_stopped_at:
        subj = Subject.query.get(current_user.active_subject_id)
        if subj:
            return {'global_active_timer': {
                'subject_name': subj.name,
                'started_at_iso': current_user.active_started_at.isoformat() + 'Z',
            }}
    return {'global_active_timer': None}


# ----------------------------------------------------------------------
# AUTH ROUTES
# ----------------------------------------------------------------------

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        year_level = request.form.get('year_level', '1st Year')
        branch = request.form.get('branch', '').strip()
        university = request.form.get('university', '').strip()
        security_question = request.form.get('security_question', '').strip()
        security_answer = request.form.get('security_answer', '').strip()

        if not GMAIL_REGEX.match(email):
            flash('Please sign up with a valid Gmail address (e.g. you@gmail.com).', 'error')
        elif not name:
            flash('Please tell us your name.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        elif not security_question or not security_answer:
            flash('Please set a security question and answer — this is how you\'ll recover your account if you forget your password.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('An account with this Gmail address already exists. Try logging in.', 'error')
        else:
            user = User(
                email=email,
                password_hash=generate_password_hash(password),
                name=name,
                year_level=year_level,
                branch=branch,
                university=university,
                security_question=security_question,
                security_answer_hash=generate_password_hash(normalize_answer(security_answer)),
            )
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Welcome to StudyTrack! Your account has been created.', 'success')
            return redirect(url_for('dashboard'))

    return render_template('signup.html', year_levels=YEAR_LEVELS)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not GMAIL_REGEX.match(email):
            flash('Please enter a valid Gmail address (e.g. you@gmail.com).', 'error')
        elif is_locked_out(f'login:{email}'):
            wait_min = max(1, seconds_until_unlocked(f'login:{email}') // 60 + 1)
            flash(f'Too many failed attempts. Please try again in about {wait_min} minute(s).', 'error')
        else:
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password_hash, password):
                clear_attempts(f'login:{email}')
                login_user(user, remember=True)
                return redirect(url_for('dashboard'))
            record_failed_attempt(f'login:{email}')
            flash('Incorrect email or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not GMAIL_REGEX.match(email):
            flash('Please enter a valid Gmail address (e.g. you@gmail.com).', 'error')
        else:
            user = User.query.filter_by(email=email).first()
            if not user or not user.security_question:
                flash('No recoverable account found with that Gmail address.', 'error')
            else:
                session['reset_user_id'] = user.id
                return redirect(url_for('reset_password'))

    return render_template('forgot_password.html')


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    user_id = session.get('reset_user_id')
    user = User.query.get(user_id) if user_id else None
    if not user:
        flash('Please verify your Gmail address first.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        answer = request.form.get('security_answer', '')
        new_password = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        lock_key = f'reset:{user.id}'

        if is_locked_out(lock_key):
            wait_min = max(1, seconds_until_unlocked(lock_key) // 60 + 1)
            flash(f'Too many incorrect answers. Please try again in about {wait_min} minute(s).', 'error')
        elif not check_password_hash(user.security_answer_hash, normalize_answer(answer)):
            record_failed_attempt(lock_key)
            flash('That answer doesn\'t match what we have on file.', 'error')
        elif len(new_password) < 6:
            flash('New password must be at least 6 characters long.', 'error')
        elif new_password != confirm:
            flash('Passwords do not match.', 'error')
        else:
            clear_attempts(lock_key)
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            session.pop('reset_user_id', None)
            flash('Password updated! You can log in now.', 'success')
            return redirect(url_for('login'))

    return render_template('reset_password.html', security_question=user.security_question, email=user.email)


# ----------------------------------------------------------------------
# DASHBOARD
# ----------------------------------------------------------------------

@app.route('/')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')


@app.route('/dashboard')
@login_required
def dashboard():
    dept = request.args.get('dept', 'all')

    all_subjects = Subject.query.filter_by(user_id=current_user.id).all()
    departments = sorted(set(s.category for s in all_subjects))

    if dept != 'all':
        scoped_subjects = [s for s in all_subjects if s.category == dept]
    else:
        scoped_subjects = all_subjects
    subject_ids = [s.id for s in scoped_subjects]

    today = date.today()
    today_minutes = 0
    total_minutes = 0
    pending_count = 0
    deadlines = []

    if subject_ids:
        today_minutes = db.session.query(db.func.coalesce(db.func.sum(StudySession.duration_minutes), 0)).filter(
            StudySession.user_id == current_user.id,
            StudySession.session_date == today,
            StudySession.subject_id.in_(subject_ids)
        ).scalar()

        total_minutes = db.session.query(db.func.coalesce(db.func.sum(StudySession.duration_minutes), 0)).filter(
            StudySession.user_id == current_user.id,
            StudySession.subject_id.in_(subject_ids)
        ).scalar()

        pending_count = Assignment.query.filter(
            Assignment.user_id == current_user.id,
            Assignment.status == 'Pending',
            Assignment.subject_id.in_(subject_ids)
        ).count()

        deadlines = Assignment.query.filter(
            Assignment.user_id == current_user.id,
            Assignment.status == 'Pending',
            Assignment.subject_id.in_(subject_ids)
        ).order_by(Assignment.due_date.asc()).limit(3).all()

    return render_template(
        'dashboard.html',
        departments=departments,
        current_dept=dept,
        today_time_str=fmt_hm(today_minutes),
        total_hours=round((total_minutes or 0) / 60, 1),
        subjects_count=len(scoped_subjects),
        pending_count=pending_count,
        deadlines=deadlines,
        today=today,
    )


# ----------------------------------------------------------------------
# ASSIGNMENTS
# ----------------------------------------------------------------------

@app.route('/assignments')
@login_required
def assignments():
    status_filter = request.args.get('status', 'All')
    subject_filter = request.args.get('subject', 'all')
    query_text = request.args.get('q', '').strip()
    sort_by = request.args.get('sort', 'due_asc')
    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        page = 1
    per_page = 12

    query = Assignment.query.filter_by(user_id=current_user.id)
    if status_filter != 'All':
        query = query.filter_by(status=status_filter)
    if subject_filter != 'all':
        query = query.filter_by(subject_id=int(subject_filter))
    if query_text:
        query = query.filter(Assignment.title.ilike(f'%{query_text}%'))

    sort_map = {
        'due_asc': Assignment.due_date.asc(),
        'due_desc': Assignment.due_date.desc(),
        'title_asc': Assignment.title.asc(),
        'priority': db.case(
            (Assignment.priority == 'High', 0),
            (Assignment.priority == 'Medium', 1),
            (Assignment.priority == 'Low', 2),
            else_=3
        ),
    }
    query = query.order_by(sort_map.get(sort_by, Assignment.due_date.asc()))

    total_count = query.count()
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = min(page, total_pages)
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.name).all()
    today = date.today()

    return render_template(
        'assignments.html',
        assignments=items,
        subjects=subjects,
        status_filter=status_filter,
        subject_filter=subject_filter,
        query_text=query_text,
        sort_by=sort_by,
        today=today,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
    )


@app.route('/assignments/new', methods=['GET', 'POST'])
@login_required
def new_assignment():
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.name).all()
    if not subjects:
        flash('Add a subject first before creating an assignment.', 'error')
        return redirect(url_for('subjects'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        subject_id = request.form.get('subject_id')
        due_date = parse_date(request.form.get('due_date'), default=date.today())
        priority = request.form.get('priority', 'Medium')
        status = request.form.get('status', 'Pending')

        if not title:
            flash('Please enter an assignment title.', 'error')
        else:
            a = Assignment(
                user_id=current_user.id, subject_id=int(subject_id),
                title=title, due_date=due_date, priority=priority, status=status
            )
            db.session.add(a)
            db.session.commit()
            flash('Assignment added.', 'success')
            return redirect(url_for('assignments'))

    return render_template('assignment_form.html', subjects=subjects, priorities=PRIORITIES,
                            assignment=None, form_title='New Assignment')


@app.route('/assignments/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_assignment(item_id):
    a = Assignment.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.name).all()

    if request.method == 'POST':
        a.title = request.form.get('title', '').strip() or a.title
        a.subject_id = int(request.form.get('subject_id'))
        a.due_date = parse_date(request.form.get('due_date'), default=a.due_date)
        a.priority = request.form.get('priority', a.priority)
        a.status = request.form.get('status', a.status)
        db.session.commit()
        flash('Assignment updated.', 'success')
        return redirect(url_for('assignments'))

    return render_template('assignment_form.html', subjects=subjects, priorities=PRIORITIES,
                            assignment=a, form_title='Edit Assignment')


@app.route('/assignments/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_assignment(item_id):
    a = Assignment.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(a)
    db.session.commit()
    flash('Assignment deleted.', 'success')
    return redirect(url_for('assignments'))


@app.route('/assignments/<int:item_id>/toggle', methods=['POST'])
@login_required
def toggle_assignment(item_id):
    a = Assignment.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    a.status = 'Completed' if a.status == 'Pending' else 'Pending'
    db.session.commit()
    return redirect(url_for('assignments'))


@app.route('/assignments/calendar')
@login_required
def assignments_calendar():
    today = date.today()
    try:
        year = int(request.args.get('year', today.year))
        month = int(request.args.get('month', today.month))
    except ValueError:
        year, month = today.year, today.month

    if month < 1:
        month, year = 12, year - 1
    elif month > 12:
        month, year = 1, year + 1

    cal = calendar_module.Calendar(firstweekday=0)  # weeks start Monday
    month_days = cal.monthdatescalendar(year, month)

    assignments = Assignment.query.filter_by(user_id=current_user.id).all()
    assignments_by_date = {}
    for a in assignments:
        assignments_by_date.setdefault(a.due_date, []).append(a)

    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)

    return render_template(
        'assignments_calendar.html',
        month_days=month_days,
        assignments_by_date=assignments_by_date,
        year=year, month=month, today=today,
        month_label=f"{calendar_module.month_name[month]} {year}",
        prev_year=prev_year, prev_month=prev_month,
        next_year=next_year, next_month=next_month,
    )


# ----------------------------------------------------------------------
# SUBJECTS
# ----------------------------------------------------------------------

@app.route('/subjects')
@login_required
def subjects():
    year_filter = request.args.get('year', 'All')

    query = Subject.query.filter_by(user_id=current_user.id)
    if year_filter != 'All':
        query = query.filter_by(year_level=year_filter)
    items = query.order_by(Subject.category, Subject.name).all()

    grouped = {}
    for s in items:
        grouped.setdefault(s.category, []).append(s)

    color_map = {}
    for i, cat in enumerate(sorted(grouped.keys())):
        color_map[cat] = CARD_COLORS[i % len(CARD_COLORS)]

    return render_template(
        'subjects.html',
        grouped=grouped,
        color_map=color_map,
        year_levels=YEAR_LEVELS,
        year_filter=year_filter,
        card_colors=CARD_COLORS,
    )


@app.route('/subjects/new', methods=['GET', 'POST'])
@login_required
def new_subject():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip().upper() or 'CORE'
        credits = request.form.get('credits', 0)
        year_level = request.form.get('year_level', '1st Year')

        if not name:
            flash('Please enter a subject name.', 'error')
        else:
            s = Subject(
                user_id=current_user.id, name=name, category=category,
                credits=max(0, int(credits or 0)), year_level=year_level
            )
            db.session.add(s)
            db.session.commit()
            save_subject_notes(s, request.files.getlist('notes'))
            flash('Subject added.', 'success')
            return redirect(url_for('subjects'))

    return render_template('subject_form.html', year_levels=YEAR_LEVELS, subject=None, form_title='Add Subject')


@app.route('/subjects/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_subject(item_id):
    s = Subject.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        s.name = request.form.get('name', '').strip() or s.name
        s.category = (request.form.get('category', '').strip().upper()) or s.category
        s.credits = max(0, int(request.form.get('credits', s.credits) or 0))
        s.year_level = request.form.get('year_level', s.year_level)
        db.session.commit()
        save_subject_notes(s, request.files.getlist('notes'))
        flash('Subject updated.', 'success')
        return redirect(url_for('edit_subject', item_id=s.id))

    return render_template('subject_form.html', year_levels=YEAR_LEVELS, subject=s, form_title='Edit Subject')


@app.route('/subjects/<int:item_id>/notes/<int:note_id>/download')
@login_required
def download_subject_note(item_id, note_id):
    note = SubjectNote.query.filter_by(id=note_id, subject_id=item_id, user_id=current_user.id).first_or_404()
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id), note.stored_filename)
    if not os.path.exists(path):
        flash('That file could not be found on the server.', 'error')
        return redirect(url_for('edit_subject', item_id=item_id))
    return send_file(path, as_attachment=True, download_name=note.original_filename)


@app.route('/subjects/<int:item_id>/notes/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_subject_note(item_id, note_id):
    note = SubjectNote.query.filter_by(id=note_id, subject_id=item_id, user_id=current_user.id).first_or_404()
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id), note.stored_filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(note)
    db.session.commit()
    flash('Note removed.', 'success')
    return redirect(url_for('edit_subject', item_id=item_id))


@app.route('/subjects/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_subject(item_id):
    s = Subject.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    for note in s.notes:
        path = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id), note.stored_filename)
        if os.path.exists(path):
            os.remove(path)

    # If a live timer is running on this subject, stop it cleanly rather
    # than leaving a dangling reference to a subject that no longer exists.
    if current_user.active_subject_id == s.id:
        current_user.active_subject_id = None
        current_user.active_started_at = None
        current_user.active_stopped_at = None

    db.session.delete(s)
    db.session.commit()
    flash('Subject deleted.', 'success')
    return redirect(url_for('subjects'))


@app.route('/subjects/bulk-import', methods=['GET', 'POST'])
@login_required
def bulk_import_subjects():
    if request.method == 'POST':
        raw = request.form.get('bulk_data', '')
        reader = csv.reader(io.StringIO(raw.strip()))
        added = 0
        for row in reader:
            row = [c.strip() for c in row if c.strip() != '']
            if not row:
                continue
            name = row[0] if len(row) > 0 else ''
            category = row[1].upper() if len(row) > 1 else 'CORE'
            try:
                credits = max(0, int(row[2])) if len(row) > 2 else 0
            except ValueError:
                credits = 0
            year_level = row[3] if len(row) > 3 and row[3] in YEAR_LEVELS else '1st Year'
            if name:
                db.session.add(Subject(
                    user_id=current_user.id, name=name, category=category,
                    credits=credits, year_level=year_level
                ))
                added += 1
        db.session.commit()
        flash(f'Imported {added} subject(s).', 'success')
        return redirect(url_for('subjects'))

    return render_template('bulk_import.html')


# ----------------------------------------------------------------------
# STUDY HISTORY
# ----------------------------------------------------------------------

@app.route('/study-history')
@login_required
def study_history():
    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        page = 1
    per_page = 10

    base_query = StudySession.query.filter_by(user_id=current_user.id)
    all_sessions = base_query.all()
    total_minutes = sum(s.duration_minutes for s in all_sessions)
    avg_effectiveness = round(sum(s.effectiveness for s in all_sessions) / len(all_sessions), 1) if all_sessions else 0.0

    total_count = len(all_sessions)
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = min(page, total_pages)

    sessions = base_query.order_by(
        StudySession.session_date.desc(), StudySession.id.desc()
    ).offset((page - 1) * per_page).limit(per_page).all()

    return render_template(
        'study_history.html',
        sessions=sessions,
        total_time_str=fmt_hm(total_minutes),
        avg_effectiveness=avg_effectiveness,
        session_count=total_count,
        page=page,
        total_pages=total_pages,
    )


@app.route('/study-history/new')
@login_required
def study_timer():
    # Guard against a dangling timer pointing at a deleted subject — check
    # this first, before anything else, so it's cleaned up even if the user
    # has no subjects left at all.
    if current_user.active_subject_id:
        active_subject_check = Subject.query.get(current_user.active_subject_id)
        if not active_subject_check:
            current_user.active_subject_id = None
            current_user.active_started_at = None
            current_user.active_stopped_at = None
            db.session.commit()

    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.name).all()
    if not subjects:
        flash('Add a subject first before starting a study session.', 'error')
        return redirect(url_for('subjects'))

    active_subject = None
    if current_user.active_subject_id:
        active_subject = Subject.query.get(current_user.active_subject_id)

    state = 'idle'
    elapsed_seconds = 0
    started_at_iso = None

    if active_subject and current_user.active_started_at:
        started_at_iso = current_user.active_started_at.isoformat() + 'Z'
        if current_user.active_stopped_at:
            state = 'review'
            elapsed_seconds = max(int((current_user.active_stopped_at - current_user.active_started_at).total_seconds()), 0)
        else:
            state = 'running'

    return render_template(
        'study_timer.html',
        subjects=subjects,
        state=state,
        active_subject=active_subject,
        started_at_iso=started_at_iso,
        elapsed_seconds=elapsed_seconds,
    )


@app.route('/study-history/start', methods=['POST'])
@login_required
def start_timer():
    if current_user.active_subject_id:
        flash('A session is already in progress.', 'error')
        return redirect(url_for('study_timer'))

    subject_id = request.form.get('subject_id')
    subj = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first()
    if not subj:
        flash('Please choose a valid subject.', 'error')
        return redirect(url_for('study_timer'))

    current_user.active_subject_id = subj.id
    current_user.active_started_at = datetime.utcnow()
    current_user.active_stopped_at = None
    db.session.commit()
    return redirect(url_for('study_timer'))


@app.route('/study-history/stop', methods=['POST'])
@login_required
def stop_timer():
    if current_user.active_subject_id and current_user.active_started_at and not current_user.active_stopped_at:
        current_user.active_stopped_at = datetime.utcnow()
        db.session.commit()
    return redirect(url_for('study_timer'))


@app.route('/study-history/finalize', methods=['POST'])
@login_required
def finalize_timer():
    if not (current_user.active_subject_id and current_user.active_started_at and current_user.active_stopped_at):
        flash('No session to save.', 'error')
        return redirect(url_for('study_timer'))

    effectiveness = int(request.form.get('effectiveness', 3))
    started = current_user.active_started_at
    stopped = current_user.active_stopped_at
    duration = max(int((stopped - started).total_seconds() // 60), 0)

    s = StudySession(
        user_id=current_user.id, subject_id=current_user.active_subject_id,
        session_date=started.date(), start_time=started.strftime('%H:%M'),
        end_time=stopped.strftime('%H:%M'), duration_minutes=duration,
        effectiveness=effectiveness
    )
    db.session.add(s)

    current_user.active_subject_id = None
    current_user.active_started_at = None
    current_user.active_stopped_at = None
    db.session.commit()
    flash('Study session saved.', 'success')
    return redirect(url_for('study_history'))


@app.route('/study-history/discard', methods=['POST'])
@login_required
def discard_timer():
    current_user.active_subject_id = None
    current_user.active_started_at = None
    current_user.active_stopped_at = None
    db.session.commit()
    flash('Session discarded.', 'success')
    return redirect(url_for('study_history'))


@app.route('/study-history/manual', methods=['GET', 'POST'])
@login_required
def new_study_session():
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.name).all()
    if not subjects:
        flash('Add a subject first before logging a study session.', 'error')
        return redirect(url_for('subjects'))

    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        session_date = parse_date(request.form.get('session_date'), default=date.today())
        start_time = request.form.get('start_time', '')
        end_time = request.form.get('end_time', '')
        effectiveness = int(request.form.get('effectiveness', 3))
        duration = compute_duration_minutes(start_time, end_time)

        s = StudySession(
            user_id=current_user.id, subject_id=int(subject_id), session_date=session_date,
            start_time=start_time, end_time=end_time, duration_minutes=duration,
            effectiveness=effectiveness
        )
        db.session.add(s)
        db.session.commit()
        flash('Study session logged.', 'success')
        return redirect(url_for('study_history'))

    return render_template('study_session_form.html', subjects=subjects, today=date.today())


@app.route('/study-history/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_study_session(item_id):
    s = StudySession.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(s)
    db.session.commit()
    flash('Session removed.', 'success')
    return redirect(url_for('study_history'))


# ----------------------------------------------------------------------
# PROGRESS & ANALYTICS
# ----------------------------------------------------------------------

@app.route('/progress')
@login_required
def progress():
    all_subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.name).all()
    departments = sorted(set(s.category for s in all_subjects))

    subject_filter = request.args.get('subject', 'all')
    dept_filter = request.args.get('dept', 'all')
    period = request.args.get('period', '7')  # '7', '30', 'all'

    query = StudySession.query.filter_by(user_id=current_user.id)
    if subject_filter != 'all':
        query = query.filter_by(subject_id=int(subject_filter))
    if dept_filter != 'all':
        dept_subject_ids = [s.id for s in all_subjects if s.category == dept_filter]
        query = query.filter(StudySession.subject_id.in_(dept_subject_ids or [-1]))

    if period != 'all':
        days = int(period)
        start_date = date.today() - timedelta(days=days - 1)
        query = query.filter(StudySession.session_date >= start_date)
    else:
        days = 30
        start_date = date.today() - timedelta(days=days - 1)

    sessions = query.all()
    total_minutes = sum(s.duration_minutes for s in sessions)

    day_set = days_with_sessions(current_user.id)
    streak = calculate_current_streak(day_set)

    # Completion % among assignments belonging to filtered subjects (or all)
    if subject_filter != 'all':
        assignment_subject_ids = [int(subject_filter)]
    elif dept_filter != 'all':
        assignment_subject_ids = [s.id for s in all_subjects if s.category == dept_filter]
    else:
        assignment_subject_ids = [s.id for s in all_subjects]

    if assignment_subject_ids:
        total_assignments = Assignment.query.filter(
            Assignment.user_id == current_user.id,
            Assignment.subject_id.in_(assignment_subject_ids)
        ).count()
        completed_assignments = Assignment.query.filter(
            Assignment.user_id == current_user.id,
            Assignment.subject_id.in_(assignment_subject_ids),
            Assignment.status == 'Completed'
        ).count()
    else:
        total_assignments = completed_assignments = 0

    completion_pct = round((completed_assignments / total_assignments) * 100) if total_assignments else 0
    avg_per_day = round(total_minutes / max(days, 1))

    # Daily trend (chronological)
    trend_labels = []
    trend_values = []
    cur_day = start_date
    while cur_day <= date.today():
        day_minutes = sum(s.duration_minutes for s in sessions if s.session_date == cur_day)
        trend_labels.append(cur_day.strftime('%b %d'))
        trend_values.append(round(day_minutes / 60, 2))
        cur_day += timedelta(days=1)

    # Subject time allocation
    allocation = {}
    for s in sessions:
        subj = Subject.query.get(s.subject_id)
        key = subj.name if subj else 'Unknown'
        allocation[key] = allocation.get(key, 0) + s.duration_minutes

    allocation_list = []
    for i, (name, minutes) in enumerate(sorted(allocation.items(), key=lambda x: -x[1])):
        pct = round((minutes / total_minutes) * 100) if total_minutes else 0
        color = CARD_COLORS[i % len(CARD_COLORS)]
        allocation_list.append({
            'name': name, 'minutes': minutes, 'hours': round(minutes / 60, 2), 'pct': pct,
            'color': color, 'hex': CARD_HEX[color]
        })

    # Per-subject progress (assignment completion %) for the subjects in scope
    if subject_filter != 'all':
        progress_subjects = [s for s in all_subjects if s.id == int(subject_filter)]
    elif dept_filter != 'all':
        progress_subjects = [s for s in all_subjects if s.category == dept_filter]
    else:
        progress_subjects = all_subjects

    subject_progress_list = []
    for i, s in enumerate(progress_subjects):
        total_a = Assignment.query.filter_by(user_id=current_user.id, subject_id=s.id).count()
        done_a = Assignment.query.filter_by(user_id=current_user.id, subject_id=s.id, status='Completed').count()
        pct = round((done_a / total_a) * 100) if total_a else 0
        color = CARD_COLORS[i % len(CARD_COLORS)]
        subject_progress_list.append({
            'name': s.name, 'pct': pct, 'total': total_a, 'done': done_a,
            'color': color, 'hex': CARD_HEX[color]
        })
    subject_progress_list.sort(key=lambda x: -x['pct'])

    return render_template(
        'progress.html',
        all_subjects=all_subjects,
        departments=departments,
        subject_filter=subject_filter,
        dept_filter=dept_filter,
        period=period,
        total_hours=round(total_minutes / 60, 1),
        streak=streak,
        completion_pct=completion_pct,
        avg_per_day=avg_per_day,
        trend_labels=trend_labels,
        trend_values=trend_values,
        allocation_list=allocation_list,
        subject_progress_list=subject_progress_list,
    )


# ----------------------------------------------------------------------
# PROFILE
# ----------------------------------------------------------------------

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name', current_user.name).strip()
        current_user.year_level = request.form.get('year_level', current_user.year_level)
        current_user.branch = request.form.get('branch', current_user.branch).strip()
        current_user.university = request.form.get('university', current_user.university).strip()
        current_user.bio = request.form.get('bio', current_user.bio).strip()

        try:
            current_user.gpa_current = float(request.form.get('gpa_current') or 0)
        except ValueError:
            pass
        try:
            current_user.gpa_target = float(request.form.get('gpa_target') or current_user.gpa_target)
        except ValueError:
            pass
        try:
            current_user.attendance = float(request.form.get('attendance') or 0)
        except ValueError:
            pass
        try:
            current_user.weekly_study_target = float(request.form.get('weekly_study_target') or current_user.weekly_study_target)
        except ValueError:
            pass

        current_user.next_milestone_title = request.form.get('next_milestone_title', '').strip()
        current_user.next_milestone_date = parse_date(request.form.get('next_milestone_date'))

        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('profile'))

    subjects_count = Subject.query.filter_by(user_id=current_user.id).count()

    total_minutes = db.session.query(db.func.coalesce(db.func.sum(StudySession.duration_minutes), 0)).filter_by(
        user_id=current_user.id
    ).scalar()
    total_hours = round((total_minutes or 0) / 60, 1)

    # Weekly study progress (current week, Mon-Sun)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_minutes = db.session.query(db.func.coalesce(db.func.sum(StudySession.duration_minutes), 0)).filter(
        StudySession.user_id == current_user.id,
        StudySession.session_date >= week_start
    ).scalar()
    week_hours = round((week_minutes or 0) / 60, 1)

    day_set = days_with_sessions(current_user.id)
    current_streak = calculate_current_streak(day_set)
    longest_streak = calculate_longest_streak(day_set)

    badges = get_badges(current_user, subjects_count, longest_streak, total_hours)

    gpa_progress_pct = min(round((current_user.gpa_current / current_user.gpa_target) * 100), 100) if current_user.gpa_target else 0
    week_progress_pct = min(round((week_hours / current_user.weekly_study_target) * 100), 100) if current_user.weekly_study_target else 0

    days_away = None
    if current_user.next_milestone_date:
        days_away = (current_user.next_milestone_date - today).days

    return render_template(
        'profile.html',
        subjects_count=subjects_count,
        total_hours=total_hours,
        week_hours=week_hours,
        current_streak=current_streak,
        longest_streak=longest_streak,
        badges=badges,
        gpa_progress_pct=gpa_progress_pct,
        week_progress_pct=week_progress_pct,
        days_away=days_away,
        year_levels=YEAR_LEVELS,
    )


@app.route('/profile/theme/<mode>', methods=['POST'])
@login_required
def set_theme(mode):
    if mode in ('dark', 'light'):
        current_user.theme = mode
        db.session.commit()
    return redirect(request.referrer or url_for('profile'))


@app.route('/profile/security', methods=['POST'])
@login_required
def update_security():
    current_password = request.form.get('current_password', '')
    new_question = request.form.get('security_question', '').strip()
    new_answer = request.form.get('security_answer', '').strip()

    if not check_password_hash(current_user.password_hash, current_password):
        flash('Current password is incorrect.', 'error')
    elif not new_question or not new_answer:
        flash('Please fill in both the security question and answer.', 'error')
    else:
        current_user.security_question = new_question
        current_user.security_answer_hash = generate_password_hash(normalize_answer(new_answer))
        db.session.commit()
        flash('Security question updated.', 'success')

    return redirect(url_for('profile'))


@app.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not check_password_hash(current_user.password_hash, current_password):
        flash('Current password is incorrect.', 'error')
    elif len(new_password) < 6:
        flash('New password must be at least 6 characters long.', 'error')
    elif new_password != confirm_password:
        flash('New passwords do not match.', 'error')
    else:
        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash('Password changed successfully.', 'success')

    return redirect(url_for('profile'))


@app.route('/profile/export')
@login_required
def export_data():
    """Lets a user download their own data as JSON — for backup or migration.
    Deliberately excludes the password hash and security answer hash; this is
    about data portability, not credential export."""
    user = current_user

    subjects = Subject.query.filter_by(user_id=user.id).order_by(Subject.name).all()
    subject_name_by_id = {s.id: s.name for s in subjects}

    assignments = Assignment.query.filter_by(user_id=user.id).order_by(Assignment.due_date).all()
    sessions = StudySession.query.filter_by(user_id=user.id).order_by(StudySession.session_date).all()

    data = {
        'exported_at': datetime.utcnow().isoformat() + 'Z',
        'profile': {
            'name': user.name,
            'email': user.email,
            'year_level': user.year_level,
            'branch': user.branch,
            'university': user.university,
            'bio': user.bio,
            'gpa_current': user.gpa_current,
            'gpa_target': user.gpa_target,
            'attendance': user.attendance,
            'weekly_study_target_hours': user.weekly_study_target,
            'next_milestone_title': user.next_milestone_title,
            'next_milestone_date': user.next_milestone_date.isoformat() if user.next_milestone_date else None,
            'theme': user.theme,
            'account_created': user.created_at.isoformat() if user.created_at else None,
        },
        'subjects': [
            {
                'name': s.name,
                'category': s.category,
                'credits': s.credits,
                'year_level': s.year_level,
                'notes': [
                    {
                        'filename': n.original_filename,
                        'uploaded_at': n.uploaded_at.isoformat() if n.uploaded_at else None,
                        'size_bytes': n.file_size,
                    }
                    for n in s.notes
                ],
            }
            for s in subjects
        ],
        'assignments': [
            {
                'title': a.title,
                'subject': subject_name_by_id.get(a.subject_id, 'Unknown'),
                'due_date': a.due_date.isoformat(),
                'priority': a.priority,
                'status': a.status,
            }
            for a in assignments
        ],
        'study_sessions': [
            {
                'subject': subject_name_by_id.get(s.subject_id, 'Unknown'),
                'date': s.session_date.isoformat(),
                'start_time': s.start_time,
                'end_time': s.end_time,
                'duration_minutes': s.duration_minutes,
                'effectiveness': s.effectiveness,
            }
            for s in sessions
        ],
    }

    json_str = json.dumps(data, indent=2)
    filename = f"studytrack_export_{date.today().isoformat()}.json"
    return Response(
        json_str,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@app.route('/profile/delete-account', methods=['POST'])
@login_required
def delete_account():
    password = request.form.get('current_password', '')
    if not check_password_hash(current_user.password_hash, password):
        flash('Current password is incorrect — your account was not deleted.', 'error')
        return redirect(url_for('profile'))

    user_id = current_user.id
    user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))

    logout_user()
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)  # cascades to subjects, assignments, sessions, notes
        db.session.commit()

    if os.path.isdir(user_upload_dir):
        import shutil
        shutil.rmtree(user_upload_dir, ignore_errors=True)

    flash('Your account and all associated data have been deleted.', 'success')
    return redirect(url_for('login'))


# ----------------------------------------------------------------------
# ERROR HANDLERS
# ----------------------------------------------------------------------

@app.errorhandler(404)
def not_found_error(e):
    return render_template('error.html', code=404,
                            title='Page Not Found',
                            message="That page doesn't exist — it may have been moved or the link is off."), 404


@app.errorhandler(403)
def forbidden_error(e):
    return render_template('error.html', code=403,
                            title='Forbidden',
                            message="You don't have access to that."), 403


@app.errorhandler(413)
def too_large_error(e):
    return render_template('error.html', code=413,
                            title='File Too Large',
                            message='That upload was too big — the limit is 20MB per file.'), 413


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', code=500,
                            title='Something Went Wrong',
                            message="An unexpected error happened on our end. Try again in a moment."), 500


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
