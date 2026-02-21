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
app.secret_key = 'secret123'

# Database Configuration
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
    email = db.Column(db.String(150), nullable=True)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # admin / staff
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)


class Tile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(100), nullable=False)
    size = db.Column(db.String(50), nullable=False)
    buy_price = db.Column(db.Float, nullable=True)  # Cost price - admin only
    price = db.Column(db.Float, nullable=False)  # Selling price
    quantity = db.Column(db.Integer, nullable=False)


class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(150))
    customer_mobile = db.Column(db.String(15))
    total = db.Column(db.Float, nullable=False)
    gst = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)


class BillItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bill.id'))
    tile_name = db.Column(db.String(150))
    size = db.Column(db.String(50))
    price = db.Column(db.Float)
    quantity = db.Column(db.Integer)
    total = db.Column(db.Float)


# ================= DECORATORS =================
def login_required(f):
    """Decorator to require login for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page')
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin role for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page')
            return redirect('/')
        if session.get('role') != 'admin':
            flash('Access denied. Admin privileges required.')
            return redirect('/dashboard')
        return f(*args, **kwargs)
    return decorated_function


# ================= AUTH =================
@app.route('/', methods=['GET', 'POST'])
def login():
    # If already logged in, redirect to dashboard
    if 'user_id' in session:
        return redirect('/dashboard')
    
    if request.method == 'POST':
        user = User.query.filter_by(
            username=request.form['username']
        ).first()

        if user and check_password_hash(user.password, request.form['password']):
            # Check if user is active
            if not user.is_active:
                flash('Your account has been deactivated. Please contact admin.')
                return render_template('login.html')
            
            session['user_id'] = user.id
            session['user'] = user.username
            session['role'] = user.role
            flash(f'Welcome back, {user.username}!')
            return redirect('/dashboard')
        else:
            flash('Invalid username or password')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully')
    return redirect('/')


# ================= DASHBOARD =================
@app.route('/dashboard')
@login_required
def dashboard():
    search = request.args.get('search')
    if search:
        tiles = Tile.query.filter(
            (Tile.brand.ilike(f"%{search}%")) |
            (Tile.size.ilike(f"%{search}%"))
        ).all()
    else:
        tiles = Tile.query.all()

    return render_template('dashboard.html', tiles=tiles)


# ================= USER MANAGEMENT (Admin Only) =================
@app.route('/admin/users')
@admin_required
def user_management():
    """List all users for admin management"""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('user_management.html', users=users)


@app.route('/admin/users/create', methods=['GET', 'POST'])
@admin_required
def create_user():
    """Create a new user (admin only)"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip() or None
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'staff')
        
        # Validation
        if not username:
            flash('Username is required')
            return render_template('add_user.html')
        
        if len(username) < 3:
            flash('Username must be at least 3 characters')
            return render_template('add_user.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return render_template('add_user.html')
        
        if not password:
            flash('Password is required')
            return render_template('add_user.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters')
            return render_template('add_user.html')
        
        if password != confirm_password:
            flash('Passwords do not match')
            return render_template('add_user.html')
        
        if role not in ['admin', 'staff']:
            flash('Invalid role selected')
            return render_template('add_user.html')
        
        # Create user
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            role=role,
            is_active=True,
            created_by=session.get('user_id')
        )
        db.session.add(user)
        db.session.commit()
        
        flash(f'User "{username}" created successfully!')
        return redirect('/admin/users')
    
    return render_template('add_user.html')


@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Edit an existing user (admin only)"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip() or None
        role = request.form.get('role', 'staff')
        new_password = request.form.get('new_password', '').strip()
        
        # Validate role
        if role not in ['admin', 'staff']:
            flash('Invalid role selected')
            return render_template('edit_user.html', user=user)
        
        # Update email and role
        user.email = email
        user.role = role
        
        # Update password if provided
        if new_password:
            if len(new_password) < 6:
                flash('Password must be at least 6 characters')
                return render_template('edit_user.html', user=user)
            user.password = generate_password_hash(new_password)
        
        db.session.commit()
        flash(f'User "{user.username}" updated successfully!')
        return redirect('/admin/users')
    
    return render_template('edit_user.html', user=user)


@app.route('/admin/users/<int:user_id>/toggle-active', methods=['POST'])
@admin_required
def toggle_user_active(user_id):
    """Toggle user active status (admin only)"""
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deactivating themselves
    if user.id == session.get('user_id'):
        flash('You cannot deactivate your own account')
        return redirect('/admin/users')
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User "{user.username}" has been {status}')
    return redirect('/admin/users')


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user (admin only)"""
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deleting themselves
    if user.id == session.get('user_id'):
        flash('You cannot delete your own account')
        return redirect('/admin/users')
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User "{username}" has been deleted')
    return redirect('/admin/users')


# ================= TILE CRUD =================
@app.route('/add_tile', methods=['GET', 'POST'])
@admin_required
def add_tile():
    if request.method == 'POST':
        buy_price_str = request.form.get('buy_price', '').strip()
        buy_price = float(buy_price_str) if buy_price_str else None
        
        tile = Tile(
            brand=request.form['brand'],
            size=request.form['size'],
            buy_price=buy_price,
            price=float(request.form['price']),
            quantity=int(request.form['quantity'])
        )
        db.session.add(tile)
        db.session.commit()
        flash('Tile added successfully!')
        return redirect('/dashboard')

    return render_template('add_tile.html')


@app.route('/edit_tile/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_tile(id):
    tile = Tile.query.get_or_404(id)

    if request.method == 'POST':
        buy_price_str = request.form.get('buy_price', '').strip()
        
        tile.brand = request.form['brand']
        tile.size = request.form['size']
        tile.buy_price = float(buy_price_str) if buy_price_str else None
        tile.price = float(request.form['price'])
        tile.quantity = int(request.form['quantity'])
        db.session.commit()
        flash('Tile updated successfully!')
        return redirect('/dashboard')

    return render_template('add_tile.html', tile=tile)


@app.route('/delete_tile/<int:id>')
@admin_required
def delete_tile(id):
    tile = Tile.query.get_or_404(id)
    db.session.delete(tile)
    db.session.commit()
    flash('Tile deleted successfully!')
    return redirect('/dashboard')


# ================= BILLING =================
@app.route('/billing', methods=['GET', 'POST'])
@login_required
def billing():
    tiles = Tile.query.all()

    if request.method == 'POST':
        customer_name = request.form.get('customer_name')
        customer_mobile = request.form.get('customer_mobile', '').strip() or None
        gst = float(request.form.get('gst', 0))
        discount = float(request.form.get('discount', 0))

        # Create empty bill
        bill = Bill(
            customer_name=customer_name,
            customer_mobile=customer_mobile,
            total=0,
            gst=gst,
            discount=discount
        )
        db.session.add(bill)
        db.session.commit()

        subtotal = 0

        for tile in tiles:
            qty = int(request.form.get(f'qty_{tile.id}', 0))
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

        bill.total = subtotal + (subtotal * gst / 100) - discount
        db.session.commit()

        return redirect(url_for('invoice', bill_id=bill.id))

    return render_template('billing.html', tiles=tiles)


# ================= INVOICE =================
@app.route('/invoice/<int:bill_id>')
@login_required
def invoice(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    items = BillItem.query.filter_by(bill_id=bill_id).all()

    # Format WhatsApp message
    whatsapp_message = f"""🧾 *Invoice #{bill.id}*
From: Sita Ram Traders

*Customer:* {bill.customer_name or 'Walk-in'}
*Date:* {bill.date.strftime('%d-%m-%Y') if bill.date else '—'}

*Items:*
"""
    subtotal = 0
    for item in items:
        whatsapp_message += f"• {item.tile_name} ({item.size}) - {item.quantity} x ₹{item.price:.2f} = ₹{item.total:.2f}\n"
        subtotal += item.total

    whatsapp_message += f"""
*Subtotal:* ₹{subtotal:.2f}
*GST ({bill.gst}%):* ₹{(subtotal * bill.gst / 100):.2f}
*Discount:* -₹{bill.discount:.2f}
*Grand Total:* ₹{bill.total:.2f}

Thank you for your purchase! 🙏"""

    return render_template('invoice.html', bill=bill, items=items, whatsapp_message=whatsapp_message)


@app.route('/invoice_pdf/<int:bill_id>')
@login_required
def invoice_pdf(bill_id):
    from xhtml2pdf import pisa
    bill = Bill.query.get_or_404(bill_id)
    items = BillItem.query.filter_by(bill_id=bill_id).all()

    html = render_template(
        'invoice_pdf.html',
        bill=bill,
        items=items
    )

    result = io.BytesIO()
    pisa.CreatePDF(html, dest=result)

    response = make_response(result.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = (
        f'attachment; filename=invoice_{bill.id}.pdf'
    )
    return response


@app.route('/stock_availability_pdf')
@admin_required
def stock_availability_pdf():
    from xhtml2pdf import pisa
    
    # Get all tiles ordered by brand and size
    tiles = Tile.query.order_by(Tile.brand, Tile.size).all()
    
    # Get current date for the report
    current_date = datetime.utcnow().strftime('%d-%m-%Y %H:%M')
    
    html = render_template(
        'stock_availability_pdf.html',
        tiles=tiles,
        current_date=current_date
    )
    
    result = io.BytesIO()
    pisa.CreatePDF(html, dest=result)
    
    # Generate filename with current date
    filename_date = datetime.utcnow().strftime('%Y-%m-%d')
    
    response = make_response(result.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = (
        f'attachment; filename=stock_availability_{filename_date}.pdf'
    )
    return response


# ================= HISTORY =================
@app.route('/history')
@login_required
def history():
    bills = Bill.query.order_by(Bill.date.desc()).all()
    return render_template('history.html', bills=bills)


# ================= SALES REPORT =================
@app.route('/sales_report')
@login_required
def sales_report():
    today = datetime.utcnow().date()

    total_sales = db.session.query(
        func.sum(Bill.total)
    ).filter(
        func.date(Bill.date) == today
    ).scalar() or 0

    bills = Bill.query.filter(
        func.date(Bill.date) == today
    ).all()

    return render_template(
        'sales_report.html',
        total_sales=total_sales,
        bills=bills,
        today=today
    )


@app.route('/edit_bill/<int:bill_id>', methods=['GET', 'POST'])
@admin_required
def edit_bill(bill_id):
    bill = Bill.query.get_or_404(bill_id)

    if request.method == 'POST':
        bill.customer_name = request.form['customer_name']
        bill.customer_mobile = request.form.get('customer_mobile', '').strip() or None
        bill.gst = float(request.form['gst'])
        bill.discount = float(request.form['discount'])

        # Recalculate total
        subtotal = db.session.query(
            func.sum(BillItem.total)
        ).filter_by(bill_id=bill.id).scalar() or 0

        bill.total = subtotal + (subtotal * bill.gst / 100) - bill.discount
        db.session.commit()

        flash('Bill updated successfully')
        return redirect('/history')

    return render_template('edit_bill.html', bill=bill)


@app.route('/delete_bill/<int:bill_id>')
@admin_required
def delete_bill(bill_id):
    bill = Bill.query.get_or_404(bill_id)

    # delete bill items first
    BillItem.query.filter_by(bill_id=bill.id).delete()

    db.session.delete(bill)
    db.session.commit()

    flash('Bill deleted successfully')
    return redirect('/history')


# ================= DATABASE INITIALIZATION =================
def init_db():
    """Initialize database and create default admin if no users exist"""
    db.create_all()
    
    # Create default admin user if no users exist
    if not User.query.first():
        admin = User(
            username='admin',
            email='admin@example.com',
            password=generate_password_hash('admin123'),
            role='admin',
            is_active=True
        )
        db.session.add(admin)
        db.session.commit()
        print('Default admin user created (username: admin, password: admin123)')


# ================= RUN =================
if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
