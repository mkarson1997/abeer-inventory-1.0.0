import json
import os
import secrets
import shutil
import sqlite3
import zipfile
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import click
from flask import Flask, g, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from . import admin, auth, db, inventory
from .i18n import texts
from .security import install_security, validate_password, validate_username


def _bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    environment = os.getenv("ABEER_ENV", "development").strip().lower()
    secret = os.getenv("ABEER_SECRET_KEY")
    if environment == "production" and (not secret or len(secret) < 32 or secret.lower().startswith("replace-")):
        raise RuntimeError("ABEER_SECRET_KEY must be a strong secret (32+ chars) in production")
    if not secret:
        secret = secrets.token_hex(32)

    max_upload_mb = max(1, min(20, int(os.getenv("ABEER_MAX_UPLOAD_MB", "5"))))
    app.config.from_mapping(
        SECRET_KEY=secret,
        ENVIRONMENT=environment,
        DATABASE=str(Path(app.instance_path) / "abeer.sqlite3"),
        UPLOAD_FOLDER=str(Path(app.instance_path) / "uploads"),
        MAX_CONTENT_LENGTH=(max_upload_mb + 1) * 1024 * 1024,
        MAX_IMAGE_BYTES=max_upload_mb * 1024 * 1024,
        ALLOW_REGISTRATION=_bool_env("ABEER_ALLOW_REGISTRATION", False),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=_bool_env("ABEER_COOKIE_SECURE", environment == "production"),
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        LOGIN_MAX_FAILURES=5,
        LOGIN_WINDOW_SECONDS=15 * 60,
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    trusted = [x.strip() for x in os.getenv("ABEER_TRUSTED_HOSTS", "").split(",") if x.strip()]
    if trusted:
        app.config["TRUSTED_HOSTS"] = trusted

    db.init_app(app)
    install_security(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(inventory.bp)

    @app.context_processor
    def template_context():
        lang = session.get("lang", "ar")
        return {
            "t": texts(lang), "lang": lang, "rtl": lang == "ar", "current_user": g.get("user"),
            "theme": session.get("theme", "light"),
        }

    @app.post("/preferences")
    def preferences():
        if g.get("user") is None:
            return redirect(url_for("auth.login"))
        lang = request.form.get("lang", session.get("lang", "ar"))
        theme = request.form.get("theme", session.get("theme", "light"))
        if lang in {"ar", "tr", "en"}:
            session["lang"] = lang
        if theme in {"light", "dark"}:
            session["theme"] = theme
        return redirect(request.referrer or url_for("inventory.dashboard"))

    @app.get("/healthz")
    def healthz():
        try:
            db.get_db().execute("SELECT 1").fetchone()
            return {"status": "ok", "app": "abeer-inventory"}
        except Exception:
            return {"status": "error"}, 503

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="Access denied"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="Not found"), 404

    @app.errorhandler(413)
    def too_large(_error):
        return render_template("error.html", code=413, message="Upload is too large"), 413

    register_cli(app)
    return app


def register_cli(app):
    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.password_option(confirmation_prompt=True)
    def create_admin(username, password):
        """Create or promote an administrator."""
        username = validate_username(username)
        validate_password(password)
        conn = db.get_db()
        existing = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE users SET password_hash=?,role='admin',is_active=1,session_version=session_version+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (generate_password_hash(password), existing["id"]),
            )
            click.echo("Administrator updated.")
        else:
            conn.execute(
                "INSERT INTO users(username,password_hash,role) VALUES(?,?,'admin')",
                (username, generate_password_hash(password)),
            )
            click.echo("Administrator created.")

    @app.cli.command("check-db")
    def check_db():
        """Run SQLite integrity and foreign-key checks."""
        conn = db.get_db()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        click.echo(f"integrity: {integrity}")
        click.echo(f"foreign-key violations: {len(fk)}")
        if integrity != "ok" or fk:
            raise click.ClickException("Database check failed")

    @app.cli.command("import-legacy")
    @click.option("--path", "legacy_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
    def import_legacy(legacy_path):
        """Import products from the old stok.db. Users and images are intentionally excluded."""
        source = sqlite3.connect(legacy_path)
        source.row_factory = sqlite3.Row
        try:
            cols = {r[1] for r in source.execute("PRAGMA table_info(urunler)").fetchall()}
            required = {"ad", "kategori", "miktar", "birim_fiyat", "kritik_stok"}
            if not required.issubset(cols):
                raise click.ClickException("Legacy database does not contain the expected urunler schema")
            rows = source.execute("SELECT * FROM urunler ORDER BY id").fetchall()
            target = db.get_db()
            count = 0
            target.execute("BEGIN IMMEDIATE")
            for row in rows:
                name = str(row["ad"] or "").strip()[:160]
                if not name:
                    continue
                category = str(row["kategori"] or "").strip()[:120]
                quantity = max(0, int(row["miktar"] or 0))
                critical = max(0, int(row["kritik_stok"] or 0))
                currency = str(row["para_birimi"] if "para_birimi" in cols else "TRY").upper()
                if currency not in {"TRY", "USD", "EUR"}:
                    currency = "TRY"
                try:
                    amount = Decimal(str(row["birim_fiyat"] or 0))
                    if not amount.is_finite() or amount < 0:
                        amount = Decimal(0)
                except InvalidOperation:
                    amount = Decimal(0)
                amount = min(amount, Decimal("999999999999.99"))
                price_minor = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                barcode = str(row["barkod"] if "barkod" in cols else "")[:120]
                cur = target.execute(
                    "INSERT INTO products(name,category,quantity,price_minor,currency,critical_stock,barcode) VALUES(?,?,?,?,?,?,?)",
                    (name, category, quantity, price_minor, currency, critical, barcode),
                )
                if quantity:
                    target.execute(
                        "INSERT INTO stock_movements(product_id,user_id,delta,quantity_before,quantity_after,reason) VALUES(?,?,?,?,?,?)",
                        (cur.lastrowid, None, quantity, 0, quantity, "Legacy import"),
                    )
                count += 1
            target.execute("COMMIT")
            click.echo(f"Imported {count} products. Users and images were not imported.")
        except Exception:
            try:
                db.get_db().execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            source.close()

    @app.cli.command("backup")
    @click.option("--output", required=True, type=click.Path(dir_okay=False, path_type=Path))
    def backup(output):
        """Create a consistent SQLite + managed-image ZIP backup."""
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        tmpdb = Path(app.instance_path) / f".backup-{secrets.token_hex(8)}.sqlite3"
        source = sqlite3.connect(app.config["DATABASE"])
        dest = sqlite3.connect(tmpdb)
        try:
            source.backup(dest)
        finally:
            dest.close()
            source.close()
        check = sqlite3.connect(tmpdb)
        try:
            image_rows = check.execute(
                "SELECT DISTINCT image_name FROM products WHERE image_name<>''"
            ).fetchall()
        finally:
            check.close()
        image_names = {Path(r[0]).name for r in image_rows}
        manifest = {"format": 1, "application": "abeer-inventory", "images": sorted(image_names)}
        try:
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
                z.write(tmpdb, "abeer.sqlite3")
                z.writestr("manifest.json", json.dumps(manifest, indent=2))
                folder = Path(app.config["UPLOAD_FOLDER"])
                for name in sorted(image_names):
                    path = folder / name
                    if path.is_file():
                        z.write(path, f"uploads/{name}")
            click.echo(str(output))
        finally:
            tmpdb.unlink(missing_ok=True)
