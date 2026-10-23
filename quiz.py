"""English vocabulary practice application with session-based authentication."""

import csv
import io
import os
import re
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ["FLASK_SECRET_KEY"],
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///db.sqlite"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=os.getenv("DEV_INSECURE_COOKIES") != "1",
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"))
WORDS_ROOT = Path(os.getenv("WORDS_ROOT", str(Path(app.instance_path) / "words"))).resolve()
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,50}$")


class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # Werkzeug password hash only
    lastlogin = db.Column(db.DateTime, nullable=False)


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(Users, int(user_id))
    except (ValueError, TypeError):
        return None


def user_words_path():
    # Use the authenticated integer ID, never a client-supplied filesystem component.
    return WORDS_ROOT / str(current_user.id) / "wordsbank.csv"


def load_words():
    path = user_words_path()
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        if not {"Word", "Meaning"}.issubset(rows.fieldnames or []):
            raise ValueError("CSV requires Word and Meaning columns")
        return {row["Word"].strip(): row["Meaning"].strip()
                for row in rows if row.get("Word") and row.get("Meaning")}


def read_upload(file):
    try:
        text = file.stream.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if not {"Word", "Meaning"}.issubset(reader.fieldnames or []):
            raise ValueError
        rows = [(r["Word"].strip(), r["Meaning"].strip()) for r in reader]
    except (UnicodeError, csv.Error, ValueError, TypeError, KeyError):
        raise ValueError("Upload a UTF-8 CSV with Word and Meaning columns") from None
    if not rows or any(not word or not meaning for word, meaning in rows):
        raise ValueError("Every CSV row must contain a Word and Meaning")
    if len(rows) > 10000:
        raise ValueError("Too many vocabulary entries")
    return rows


@app.route("/")
def home():
    return render_template("landingpage.html")


@app.route("/register", methods=["GET", "POST"])
@limiter.limit("3 per hour", methods=["POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not USERNAME_PATTERN.fullmatch(username) or len(password) < 12:
            flash("Use a 3–50 character username (letters, numbers, _ or -) and a password of at least 12 characters.")
        elif Users.query.filter_by(username=username).first():
            flash("Unable to create account with those details.")
        else:
            user = Users(username=username, password=generate_password_hash(password), lastlogin=datetime.now(timezone.utc).replace(tzinfo=None))
            db.session.add(user)
            db.session.commit()
            flash("Account created. Please log in.")
            return redirect(url_for("login"))
    return render_template("sign_up.html")


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if request.method == "POST":
        user = Users.query.filter_by(username=request.form.get("username", "").strip()).first()
        password = request.form.get("password", "")
        if user and check_password_hash(user.password, password):
            session.clear()
            login_user(user, fresh=True)
            session.permanent = True
            user.lastlogin = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.commit()
            return redirect(url_for("index"))
        flash("Invalid username or password.")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("home"))


@app.route("/mainpage")
@login_required
def index():
    try:
        count = len(load_words())
        message = f"Your word bank contains {count} entries." if count else "Upload a Word/Meaning CSV to begin."
    except ValueError:
        message = "Your word bank is invalid. Please upload a new CSV."
    return render_template("index.html", msg=message)


@app.route("/upload")
@login_required
def upload():
    return render_template("upload.html")


@app.route("/uploadsubmit", methods=["POST"])
@login_required
def upload_file():
    file = request.files.get("file")
    if not file or not file.filename or not file.filename.lower().endswith(".csv"):
        flash("Choose a CSV file.")
        return redirect(url_for("upload"))
    try:
        rows = read_upload(file)
    except ValueError as exc:
        flash(str(exc))
        return redirect(url_for("upload"))
    target = user_words_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / ("." + secrets.token_hex(16) + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Word", "Meaning"])
            writer.writerows(rows)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    session.pop("quiz_words", None)
    session.pop("spell_words", None)
    return render_template("uploaded_file.html", filename="wordsbank.csv")


@app.route("/refresh")
@login_required
def refresh():
    try:
        count = len(load_words())
    except ValueError:
        flash("Invalid vocabulary file.")
        return redirect(url_for("upload"))
    session.pop("quiz_words", None)
    session.pop("spell_words", None)
    return render_template("data_refreshed.html", p=count, c=count)


@app.route("/quiz")
@login_required
def quiz():
    try:
        bank = load_words()
    except ValueError:
        abort(400, "Invalid word bank")
    if len(bank) < 4 or len(set(bank.values())) < 4:
        flash("At least four words with distinct meanings are required for quizzes.")
        return redirect(url_for("index"))
    rng = secrets.SystemRandom()
    questions = {}
    for word in rng.sample(list(bank), min(10, len(bank))):
        alternatives = rng.sample([meaning for meaning in set(bank.values()) if meaning != bank[word]], 3)
        options = [bank[word], *alternatives]
        rng.shuffle(options)
        questions[word] = options
    session["quiz_words"] = list(questions)
    return render_template("quiz.html", q=questions)


@app.route("/quiz_answer", methods=["POST"])
@login_required
def quiz_answers():
    selected = session.pop("quiz_words", None)
    if not selected:
        abort(400, "Start a quiz first")
    bank = load_words()
    if any(word not in bank for word in selected):
        abort(400, "Quiz expired; start again")
    correct = {word: bank[word] for word in selected}
    results = {word: request.form.get(word) == bank[word] for word in selected}
    return render_template("quiz_answer.html", count=sum(results.values()), ca=correct, cad=results)


@app.route("/spell")
@login_required
def spell():
    bank = load_words()
    candidates = [word for word in bank if " " not in word and len(word) >= 2]
    if not candidates:
        flash("Upload words with at least two letters to practise spelling.")
        return redirect(url_for("index"))
    rng = secrets.SystemRandom()
    selected = rng.sample(candidates, min(10, len(candidates)))
    masked = {}
    for word in selected:
        n = min(max(1, len(word) // 4), len(word) - 1)
        positions = set(rng.sample(range(1, len(word)), n))
        masked[word] = "".join("_" if i in positions else char for i, char in enumerate(word))
    session["spell_words"] = selected
    return render_template("spell.html", q=masked, a={word: bank[word] for word in selected})


@app.route("/spell_answer", methods=["POST"])
@login_required
def spell_answers():
    selected = session.pop("spell_words", None)
    if not selected:
        abort(400, "Start a spelling test first")
    bank = load_words()
    if any(word not in bank for word in selected):
        abort(400, "Spelling test expired; start again")
    results = {word: request.form.get(word, "").strip() == word for word in selected}
    return render_template("spell_answer.html", count=sum(results.values()),
                           ca={word: bank[word] for word in selected}, cad=results)


@app.route("/misspelled")
@login_required
def misspelled():
    return render_template("underconstruct.html")


if __name__ == "__main__":
    app.run(port=5002, debug=False)
