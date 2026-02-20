# manager.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
import os
import uuid

from extensions import db
from models import User, Product, Order, CompanyActivity, DiscountRequest, DiscountCustomer, DailyReport, PayoutRequest, Company
from activity import log_activity
from flask import send_file
from io import BytesIO
from reportlab.pdfgen import canvas
from datetime import datetime
from opay_api import query_status as opay_query_status
import cloudinary
import cloudinary.uploader

manager_bp = Blueprint('manager', __name__, template_folder='templates', url_prefix='/manager')
ALLOWED_PRODUCT_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_REPORT_EXTS = {"pdf"}


def _upload_product_image_cloud(file_storage):
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    api_key = os.getenv("CLOUDINARY_API_KEY", "").strip()
    api_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()
    base_folder = os.getenv("CLOUDINARY_FOLDER", "abils-mall").strip() or "abils-mall"
    if not (cloud_name and api_key and api_secret):
        return None

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )
    try:
        result = cloudinary.uploader.upload(
            file_storage,
            folder=f"{base_folder}/products",
            resource_type="image",
            use_filename=True,
            unique_filename=True,
            overwrite=False,
        )
        return result.get("secure_url")
    except Exception:
        return None


def _save_product_image(file_storage):
    filename = secure_filename(file_storage.filename or "")
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in ALLOWED_PRODUCT_IMAGE_EXTS:
        return None

    cloud_url = _upload_product_image_cloud(file_storage)
    if cloud_url:
        return cloud_url

    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'products')
    os.makedirs(upload_dir, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    full_path = os.path.join(upload_dir, unique_name)
    file_storage.save(full_path)
    return f"uploads/products/{unique_name}"


# =========================================
# MANAGER DASHBOARD
# =========================================
@manager_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    products = Product.query.filter_by(company_id=current_user.company_id).all()
    orders = Order.query.filter_by(company_id=current_user.company_id).all()
    pending_users = User.query.filter_by(company_id=current_user.company_id, is_verified=False).all()
    discount_requests = DiscountRequest.query.filter_by(company_id=current_user.company_id, status='pending').all()
    buyer_ids = [req.buyer_id for req in discount_requests]
    buyer_map = {u.id: u.username for u in User.query.filter(User.id.in_(buyer_ids)).all()} if buyer_ids else {}
    company = Company.query.get(current_user.company_id)

    last_seen_raw = session.get('manager_last_seen_activity')
    last_seen = None
    if last_seen_raw:
        try:
            last_seen = datetime.fromisoformat(last_seen_raw)
        except ValueError:
            session.pop('manager_last_seen_activity', None)

    activities_query = CompanyActivity.query.filter(
        CompanyActivity.company_id == current_user.company_id
    ).order_by(CompanyActivity.created_at.desc())
    activities = activities_query.limit(20).all()
    if last_seen:
        unread_count = CompanyActivity.query.filter(
            CompanyActivity.company_id == current_user.company_id,
            CompanyActivity.created_at > last_seen
        ).count()
    else:
        unread_count = CompanyActivity.query.filter(
            CompanyActivity.company_id == current_user.company_id
        ).count()
    return render_template(
        'manager_dashboard.html',
        products=products,
        orders=orders,
        pending_users=pending_users,
        discount_requests=discount_requests,
        company=company,
        buyer_map=buyer_map,
        activities=activities,
        unread_count=unread_count
    )


@manager_bp.route('/pickup-location', methods=['POST'])
@login_required
def update_pickup_location():
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    company = Company.query.get_or_404(current_user.company_id)
    company.pickup_country = request.form.get('pickup_country', '').strip()
    company.pickup_state = request.form.get('pickup_state', '').strip()
    company.pickup_area = request.form.get('pickup_area', '').strip()
    company.pickup_bus_stop = request.form.get('pickup_bus_stop', '').strip()
    company.pickup_address = request.form.get('pickup_address', '').strip()
    company.pickup_map_url = request.form.get('pickup_map_url', '').strip()
    lat_raw = request.form.get('pickup_lat', '').strip()
    lng_raw = request.form.get('pickup_lng', '').strip()
    try:
        company.pickup_lat = float(lat_raw) if lat_raw else None
        company.pickup_lng = float(lng_raw) if lng_raw else None
    except ValueError:
        flash('Invalid pickup coordinates.', 'danger')
        return redirect(url_for('manager.dashboard'))

    db.session.commit()
    flash('Pickup location updated.', 'success')
    return redirect(url_for('manager.dashboard'))


@manager_bp.route('/activities')
@login_required
def activities():
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    last_seen_raw = session.get('manager_last_seen_activity')
    last_seen = None
    if last_seen_raw:
        try:
            last_seen = datetime.fromisoformat(last_seen_raw)
        except ValueError:
            session.pop('manager_last_seen_activity', None)

    activities_query = CompanyActivity.query.filter(
        CompanyActivity.company_id == current_user.company_id
    ).order_by(CompanyActivity.created_at.desc())
    activities_list = activities_query.limit(200).all()
    if last_seen:
        unread_count = CompanyActivity.query.filter(
            CompanyActivity.company_id == current_user.company_id,
            CompanyActivity.created_at > last_seen
        ).count()
    else:
        unread_count = CompanyActivity.query.filter(
            CompanyActivity.company_id == current_user.company_id
        ).count()

    return render_template(
        'manager_activities.html',
        activities=activities_list,
        unread_count=unread_count
    )


@manager_bp.route('/activities/mark-seen', methods=['POST'])
@login_required
def mark_activities_seen():
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    session['manager_last_seen_activity'] = datetime.utcnow().isoformat()
    return redirect(url_for('manager.activities'))


# =========================================
# ADD PRODUCT
# =========================================
@manager_bp.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        price = float(request.form['price'])
        sale_price = request.form.get('sale_price') or None
        stock = int(request.form.get('stock', 0))
        weight_grams = int(request.form.get('weight_grams', 0) or 0)
        size_desc = request.form.get('size_desc', '').strip()
        image_url = request.form.get('image_url', '').strip()
        is_new = bool(request.form.get('is_new'))
        is_hot = bool(request.form.get('is_hot'))

        image_file = request.files.get('image_file')
        if image_file and image_file.filename:
            saved_path = _save_product_image(image_file)
            if not saved_path:
                flash("Product image must be png, jpg, jpeg, gif, or webp.", "danger")
                return redirect(url_for('manager.add_product'))
            image_url = saved_path

        product = Product(
            name=name,
            description=description,
            price=price,
            sale_price=sale_price,
            stock=stock,
            image_url=image_url,
            is_new=is_new,
            is_hot=is_hot,
            weight_grams=weight_grams,
            size_desc=size_desc,
            company_id=current_user.company_id,
            manager_id=current_user.id
        )
        db.session.add(product)
        db.session.add(CompanyActivity(
            company_id=current_user.company_id,
            action='PRODUCT_ADDED',
            description=f'Product {name} added by manager {current_user.username}'
        ))
        db.session.commit()
        log_activity(current_user.id, "PRODUCT_ADDED", f"Product {name} added", company_id=current_user.company_id)
        flash(f'Product "{name}" added successfully!', 'success')
        return redirect(url_for('manager.dashboard'))

    return render_template('manager_add_product.html')


# =========================================
# EDIT PRODUCT
# =========================================
@manager_bp.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    product = Product.query.get_or_404(product_id)
    if product.company_id != current_user.company_id:
        flash('Cannot edit product from another company', 'danger')
        return redirect(url_for('manager.dashboard'))

    if request.method == 'POST':
        product.name = request.form['name']
        product.description = request.form.get('description', '')
        product.price = float(request.form['price'])
        product.sale_price = request.form.get('sale_price') or None
        product.stock = int(request.form.get('stock', 0))
        product.weight_grams = int(request.form.get('weight_grams', 0) or 0)
        product.size_desc = request.form.get('size_desc', '').strip()
        image_url = request.form.get('image_url', '').strip()
        product.is_new = bool(request.form.get('is_new'))
        product.is_hot = bool(request.form.get('is_hot'))
        if not product.manager_id:
            product.manager_id = current_user.id

        image_file = request.files.get('image_file')
        if image_file and image_file.filename:
            saved_path = _save_product_image(image_file)
            if not saved_path:
                flash("Product image must be png, jpg, jpeg, gif, or webp.", "danger")
                return redirect(url_for('manager.edit_product', product_id=product_id))
            image_url = saved_path
        if image_url:
            product.image_url = image_url

        db.session.add(CompanyActivity(
            company_id=current_user.company_id,
            action='PRODUCT_UPDATED',
            description=f'Product {product.name} updated by manager {current_user.username}'
        ))
        db.session.commit()
        log_activity(current_user.id, "PRODUCT_UPDATED", f"Product {product.name} updated", company_id=current_user.company_id)
        flash(f'Product "{product.name}" updated successfully!', 'success')
        return redirect(url_for('manager.dashboard'))

    return render_template('manager_edit_product.html', product=product)


# =========================================
# MANAGE PRODUCTS
# =========================================
@manager_bp.route('/products')
@login_required
def manage_products():
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    products = Product.query.filter_by(company_id=current_user.company_id).all()
    return render_template('manager_products.html', products=products)


# =========================================
# DELETE PRODUCT
# =========================================
@manager_bp.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    product = Product.query.get_or_404(product_id)
    if product.company_id != current_user.company_id:
        flash('Cannot delete product from another company', 'danger')
        return redirect(url_for('manager.dashboard'))

    product_name = product.name
    db.session.delete(product)
    db.session.add(CompanyActivity(
        company_id=current_user.company_id,
        action='PRODUCT_DELETED',
        description=f'Product {product_name} deleted by manager {current_user.username}'
    ))
    db.session.commit()
    log_activity(current_user.id, "PRODUCT_DELETED", f"Product {product_name} deleted", company_id=current_user.company_id)
    flash(f'Product "{product_name}" deleted successfully!', 'success')
    return redirect(url_for('manager.dashboard'))

# =========================================
# APPROVE USER (make regular customer)
# =========================================
@manager_bp.route('/users/approve/<int:user_id>')
@login_required
def approve_user(user_id):
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.get_or_404(user_id)
    if user.company_id != current_user.company_id:
        flash('Cannot approve user from another company', 'danger')
        return redirect(url_for('manager.dashboard'))

    user.is_verified = True
    db.session.add(CompanyActivity(
        company_id=current_user.company_id,
        action='USER_APPROVED',
        description=f'User {user.username} approved as regular customer by manager {current_user.username}'
    ))
    db.session.commit()
    log_activity(current_user.id, "USER_APPROVED", f"User {user.username} approved", company_id=current_user.company_id)
    flash(f'User "{user.username}" approved successfully!', 'success')
    return redirect(url_for('manager.dashboard'))


# =========================================
# APPROVE DISCOUNT REQUEST
# =========================================
@manager_bp.route('/discounts/approve/<int:request_id>', methods=['POST'])
@login_required
def approve_discount(request_id):
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    discount_rate = float(request.form.get('discount_rate', 10))
    request_item = DiscountRequest.query.get_or_404(request_id)
    if request_item.company_id != current_user.company_id:
        flash('Access denied', 'danger')
        return redirect(url_for('manager.dashboard'))

    request_item.status = 'approved'
    existing = DiscountCustomer.query.filter_by(
        buyer_id=request_item.buyer_id,
        company_id=request_item.company_id
    ).first()
    if existing:
        existing.approved = True
        existing.discount_rate = discount_rate
    else:
        db.session.add(DiscountCustomer(
            buyer_id=request_item.buyer_id,
            company_id=request_item.company_id,
            approved=True,
            discount_rate=discount_rate
        ))

    db.session.add(CompanyActivity(
        company_id=current_user.company_id,
        action='DISCOUNT_APPROVED',
        description=f'Discount approved for buyer ID {request_item.buyer_id}'
    ))
    db.session.commit()
    log_activity(current_user.id, "DISCOUNT_APPROVED", f"Discount approved for buyer {request_item.buyer_id}", company_id=current_user.company_id)
    flash('Discount request approved.', 'success')
    return redirect(url_for('manager.dashboard'))


# =========================================
# REJECT DISCOUNT REQUEST
# =========================================
@manager_bp.route('/discounts/reject/<int:request_id>')
@login_required
def reject_discount(request_id):
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    request_item = DiscountRequest.query.get_or_404(request_id)
    if request_item.company_id != current_user.company_id:
        flash('Access denied', 'danger')
        return redirect(url_for('manager.dashboard'))

    request_item.status = 'rejected'
    db.session.commit()
    log_activity(current_user.id, "DISCOUNT_REJECTED", f"Discount rejected for buyer {request_item.buyer_id}", company_id=current_user.company_id)
    flash('Discount request rejected.', 'info')
    return redirect(url_for('manager.dashboard'))


# =========================================
# DAILY REPORTS
# =========================================
@manager_bp.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        report_file = request.files.get('report_pdf')
        if not report_file or not report_file.filename:
            flash('Please upload a PDF report.', 'danger')
            return redirect(url_for('manager.reports'))
        filename = secure_filename(report_file.filename)
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ALLOWED_REPORT_EXTS:
            flash('Report must be a PDF file.', 'danger')
            return redirect(url_for('manager.reports'))
        pdf_data = report_file.read()
        if not pdf_data:
            flash('Uploaded PDF is empty.', 'danger')
            return redirect(url_for('manager.reports'))

        report = DailyReport(
            company_id=current_user.company_id,
            manager_id=current_user.id,
            content=content,
            pdf_filename=filename,
            pdf_data=pdf_data,
            pdf_mimetype=report_file.mimetype or "application/pdf"
        )
        db.session.add(report)
        db.session.add(CompanyActivity(
            company_id=current_user.company_id,
            action='REPORT_SUBMITTED',
            description=f'Manager {current_user.username} submitted a daily report'
        ))
        db.session.commit()
        log_activity(current_user.id, "REPORT_SUBMITTED", "Daily report submitted", company_id=current_user.company_id)
        flash('Report submitted.', 'success')
        return redirect(url_for('manager.reports'))

    reports = DailyReport.query.filter_by(company_id=current_user.company_id).order_by(DailyReport.created_at.desc()).all()
    return render_template('manager_reports.html', reports=reports)


@manager_bp.route('/reports/<int:report_id>/download')
@login_required
def download_report(report_id):
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    report = DailyReport.query.get_or_404(report_id)
    if report.company_id != current_user.company_id:
        flash('Access denied', 'danger')
        return redirect(url_for('manager.reports'))
    if not report.pdf_data:
        flash('No PDF available for this report.', 'danger')
        return redirect(url_for('manager.reports'))

    return send_file(
        BytesIO(report.pdf_data),
        as_attachment=True,
        download_name=report.pdf_filename or "daily_report.pdf",
        mimetype=report.pdf_mimetype or "application/pdf"
    )


# =========================================
# PAYOUT REQUEST
# =========================================
@manager_bp.route('/payouts/request', methods=['POST'])
@login_required
def request_payout():
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    amount = float(request.form.get('amount', 0))
    if amount <= 0:
        flash('Invalid payout amount.', 'danger')
        return redirect(url_for('manager.dashboard'))

    payout = PayoutRequest(
        company_id=current_user.company_id,
        manager_id=current_user.id,
        amount=amount
    )
    db.session.add(payout)
    db.session.add(CompanyActivity(
        company_id=current_user.company_id,
        action='PAYOUT_REQUESTED',
        description=f'Manager {current_user.username} requested payout of {amount}'
    ))
    db.session.commit()
    log_activity(current_user.id, "PAYOUT_REQUESTED", f"Payout {amount} requested", company_id=current_user.company_id)
    flash('Payout request submitted.', 'success')
    return redirect(url_for('manager.dashboard'))


# =========================================
# DAILY STATEMENT PDF (MANAGER)
# =========================================
@manager_bp.route('/statements/daily.pdf')
@login_required
def daily_statement_pdf():
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 800, f"Daily Statement - {datetime.utcnow().date()}")
    y = 770
    p.setFont("Helvetica", 11)
    for order in Order.query.filter_by(company_id=current_user.company_id).order_by(Order.created_at.desc()).limit(50).all():
        p.drawString(50, y, f"Order #{order.id} - ₦{order.total_amount:,.0f} - {order.status}")
        y -= 15
        if y < 50:
            p.showPage()
            y = 800
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="manager_daily_statement.pdf", mimetype="application/pdf")


# =========================================
# MANAGER OPay STATUS CHECK
# =========================================
@manager_bp.route('/opay/status', methods=['POST'])
@login_required
def manager_opay_status():
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))
    order_id = request.form.get('order_id', '')
    if not order_id.isdigit():
        flash('Invalid order id', 'danger')
        return redirect(url_for('manager.dashboard'))
    order = Order.query.get(int(order_id))
    if not order or order.company_id != current_user.company_id:
        flash('Order not found for your company', 'danger')
        return redirect(url_for('manager.dashboard'))
    response = opay_query_status(str(order.id))
    flash(f"OPay Status: {response}", "info")
    return redirect(url_for('manager.dashboard'))
