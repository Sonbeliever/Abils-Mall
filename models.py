from datetime import datetime
from flask_login import UserMixin
from extensions import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# =========================
# USER
# =========================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(30))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='buyer')  # admin, manager, buyer
    is_verified = db.Column(db.Boolean, default=False)
    discount_rate = db.Column(db.Float, default=0.0)
    wallet_balance = db.Column(db.Float, default=0.0)
    notify_email = db.Column(db.Boolean, default=True)
    notify_sms = db.Column(db.Boolean, default=True)
    avatar_path = db.Column(db.String(300))
    commission_rate = db.Column(db.Float, default=5.0)

    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))  # managers only

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='buyer', lazy=True)
    cart_items = db.relationship('CartItem', backref='buyer', lazy=True)
    wallet_transactions = db.relationship('WalletTransaction', backref='user', lazy=True)


# =========================
# COMPANY
# =========================
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Admin
    wallet_balance = db.Column(db.Float, default=0.0)
    pickup_country = db.Column(db.String(120))
    pickup_state = db.Column(db.String(120))
    pickup_area = db.Column(db.String(120))
    pickup_bus_stop = db.Column(db.String(120))
    pickup_address = db.Column(db.String(255))
    pickup_map_url = db.Column(db.String(500))
    pickup_lat = db.Column(db.Float)
    pickup_lng = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship('User', foreign_keys=[owner_id])
    managers = db.relationship('User', foreign_keys=[User.company_id], backref='company', lazy=True)

    products = db.relationship('Product', backref='company', lazy=True)
    activities = db.relationship('CompanyActivity', backref='company', lazy=True)
    payments = db.relationship('Payment', backref='company', lazy=True)
    daily_reports = db.relationship('DailyReport', backref='company', lazy=True)


# =========================
# PRODUCT
# =========================
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    sale_price = db.Column(db.Float)
    stock = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String(500))
    is_new = db.Column(db.Boolean, default=False)
    is_hot = db.Column(db.Boolean, default=False)
    weight_grams = db.Column(db.Integer, default=0)
    size_desc = db.Column(db.String(120))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cart_items = db.relationship('CartItem', backref='product', lazy=True)
    order_items = db.relationship('OrderItem', backref='product', lazy=True)
    price_logs = db.relationship('PriceHistory', backref='product', lazy=True)


# =========================
# PRICE HISTORY
# =========================
class PriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    old_price = db.Column(db.Float)
    new_price = db.Column(db.Float)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# CART
# =========================
class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer, default=1)


# =========================
# ORDER
# =========================
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    total_amount = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')
    payment_reference = db.Column(db.String(100))
    delivery_country = db.Column(db.String(120))
    delivery_state = db.Column(db.String(120))
    delivery_area = db.Column(db.String(120))
    delivery_bus_stop = db.Column(db.String(120))
    delivery_address = db.Column(db.String(255))
    delivery_phone = db.Column(db.String(30))
    delivery_map_url = db.Column(db.String(500))
    delivery_distance_km = db.Column(db.Float)
    shipping_fee = db.Column(db.Float, default=0.0)
    total_weight_grams = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy=True)


# =========================
# ORDER ITEMS
# =========================
class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer)
    price = db.Column(db.Float)


# =========================
# PAYMENT
# =========================
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    amount = db.Column(db.Float)
    provider = db.Column(db.String(50))
    reference = db.Column(db.String(100))
    status = db.Column(db.String(20), default='initiated')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# DISCOUNT CUSTOMERS
# =========================
class DiscountCustomer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer)
    company_id = db.Column(db.Integer)
    approved = db.Column(db.Boolean, default=False)
    discount_rate = db.Column(db.Float, default=0.0)


# =========================
# DISCOUNT REQUEST
# =========================
class DiscountRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer)
    company_id = db.Column(db.Integer)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# DAILY REPORTS (PDF)
# =========================
class DailyReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    content = db.Column(db.Text)
    pdf_filename = db.Column(db.String(255))
    pdf_data = db.Column(db.LargeBinary)
    pdf_mimetype = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# REFERRALS
# =========================
class Referral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    referred_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ReferralWallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    token_balance = db.Column(db.Integer, default=0)
    total_earned = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ReferralWithdrawalRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tokens = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending/approved/rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# WALLET TRANSACTIONS
# =========================
class WalletTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Float)
    tx_type = db.Column(db.String(20))  # credit/debit
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# PAYOUT REQUESTS
# =========================
class PayoutRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer)
    manager_id = db.Column(db.Integer)
    amount = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# ACTIVITY LOG
# =========================
class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    action = db.Column(db.String(100))
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# BANK TRANSFER DEPOSITS
# =========================
class BankTransfer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    amount = db.Column(db.Float)
    proof_path = db.Column(db.String(300))
    status = db.Column(db.String(20), default='pending')  # pending/approved/rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# PASSWORD RESET TOKEN
# =========================
class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    token = db.Column(db.String(120), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)


# =========================
# OTP VERIFICATION
# =========================
class OtpVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    otp_hash = db.Column(db.String(255), nullable=False)
    referrer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# ACTIVITY LOG
# =========================
class CompanyActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    action = db.Column(db.String(100))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# MANAGER ACCOUNT REQUEST
# =========================
class ManagerAccountRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_name = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending/approved/rejected
    commission_rate = db.Column(db.Float)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
