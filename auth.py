from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import re
from PIL import Image
from extensions import db
from models import User, Company, Referral, ReferralWallet, ReferralWithdrawalRequest, CompanyActivity, OtpVerification, ActivityLog
from notifications import notify_user, send_email, send_sms
import os
import uuid
from datetime import datetime, timedelta
from models import PasswordResetToken
from activity import log_activity

auth_bp = Blueprint('auth', __name__, template_folder='templates')
ALLOWED_AVATAR_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}
REFERRAL_TOKEN_VALUE = 100
REFERRAL_MIN_TOKENS = 20
REFERRAL_REWARD_TOKENS = 2
OTP_TTL_MINUTES = 10
PASSWORD_RULES = {
    "min_len": 8,
    "upper": re.compile(r"[A-Z]"),
    "lower": re.compile(r"[a-z]"),
    "digit": re.compile(r"\d"),
    "special": re.compile(r"[^\w\s]"),
}


def _is_strong_password(password):
    if not password or len(password) < PASSWORD_RULES["min_len"]:
        return False
    if not PASSWORD_RULES["upper"].search(password):
        return False
    if not PASSWORD_RULES["lower"].search(password):
        return False
    if not PASSWORD_RULES["digit"].search(password):
        return False
    if not PASSWORD_RULES["special"].search(password):
        return False
    return True


def _get_file_size(file_storage):
    try:
        pos = file_storage.stream.tell()
        file_storage.stream.seek(0, os.SEEK_END)
        size = file_storage.stream.tell()
        file_storage.stream.seek(pos)
        return size
    except Exception:
        return 0


def _process_avatar(file_storage):
    file_storage.stream.seek(0)
    img = Image.open(file_storage.stream)
    img = img.convert("RGBA")
    # Center-crop to square
    width, height = img.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((256, 256), Image.LANCZOS)

    # Flatten transparency to white background for JPEG
    background = Image.new("RGB", img.size, (255, 255, 255))
    background.paste(img, mask=img.split()[3])
    return background

# ... rest of auth routes ...

# ==================================
# REGISTER
# ==================================
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        username = request.form['username']
        email    = request.form['email']
        phone    = request.form.get('phone', '').strip()
        password = request.form['password']
        role     = 'buyer'  # PUBLIC can only register as buyers
        ref_code = request.form.get('ref', '').strip()

        if not _is_strong_password(password):
            flash("Password must be at least 8 characters and include upper, lower, number, and symbol.", "danger")
            return redirect(url_for('auth.register'))

        if User.query.filter((User.username==username)|(User.email==email)).first():
            flash("Username or email already exists.", "danger")
            return redirect(url_for('auth.register'))

        new_user = User(
            username=username,
            email=email,
            phone=phone,
            password_hash=generate_password_hash(password),
            role=role,
            is_verified=False
        )
        db.session.add(new_user)
        db.session.commit()

        referrer_id = None
        if ref_code:
            referrer = User.query.filter_by(username=ref_code).first()
            if referrer and referrer.id != new_user.id:
                referrer_id = referrer.id

        OtpVerification.query.filter_by(user_id=new_user.id).delete()
        otp = f"{uuid.uuid4().int % 1000000:06d}"
        otp_hash = generate_password_hash(otp)
        expires_at = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)
        db.session.add(OtpVerification(
            user_id=new_user.id,
            otp_hash=otp_hash,
            referrer_id=referrer_id,
            expires_at=expires_at
        ))
        db.session.commit()

        email_ok = send_email(
            new_user.email,
            "Verify your account",
            f"Your OTP is {otp}. It expires in {OTP_TTL_MINUTES} minutes.",
            enabled=True,
        )
        sms_ok = send_sms(
            new_user.phone,
            f"Your Abils Mall OTP is {otp}. Expires in {OTP_TTL_MINUTES} minutes.",
            enabled=True,
        )
        if not email_ok and not sms_ok:
            flash(
                "OTP could not be delivered. Check email/SMS settings or try resend.",
                "warning",
            )

        notify_user(
            new_user,
            "Welcome to Abils Mall",
            f"Hi {new_user.username}, your account has been created successfully.",
            "Your Abils Mall account has been created successfully."
        )
        log_activity(new_user.id, "ACCOUNT_CREATED", f"Account created for {new_user.email}")
        flash("Account created. Please verify with the OTP sent to your email and phone.", "success")
        return redirect(url_for('auth.verify_otp', user_id=new_user.id))

    return render_template('register.html', ref_code=request.args.get('ref', '').strip())


# ==================================
# LOGIN
# ==================================
@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        identity = request.form['email_or_username']
        password = request.form['password']

        user = User.query.filter((User.email==identity)|(User.username==identity)).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid login credentials.", "danger")
            return redirect(url_for('auth.login'))

        if not user.is_verified:
            flash("Account pending verification. Enter OTP to verify.", "warning")
            return redirect(url_for('auth.verify_otp', user_id=user.id))

        login_user(user)
        log_activity(user.id, "LOGIN", f"User logged in: {user.email}", company_id=user.company_id)

        if user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif user.role == 'manager':
            return redirect(url_for('manager.dashboard'))
        else:
            return redirect(url_for('shop.products'))

    return render_template('login.html')


# ==================================
# LOGOUT
# ==================================
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for('auth.login'))


# ==================================
# PROFILE / NOTIFICATION SETTINGS
# ==================================
@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.phone = request.form.get('phone', '').strip()
        current_user.notify_email = True if request.form.get('notify_email') == 'on' else False
        current_user.notify_sms = True if request.form.get('notify_sms') == 'on' else False

        avatar_file = request.files.get('avatar')
        remove_avatar = request.form.get('remove_avatar') == 'on'

        if avatar_file and avatar_file.filename:
            filename = secure_filename(avatar_file.filename)
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            if ext not in ALLOWED_AVATAR_EXTS:
                flash("Avatar must be an image file (png, jpg, jpeg, gif, webp).", "danger")
                return redirect(url_for('auth.profile'))

            max_bytes = current_app.config.get('AVATAR_MAX_BYTES', 2 * 1024 * 1024)
            file_size = _get_file_size(avatar_file)
            if file_size and file_size > max_bytes:
                flash("Avatar file too large. Please upload an image under 2MB.", "danger")
                return redirect(url_for('auth.profile'))

            unique_name = f"{uuid.uuid4().hex}.jpg"
            upload_dir = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
            if not os.path.isabs(upload_dir):
                upload_dir = os.path.join(current_app.root_path, upload_dir)
            os.makedirs(upload_dir, exist_ok=True)

            avatar_path = os.path.join(upload_dir, unique_name)
            try:
                processed = _process_avatar(avatar_file)
                processed.save(avatar_path, format="JPEG", quality=88, optimize=True)
            except Exception:
                flash("Unable to process that image. Please try another file.", "danger")
                return redirect(url_for('auth.profile'))

            # Remove old avatar file if it exists in uploads
            if current_user.avatar_path and current_user.avatar_path.startswith("uploads/"):
                old_full = os.path.join(current_app.root_path, 'static', current_user.avatar_path)
                if os.path.isfile(old_full):
                    os.remove(old_full)

            current_user.avatar_path = f"uploads/{unique_name}"
        elif remove_avatar:
            if current_user.avatar_path and current_user.avatar_path.startswith("uploads/"):
                old_full = os.path.join(current_app.root_path, 'static', current_user.avatar_path)
                if os.path.isfile(old_full):
                    os.remove(old_full)
            current_user.avatar_path = None

        db.session.commit()
        log_activity(current_user.id, "PROFILE_UPDATED", "Updated profile and notification preferences", company_id=current_user.company_id)
        flash("Profile updated.", "success")
        return redirect(url_for('auth.profile'))

    activities = []
    unread_count = None
    if current_user.role == 'buyer':
        last_seen_raw = session.get('buyer_last_seen_activity')
        last_seen = None
        if last_seen_raw:
            try:
                last_seen = datetime.fromisoformat(last_seen_raw)
            except ValueError:
                session.pop('buyer_last_seen_activity', None)

        activities_query = ActivityLog.query.filter(
            ActivityLog.actor_id == current_user.id
        ).order_by(ActivityLog.created_at.desc())
        activities = activities_query.limit(20).all()
        if last_seen:
            unread_count = ActivityLog.query.filter(
                ActivityLog.actor_id == current_user.id,
                ActivityLog.created_at > last_seen
            ).count()
        else:
            unread_count = ActivityLog.query.filter(
                ActivityLog.actor_id == current_user.id
            ).count()

    return render_template('profile.html', activities=activities, unread_count=unread_count)


@auth_bp.route('/activities')
@login_required
def activities():
    if current_user.role != 'buyer':
        flash("Access denied.", "danger")
        return redirect(url_for('auth.profile'))

    last_seen_raw = session.get('buyer_last_seen_activity')
    last_seen = None
    if last_seen_raw:
        try:
            last_seen = datetime.fromisoformat(last_seen_raw)
        except ValueError:
            session.pop('buyer_last_seen_activity', None)

    activities_query = ActivityLog.query.filter(
        ActivityLog.actor_id == current_user.id
    ).order_by(ActivityLog.created_at.desc())
    activities_list = activities_query.limit(200).all()
    if last_seen:
        unread_count = ActivityLog.query.filter(
            ActivityLog.actor_id == current_user.id,
            ActivityLog.created_at > last_seen
        ).count()
    else:
        unread_count = ActivityLog.query.filter(
            ActivityLog.actor_id == current_user.id
        ).count()

    return render_template('buyer_activities.html', activities=activities_list, unread_count=unread_count)


@auth_bp.route('/activities/mark-seen', methods=['POST'])
@login_required
def mark_buyer_activities_seen():
    if current_user.role != 'buyer':
        flash("Access denied.", "danger")
        return redirect(url_for('auth.profile'))

    session['buyer_last_seen_activity'] = datetime.utcnow().isoformat()
    return redirect(url_for('auth.activities'))


# ==================================
# REFERRALS
# ==================================
@auth_bp.route('/referrals', methods=['GET'])
@login_required
def referrals():
    if current_user.role not in {'buyer', 'manager'}:
        flash("Access denied.", "danger")
        return redirect(url_for('auth.profile'))

    wallet = ReferralWallet.query.filter_by(user_id=current_user.id).first()
    if not wallet:
        wallet = ReferralWallet(user_id=current_user.id, token_balance=0, total_earned=0)
        db.session.add(wallet)
        db.session.commit()

    referrals = Referral.query.filter_by(referrer_id=current_user.id).order_by(Referral.created_at.desc()).all()
    referred_ids = [ref.referred_id for ref in referrals]
    referred_users = {u.id: u.username for u in User.query.filter(User.id.in_(referred_ids)).all()} if referred_ids else {}
    pending_requests = ReferralWithdrawalRequest.query.filter_by(user_id=current_user.id, status='pending').all()
    token_balance = wallet.token_balance
    progress = min(100, int((token_balance / REFERRAL_MIN_TOKENS) * 100)) if REFERRAL_MIN_TOKENS else 0
    progress_level = 0
    if progress >= 100:
        progress_level = 4
    elif progress >= 75:
        progress_level = 3
    elif progress >= 50:
        progress_level = 2
    elif progress >= 25:
        progress_level = 1

    return render_template(
        'referrals.html',
        referral_link=f"{request.host_url}register?ref={current_user.username}",
        token_balance=token_balance,
        token_value=REFERRAL_TOKEN_VALUE,
        min_tokens=REFERRAL_MIN_TOKENS,
        referrals=referrals,
        referred_users=referred_users,
        pending_requests=pending_requests,
        progress=progress,
        progress_level=progress_level
    )


# ==================================
# OTP VERIFICATION
# ==================================
@auth_bp.route('/verify-otp/<int:user_id>', methods=['GET', 'POST'])
def verify_otp(user_id):
    user = User.query.get_or_404(user_id)
    otp_record = OtpVerification.query.filter_by(user_id=user.id).order_by(OtpVerification.created_at.desc()).first()
    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()
        if not otp_record or otp_record.expires_at < datetime.utcnow():
            flash("OTP expired. Please request a new one.", "danger")
            return redirect(url_for('auth.verify_otp', user_id=user.id))
        if not check_password_hash(otp_record.otp_hash, otp):
            flash("Invalid OTP.", "danger")
            return redirect(url_for('auth.verify_otp', user_id=user.id))

        user.is_verified = True
        if otp_record.referrer_id:
            referrer = User.query.get(otp_record.referrer_id)
            existing_ref = Referral.query.filter_by(referrer_id=otp_record.referrer_id, referred_id=user.id).first()
            if not existing_ref:
                db.session.add(Referral(referrer_id=otp_record.referrer_id, referred_id=user.id))
                wallet = ReferralWallet.query.filter_by(user_id=otp_record.referrer_id).first()
                if not wallet:
                    wallet = ReferralWallet(user_id=otp_record.referrer_id, token_balance=0, total_earned=0)
                    db.session.add(wallet)
                wallet.token_balance += REFERRAL_REWARD_TOKENS
                wallet.total_earned += REFERRAL_REWARD_TOKENS
                if referrer:
                    db.session.add(CompanyActivity(
                        company_id=referrer.company_id,
                        action='REFERRAL_REWARD',
                        description=f'Referral reward: {REFERRAL_REWARD_TOKENS} tokens for {referrer.username}'
                    ))
        db.session.delete(otp_record)
        db.session.commit()
        flash("Account verified. Please log in.", "success")
        return redirect(url_for('auth.login'))

    return render_template('verify_otp.html', user=user)


@auth_bp.route('/resend-otp/<int:user_id>', methods=['POST'])
def resend_otp(user_id):
    user = User.query.get_or_404(user_id)
    otp_record = OtpVerification.query.filter_by(user_id=user.id).order_by(OtpVerification.created_at.desc()).first()
    referrer_id = otp_record.referrer_id if otp_record else None
    OtpVerification.query.filter_by(user_id=user.id).delete()
    otp = f"{uuid.uuid4().int % 1000000:06d}"
    otp_hash = generate_password_hash(otp)
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)
    db.session.add(OtpVerification(
        user_id=user.id,
        otp_hash=otp_hash,
        referrer_id=referrer_id,
        expires_at=expires_at
    ))
    db.session.commit()

    email_ok = send_email(
        user.email,
        "Verify your account",
        f"Your OTP is {otp}. It expires in {OTP_TTL_MINUTES} minutes.",
        enabled=True,
    )
    sms_ok = send_sms(
        user.phone,
        f"Your Abils Mall OTP is {otp}. Expires in {OTP_TTL_MINUTES} minutes.",
        enabled=True,
    )
    if not email_ok and not sms_ok:
        flash(
            "OTP could not be delivered. Check email/SMS settings or try resend.",
            "warning",
        )
    flash("OTP resent.", "success")
    return redirect(url_for('auth.verify_otp', user_id=user.id))


@auth_bp.route('/referrals/withdraw', methods=['POST'])
@login_required
def referral_withdraw():
    if current_user.role not in {'buyer', 'manager'}:
        flash("Access denied.", "danger")
        return redirect(url_for('auth.referrals'))

    wallet = ReferralWallet.query.filter_by(user_id=current_user.id).first()
    if not wallet:
        flash("No referral wallet found.", "danger")
        return redirect(url_for('auth.referrals'))

    if wallet.token_balance < REFERRAL_MIN_TOKENS:
        flash(f"Minimum withdrawal is {REFERRAL_MIN_TOKENS} tokens.", "danger")
        return redirect(url_for('auth.referrals'))

    amount = wallet.token_balance * REFERRAL_TOKEN_VALUE
    tokens = wallet.token_balance
    wallet.token_balance = 0
    request_item = ReferralWithdrawalRequest(
        user_id=current_user.id,
        tokens=tokens,
        amount=amount,
        status='pending'
    )
    db.session.add(request_item)
    db.session.add(CompanyActivity(
        company_id=current_user.company_id,
        action='REFERRAL_WITHDRAW_REQUESTED',
        description=f'Referral withdrawal requested: {tokens} tokens by {current_user.username}'
    ))
    db.session.commit()
    flash("Withdrawal request submitted.", "success")
    return redirect(url_for('auth.referrals'))


# ==================================
# ADMIN PASSWORD RESET (ONE-TIME)
# ==================================
@auth_bp.route('/reset-admin', methods=['GET', 'POST'])
def reset_admin():
    token = request.args.get('token') or request.form.get('token')
    expected = os.getenv('RESET_ADMIN_TOKEN', '')
    if not expected or token != expected:
        return "Unauthorized", 403

    admin_user = User.query.filter_by(role='admin').first()
    if not admin_user:
        return "No admin user found", 404

    if request.method == 'POST':
        new_password = request.form.get('password', '')
        if len(new_password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for('auth.reset_admin', token=token))
        admin_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        log_activity(admin_user.id, "ADMIN_PASSWORD_RESET", "Admin password reset")
        flash("Admin password updated. Please log in.", "success")
        return redirect(url_for('auth.login'))

    return render_template('reset_admin.html', token=token)


# ==================================
# FORGOT PASSWORD
# ==================================
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("If that email exists, a reset link was sent.", "info")
            return redirect(url_for('auth.forgot_password'))

        token = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=2)
        reset = PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at)
        db.session.add(reset)
        db.session.commit()

        reset_link = f"{os.getenv('RESET_URL_BASE', 'http://127.0.0.1:5000')}/reset-password/{token}"
        send_email(user.email, "Password Reset", f"Click to reset your password: {reset_link}", enabled=True)
        log_activity(user.id, "PASSWORD_RESET_REQUEST", "Requested password reset")
        flash("Reset link sent to your email.", "success")
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    reset = PasswordResetToken.query.filter_by(token=token).first()
    if not reset or reset.expires_at < datetime.utcnow():
        flash("Reset link expired.", "danger")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        new_password = request.form.get('password', '')
        user = User.query.get(reset.user_id)
        if not user or len(new_password) < 6:
            flash("Invalid password.", "danger")
            return redirect(url_for('auth.reset_password', token=token))

        user.password_hash = generate_password_hash(new_password)
        db.session.delete(reset)
        db.session.commit()
        log_activity(user.id, "PASSWORD_RESET", "Password reset via email link")
        flash("Password updated. Please log in.", "success")
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)


# ==================================
# CHANGE PASSWORD (LOGGED IN)
# ==================================
@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        if not check_password_hash(current_user.password_hash, current):
            flash("Current password incorrect.", "danger")
            return redirect(url_for('auth.change_password'))
        if len(new_password) < 6:
            flash("New password too short.", "danger")
            return redirect(url_for('auth.change_password'))
        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        log_activity(current_user.id, "PASSWORD_CHANGED", "Password changed while logged in")
        flash("Password changed successfully.", "success")
        return redirect(url_for('auth.profile'))

    return render_template('change_password.html')
