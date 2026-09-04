# Abeer Inventory

[![CI](https://github.com/mkarson1997/abeer-inventory-1.0.0/actions/workflows/ci.yml/badge.svg)](https://github.com/mkarson1997/abeer-inventory-1.0.0/actions/workflows/ci.yml)

A security-focused, multilingual inventory-management application for small businesses and teams.

Abeer Inventory is designed as more than CRUD. The project demonstrates authentication hardening, role-based access control, auditability, safe file handling, backup/restore workflows, multilingual UI, Docker delivery and automated validation.

**Languages:** Arabic RTL, Turkish and English.

## Why this repository stands out

The project intentionally addresses common production risks that small internal tools often ignore:

- role separation,
- CSRF protection,
- login throttling,
- session invalidation,
- safe image processing,
- database integrity,
- spreadsheet formula injection,
- mixed-currency accounting mistakes,
- secret management,
- backup consistency,
- migration of legacy data without exposing old credentials.

## Engineering highlights

### Authentication and authorization

- Roles: `admin`, `editor`, `viewer`
- Public registration disabled by default
- No default administrator password
- CSRF protection on state-changing operations
- Temporary lockout after repeated failed sign-in attempts
- Existing sessions invalidated after password or account-state changes
- Administrative user and permission management

### Security hardening

- Security headers and Content Security Policy
- No JavaScript or CSS CDN dependency in the protected application surface
- Production startup refuses weak or missing session secrets
- Secure-cookie mode for HTTPS deployments
- Trusted-host configuration
- Controlled image upload size and content validation
- Uploaded images are re-encoded as JPEG and metadata is removed
- Runtime data and secrets are excluded from version control

### Data integrity

- SQLite foreign keys enabled
- WAL mode
- database constraints for invalid values
- monetary values stored as integer minor units rather than floating-point numbers
- inventory value kept separate per currency instead of incorrectly summing TRY, USD and EUR
- negative-stock protection
- archived products preserve historical records
- complete quantity-change history with actor information

### Export and operational tooling

- Excel export protected against Formula Injection
- Unicode/PDF support, including Arabic when appropriate fonts are available
- Code128 SVG barcode generation in memory
- consistent database backup command
- database integrity check command
- legacy-product migration tool
- `/healthz` endpoint
- Docker and Docker Compose
- GitHub CI
- automated tests

## Architecture

```text
Browser
  │
  ▼
Flask application
  ├── auth          authentication / sessions
  ├── admin         users / roles / account management
  ├── inventory     products / stock / exports
  ├── security      CSRF / headers / security helpers
  ├── i18n          Arabic / Turkish / English
  └── db            SQLite access / constraints / integrity
          │
          ▼
      SQLite
          │
          ├── product and stock state
          ├── users and roles
          └── inventory movement history
```

## Repository structure

```text
abeer_inventory/
├── __init__.py
├── db.py
├── security.py
├── auth.py
├── admin.py
├── inventory.py
├── i18n.py
├── templates/
└── static/

tests/
.github/workflows/ci.yml
Dockerfile
docker-compose.yml
setup_windows.ps1
start_windows.ps1
SECURITY.md
CONTRIBUTING.md
AUDIT.md
LICENSE
```

## Quick start on Windows

Requires Python 3.11 or 3.12.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

The setup flow asks you to create the first administrator account.

Then:

```powershell
.\start_windows.ps1
```

Open:

```text
http://127.0.0.1:5000
```

## Manual local setup

```bash
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install and create the initial administrator:

```bash
pip install -e .
flask --app wsgi create-admin
flask --app wsgi run
```

## Docker

```bash
cp .env.example .env
# Set a strong ABEER_SECRET_KEY in .env

docker compose up -d --build
docker compose exec web flask --app wsgi create-admin
```

Default container endpoint:

```text
http://localhost:8000
```

## Production configuration

Generate a strong secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Example environment:

```env
ABEER_ENV=production
ABEER_SECRET_KEY=<strong-secret>
ABEER_COOKIE_SECURE=1
ABEER_TRUSTED_HOSTS=inventory.example.com
ABEER_ALLOW_REGISTRATION=0
ABEER_MAX_UPLOAD_MB=5
```

In production mode the application refuses to start when the session key is absent or too weak.

`ABEER_COOKIE_SECURE=1` requires HTTPS.

## Permission matrix

| Role | View | Export | Change stock | Manage users |
|---|---:|---:|---:|---:|
| `viewer` | ✅ | ✅ | ❌ | ❌ |
| `editor` | ✅ | ✅ | ✅ | ❌ |
| `admin` | ✅ | ✅ | ✅ | ✅ |

When optional public registration is enabled, new users enter as `viewer` only.

## Testing and quality

Install development dependencies and run:

```bash
pip install -e '.[dev]'
pytest
ruff check .
```

The test suite covers areas including:

- authentication,
- CSRF,
- role enforcement,
- login throttling,
- CRUD behavior,
- stock movement,
- negative-stock prevention,
- image handling,
- Excel and PDF paths,
- barcode generation,
- user management,
- password changes,
- legacy import,
- backup,
- SQLite integrity.

## Legacy migration

Do **not** publish an old production database.

The migration tool imports products only and intentionally excludes legacy users, password hashes and old images:

```powershell
flask --app wsgi import-legacy --path "C:\path\to\stok.db"
```

## Backup and integrity checks

```bash
flask --app wsgi backup --output "backups/abeer-backup.zip"
flask --app wsgi check-db
```

Backups contain a consistent SQLite snapshot, linked product images and a manifest. `.env` and the session secret are excluded.

## Repository hygiene

Never commit runtime or customer data such as:

```text
instance/
*.db
*.sqlite3
.env
customer images
.venv/
venv/
real backups
```

## Security

See [SECURITY.md](SECURITY.md) and [AUDIT.md](AUDIT.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT License.

## العربية

**عبير لإدارة المخزون** هو تطبيق مفتوح المصدر لإدارة المخزون بواجهة عربية RTL مع التركية والإنجليزية. يركز المشروع على الصلاحيات، حماية تسجيل الدخول والجلسات، سجل حركة المخزون، التصدير الآمن، النسخ الاحتياطي، Docker والاختبارات الآلية.

---

Built and maintained by [Mahmoud Karzoun](https://github.com/mkarson1997).