import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(username) BETWEEN 3 AND 64),
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer' CHECK(role IN ('admin','editor','viewer')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
    session_version INTEGER NOT NULL DEFAULT 1 CHECK(session_version >= 1),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 160),
    category TEXT NOT NULL DEFAULT '' CHECK(length(category) <= 120),
    quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity BETWEEN 0 AND 2000000000),
    price_minor INTEGER NOT NULL DEFAULT 0 CHECK(price_minor BETWEEN 0 AND 99999999999999),
    currency TEXT NOT NULL DEFAULT 'TRY' CHECK(currency IN ('TRY','USD','EUR')),
    critical_stock INTEGER NOT NULL DEFAULT 5 CHECK(critical_stock BETWEEN 0 AND 2000000000),
    barcode TEXT NOT NULL DEFAULT '' CHECK(length(barcode) <= 120),
    image_name TEXT NOT NULL DEFAULT '' CHECK(length(image_name) <= 180),
    is_archived INTEGER NOT NULL DEFAULT 0 CHECK(is_archived IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_products_active_name ON products(is_archived, name);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    delta INTEGER NOT NULL,
    quantity_before INTEGER NOT NULL CHECK(quantity_before >= 0),
    quantity_after INTEGER NOT NULL CHECK(quantity_after >= 0),
    reason TEXT NOT NULL DEFAULT '' CHECK(length(reason) <= 250),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_movements_product_id ON stock_movements(product_id, id DESC);

CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL COLLATE NOCASE,
    ip_address TEXT NOT NULL,
    attempted_at INTEGER NOT NULL,
    success INTEGER NOT NULL DEFAULT 0 CHECK(success IN (0,1))
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_lookup
ON login_attempts(username, ip_address, attempted_at DESC);
"""


def get_db():
    if "db" not in g:
        path = Path(current_app.config["DATABASE"])
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=5000")
        g.db = db
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
