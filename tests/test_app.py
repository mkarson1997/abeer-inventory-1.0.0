import io
import os
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image
from werkzeug.security import generate_password_hash

from abeer_inventory import create_app
from abeer_inventory.db import get_db


class AbeerInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret-key-that-is-long-enough-123456",
            "DATABASE": str(base / "test.sqlite3"),
            "UPLOAD_FOLDER": str(base / "uploads"),
            "ALLOW_REGISTRATION": False,
            "MAX_CONTENT_LENGTH": 2 * 1024 * 1024,
            "MAX_IMAGE_BYTES": 1024 * 1024,
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db = get_db()
            for username, role in [("admin", "admin"), ("editor", "editor"), ("viewer", "viewer")]:
                db.execute(
                    "INSERT INTO users(username,password_hash,role) VALUES(?,?,?)",
                    (username, generate_password_hash("StrongPass123!"), role),
                )

    def tearDown(self):
        self.tmp.cleanup()

    def _csrf(self):
        with self.client.session_transaction() as s:
            token = s.get("_csrf_token", "test-csrf-token")
            s["_csrf_token"] = token
            return token

    def login(self, username="admin", password="StrongPass123!"):
        token = self._csrf()
        return self.client.post("/auth/login", data={"username": username, "password": password, "csrf_token": token})

    def add_product(self, name="Laptop", quantity="5", price="19.99", currency="TRY", **extra):
        token = self._csrf()
        data = {
            "csrf_token": token, "name": name, "category": extra.get("category", "Tech"),
            "quantity": quantity, "price": price, "currency": currency,
            "critical_stock": extra.get("critical_stock", "2"), "barcode": extra.get("barcode", "ABC123"),
        }
        if "image" in extra:
            data["image"] = extra["image"]
        return self.client.post("/products/new", data=data, content_type="multipart/form-data")

    def test_health(self):
        r = self.client.get("/healthz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "ok")

    def test_csrf_blocks_state_change(self):
        r = self.client.post("/auth/login", data={"username": "admin", "password": "StrongPass123!"})
        self.assertEqual(r.status_code, 400)

    def test_login_and_logout(self):
        r = self.login()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 200)
        token = self._csrf()
        self.assertEqual(self.client.post("/auth/logout", data={"csrf_token": token}).status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_login_throttling(self):
        for _ in range(5):
            token = self._csrf()
            self.client.post("/auth/login", data={"username": "admin", "password": "wrong", "csrf_token": token})
        token = self._csrf()
        r = self.client.post("/auth/login", data={"username": "admin", "password": "wrong", "csrf_token": token})
        self.assertEqual(r.status_code, 429)

    def test_viewer_cannot_edit(self):
        self.login("viewer")
        self.assertEqual(self.client.get("/products/new").status_code, 403)

    def test_product_crud_and_currency(self):
        self.login()
        self.assertEqual(self.add_product(currency="USD").status_code, 302)
        with self.app.app_context():
            row = get_db().execute("SELECT * FROM products WHERE name='Laptop'").fetchone()
            self.assertEqual(row["price_minor"], 1999)
            self.assertEqual(row["currency"], "USD")
            self.assertEqual(row["quantity"], 5)
            movement = get_db().execute("SELECT * FROM stock_movements WHERE product_id=?", (row["id"],)).fetchone()
            self.assertEqual(movement["quantity_after"], 5)

    def test_negative_stock_is_rejected(self):
        self.login()
        self.add_product(quantity="2")
        with self.app.app_context():
            pid = get_db().execute("SELECT id FROM products WHERE name='Laptop'").fetchone()["id"]
        token = self._csrf()
        r = self.client.post(f"/products/{pid}/adjust", data={"csrf_token": token, "delta": "-3", "reason": "sale"})
        self.assertEqual(r.status_code, 400)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT quantity FROM products WHERE id=?", (pid,)).fetchone()[0], 2)

    def test_adjust_creates_audit_history(self):
        self.login("editor")
        self.add_product(quantity="2")
        with self.app.app_context():
            pid = get_db().execute("SELECT id FROM products WHERE name='Laptop'").fetchone()["id"]
        token = self._csrf()
        r = self.client.post(f"/products/{pid}/adjust", data={"csrf_token": token, "delta": "4", "reason": "purchase"})
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            rows = get_db().execute("SELECT * FROM stock_movements WHERE product_id=? ORDER BY id", (pid,)).fetchall()
            self.assertEqual([x["quantity_after"] for x in rows], [2, 6])
            self.assertEqual(rows[-1]["reason"], "purchase")

    def test_archive_preserves_product_and_movements(self):
        self.login()
        self.add_product(quantity="3")
        with self.app.app_context():
            pid = get_db().execute("SELECT id FROM products WHERE name='Laptop'").fetchone()["id"]
        token = self._csrf()
        self.client.post(f"/products/{pid}/archive", data={"csrf_token": token})
        with self.app.app_context():
            p = get_db().execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            self.assertEqual(p["is_archived"], 1)
            self.assertGreater(get_db().execute("SELECT COUNT(*) FROM stock_movements WHERE product_id=?", (pid,)).fetchone()[0], 0)

    def test_valid_image_is_reencoded(self):
        self.login()
        buf = io.BytesIO()
        Image.new("RGB", (32, 32), "red").save(buf, "PNG")
        buf.seek(0)
        r = self.add_product(image=(buf, "test.png"))
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            row = get_db().execute("SELECT image_name FROM products").fetchone()
            self.assertTrue(row["image_name"].endswith(".jpg"))
            self.assertTrue((Path(self.app.config["UPLOAD_FOLDER"]) / row["image_name"]).is_file())

    def test_fake_image_rejected(self):
        self.login()
        r = self.add_product(image=(io.BytesIO(b"not-an-image"), "x.jpg"))
        self.assertEqual(r.status_code, 400)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM products").fetchone()[0], 0)

    def test_excel_formula_injection_is_neutralized(self):
        self.login()
        self.add_product(name="=1+1")
        r = self.client.get("/export.xlsx")
        self.assertEqual(r.status_code, 200)
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(r.data), read_only=True, data_only=False)
        self.assertEqual(wb.active["A2"].value, "'=1+1")

    def test_barcode_svg(self):
        self.login()
        self.add_product(barcode="ABC123")
        with self.app.app_context():
            pid = get_db().execute("SELECT id FROM products").fetchone()[0]
        r = self.client.get(f"/products/{pid}/barcode.svg")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"<svg", r.data.lower())

    def test_pdf_export(self):
        self.login()
        self.add_product(name="كاميرا")
        r = self.client.get("/export.pdf")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"%PDF"))

    def test_last_admin_cannot_be_disabled(self):
        self.login()
        with self.app.app_context():
            aid = get_db().execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
        token = self._csrf()
        r = self.client.post(f"/admin/users/{aid}/update", data={"csrf_token": token, "role": "viewer"})
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            row = get_db().execute("SELECT role,is_active FROM users WHERE id=?", (aid,)).fetchone()
            self.assertEqual(row["role"], "admin")
            self.assertEqual(row["is_active"], 1)

    def test_password_change_keeps_current_session_and_invalidates_version(self):
        self.login()
        with self.app.app_context():
            before = get_db().execute("SELECT session_version FROM users WHERE username='admin'").fetchone()[0]
        token = self._csrf()
        r = self.client.post("/auth/password", data={
            "csrf_token": token, "current_password": "StrongPass123!", "new_password": "AnotherStrong123!"
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 200)
        with self.app.app_context():
            after = get_db().execute("SELECT session_version FROM users WHERE username='admin'").fetchone()[0]
            self.assertEqual(after, before + 1)

    def test_registration_is_disabled_by_default(self):
        self.assertEqual(self.client.get("/auth/register").status_code, 404)

    def test_legacy_import_products_only(self):
        legacy = Path(self.tmp.name) / "legacy.db"
        c = sqlite3.connect(legacy)
        c.execute("CREATE TABLE urunler(id INTEGER, ad TEXT, kategori TEXT, miktar INTEGER, birim_fiyat REAL, kritik_stok INTEGER, barkod TEXT, para_birimi TEXT)")
        c.execute("CREATE TABLE kullanicilar(id INTEGER, kullanici TEXT, sifre_hash TEXT)")
        c.execute("INSERT INTO urunler VALUES(1,'Saat','Elektronik',7,12.34,2,'38','USD')")
        c.execute("INSERT INTO kullanicilar VALUES(1,'legacy-user','hash')")
        c.commit(); c.close()
        runner = self.app.test_cli_runner()
        r = runner.invoke(args=["import-legacy", "--path", str(legacy)])
        self.assertEqual(r.exit_code, 0, r.output)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM products").fetchone()[0], 1)
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0], 3)
            p = get_db().execute("SELECT * FROM products").fetchone()
            self.assertEqual(p["price_minor"], 1234)
            self.assertEqual(p["currency"], "USD")

    def test_registration_enabled_creates_viewer(self):
        app2 = create_app({
            "TESTING": True,
            "SECRET_KEY": "z" * 64,
            "DATABASE": str(Path(self.tmp.name) / "register.sqlite3"),
            "UPLOAD_FOLDER": str(Path(self.tmp.name) / "register-uploads"),
            "ALLOW_REGISTRATION": True,
        })
        client = app2.test_client()
        with client.session_transaction() as sess:
            sess["_csrf_token"] = "reg-token"
        r = client.post("/auth/register", data={
            "csrf_token": "reg-token", "username": "new-user", "password": "StrongPass456!"
        })
        self.assertEqual(r.status_code, 302)
        with app2.app_context():
            row = get_db().execute("SELECT role FROM users WHERE username='new-user'").fetchone()
            self.assertEqual(row["role"], "viewer")

    def test_admin_can_create_editor(self):
        self.login()
        token = self._csrf()
        r = self.client.post("/admin/users/create", data={
            "csrf_token": token, "username": "staff-user", "password": "StrongPass789!", "role": "editor"
        })
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            row = get_db().execute("SELECT role FROM users WHERE username='staff-user'").fetchone()
            self.assertEqual(row["role"], "editor")

    def test_open_redirect_is_rejected(self):
        token = self._csrf()
        r = self.client.post("/auth/login", data={
            "csrf_token": token, "username": "admin", "password": "StrongPass123!", "next": "//evil.example/"
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/"))
        self.assertNotIn("evil.example", r.headers["Location"])

    def test_dashboard_keeps_currency_totals_separate(self):
        self.login()
        self.add_product(name="TL Item", quantity="2", price="10", currency="TRY")
        self.add_product(name="USD Item", quantity="3", price="5", currency="USD")
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"20.00", r.data)
        self.assertIn(b"15.00", r.data)
        self.assertIn(b"TRY", r.data)
        self.assertIn(b"USD", r.data)

    def test_backup_and_integrity_cli(self):
        self.login()
        self.add_product()
        output = Path(self.tmp.name) / "backup.zip"
        runner = self.app.test_cli_runner()
        check = runner.invoke(args=["check-db"])
        self.assertEqual(check.exit_code, 0, check.output)
        result = runner.invoke(args=["backup", "--output", str(output)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(output.is_file())
        with zipfile.ZipFile(output) as z:
            self.assertIn("abeer.sqlite3", z.namelist())
            self.assertIn("manifest.json", z.namelist())


if __name__ == "__main__":
    unittest.main()
