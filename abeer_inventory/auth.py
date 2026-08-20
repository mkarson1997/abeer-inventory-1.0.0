import time

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .security import request_ip, safe_next_url, validate_password, validate_username

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _blocked(db, username, ip):
    now = int(time.time())
    window = current_app.config["LOGIN_WINDOW_SECONDS"]
    row = db.execute(
        "SELECT COUNT(*) AS n FROM login_attempts WHERE username=? AND ip_address=? "
        "AND success=0 AND attempted_at>=?",
        (username, ip, now - window),
    ).fetchone()
    return row["n"] >= current_app.config["LOGIN_MAX_FAILURES"]


def _record_attempt(db, username, ip, success):
    now = int(time.time())
    db.execute(
        "INSERT INTO login_attempts(username,ip_address,attempted_at,success) VALUES(?,?,?,?)",
        (username, ip, now, 1 if success else 0),
    )
    # Bound the table and remove stale entries.
    db.execute("DELETE FROM login_attempts WHERE attempted_at < ?", (now - 7 * 86400,))
    db.execute(
        "DELETE FROM login_attempts WHERE id NOT IN (SELECT id FROM login_attempts ORDER BY id DESC LIMIT 20000)"
    )


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if not user_id:
        g.user = None
        return
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=? AND is_active=1", (user_id,)).fetchone()
    if user is None or session.get("session_version") != user["session_version"]:
        session.clear()
        g.user = None
    else:
        g.user = user


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("inventory.dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()[:64]
        password = request.form.get("password") or ""
        ip = request_ip()
        db = get_db()
        if _blocked(db, username, ip):
            flash("Too many failed attempts. Try again later.", "danger")
            return render_template("login.html"), 429
        user = db.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
        ok = bool(user) and len(password) <= 256 and check_password_hash(user["password_hash"], password)
        _record_attempt(db, username, ip, ok)
        if not ok:
            flash("Invalid username or password.", "danger")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["session_version"] = user["session_version"]
            session["lang"] = "ar"
            session.permanent = True
            return redirect(safe_next_url(request.form.get("next")) or url_for("inventory.dashboard"))
    return render_template("login.html")


@bp.route("/register", methods=("GET", "POST"))
def register():
    if not current_app.config["ALLOW_REGISTRATION"]:
        return ("Registration disabled", 404)
    if request.method == "POST":
        try:
            username = validate_username(request.form.get("username"))
            password = validate_password(request.form.get("password"))
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("register.html"), 400
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users(username,password_hash,role) VALUES(?,?, 'viewer')",
                (username, generate_password_hash(password)),
            )
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                flash("Username already exists.", "danger")
                return render_template("register.html"), 409
            raise
        flash("Account created. You can log in now.", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html")


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/password", methods=("GET", "POST"))
def change_password():
    if g.user is None:
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        current = request.form.get("current_password") or ""
        new = request.form.get("new_password") or ""
        if not check_password_hash(g.user["password_hash"], current):
            flash("Current password is incorrect.", "danger")
            return render_template("change_password.html"), 400
        try:
            validate_password(new)
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("change_password.html"), 400
        db = get_db()
        db.execute(
            "UPDATE users SET password_hash=?, session_version=session_version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (generate_password_hash(new), g.user["id"]),
        )
        updated = db.execute("SELECT session_version FROM users WHERE id=?", (g.user["id"],)).fetchone()
        session["session_version"] = updated["session_version"]
        flash("Password changed.", "success")
        return redirect(url_for("inventory.dashboard"))
    return render_template("change_password.html")
