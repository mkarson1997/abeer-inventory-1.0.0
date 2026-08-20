# عبير لإدارة المخزون · Abeer Inventory

تطبيق مفتوح المصدر وخفيف لإدارة مخزون المتاجر والفرق الصغيرة، بواجهة عربية RTL مع التركية والإنجليزية.

هذه النسخة إعادة بناء آمنة للمشروع القديم `stok takibi4`. لا تحتوي قاعدة البيانات القديمة، حسابات المستخدمين، كلمات المرور، الصور التشغيلية، أو مجلدات `venv` التي كانت موجودة في الأرشيف الأصلي.

## المزايا

- أدوار `admin` و`editor` و`viewer`.
- التسجيل العام مغلق افتراضياً، ولا توجد كلمة مرور مدير افتراضية.
- حماية CSRF لكل العمليات التي تعدّل البيانات.
- قفل مؤقت بعد محاولات دخول فاشلة متكررة.
- إبطال الجلسات السابقة عند تغيير كلمة المرور أو صلاحية الحساب.
- Security Headers وCSP بدون JavaScript أو CSS من CDN.
- SQLite مع Foreign Keys وWAL وقيود تمنع القيم غير المنطقية.
- الأسعار محفوظة كـ integer minor units بدل `float`.
- قيمة المخزون تحسب لكل عملة بشكل مستقل، فلا يتم جمع TRY وUSD وEUR في رقم واحد.
- رفع الصور محدود الحجم مع فحص فعلي وإعادة ترميز JPEG وإزالة metadata.
- باركود Code128 SVG يولّد في الذاكرة، بدون تراكم ملفات على القرص.
- سجل كامل لحركة الكمية ومن قام بها.
- أرشفة المنتجات بدلاً من حذف تاريخها.
- Excel محمي من Formula Injection.
- PDF يدعم Unicode والعربية عند توفر الخطوط المناسبة.
- إدارة مستخدمين وصلاحيات من لوحة المدير.
- بحث، تصفية، pagination، تنبيهات مخزون، ثيم فاتح/داكن.
- `/healthz`، Docker، GitHub CI، اختبارات، Backup، وأداة نقل للقاعدة القديمة.

## تشغيل سريع على Windows

يتطلب Python 3.11 أو 3.12.

افتح PowerShell داخل مجلد المشروع:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

سيطلب منك إنشاء أول حساب مدير. بعدها:

```powershell
.\start_windows.ps1
```

ثم افتح:

```text
http://127.0.0.1:5000
```

## تشغيل يدوي

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
# Linux/macOS
# source .venv/bin/activate

pip install -e .
flask --app wsgi create-admin
flask --app wsgi run
```

في وضع التطوير، إذا لم تضبط `ABEER_SECRET_KEY` سيولد التطبيق مفتاح جلسة مؤقتاً عند كل تشغيل. هذا مناسب للتطوير المحلي فقط.

## إعداد الإنتاج

ولّد مفتاحاً عشوائياً قوياً:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

واضبط:

```env
ABEER_ENV=production
ABEER_SECRET_KEY=<64-hex-or-equivalent-strong-secret>
ABEER_COOKIE_SECURE=1
ABEER_TRUSTED_HOSTS=inventory.example.com
ABEER_ALLOW_REGISTRATION=0
ABEER_MAX_UPLOAD_MB=5
```

في `production` يرفض التطبيق الإقلاع إذا كان مفتاح الجلسة مفقوداً أو قصيراً.

> عند استخدام `ABEER_COOKIE_SECURE=1` يجب أن يدخل المستخدم عبر HTTPS.

## Docker

```bash
cp .env.example .env
# غيّر ABEER_SECRET_KEY داخل .env

docker compose up -d --build
docker compose exec web flask --app wsgi create-admin
```

التطبيق على `http://localhost:8000` افتراضياً. عند وضعه خلف HTTPS اضبط `ABEER_ENV=production` و`ABEER_COOKIE_SECURE=1`.

## الصلاحيات

| الدور | مشاهدة | تصدير | تعديل المخزون | إدارة المستخدمين |
|---|---:|---:|---:|---:|
| viewer | ✅ | ✅ | ❌ | ❌ |
| editor | ✅ | ✅ | ✅ | ❌ |
| admin | ✅ | ✅ | ✅ | ✅ |

إذا فعّلت `ABEER_ALLOW_REGISTRATION=1` فإن أي حساب جديد يدخل كـ `viewer` فقط.

## نقل بيانات النسخة القديمة

لا تنسخ `stok.db` القديم إلى GitHub العام. بعد تثبيت عبير شغّل:

```powershell
flask --app wsgi import-legacy --path "C:\path\to\stok.db"
```

الأداة تنقل **المنتجات فقط**. لا تنقل المستخدمين أو password hashes أو الصور القديمة عمداً.

تم اختبار الأداة على قاعدة المشروع الأصلية المرفقة، واستوردت 4/4 منتجات مع العملات والأسعار والكمية بنجاح.

## النسخ الاحتياطي

```bash
flask --app wsgi backup --output "backups/abeer-backup.zip"
flask --app wsgi check-db
```

النسخة الاحتياطية تحتوي قاعدة SQLite snapshot متسقة وصور المنتجات المرتبطة و`manifest.json`. لا تحتوي `.env` أو مفتاح الجلسة.

## الاختبارات

```bash
pip install -e '.[dev]'
pytest
ruff check .
```

مجموعة الاختبارات تغطي المصادقة، CSRF، الأدوار، login throttling، CRUD، حركة المخزون، منع المخزون السالب، الصور، Excel، PDF، الباركود، إدارة المستخدمين، تغيير كلمة المرور، استيراد النسخة القديمة، Backup، وفحص SQLite.

## هيكل المشروع

```text
abeer_inventory/
  __init__.py
  db.py
  security.py
  auth.py
  admin.py
  inventory.py
  i18n.py
  templates/
  static/
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

## بيانات التشغيل

كل البيانات الجديدة تحفظ داخل `instance/`، والمجلد مستثنى من Git. لا ترفع أبداً:

- `instance/`
- `*.db` / `*.sqlite3`
- `.env`
- صور العملاء
- `.venv` أو `venv`
- نسخ backup تحتوي بيانات حقيقية

## الترخيص

MIT License.
