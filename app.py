from flask import Flask, render_template, redirect, url_for, request, flash
from extensions import db, login_manager
from flask_login import current_user
from datetime import timedelta
import os
from dotenv import load_dotenv

from auth import auth_bp
from admin import admin_bp
from manager import manager_bp
from shop import shop_bp
from payments import payments_bp


def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'CHANGE_THIS_SECRET_KEY'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///abils_mall.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=7)
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    # Payment keys (set in environment)
    # TODO: Set these in your environment variables
    app.config['PAYSTACK_SECRET_KEY'] = os.getenv('PAYSTACK_SECRET_KEY', '')
    app.config['FLUTTERWAVE_SECRET_KEY'] = os.getenv('FLUTTERWAVE_SECRET_KEY', '')
    app.config['FLUTTERWAVE_PUBLIC_KEY'] = os.getenv('FLUTTERWAVE_PUBLIC_KEY', '')
    app.config['OPAY_PUBLIC_KEY'] = os.getenv('OPAY_PUBLIC_KEY', '')  # TODO: set this
    app.config['OPAY_SECRET_KEY'] = os.getenv('OPAY_SECRET_KEY', '')  # TODO: set this
    app.config['OPAY_MERCHANT_ID'] = os.getenv('OPAY_MERCHANT_ID', '')  # TODO: set this
    app.config['OPAY_CALLBACK_URL'] = os.getenv('OPAY_CALLBACK_URL', '')
    app.config['OPAY_RETURN_URL'] = os.getenv('OPAY_RETURN_URL', '')
    app.config['OPAY_CANCEL_URL'] = os.getenv('OPAY_CANCEL_URL', '')
    app.config['OPAY_PAY_METHOD'] = os.getenv('OPAY_PAY_METHOD', 'BankCard')
    app.config['OPAY_COUNTRY'] = os.getenv('OPAY_COUNTRY', 'NG')
    app.config['OPAY_API_BASE'] = os.getenv('OPAY_API_BASE', 'https://testapi.opaycheckout.com')
    app.config['OPAY_STATUS_ENDPOINT'] = os.getenv('OPAY_STATUS_ENDPOINT', '/api/v1/international/cashier/status')
    app.config['OPAY_REFUND_ENDPOINT'] = os.getenv('OPAY_REFUND_ENDPOINT', '/api/v1/international/cashier/refund')
    app.config['BANK_TRANSFER_BANK'] = os.getenv('BANK_TRANSFER_BANK', 'Your Bank')
    app.config['BANK_TRANSFER_ACCOUNT_NAME'] = os.getenv('BANK_TRANSFER_ACCOUNT_NAME', 'Your Account Name')
    app.config['BANK_TRANSFER_ACCOUNT_NUMBER'] = os.getenv('BANK_TRANSFER_ACCOUNT_NUMBER', '0000000000')
    app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'static/uploads')
    app.config['AVATAR_MAX_BYTES'] = int(os.getenv('AVATAR_MAX_BYTES', str(2 * 1024 * 1024)))
    app.config['RESET_URL_BASE'] = os.getenv('RESET_URL_BASE', 'http://127.0.0.1:5000')

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(manager_bp, url_prefix='/manager')
    app.register_blueprint(shop_bp, url_prefix='/shop')
    app.register_blueprint(payments_bp, url_prefix='/payments')

    @app.route('/')
    def home():
        from models import Product
        products = Product.query.all()
        return render_template('marketplace.html', products=products)

    @app.route('/setup', methods=['GET', 'POST'])
    def setup_admin():
        from models import User
        from werkzeug.security import generate_password_hash

        existing_admin = User.query.filter_by(role='admin').first()
        if existing_admin:
            flash('Admin already exists.', 'info')
            return redirect(url_for('auth.login'))

        if request.method == 'POST':
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']

            admin_user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role='admin',
                is_verified=True
            )
            db.session.add(admin_user)
            db.session.commit()
            flash('Admin account created. Please log in.', 'success')
            return redirect(url_for('auth.login'))

        return render_template('setup_admin.html')

    @app.route('/dashboard')
    def dashboard_redirect():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role == 'admin':
            return redirect('/admin')
        elif current_user.role == 'manager':
            return redirect('/manager')
        return redirect('/shop')

    @app.after_request
    def disable_static_cache(response):
        if request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    return app


app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
