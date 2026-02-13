# payments.py
import requests, os, uuid, json, hmac, hashlib
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from extensions import db
from models import Order, CompanyActivity, Payment, Company, BankTransfer
from notifications import notify_user
from activity import log_activity
from opay_api import query_status as opay_query_status, refund as opay_refund
from finance import distribute_order_amount

payments_bp = Blueprint('payments', __name__, template_folder='templates', url_prefix='/payments')


# =========================================
# PAYMENT SELECT PAGE
# =========================================
@payments_bp.route('/pay/<int:order_id>', methods=['GET','POST'])
@login_required
def payment_page(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != current_user.id:
        flash("Access denied", "danger")
        return redirect(url_for('shop.products'))

    if request.method == 'POST':
        method = request.form.get('payment_method')
        if method == "paystack":
            return redirect(url_for('payments.start_paystack', order_id=order.id))
        elif method == "flutterwave":
            return redirect(url_for('payments.start_flutterwave', order_id=order.id))
        elif method == "opay":
            return redirect(url_for('payments.start_opay', order_id=order.id))
        elif method == "bank_transfer":
            return redirect(url_for('payments.bank_transfer', order_id=order.id))

    return render_template("payment_page.html", order=order)


# =========================================
# PAYSTACK START
# =========================================
@payments_bp.route('/paystack/start/<int:order_id>')
@login_required
def start_paystack(order_id):
    order = Order.query.get_or_404(order_id)
    reference = str(uuid.uuid4())

    if not current_app.config.get('PAYSTACK_SECRET_KEY'):
        flash("Paystack key not configured.", "danger")
        return redirect(url_for("payments.payment_page", order_id=order.id))

    headers = {
        "Authorization": f"Bearer {current_app.config['PAYSTACK_SECRET_KEY']}",
        "Content-Type": "application/json"
    }

    data = {
        "email": current_user.email,
        "amount": int(order.total_amount * 100),
        "reference": reference,
        "callback_url": url_for('payments.verify_paystack', _external=True)
    }

    payment = Payment(order_id=order.id, company_id=order.company_id, amount=order.total_amount, provider='paystack', reference=reference)
    db.session.add(payment)
    db.session.commit()

    res = requests.post("https://api.paystack.co/transaction/initialize", json=data, headers=headers)
    response = res.json()

    if response.get("status"):
        return redirect(response["data"]["authorization_url"])
    flash("Payment failed", "danger")
    return redirect(url_for("payments.payment_page", order_id=order.id))


@payments_bp.route('/paystack/verify')
@login_required
def verify_paystack():
    ref = request.args.get("reference")
    headers = {"Authorization": f"Bearer {current_app.config['PAYSTACK_SECRET_KEY']}"}
    res = requests.get(f"https://api.paystack.co/transaction/verify/{ref}", headers=headers)
    data = res.json()

    if data["data"]["status"] == "success":
        payment = Payment.query.filter_by(reference=ref, provider='paystack').first()
        if not payment:
            flash("Payment record not found.", "danger")
            return redirect(url_for("shop.products"))

        order = Order.query.get(payment.order_id)
        if not order:
            flash("Order not found.", "danger")
            return redirect(url_for("shop.products"))

        order.status = "paid"
        payment.status = "paid"
        distribute_order_amount(order)
        db.session.add(CompanyActivity(
            company_id=order.company_id,
            action="PAYMENT_SUCCESS",
            description=f"{current_user.username} paid order #{order.id} via Paystack"
        ))
        db.session.commit()
        log_activity(current_user.id, "PAYSTACK_PAYMENT", f"Order #{order.id} paid", company_id=order.company_id)
        flash("Paystack payment successful", "success")
        notify_user(
            current_user,
            "Payment Successful",
            f"Payment received for order #{order.id}. Amount: ₦{order.total_amount:,.0f}.",
            f"Payment success for order #{order.id}. Amount: ₦{order.total_amount:,.0f}."
        )
        return redirect(url_for("shop.products"))

    flash("Payment verification failed", "danger")
    return redirect(url_for("shop.products"))


# =========================================
# FLUTTERWAVE START
# =========================================
@payments_bp.route('/flutterwave/start/<int:order_id>')
@login_required
def start_flutterwave(order_id):
    order = Order.query.get_or_404(order_id)
    tx_ref = str(uuid.uuid4())

    if not current_app.config.get('FLUTTERWAVE_SECRET_KEY'):
        flash("Flutterwave key not configured.", "danger")
        return redirect(url_for("payments.payment_page", order_id=order.id))

    payload = {
        "tx_ref": tx_ref,
        "amount": order.total_amount,
        "currency": "NGN",
        "redirect_url": url_for("payments.verify_flutterwave", _external=True),
        "customer": {
            "email": current_user.email,
            "name": current_user.username
        },
        "customizations": {"title": "Abils Mall Payment"}
    }

    payment = Payment(order_id=order.id, company_id=order.company_id, amount=order.total_amount, provider='flutterwave', reference=tx_ref)
    db.session.add(payment)
    db.session.commit()

    headers = {
        "Authorization": f"Bearer {current_app.config['FLUTTERWAVE_SECRET_KEY']}",
        "Content-Type": "application/json"
    }

    res = requests.post("https://api.flutterwave.com/v3/payments", json=payload, headers=headers)
    response = res.json()

    if response["status"] == "success":
        return redirect(response["data"]["link"])

    flash("Flutterwave init failed", "danger")
    return redirect(url_for("payments.payment_page", order_id=order.id))


@payments_bp.route('/flutterwave/verify')
@login_required
def verify_flutterwave():
    tx_ref = request.args.get("tx_ref")
    transaction_id = request.args.get("transaction_id")

    headers = {"Authorization": f"Bearer {current_app.config['FLUTTERWAVE_SECRET_KEY']}"}
    res = requests.get(f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify", headers=headers)
    data = res.json()

    if data["data"]["status"] == "successful":
        payment = Payment.query.filter_by(reference=tx_ref, provider='flutterwave').first()
        if not payment:
            flash("Payment record not found.", "danger")
            return redirect(url_for("shop.products"))

        order = Order.query.get(payment.order_id)
        if not order:
            flash("Order not found.", "danger")
            return redirect(url_for("shop.products"))

        order.status = "paid"
        payment.status = "paid"
        distribute_order_amount(order)
        db.session.add(CompanyActivity(
            company_id=order.company_id,
            action="PAYMENT_SUCCESS",
            description=f"{current_user.username} paid order #{order.id} via Flutterwave"
        ))
        db.session.commit()
        log_activity(current_user.id, "FLUTTERWAVE_PAYMENT", f"Order #{order.id} paid", company_id=order.company_id)
        flash("Flutterwave payment successful", "success")
        notify_user(
            current_user,
            "Payment Successful",
            f"Payment received for order #{order.id}. Amount: ₦{order.total_amount:,.0f}.",
            f"Payment success for order #{order.id}. Amount: ₦{order.total_amount:,.0f}."
        )
        return redirect(url_for("shop.products"))


# =========================================
# OPAY START (PLACEHOLDER INTEGRATION)
# =========================================
@payments_bp.route('/opay/start/<int:order_id>')
@login_required
def start_opay(order_id):
    order = Order.query.get_or_404(order_id)
    if not current_app.config.get('OPAY_PUBLIC_KEY') or not current_app.config.get('OPAY_SECRET_KEY'):
        flash("OPay not configured. Add API keys in environment.", "danger")
        return redirect(url_for("payments.payment_page", order_id=order.id))

    payload = {
        "amount": {
            "currency": "NGN",
            "total": int(order.total_amount)
        },
        "callbackUrl": current_app.config.get('OPAY_CALLBACK_URL') or url_for('payments.opay_callback', _external=True),
        "returnUrl": current_app.config.get('OPAY_RETURN_URL') or url_for('payments.payment_page', order_id=order.id, _external=True),
        "cancelUrl": current_app.config.get('OPAY_CANCEL_URL') or url_for('payments.payment_page', order_id=order.id, _external=True),
        "country": "NG",
        "payMethod": current_app.config.get('OPAY_PAY_METHOD', 'BankCard'),
        "product": {
            "name": f"Order #{order.id}",
            "description": "Abils Mall Order"
        },
        "reference": str(order.id)
    }

    payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)

    headers = {
        "Authorization": f"Bearer {current_app.config.get('OPAY_PUBLIC_KEY', '')}",
        "MerchantId": current_app.config.get('OPAY_MERCHANT_ID', ''),
        "Content-Type": "application/json"
    }

    api_base = current_app.config.get('OPAY_API_BASE', 'https://testapi.opaycheckout.com')
    res = requests.post(f"{api_base}/api/v1/international/cashier/create", data=payload_json, headers=headers, timeout=30)
    response = res.json()

    if response.get("code") == "00000":
        data = response.get("data", {})
        order.payment_reference = str(order.id)
        payment = Payment(order_id=order.id, company_id=order.company_id, amount=order.total_amount, provider='opay', reference=str(order.id), status='pending')
        db.session.add(payment)
        db.session.commit()

        cashier_url = data.get("cashierUrl")
        if cashier_url:
            return redirect(cashier_url)

        qr_code = data.get("nextAction", {}).get("qrCode", "")
        if qr_code:
            return render_template("opay_qr.html", order=order, qr_code=qr_code)

    flash("OPay initialization failed. Please try another method.", "danger")
    return redirect(url_for("payments.payment_page", order_id=order.id))


# =========================================
# BANK TRANSFER (MANUAL VERIFICATION)
# =========================================
@payments_bp.route('/bank-transfer/<int:order_id>', methods=['GET', 'POST'])
@login_required
def bank_transfer(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != current_user.id:
        flash("Access denied", "danger")
        return redirect(url_for('shop.products'))

    if request.method == 'POST':
        proof = request.files.get('proof')
        proof_path = ''
        if proof:
            filename = f"transfer_{order.id}_{uuid.uuid4().hex}.png"
            upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            proof.save(upload_path)
            proof_path = upload_path.replace("\\", "/")

        transfer = BankTransfer(
            order_id=order.id,
            buyer_id=current_user.id,
            company_id=order.company_id,
            amount=order.total_amount,
            proof_path=proof_path
        )
        order.status = 'pending_verification'
        db.session.add(transfer)
        db.session.commit()
        log_activity(current_user.id, "BANK_TRANSFER_SUBMITTED", f"Transfer for order #{order.id} submitted", company_id=order.company_id)
        flash("Bank transfer submitted. Await admin approval.", "success")
        return redirect(url_for('shop.orders'))

    bank_info = {
        "bank": current_app.config['BANK_TRANSFER_BANK'],
        "account_name": current_app.config['BANK_TRANSFER_ACCOUNT_NAME'],
        "account_number": current_app.config['BANK_TRANSFER_ACCOUNT_NUMBER']
    }
    return render_template("bank_transfer.html", order=order, bank_info=bank_info)


# =========================================
# OPAY CALLBACK
# =========================================
@payments_bp.route('/opay/callback', methods=['POST'])
def opay_callback():
    data = request.get_json(silent=True) or {}
    payload = data.get("payload", {})
    sha = data.get("sha512", "")

    refunded_value = payload.get("refunded")
    refunded = "t" if refunded_value in [True, "true", "TRUE", "t", "T", 1, "1"] else "f"

    signature_payload = dict(payload)
    signature_payload["refunded"] = refunded
    auth_json = json.dumps(signature_payload, separators=(',', ':'), sort_keys=True)

    expected = hmac.new(
        current_app.config.get('OPAY_SECRET_KEY', '').encode(),
        auth_json.encode(),
        hashlib.sha3_512
    ).hexdigest()

    if expected != sha:
        return "Invalid signature", 400

    reference = payload.get("reference")
    order = None
    if reference and str(reference).isdigit():
        order = Order.query.get(int(reference))
    if not order:
        order = Order.query.filter_by(payment_reference=reference).first()

    if not order:
        return "Order not found", 404

    if payload.get("status") == "SUCCESS":
        order.status = "paid"
        payment = Payment.query.filter_by(order_id=order.id, provider='opay').first()
        if payment:
            payment.status = "paid"
        distribute_order_amount(order)
        db.session.commit()
        log_activity(order.buyer_id, "OPAY_PAYMENT", f"Order #{order.id} paid", company_id=order.company_id)
        buyer = order.buyer
        if buyer:
            notify_user(
                buyer,
                "Payment Successful",
                f"OPay payment received for order #{order.id}. Amount: ₦{order.total_amount:,.0f}.",
                f"OPay payment success for order #{order.id}. Amount: ₦{order.total_amount:,.0f}."
            )
        return "OK", 200

    return "Ignored", 200


# =========================================
# OPAY STATUS QUERY (ADMIN/MANAGER)
# =========================================
@payments_bp.route('/opay/status/<reference>')
@login_required
def opay_status(reference):
    response = opay_query_status(reference)
    return response, 200


# =========================================
# OPAY REFUND (ADMIN ONLY)
# =========================================
@payments_bp.route('/opay/refund/<reference>', methods=['POST'])
@login_required
def opay_refund_route(reference):
    amount = int(request.form.get('amount', 0))
    if amount <= 0:
        return {"status": "error", "message": "Invalid amount"}, 400
    response = opay_refund(reference, amount)
    return response, 200

    flash("Payment failed", "danger")
    return redirect(url_for("shop.products"))
