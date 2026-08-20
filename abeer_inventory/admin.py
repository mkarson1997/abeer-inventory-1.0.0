import sqlite3
from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from .db import get_db
from .security import ALLOWED_ROLES, roles_required, validate_password, validate_username

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/users")
@roles_required("admin")
def users():
    rows = get_db().execute("SELECT * FROM users ORDER BY username COLLATE NOCASE").fetchall()
    return render_template("users.html", users=rows)


@bp.post("/users/create")
@roles_required("admin")
def create_user():
    try:
        username = validate_username(request.form.get("username"))
        password = validate_password(request.form.get("password"))
        role = request.form.get("role", "viewer")
        if role not in ALLOWED_ROLES:
            raise ValueError("Invalid role")
        db = get_db()
        db.execute(
            "INSERT INTO users(username,password_hash,role) VALUES(?,?,?)",
            (username, generate_password_hash(password), role),
        )
        flash("User created.", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    except sqlite3.IntegrityError:
        flash("Username already exists or the user data is invalid.", "danger")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:user_id>/update")
@roles_required("admin")
def update_user(user_id):
    db = get_db()
    target = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if target is None:
        return ("Not found", 404)
    role = request.form.get("role", target["role"])
    active = 1 if request.form.get("is_active") == "1" else 0
    if role not in ALLOWED_ROLES:
        return ("Invalid role", 400)
    if target["role"] == "admin" and (role != "admin" or not active):
        admins = db.execute("SELECT COUNT(*) AS n FROM users WHERE role='admin' AND is_active=1").fetchone()["n"]
        if admins <= 1:
            flash("The last active administrator cannot be disabled or demoted.", "danger")
            return redirect(url_for("admin.users"))
    db.execute(
        "UPDATE users SET role=?, is_active=?, session_version=session_version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (role, active, user_id),
    )
    flash("User updated.", "success")
    return redirect(url_for("admin.users"))
