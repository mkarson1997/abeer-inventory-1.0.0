from io import BytesIO
from pathlib import Path

from flask import Blueprint, abort, flash, g, redirect, render_template, request, send_file, url_for

from .db import get_db
from .security import (
    ALLOWED_CURRENCIES,
    excel_safe,
    login_required,
    parse_delta,
    parse_nonnegative_int,
    price_to_minor,
    process_image,
    remove_image,
    roles_required,
)

bp = Blueprint("inventory", __name__)


def _product_form_data():
    name = (request.form.get("name") or "").strip()
    category = (request.form.get("category") or "").strip()
    barcode = (request.form.get("barcode") or "").strip()
    currency = request.form.get("currency") or "TRY"
    if not 1 <= len(name) <= 160:
        raise ValueError("Product name must be 1-160 characters")
    if len(category) > 120 or len(barcode) > 120:
        raise ValueError("Category or barcode is too long")
    if currency not in ALLOWED_CURRENCIES:
        raise ValueError("Invalid currency")
    return {
        "name": name,
        "category": category,
        "quantity": parse_nonnegative_int(request.form.get("quantity", 0), "Quantity"),
        "price_minor": price_to_minor(request.form.get("price", 0)),
        "currency": currency,
        "critical_stock": parse_nonnegative_int(request.form.get("critical_stock", 5), "Critical stock"),
        "barcode": barcode,
    }


@bp.get("/")
@login_required
def dashboard():
    db = get_db()
    stats = db.execute(
        "SELECT COUNT(*) products, COALESCE(SUM(CASE WHEN quantity<=critical_stock THEN 1 ELSE 0 END),0) low "
        "FROM products WHERE is_archived=0"
    ).fetchone()
    values = db.execute(
        "SELECT currency, COALESCE(SUM(quantity*price_minor),0) total_minor FROM products "
        "WHERE is_archived=0 GROUP BY currency ORDER BY currency"
    ).fetchall()
    recent = db.execute(
        "SELECT m.*, p.name product_name, u.username FROM stock_movements m "
        "JOIN products p ON p.id=m.product_id LEFT JOIN users u ON u.id=m.user_id "
        "ORDER BY m.id DESC LIMIT 8"
    ).fetchall()
    return render_template("dashboard.html", stats=stats, values=values, recent=recent)


@bp.get("/products")
@login_required
def products():
    q = (request.args.get("q") or "").strip()[:160]
    category = (request.args.get("category") or "").strip()[:120]
    archived = request.args.get("archived") == "1"
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    per_page = 25
    where = ["is_archived=?"]
    params = [1 if archived else 0]
    if q:
        where.append("(name LIKE ? ESCAPE '\\' OR category LIKE ? ESCAPE '\\' OR barcode LIKE ? ESCAPE '\\')")
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params += [f"%{escaped}%"] * 3
    if category:
        where.append("category=?")
        params.append(category)
    db = get_db()
    condition = " AND ".join(where)
    total = db.execute(f"SELECT COUNT(*) n FROM products WHERE {condition}", params).fetchone()["n"]
    rows = db.execute(
        f"SELECT * FROM products WHERE {condition} ORDER BY name COLLATE NOCASE LIMIT ? OFFSET ?",
        (*params, per_page, (page - 1) * per_page),
    ).fetchall()
    categories = db.execute(
        "SELECT DISTINCT category FROM products WHERE is_archived=0 AND category<>'' ORDER BY category"
    ).fetchall()
    pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        "products.html", products=rows, categories=categories, q=q, category=category,
        archived=archived, page=page, pages=pages,
    )


@bp.route("/products/new", methods=("GET", "POST"))
@roles_required("admin", "editor")
def product_new():
    if request.method == "POST":
        new_image = None
        try:
            data = _product_form_data()
            new_image = process_image(request.files.get("image"))
            db = get_db()
            db.execute("BEGIN IMMEDIATE")
            cur = db.execute(
                "INSERT INTO products(name,category,quantity,price_minor,currency,critical_stock,barcode,image_name) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (*data.values(), new_image or ""),
            )
            product_id = cur.lastrowid
            if data["quantity"]:
                db.execute(
                    "INSERT INTO stock_movements(product_id,user_id,delta,quantity_before,quantity_after,reason) "
                    "VALUES(?,?,?,?,?,?)",
                    (product_id, g.user["id"], data["quantity"], 0, data["quantity"], "Initial stock"),
                )
            db.execute("COMMIT")
            flash("Product created.", "success")
            return redirect(url_for("inventory.products"))
        except ValueError as exc:
            try:
                get_db().execute("ROLLBACK")
            except Exception:
                pass
            if new_image:
                remove_image(new_image)
            flash(str(exc), "danger")
            return render_template("product_form.html", product=None), 400
        except Exception:
            try:
                get_db().execute("ROLLBACK")
            except Exception:
                pass
            if new_image:
                remove_image(new_image)
            raise
    return render_template("product_form.html", product=None)


@bp.route("/products/<int:product_id>/edit", methods=("GET", "POST"))
@roles_required("admin", "editor")
def product_edit(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not product:
        abort(404)
    if request.method == "POST":
        new_image = None
        old_image = product["image_name"]
        try:
            data = _product_form_data()
            new_image = process_image(request.files.get("image"))
            image_name = new_image or old_image
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT quantity FROM products WHERE id=?", (product_id,)).fetchone()
            before = current["quantity"]
            db.execute(
                "UPDATE products SET name=?,category=?,quantity=?,price_minor=?,currency=?,critical_stock=?,"
                "barcode=?,image_name=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (*data.values(), image_name, product_id),
            )
            if data["quantity"] != before:
                db.execute(
                    "INSERT INTO stock_movements(product_id,user_id,delta,quantity_before,quantity_after,reason) "
                    "VALUES(?,?,?,?,?,?)",
                    (product_id, g.user["id"], data["quantity"] - before, before, data["quantity"], "Edit product"),
                )
            db.execute("COMMIT")
            if new_image and old_image:
                remove_image(old_image)
            flash("Product updated.", "success")
            return redirect(url_for("inventory.products"))
        except ValueError as exc:
            try:
                db.execute("ROLLBACK")
            except Exception:
                pass
            if new_image:
                remove_image(new_image)
            flash(str(exc), "danger")
            product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
            return render_template("product_form.html", product=product), 400
        except Exception:
            try:
                db.execute("ROLLBACK")
            except Exception:
                pass
            if new_image:
                remove_image(new_image)
            raise
    return render_template("product_form.html", product=product)


@bp.post("/products/<int:product_id>/archive")
@roles_required("admin", "editor")
def product_archive(product_id):
    db = get_db()
    cur = db.execute("UPDATE products SET is_archived=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (product_id,))
    if cur.rowcount == 0:
        abort(404)
    flash("Product archived.", "success")
    return redirect(url_for("inventory.products"))


@bp.post("/products/<int:product_id>/restore")
@roles_required("admin", "editor")
def product_restore(product_id):
    db = get_db()
    cur = db.execute("UPDATE products SET is_archived=0, updated_at=CURRENT_TIMESTAMP WHERE id=?", (product_id,))
    if cur.rowcount == 0:
        abort(404)
    flash("Product restored.", "success")
    return redirect(url_for("inventory.products", archived=1))


@bp.route("/products/<int:product_id>/adjust", methods=("GET", "POST"))
@roles_required("admin", "editor")
def adjust(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id=? AND is_archived=0", (product_id,)).fetchone()
    if not product:
        abort(404)
    if request.method == "POST":
        try:
            delta = parse_delta(request.form.get("delta"))
            reason = (request.form.get("reason") or "Manual adjustment").strip()[:250]
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT quantity FROM products WHERE id=? AND is_archived=0", (product_id,)).fetchone()
            before = current["quantity"]
            after = before + delta
            if after < 0:
                raise ValueError("Stock cannot become negative")
            db.execute("UPDATE products SET quantity=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (after, product_id))
            db.execute(
                "INSERT INTO stock_movements(product_id,user_id,delta,quantity_before,quantity_after,reason) "
                "VALUES(?,?,?,?,?,?)",
                (product_id, g.user["id"], delta, before, after, reason),
            )
            db.execute("COMMIT")
            flash("Stock adjusted.", "success")
            return redirect(url_for("inventory.products"))
        except ValueError as exc:
            try:
                db.execute("ROLLBACK")
            except Exception:
                pass
            flash(str(exc), "danger")
            return render_template("adjust.html", product=product), 400
        except Exception:
            try:
                db.execute("ROLLBACK")
            except Exception:
                pass
            raise
    return render_template("adjust.html", product=product)


@bp.get("/alerts")
@login_required
def alerts():
    rows = get_db().execute(
        "SELECT * FROM products WHERE is_archived=0 AND quantity<=critical_stock ORDER BY quantity, name"
    ).fetchall()
    return render_template("alerts.html", products=rows)


@bp.get("/movements")
@login_required
def movements():
    rows = get_db().execute(
        "SELECT m.*, p.name product_name, u.username FROM stock_movements m "
        "JOIN products p ON p.id=m.product_id LEFT JOIN users u ON u.id=m.user_id "
        "ORDER BY m.id DESC LIMIT 500"
    ).fetchall()
    return render_template("movements.html", movements=rows)


@bp.get("/uploads/<path:name>")
@login_required
def uploaded_image(name):
    from flask import current_app, send_from_directory
    safe_name = Path(name).name
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], safe_name, conditional=True)


@bp.get("/products/<int:product_id>/barcode.svg")
@login_required
def barcode_svg(product_id):
    product = get_db().execute("SELECT id,barcode FROM products WHERE id=?", (product_id,)).fetchone()
    if not product:
        abort(404)
    value = product["barcode"] or f"ABEER-{product_id:08d}"
    try:
        from reportlab.graphics import renderSVG
        from reportlab.graphics.barcode import createBarcodeDrawing
        drawing = createBarcodeDrawing(
            "Code128", value=value, barHeight=44, humanReadable=True, quiet=True
        )
        payload = renderSVG.drawToString(drawing).encode("utf-8")
        out = BytesIO(payload)
        return send_file(out, mimetype="image/svg+xml", download_name=f"barcode-{product_id}.svg")
    except Exception:
        abort(503, "Barcode generator unavailable")


@bp.get("/export.xlsx")
@login_required
def export_excel():
    from openpyxl import Workbook
    db = get_db()
    rows = db.execute("SELECT * FROM products WHERE is_archived=0 ORDER BY name").fetchall()
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventory"
    ws.append(["Name", "Category", "Quantity", "Price", "Currency", "Critical", "Barcode"])
    for row in rows:
        ws.append([
            excel_safe(row["name"]), excel_safe(row["category"]), row["quantity"], row["price_minor"] / 100,
            row["currency"], row["critical_stock"], excel_safe(row["barcode"]),
        ])
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return send_file(out, as_attachment=True, download_name="abeer-inventory.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.get("/export.pdf")
@login_required
def export_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from flask import current_app
    rows = get_db().execute("SELECT * FROM products WHERE is_archived=0 ORDER BY name").fetchall()
    out = BytesIO()
    font = "Helvetica"
    for candidate in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        if Path(candidate).exists():
            try:
                pdfmetrics.registerFont(TTFont("AbeerUnicode", candidate))
                font = "AbeerUnicode"
                break
            except Exception:
                pass
    def shape(text):
        text = str(text)
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            return text
    doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=24, leftMargin=24, topMargin=28, bottomMargin=28)
    styles = getSampleStyleSheet()
    styles["Title"].fontName = font
    story = [Paragraph(shape("Abeer Inventory / عبير لإدارة المخزون"), styles["Title"]), Spacer(1, 12)]
    data = [[shape(x) for x in ["Product", "Category", "Qty", "Price", "Currency"]]]
    for r in rows:
        data.append([shape(r["name"]), shape(r["category"]), str(r["quantity"]), f"{r['price_minor']/100:.2f}", r["currency"]])
    table = Table(data, repeatRows=1, colWidths=[155, 115, 55, 75, 60])
    table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), font), ("FONTSIZE", (0,0), (-1,-1), 8),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), 0.3, colors.grey),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(table)
    doc.build(story)
    out.seek(0)
    return send_file(out, as_attachment=True, download_name="abeer-inventory.pdf", mimetype="application/pdf")
