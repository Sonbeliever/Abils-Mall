# admin.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db
from models import User, Company, Product, Order, CompanyActivity, PayoutRequest, DailyReport, Payment, DiscountRequest, ActivityLog, BankTransfer, ReferralWithdrawalRequest, ReferralWallet, ManagerAccountRequest, CartItem, WalletTransaction, PasswordResetToken, OtpVerification, Referral
from finance import distribute_order_amount
from activity import log_activity
from notifications import notify_user, send_email
from flask import send_file
from io import BytesIO
from reportlab.pdfgen import canvas
from datetime import datetime, timedelta
from opay_api import query_status as opay_query_status, refund as opay_refund
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
import re
import uuid

admin_bp = Blueprint('admin', __name__, template_folder='templates', url_prefix='/admin')

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_valid_email(email: str) -> bool:
    return bool(email and EMAIL_RE.match(email))


# =========================================
# ADMIN DASHBOARD
# =========================================
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    company_id_filter = request.args.get('company_id', '').strip()
    last_seen_raw = session.get('admin_last_seen_activity')
    last_seen = None
    if last_seen_raw:
        try:
            last_seen = datetime.fromisoformat(last_seen_raw)
        except ValueError:
            session.pop('admin_last_seen_activity', None)
    companies = Company.query.all()
    products = Product.query.all()
    orders = Order.query.all()
    activities_query = CompanyActivity.query.order_by(CompanyActivity.created_at.desc())
    if company_id_filter:
        try:
            company_id_value = int(company_id_filter)
            activities_query = activities_query.filter(CompanyActivity.company_id == company_id_value)
        except ValueError:
            flash('Company ID must be a number.', 'danger')
    activities = activities_query.limit(20).all()
    if last_seen:
        unread_count = CompanyActivity.query.filter(CompanyActivity.created_at > last_seen).count()
    else:
        unread_count = CompanyActivity.query.count()

    total_sales = sum(order.total_amount for order in orders)
    total_payments = sum(payment.amount for payment in Payment.query.all())
    total_company_balance = sum(company.wallet_balance for company in companies)

    return render_template(
        'admin_dashboard.html',
        companies=companies,
        products=products,
        orders=orders,
        activities=activities,
        unread_count=unread_count,
        total_sales=total_sales,
        total_payments=total_payments,
        total_company_balance=total_company_balance,
        company_id_filter=company_id_filter
    )


@admin_bp.route('/email-change', methods=['GET'])
@login_required
def admin_email_change_page():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('admin_change_email.html')


@admin_bp.route('/activities/mark-seen', methods=['POST'])
@login_required
def mark_activities_seen():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    session['admin_last_seen_activity'] = datetime.utcnow().isoformat()
    return redirect(url_for('admin.dashboard'))


# =========================================
# ADMIN EMAIL CHANGE (OTP)
# =========================================
@admin_bp.route('/change-email', methods=['POST'])
@login_required
def request_admin_email_change():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    new_email = request.form.get('new_email', '').strip().lower()
    if not _is_valid_email(new_email):
        flash('Enter a valid email address.', 'danger')
        return redirect(url_for('admin.admin_email_change_page'))

    existing = User.query.filter(User.email == new_email, User.id != current_user.id).first()
    if existing:
        flash('That email is already in use.', 'danger')
        return redirect(url_for('admin.admin_email_change_page'))

    otp = f"{uuid.uuid4().int % 1000000:06d}"
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    session['admin_email_change'] = {
        "new_email": new_email,
        "otp_hash": generate_password_hash(otp),
        "expires_at": expires_at.isoformat()
    }

    send_email(
        current_user.email,
        "Admin Email Change OTP",
        f"Your OTP is {otp}. It expires in 10 minutes.",
        enabled=True
    )

    flash("OTP sent to your current admin email.", "success")
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/confirm-email', methods=['POST'])
@login_required
def confirm_admin_email_change():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    data = session.get('admin_email_change')
    if not data:
        flash("No pending email change. Request a new OTP first.", "danger")
        return redirect(url_for('admin.admin_email_change_page'))

    try:
        expires_at = datetime.fromisoformat(data.get("expires_at", ""))
    except ValueError:
        session.pop('admin_email_change', None)
        flash("OTP expired. Request a new one.", "danger")
        return redirect(url_for('admin.dashboard'))

    if expires_at < datetime.utcnow():
        session.pop('admin_email_change', None)
        flash("OTP expired. Request a new one.", "danger")
        return redirect(url_for('admin.dashboard'))

    otp = request.form.get('otp', '').strip()
    if not otp or not check_password_hash(data.get("otp_hash", ""), otp):
        flash("Invalid OTP.", "danger")
        return redirect(url_for('admin.dashboard'))

    new_email = data.get("new_email")
    if not new_email:
        session.pop('admin_email_change', None)
        flash("Invalid email change request.", "danger")
        return redirect(url_for('admin.dashboard'))

    current_user.email = new_email
    db.session.commit()
    session.pop('admin_email_change', None)
    log_activity(current_user.id, "ADMIN_EMAIL_CHANGED", f"Admin email changed to {new_email}")
    flash("Admin email updated successfully.", "success")
    return redirect(url_for('admin.admin_email_change_page'))


# =========================================
# CREATE COMPANY
# =========================================
@admin_bp.route('/companies/create', methods=['GET', 'POST'])
@login_required
def create_company():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')

        existing = Company.query.filter_by(name=name).first()
        if existing:
            flash('Company already exists', 'danger')
            return redirect(url_for('admin.create_company'))

        company = Company(name=name, description=description)
        db.session.add(company)
        db.session.add(CompanyActivity(
            company_id=None,
            action='COMPANY_CREATED',
            description=f'Admin created company {name}'
        ))
        db.session.commit()
        flash('Company created successfully!', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('create_company.html')


# =========================================
# CREATE MANAGER
# =========================================
@admin_bp.route('/managers/create', methods=['GET', 'POST'])
@login_required
def create_manager():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    companies = Company.query.all()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        company_id = request.form['company_id']
        commission_rate = float(request.form.get('commission_rate', 5) or 5)
        if commission_rate < 0 or commission_rate > 100:
            flash('Commission rate must be between 0 and 100.', 'danger')
            return redirect(url_for('admin.create_manager'))

        existing = User.query.filter((User.username==username) | (User.email==email)).first()
        if existing:
            flash('Username or email already exists', 'danger')
            return redirect(url_for('admin.create_manager'))

        manager = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role='manager',
            company_id=company_id,
            is_verified=True,
            commission_rate=commission_rate
        )
        db.session.add(manager)
        db.session.add(CompanyActivity(
            company_id=company_id,
            action='MANAGER_CREATED',
            description=f'Manager {username} assigned to company ID {company_id}'
        ))
        db.session.commit()
        log_activity(current_user.id, "MANAGER_CREATED", f"Manager {username} created", company_id=company_id)
        flash('Manager created successfully!', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('create_manager.html', companies=companies)


# =========================================
# MANAGER ACCOUNT REQUESTS
# =========================================
@admin_bp.route('/manager-requests')
@login_required
def manager_requests():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    requests_list = ManagerAccountRequest.query.order_by(ManagerAccountRequest.created_at.desc()).all()
    user_map = {u.id: u for u in User.query.all()}
    return render_template('admin_manager_requests.html', requests=requests_list, user_map=user_map)


@admin_bp.route('/manager-requests/approve/<int:request_id>', methods=['POST'])
@login_required
def approve_manager_request(request_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    req = ManagerAccountRequest.query.get_or_404(request_id)
    if req.status != 'pending':
        flash('Request already processed.', 'info')
        return redirect(url_for('admin.manager_requests'))

    try:
        commission_rate = float(request.form.get('commission_rate', '5').strip())
    except ValueError:
        flash('Invalid commission rate.', 'danger')
        return redirect(url_for('admin.manager_requests'))

    if commission_rate < 0 or commission_rate > 100:
        flash('Commission rate must be between 0 and 100.', 'danger')
        return redirect(url_for('admin.manager_requests'))

    user = User.query.get(req.user_id)
    if not user or user.role != 'buyer':
        flash('Only buyer accounts can be promoted to manager.', 'danger')
        req.status = 'rejected'
        req.admin_id = current_user.id
        db.session.commit()
        return redirect(url_for('admin.manager_requests'))

    company = Company.query.filter(func.lower(Company.name) == req.company_name.lower()).first()
    if not company:
        company = Company(name=req.company_name, description='Created from manager account request')
        db.session.add(company)
        db.session.flush()

    user.role = 'manager'
    user.company_id = company.id
    user.commission_rate = commission_rate
    user.is_verified = True

    req.status = 'approved'
    req.commission_rate = commission_rate
    req.admin_id = current_user.id

    db.session.add(CompanyActivity(
        company_id=company.id,
        action='MANAGER_REQUEST_APPROVED',
        description=f'Admin approved manager request for {user.username}'
    ))
    db.session.commit()
    notify_user(
        user,
        "Manager Account Approved",
        "Your manager account request has been approved. You can now sell your products with us.",
        "Manager account approved. You can now sell your products with us."
    )
    log_activity(current_user.id, "MANAGER_REQUEST_APPROVED", f"Approved manager request for {user.email}", company_id=company.id)
    flash('Manager request approved and user upgraded to manager.', 'success')
    return redirect(url_for('admin.manager_requests'))


@admin_bp.route('/manager-requests/reject/<int:request_id>', methods=['POST'])
@login_required
def reject_manager_request(request_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    req = ManagerAccountRequest.query.get_or_404(request_id)
    if req.status != 'pending':
        flash('Request already processed.', 'info')
        return redirect(url_for('admin.manager_requests'))

    req.status = 'rejected'
    req.admin_id = current_user.id
    db.session.commit()
    user = User.query.get(req.user_id)
    if user:
        notify_user(
            user,
            "Manager Account Request Rejected",
            "Your manager account request was rejected. Please review your company details and submit again.",
            "Manager request rejected. Update details and try again."
        )
    log_activity(current_user.id, "MANAGER_REQUEST_REJECTED", f"Rejected manager request for user #{req.user_id}")
    flash('Manager request rejected.', 'info')
    return redirect(url_for('admin.manager_requests'))


# =========================================
# VIEW USERS
# =========================================
@admin_bp.route('/users')
@login_required
def users():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    all_users = User.query.all()
    return render_template('admin_users.html', users=all_users)


# =========================================
# UPDATE MANAGER COMMISSION
# =========================================
@admin_bp.route('/managers/commission/<int:user_id>', methods=['POST'])
@login_required
def update_manager_commission(user_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.get_or_404(user_id)
    if user.role != 'manager':
        flash('Only managers have commission rates.', 'danger')
        return redirect(url_for('admin.users'))

    try:
        rate = float(request.form.get('commission_rate', 0))
    except ValueError:
        flash('Invalid commission rate.', 'danger')
        return redirect(url_for('admin.users'))

    if rate < 0 or rate > 100:
        flash('Commission rate must be between 0 and 100.', 'danger')
        return redirect(url_for('admin.users'))

    user.commission_rate = rate
    db.session.commit()
    log_activity(current_user.id, "MANAGER_COMMISSION_UPDATED", f"Manager {user.username} commission set to {rate}%", company_id=user.company_id)
    flash('Commission rate updated.', 'success')
    return redirect(url_for('admin.users'))


# =========================================
# VIEW ORDERS
# =========================================
@admin_bp.route('/orders')
@login_required
def orders():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    all_orders = Order.query.all()
    payments = {p.order_id: p for p in Payment.query.all()}
    company_map = {c.id: c.name for c in Company.query.all()}
    return render_template('admin_orders.html', orders=all_orders, payments=payments, company_map=company_map)


# =========================================
# VERIFY BUYER (optional)
# =========================================
@admin_bp.route('/users/verify/<int:user_id>')
@login_required
def verify_user(user_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.get_or_404(user_id)
    user.is_verified = True
    db.session.commit()
    log_activity(current_user.id, "USER_VERIFIED", f"Verified user {user.email}", company_id=user.company_id)
    flash(f'User "{user.username}" verified.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/reset-password/<int:user_id>', methods=['GET', 'POST'])
@login_required
def reset_user_password(user_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        new_password = request.form.get('password', '')
        if len(new_password) < 6:
            flash('Password too short.', 'danger')
            return redirect(url_for('admin.reset_user_password', user_id=user_id))
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        log_activity(current_user.id, "ADMIN_RESET_PASSWORD", f"Reset password for {user.email}", company_id=user.company_id)
        flash('Password reset successfully.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin_reset_user_password.html', user=user)


# =========================================
# DELETE USER
# =========================================
@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    if current_user.id == user_id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin.users'))

    user = User.query.get_or_404(user_id)
    # Clean linked records so user deletion does not fail on foreign keys.
    ReferralWallet.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    ReferralWithdrawalRequest.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    CartItem.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    WalletTransaction.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    PasswordResetToken.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    Referral.query.filter((Referral.referrer_id == user.id) | (Referral.referred_id == user.id)).delete(synchronize_session=False)
    OtpVerification.query.filter((OtpVerification.user_id == user.id) | (OtpVerification.referrer_id == user.id)).delete(synchronize_session=False)
    ManagerAccountRequest.query.filter((ManagerAccountRequest.user_id == user.id) | (ManagerAccountRequest.admin_id == user.id)).delete(synchronize_session=False)

    Product.query.filter_by(manager_id=user.id).update({Product.manager_id: None}, synchronize_session=False)
    Order.query.filter_by(buyer_id=user.id).update({Order.buyer_id: None}, synchronize_session=False)
    BankTransfer.query.filter_by(buyer_id=user.id).update({BankTransfer.buyer_id: None}, synchronize_session=False)
    PayoutRequest.query.filter_by(manager_id=user.id).update({PayoutRequest.manager_id: None}, synchronize_session=False)
    DailyReport.query.filter_by(manager_id=user.id).update({DailyReport.manager_id: None}, synchronize_session=False)
    ActivityLog.query.filter_by(actor_id=user.id).update({ActivityLog.actor_id: None}, synchronize_session=False)

    db.session.delete(user)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        err = str(exc.orig)
        if 'referral_wallet_user_id_fkey' in err:
            flash('Cannot delete user: referral wallet exists. Remove referral wallet first.', 'danger')
        elif 'product_manager_id_fkey' in err:
            flash('Cannot delete user: this manager still owns products. Reassign/delete products first.', 'danger')
        else:
            flash('Cannot delete user: this account is linked to existing records.', 'danger')
        return redirect(url_for('admin.users'))

    log_activity(current_user.id, "USER_DELETED", f"Deleted user {user.email}", company_id=user.company_id)
    flash('User deleted successfully.', 'success')
    return redirect(url_for('admin.users'))


# =========================================
# PAYOUT REQUESTS
# =========================================
@admin_bp.route('/payouts')
@login_required
def payouts():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    payouts = PayoutRequest.query.order_by(PayoutRequest.created_at.desc()).all()
    company_map = {c.id: c.name for c in Company.query.all()}
    user_map = {u.id: u.username for u in User.query.all()}
    return render_template('admin_payouts.html', payouts=payouts, company_map=company_map, user_map=user_map)


@admin_bp.route('/payouts/approve/<int:payout_id>')
@login_required
def approve_payout(payout_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    payout = PayoutRequest.query.get_or_404(payout_id)
    if payout.status != 'pending':
        flash('Payout already processed.', 'info')
        return redirect(url_for('admin.payouts'))

    company = Company.query.get(payout.company_id)
    if not company or company.wallet_balance < payout.amount:
        flash('Insufficient company balance.', 'danger')
        return redirect(url_for('admin.payouts'))

    company.wallet_balance -= payout.amount
    payout.status = 'approved'
    db.session.add(CompanyActivity(
        company_id=company.id,
        action='PAYOUT_APPROVED',
        description=f'Admin approved payout #{payout.id} for company {company.name}'
    ))
    db.session.commit()
    log_activity(current_user.id, "PAYOUT_APPROVED", f"Payout #{payout.id} approved for company {company.id}", company_id=company.id)
    flash('Payout approved.', 'success')
    return redirect(url_for('admin.payouts'))


@admin_bp.route('/payouts/reject/<int:payout_id>')
@login_required
def reject_payout(payout_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    payout = PayoutRequest.query.get_or_404(payout_id)
    payout.status = 'rejected'
    db.session.commit()
    log_activity(current_user.id, "PAYOUT_REJECTED", f"Payout #{payout.id} rejected", company_id=payout.company_id)
    flash('Payout rejected.', 'info')
    return redirect(url_for('admin.payouts'))


# =========================================
# REPORTS
# =========================================
@admin_bp.route('/reports')
@login_required
def reports():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    reports = DailyReport.query.order_by(DailyReport.created_at.desc()).all()
    company_map = {c.id: c.name for c in Company.query.all()}
    user_map = {u.id: u.username for u in User.query.all()}
    return render_template('admin_reports.html', reports=reports, company_map=company_map, user_map=user_map)


@admin_bp.route('/reports/<int:report_id>/download')
@login_required
def download_report(report_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    report = DailyReport.query.get_or_404(report_id)
    if not report.pdf_data:
        flash('No PDF available for this report.', 'danger')
        return redirect(url_for('admin.reports'))

    return send_file(
        BytesIO(report.pdf_data),
        as_attachment=True,
        download_name=report.pdf_filename or "daily_report.pdf",
        mimetype=report.pdf_mimetype or "application/pdf"
    )


@admin_bp.route('/reports/<int:report_id>/delete', methods=['POST'])
@login_required
def delete_report(report_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    report = DailyReport.query.get_or_404(report_id)
    db.session.delete(report)
    db.session.commit()
    flash('Report deleted.', 'success')
    return redirect(url_for('admin.reports'))


@admin_bp.route('/reports/delete-old', methods=['POST'])
@login_required
def delete_old_reports():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    today = datetime.utcnow().date()
    deleted = DailyReport.query.filter(DailyReport.created_at < datetime(today.year, today.month, today.day)).delete(synchronize_session=False)
    db.session.commit()
    flash(f'Deleted {deleted} reports before today.', 'success')
    return redirect(url_for('admin.reports'))


# =========================================
# REFERRAL WITHDRAWALS
# =========================================
@admin_bp.route('/referrals')
@login_required
def referrals():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    requests_list = ReferralWithdrawalRequest.query.order_by(ReferralWithdrawalRequest.created_at.desc()).all()
    user_map = {u.id: u.username for u in User.query.all()}
    return render_template('admin_referrals.html', requests=requests_list, user_map=user_map)


@admin_bp.route('/referrals/approve/<int:request_id>', methods=['POST'])
@login_required
def approve_referral_withdrawal(request_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    request_item = ReferralWithdrawalRequest.query.get_or_404(request_id)
    request_item.status = 'approved'
    db.session.commit()
    flash('Referral withdrawal approved.', 'success')
    return redirect(url_for('admin.referrals'))


@admin_bp.route('/referrals/reject/<int:request_id>', methods=['POST'])
@login_required
def reject_referral_withdrawal(request_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    request_item = ReferralWithdrawalRequest.query.get_or_404(request_id)
    if request_item.status != 'pending':
        return redirect(url_for('admin.referrals'))

    wallet = ReferralWallet.query.filter_by(user_id=request_item.user_id).first()
    if wallet:
        wallet.token_balance += request_item.tokens
    request_item.status = 'rejected'
    db.session.commit()
    flash('Referral withdrawal rejected.', 'info')
    return redirect(url_for('admin.referrals'))


# =========================================
# DISCOUNT REQUESTS
# =========================================
@admin_bp.route('/discount-requests')
@login_required
def discount_requests():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    requests_list = DiscountRequest.query.order_by(DiscountRequest.created_at.desc()).all()
    company_map = {c.id: c.name for c in Company.query.all()}
    user_map = {u.id: u.username for u in User.query.all()}
    return render_template('admin_discount_requests.html', requests=requests_list, company_map=company_map, user_map=user_map)


# =========================================
# BANK TRANSFER APPROVALS
# =========================================
@admin_bp.route('/bank-transfers')
@login_required
def bank_transfers():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))
    transfers = BankTransfer.query.order_by(BankTransfer.created_at.desc()).all()
    company_map = {c.id: c.name for c in Company.query.all()}
    user_map = {u.id: u.username for u in User.query.all()}
    return render_template('admin_bank_transfers.html', transfers=transfers, company_map=company_map, user_map=user_map)


@admin_bp.route('/bank-transfers/approve/<int:transfer_id>')
@login_required
def approve_bank_transfer(transfer_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))
    transfer = BankTransfer.query.get_or_404(transfer_id)
    if transfer.status != 'pending':
        return redirect(url_for('admin.bank_transfers'))
    transfer.status = 'approved'
    company = Company.query.get(transfer.company_id)
    if company:
        distribute_order_amount(order)
    order = Order.query.get(transfer.order_id)
    if order:
        order.status = 'paid'
    db.session.commit()
    log_activity(current_user.id, "BANK_TRANSFER_APPROVED", f"Transfer #{transfer.id} approved", company_id=transfer.company_id)
    buyer = User.query.get(transfer.buyer_id)
    if buyer:
        notify_user(
            buyer,
            "Bank Transfer Approved",
            f"Your bank transfer for order #{transfer.order_id} was approved.",
            f"Bank transfer approved for order #{transfer.order_id}."
        )
    flash('Bank transfer approved.', 'success')
    return redirect(url_for('admin.bank_transfers'))


@admin_bp.route('/bank-transfers/reject/<int:transfer_id>')
@login_required
def reject_bank_transfer(transfer_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))
    transfer = BankTransfer.query.get_or_404(transfer_id)
    transfer.status = 'rejected'
    order = Order.query.get(transfer.order_id)
    if order and order.status == 'pending_verification':
        order.status = 'payment_failed'
    db.session.commit()
    log_activity(current_user.id, "BANK_TRANSFER_REJECTED", f"Transfer #{transfer.id} rejected", company_id=transfer.company_id)
    buyer = User.query.get(transfer.buyer_id)
    if buyer:
        notify_user(
            buyer,
            "Bank Transfer Rejected",
            f"Your bank transfer for order #{transfer.order_id} was rejected. Please contact support.",
            f"Bank transfer rejected for order #{transfer.order_id}."
        )
    flash('Bank transfer rejected.', 'info')
    return redirect(url_for('admin.bank_transfers'))


# =========================================
# ADMIN WITHDRAW FROM COMPANY
# =========================================
@admin_bp.route('/companies/withdraw/<int:company_id>', methods=['POST'])
@login_required
def withdraw_company(company_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))
    amount_raw = request.form.get('amount', '').strip()
    if not amount_raw:
        flash('Please enter a withdrawal amount.', 'danger')
        return redirect(url_for('admin.dashboard'))
    try:
        amount = float(amount_raw)
    except ValueError:
        flash('Invalid amount format.', 'danger')
        return redirect(url_for('admin.dashboard'))
    company = Company.query.get_or_404(company_id)
    if amount <= 0 or company.wallet_balance < amount:
        flash('Invalid amount or insufficient balance.', 'danger')
        return redirect(url_for('admin.dashboard'))
    company.wallet_balance -= amount
    db.session.commit()
    log_activity(current_user.id, "ADMIN_WITHDRAW", f"Withdrew {amount} from company {company.id}", company_id=company.id)
    flash('Withdrawal successful.', 'success')
    return redirect(url_for('admin.dashboard'))


# =========================================
# ACTIVITY LOGS & ANALYTICS
# =========================================
@admin_bp.route('/activities')
@login_required
def activities():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))
    filter_type = request.args.get('type', 'all')
    query = ActivityLog.query.join(User, ActivityLog.actor_id == User.id).filter(User.role == 'manager')
    if filter_type == 'money':
        query = query.filter(ActivityLog.action.like('%PAY%') | ActivityLog.action.like('%TRANSFER%') | ActivityLog.action.like('%WITHDRAW%'))
    elif filter_type == 'auth':
        query = query.filter(ActivityLog.action.like('%LOGIN%') | ActivityLog.action.like('%PASSWORD%'))
    logs = query.order_by(ActivityLog.created_at.desc()).limit(200).all()
    company_map = {c.id: c.name for c in Company.query.all()}
    user_map = {u.id: u.username for u in User.query.filter_by(role='manager').all()}
    return render_template(
        'admin_activities.html',
        logs=logs,
        filter_type=filter_type,
        company_map=company_map,
        user_map=user_map
    )


@admin_bp.route('/analytics')
@login_required
def analytics():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))
    companies = Company.query.all()
    labels = [c.name for c in companies]
    values = [c.wallet_balance for c in companies]
    return render_template('admin_analytics.html', labels=labels, values=values)


# =========================================
# OPay STATUS & REFUND (ADMIN)
# =========================================
@admin_bp.route('/opay/status/<int:order_id>')
@login_required
def admin_opay_status(order_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))
    order = Order.query.get_or_404(order_id)
    response = opay_query_status(str(order.id))
    flash(f"OPay Status: {response}", "info")
    return redirect(url_for('admin.orders'))


@admin_bp.route('/opay/refund/<int:order_id>', methods=['POST'])
@login_required
def admin_opay_refund(order_id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))
    order = Order.query.get_or_404(order_id)
    amount = int(request.form.get('amount', order.total_amount))
    response = opay_refund(str(order.id), amount)
    if response.get("code") == "00000":
        payment = Payment.query.filter_by(order_id=order.id, provider='opay').first()
        if payment:
            payment.status = 'refunded'
        order.status = 'refunded'
        company = Company.query.get(order.company_id)
        if company:
            company.wallet_balance = max(0, company.wallet_balance - amount)
        db.session.commit()
        log_activity(current_user.id, "OPAY_REFUND", f"Refunded order #{order.id}", company_id=order.company_id)
        flash("Refund successful.", "success")
    else:
        flash(f"Refund failed: {response}", "danger")
    return redirect(url_for('admin.orders'))


# =========================================
# DAILY STATEMENT PDF
# =========================================
@admin_bp.route('/statements/daily.pdf')
@login_required
def daily_statement_pdf():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.login'))

    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 800, f"Daily Statement - {datetime.utcnow().date()}")
    y = 770
    p.setFont("Helvetica", 11)
    for log in ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(50).all():
        p.drawString(50, y, f"{log.created_at} - {log.action} - {log.detail}")
        y -= 15
        if y < 50:
            p.showPage()
            y = 800
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="daily_statement.pdf", mimetype="application/pdf")
