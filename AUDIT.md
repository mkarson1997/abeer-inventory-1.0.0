# فحص وإعادة بناء المشروع الأصلي

التاريخ: 2026-08-20

## الخلاصة

الأرشيف الأصلي كان Prototype محلياً مفيداً، لكنه غير مناسب للنشر العام أو التحويل إلى Open Source كما هو. النسخة الحالية `Abeer Inventory 1.0.0` أعيدت بناؤها لمعالجة مشاكل الأمان، صحة البيانات، قابلية الصيانة، والتغليف.

## المشاكل الحرجة في الأصل

1. `Flask secret_key` ثابت ومكتوب داخل `app.py`.
2. بيانات مدير افتراضية `admin/admin123` ومعلومات اعتماد ضمن الملفات/الواجهة.
3. لا يوجد Authorization حقيقي بين المستخدمين.
4. التسجيل العام مفتوح مع سياسة كلمة مرور ضعيفة.
5. الأرشيف يحتوي `stok.db` تشغيلية فيها حسابات مستخدمين وبيانات فعلية.
6. الأرشيف يحتوي بيئتي Python افتراضيتين كاملتين (`venv` و`.venv`).

## مشاكل عالية الأهمية

- لا توجد CSRF protection.
- لا توجد حماية من brute-force لتسجيل الدخول.
- التحقق من الصور يعتمد على امتداد الملف فقط.
- لا يوجد حد عملي آمن لحجم/أبعاد الصور.
- الباركود كان ينشئ ملفات دائمة بلا تنظيف.
- Excel قابل لـ Formula Injection.
- عمليات تغيّر الحالة كانت تستخدم GET في بعض الأماكن.
- لا يوجد سجل لحركات المخزون.
- لا يوجد نظام Roles.

## مشاكل صحة البيانات

- جمع TRY وUSD وEUR في إجمالي مالي واحد.
- تخزين السعر باستخدام floating point.
- لا توجد DB constraints تمنع المخزون السالب أو العملات غير الصحيحة.
- أخطاء parsing يمكن أن تتحول إلى HTTP 500.
- حذف المنتج يمحو القدرة على تتبع تاريخه.

## ما تم إصلاحه في Abeer Inventory

- Application Factory وتقسيم المصادقة والإدارة والمخزون والأمان وقاعدة البيانات.
- أدوار `admin/editor/viewer`.
- التسجيل مغلق افتراضياً ولا يوجد أي Admin افتراضي.
- CSRF، Security Headers، CSP، Secure Session configuration.
- Login throttling وسجل محاولات محدود الحجم.
- Password policy وحدود لطول المدخلات.
- Session versioning لإبطال الجلسات السابقة عند تغييرات الحساب.
- SQLite Foreign Keys + WAL + Constraints.
- أسعار كـ integer minor units.
- حساب إجمالي مستقل لكل عملة.
- Stock movement audit log.
- تعديلات كمية داخل `BEGIN IMMEDIATE` لمنع lost updates المحلية.
- Soft archive بدلاً من الحذف المباشر.
- فحص الصور بواسطة Pillow وإعادة ترميزها وإزالة metadata وحماية decompression bombs.
- Barcode Code128 SVG بالذاكرة باستخدام ReportLab.
- Excel formula neutralization.
- PDF export.
- CLI: `create-admin`, `import-legacy`, `backup`, `check-db`.
- Docker، GitHub CI، README، SECURITY، CONTRIBUTING، Code of Conduct، MIT License.

## التحقق المنفذ

- Python compile check: ناجح.
- 19 اختباراً آلياً: ناجحة 19/19.
- إعادة الاختبارات مع `ResourceWarning` كخطأ: ناجحة.
- اختبار أداة النقل على `stok.db` الأصلية: استيراد 4/4 منتجات، 0 مستخدم قديم، `PRAGMA integrity_check = ok`.
- فحص أن النسخة العامة لا تتضمن قاعدة البيانات القديمة أو credentials أو `venv` يتم كـ Release Gate قبل إنشاء ZIP.

## ملاحظة

اختبارات المصدر في بيئة التدقيق شُغّلت باستخدام Flask المتاح داخل الأرشيف القديم بسبب عدم توفر اتصال حزم خارجي في بيئة التنفيذ. ملف المشروع نفسه يطلب إصدار Flask الآمن المحدد في `pyproject.toml` عند التثبيت الطبيعي.
