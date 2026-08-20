import hmac
import ipaddress
import secrets
import warnings
from functools import wraps
from io import BytesIO
from pathlib import Path

from flask import abort, current_app, flash, g, redirect, request, session, url_for
from PIL import Image, UnidentifiedImageError

ALLOWED_ROLES = {"admin", "editor", "viewer"}
ALLOWED_CURRENCIES = {"TRY", "USD", "EUR"}
Image.MAX_IMAGE_PIXELS = 20_000_000


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def validate_csrf():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    expected = session.get("_csrf_token", "")
    provided = request.form.get("csrf_token", "") or request.headers.get("X-CSRF-Token", "")
    if not expected or not provided or not hmac.compare_digest(expected, provided):
        abort(400, "Invalid CSRF token")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def deco(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return deco


def safe_next_url(value):
    if not value or not value.startswith("/") or value.startswith("//"):
        return None
    return value


def request_ip():
    # Do not trust X-Forwarded-For by default. Configure a trusted reverse proxy externally.
    raw = request.remote_addr or "0.0.0.0"
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return "0.0.0.0"


def process_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    raw = file_storage.read(current_app.config["MAX_IMAGE_BYTES"] + 1)
    if len(raw) > current_app.config["MAX_IMAGE_BYTES"]:
        raise ValueError("Image is too large")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as img:
                img.verify()
            with Image.open(BytesIO(raw)) as img:
                img = img.convert("RGB")
                img.thumbnail((1600, 1600))
                output = BytesIO()
                img.save(output, format="JPEG", quality=88, optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Invalid image") from exc
    name = f"{secrets.token_hex(16)}.jpg"
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(output.getvalue())
    return name


def remove_image(name):
    if not name:
        return
    path = Path(current_app.config["UPLOAD_FOLDER"]) / Path(name).name
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def validate_username(value):
    value = (value or "").strip()
    if not 3 <= len(value) <= 64:
        raise ValueError("Username must be 3-64 characters")
    if any(ord(ch) < 32 for ch in value):
        raise ValueError("Invalid username")
    return value


def validate_password(value):
    if not isinstance(value, str) or not 10 <= len(value) <= 256:
        raise ValueError("Password must be 10-256 characters")
    return value


def parse_nonnegative_int(value, label, maximum=2_000_000_000):
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if parsed < 0 or parsed > maximum:
        raise ValueError(f"{label} is outside the allowed range")
    return parsed


def parse_delta(value):
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("Change must be an integer") from exc
    if parsed == 0 or abs(parsed) > 2_000_000_000:
        raise ValueError("Change must be non-zero and within range")
    return parsed


def price_to_minor(value):
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid price") from exc
    if not amount.is_finite() or amount < 0 or amount > Decimal("999999999999.99"):
        raise ValueError("Price is outside the allowed range")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def excel_safe(value):
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def install_security(app):
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.before_request(validate_csrf)

    @app.after_request
    def headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; "
            "script-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; "
            "frame-ancestors 'none'; form-action 'self'",
        )
        if current_app.config.get("ENVIRONMENT") == "production" and request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
