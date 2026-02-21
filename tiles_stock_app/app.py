from flask import (
    Flask, render_template, request, redirect,
    session, flash, url_for
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import os

# ================= APP SETUP =================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# ================= DATABASE CONFIG =================
database_url = os.environ.get('DATABASE_URL')

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///database.db'
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
    gst = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)


# ================= DATABASE AUTO CREATE =================
with app.app_context():
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        admin = User(
            username='admin',
            email='admin@example.com',
            password=generate_password_hash('admin123'),
            role='admin',
            is_active=True
        )
        db.session.add(admin)
        db.session.commit()

# ================= DECORATORS =================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please login first")
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/')
        if session.get('role') != 'admin':
            flash("Admin access required")
            return redirect('/dashboard')
        return f(*args, **kwargs)
    return decorated_function

# ================= ROUTE CHECK =================
@app.route('/routes')
def routes():
    return "<br>".join([str(rule) for rule in app.url_map.iter_rules()])


# ================= LOGIN =================
@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect('/dashboard')

    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()

        if user and check_password_hash(user.password, request.form['password']):
            if not user.is_active:
                flash("Account deactivated")
                return render_template('login.html')

            session['user_id'] = user.id
            session['role'] = user.role
            session['username'] = user.username
            return redirect('/dashboard')

        flash("Invalid credentials")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ================= DASHBOARD =================
@app.route('/dashboard')
@login_required
def dashboard():
    tiles = Tile.query.all()
    return render_template('dashboard.html', tiles=tiles)


# ================= ADD TILE =================
@app.route('/add_tile', methods=['GET', 'POST'])
@admin_required
def add_tile():
    if request.method == 'POST':
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
        return redirect('/dashboard')

    return render_template('add_tile.html')


# ================= ADMIN - USERS =================
@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)


# ================= ADMIN - ADD USER =================
@app.route('/admin/add_user', methods=['GET', 'POST'])
@admin_required
def add_user():
    if request.method == 'POST':
        new_user = User(
            username=request.form['username'],
            email=request.form['email'],
            password=generate_password_hash(request.form['password']),
            role=request.form['role'],
            is_active=True
        )
        db.session.add(new_user)
        db.session.commit()
        flash("User created successfully")
        return redirect('/admin/users')

    return render_template('add_user.html')


# ================= ADMIN - TOGGLE USER =================
@app.route('/admin/toggle_user/<int:user_id>')
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.username == "admin":
        flash("Cannot deactivate main admin")
        return redirect('/admin/users')

    user.is_active = not user.is_active
    db.session.commit()
    flash("User status updated")
    return redirect('/admin/users')


# ================= ADMIN - DELETE USER =================
@app.route('/admin/delete_user/<int:user_id>')
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.username == "admin":
        flash("Cannot delete main admin")
        return redirect('/admin/users')

    db.session.delete(user)
    db.session.commit()
    flash("User deleted successfully")
    return redirect('/admin/users')


# ================= HISTORY =================
@app.route('/history')
@login_required
def history():
    bills = Bill.query.order_by(Bill.date.desc()).all()
    return render_template('history.html', bills=bills)


# ================= RUN LOCAL =================
if __name__ == '__main__':
    app.run(debug=True)
