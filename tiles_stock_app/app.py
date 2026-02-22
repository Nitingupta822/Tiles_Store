from flask import (
    Flask, render_template, request, redirect,
    session, flash, make_response, url_for
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import func
from functools import wraps
import io
import os

# ================= APP SETUP =================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-key')

# ================= DATABASE CONFIG =================
database_url = os.environ.get('DATABASE_URL')

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or "sqlite:///database.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ================= MODELS =================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(150))
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Tile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(100), nullable=False)
    size = db.Column(db.String(50), nullable=False)
    buy_price = db.Column(db.Float)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)


class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(150))
    customer_mobile = db.Column(db.String(15))
    total = db.Column(db.Float, nullable=False)
    gst = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    date = db.Column(db.DateTime, default=datetime.utcnow)


class BillItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bill.id'))
    tile_name = db.Column(db.String(150))
    size = db.Column(db.String(50))
    price = db.Column(db.Float)
    quantity = db.Column(db.Integer)
    total = db.Column(db.Float)


# ================= DATABASE INIT =================
def init_db():
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            email="admin@example.com",
            password=generate_password_hash("admin123"),
            role="admin",
            is_active=True
        )
        db.session.add(admin)
        db.session.commit()


with app.app_context():
    init_db()

# ================= DECORATORS =================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please login first")
            return redirect('/')
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/')
        if session.get('role') != "admin":
            flash("Admin access required")
            return redirect('/dashboard')
        return f(*args, **kwargs)
    return wrapper


# ================= AUTH =================
@app.route("/", methods=["GET", "POST"])
def login():
    if 'user_id' in session:
        return redirect('/dashboard')

    if request.method == "POST":
        user = User.query.filter_by(username=request.form['username']).first()

        if user and check_password_hash(user.password, request.form['password']):
            if not user.is_active:
                flash("Account deactivated")
                return render_template("login.html")

            session['user_id'] = user.id
            session['role'] = user.role
            session['user'] = user.username
            return redirect('/dashboard')

        flash("Invalid credentials")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ================= DASHBOARD =================
@app.route("/dashboard")
@login_required
def dashboard():
    tiles = Tile.query.all()
    return render_template("dashboard.html", tiles=tiles)


# ================= TILE CRUD =================
@app.route("/add_tile", methods=["GET", "POST"])
@admin_required
def add_tile():
    if request.method == "POST":
        tile = Tile(
            brand=request.form['brand'],
            size=request.form['size'],
            buy_price=float(request.form.get('buy_price') or 0),
            price=float(request.form['price']),
            quantity=int(request.form['quantity'])
        )
        db.session.add(tile)
        db.session.commit()
        flash("Tile added successfully")
        return redirect("/dashboard")

    return render_template("add_tile.html")


@app.route("/edit_tile/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_tile(id):
    tile = Tile.query.get_or_404(id)
    if request.method == "POST":
        tile.brand = request.form['brand']
        tile.size = request.form['size']
        tile.buy_price = float(request.form.get('buy_price') or 0)
        tile.price = float(request.form['price'])
        tile.quantity = int(request.form['quantity'])
        db.session.commit()
        flash("Tile updated successfully")
        return redirect("/dashboard")
    return render_template("edit_tile.html", tile=tile)


@app.route("/delete_tile/<int:id>")
@admin_required
def delete_tile(id):
    tile = Tile.query.get_or_404(id)
    db.session.delete(tile)
    db.session.commit()
    flash("Tile deleted successfully")
    return redirect("/dashboard")


@app.route("/stock_availability_pdf")
@admin_required
def stock_availability_pdf():
    from xhtml2pdf import pisa
    tiles = Tile.query.all()
    html = render_template("stock_availability_pdf.html", tiles=tiles)
    result = io.BytesIO()
    pisa.CreatePDF(html, dest=result)
    response = make_response(result.getvalue())
    response.headers['Content-Type'] = "application/pdf"
    response.headers['Content-Disposition'] = "attachment; filename=stock_availability.pdf"
    return response


# ================= USER MANAGEMENT =================
@app.route("/user_management")
@admin_required
def user_management():
    users = User.query.all()
    return render_template("user_management.html", users=users)


@app.route("/create_user", methods=["GET", "POST"])
@admin_required
def create_user():
    if request.method == "POST":
        username = request.form['username']
        email = request.form.get('email')
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']

        if password != confirm_password:
            flash("Passwords do not match")
            return render_template("add_user.html")
        
        if User.query.filter_by(username=username).first():
            flash("Username already exists")
            return render_template("add_user.html")

        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            role=role,
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        flash("User created successfully")
        return redirect(url_for("user_management"))

    return render_template("add_user.html")


@app.route("/edit_user/<int:user_id>", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        user.email = request.form.get('email')
        user.role = request.form['role']
        new_password = request.form.get('new_password')
        if new_password:
            user.password = generate_password_hash(new_password)
        db.session.commit()
        flash("User updated successfully")
        return redirect(url_for("user_management"))
    return render_template("edit_user.html", user=user)


@app.route("/toggle_user_status/<int:user_id>", methods=["POST"])
@admin_required
def toggle_user_status(user_id):
    if user_id == session.get('user_id'):
        flash("Cannot deactivate yourself")
        return redirect(url_for("user_management"))
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    flash(f"User {'activated' if user.is_active else 'deactivated'} successfully")
    return redirect(url_for("user_management"))


@app.route("/delete_user/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    if user_id == session.get('user_id'):
        flash("Cannot delete yourself")
        return redirect(url_for("user_management"))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted successfully")
    return redirect(url_for("user_management"))


# ================= BILLING =================
@app.route("/billing", methods=["GET", "POST"])
@login_required
def billing():
    tiles = Tile.query.all()

    if request.method == "POST":
        bill = Bill(
            customer_name=request.form.get("customer_name"),
            customer_mobile=request.form.get("customer_mobile"),
            total=0,
            gst=float(request.form.get("gst", 0)),
            discount=float(request.form.get("discount", 0))
        )
        db.session.add(bill)
        db.session.commit()

        subtotal = 0

        for tile in tiles:
            qty = int(request.form.get(f"qty_{tile.id}", 0))
            if qty > 0 and tile.quantity >= qty:
                tile.quantity -= qty
                item_total = tile.price * qty
                subtotal += item_total

                item = BillItem(
                    bill_id=bill.id,
                    tile_name=tile.brand,
                    size=tile.size,
                    price=tile.price,
                    quantity=qty,
                    total=item_total
                )
                db.session.add(item)

        bill.total = subtotal + (subtotal * bill.gst / 100) - bill.discount
        db.session.commit()

        return redirect(url_for("invoice", bill_id=bill.id))

    return render_template("billing.html", tiles=tiles)


# ================= SALES HISTORY =================
@app.route("/sales_history")
@login_required
def sales_history():
    bills = Bill.query.order_by(Bill.date.desc()).all()
    return render_template("history.html", bills=bills)


# ================= SALES REPORT =================
@app.route("/sales_report")
@admin_required
def sales_report():
    total_sales = db.session.query(func.sum(Bill.total)).scalar() or 0
    total_bills = Bill.query.count()

    return render_template(
        "sales_report.html",
        total_sales=total_sales,
        total_bills=total_bills
    )
   
# ================= INVOICE =================
@app.route("/invoice/<int:bill_id>")
@login_required
def invoice(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    items = BillItem.query.filter_by(bill_id=bill_id).all()

    # Construct WhatsApp Message
    msg = f"Hello {bill.customer_name or 'Customer'},\n\n"
    msg += f"Thank you for shopping with TileStock! 🛒\n\n"
    msg += f"Your Invoice #{bill.id} details:\n"
    msg += f"📅 Date: {bill.date.strftime('%d %b %Y') if bill.date else 'N/A'}\n"
    msg += f"💰 Grand Total: ₹{bill.total:.2f}\n\n"
    msg += "Please find your digital receipt attached or visit our store for more details.\n\n"
    msg += "Regards,\nTileStock"

    return render_template("invoice.html", bill=bill, items=items, whatsapp_message=msg)


@app.route("/invoice_pdf/<int:bill_id>")
@login_required
def invoice_pdf(bill_id):
    from xhtml2pdf import pisa

    bill = Bill.query.get_or_404(bill_id)
    items = BillItem.query.filter_by(bill_id=bill_id).all()

    html = render_template("invoice_pdf.html", bill=bill, items=items)

    result = io.BytesIO()
    pisa.CreatePDF(html, dest=result)

    response = make_response(result.getvalue())
    response.headers['Content-Type'] = "application/pdf"
    response.headers['Content-Disposition'] = f"attachment; filename=invoice_{bill.id}.pdf"
    return response


# ================= HEALTH CHECK =================
@app.route("/health")
def health():
    return "App is running successfully!"


# ================= LOCAL RUN =================
if __name__ == "__main__":
    app.run(debug=True)
