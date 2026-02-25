# shop.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
import os
from sqlalchemy import func

from extensions import db
from models import Product, ProductReview, CartItem, Order, OrderItem, CompanyActivity, DiscountCustomer, DiscountRequest, WalletTransaction, User, ActivityLog, ReferralWallet, ManagerAccountRequest
from notifications import notify_user, send_email
from activity import log_activity

shop_bp = Blueprint('shop', __name__, template_folder='templates', url_prefix='/shop')


# =========================================
# BUYER: DASHBOARD
# =========================================
@shop_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'buyer':
        flash('Access denied.', 'danger')
        return redirect(url_for('shop.products'))

    total_orders = Order.query.filter_by(buyer_id=current_user.id).count()
    pending_orders = Order.query.filter_by(buyer_id=current_user.id, status='pending').count()
    total_spent = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)).filter(
        Order.buyer_id == current_user.id
    ).scalar() or 0
    cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
    recent_orders = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.created_at.desc()).limit(6).all()
    recent_activities = ActivityLog.query.filter_by(actor_id=current_user.id).order_by(ActivityLog.created_at.desc()).limit(6).all()
    referral_wallet = ReferralWallet.query.filter_by(user_id=current_user.id).first()
    referral_tokens = referral_wallet.token_balance if referral_wallet else 0
    manager_request = ManagerAccountRequest.query.filter_by(user_id=current_user.id).order_by(
        ManagerAccountRequest.created_at.desc()
    ).first()

    return render_template(
        'buyer_dashboard.html',
        total_orders=total_orders,
        pending_orders=pending_orders,
        total_spent=total_spent,
        cart_count=cart_count,
        recent_orders=recent_orders,
        recent_activities=recent_activities,
        referral_tokens=referral_tokens,
        manager_request=manager_request
    )


# =========================================
# VIEW ALL PRODUCTS
# =========================================
@shop_bp.route('/products')
def products():
    all_products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('shop_products.html', products=all_products)


@shop_bp.route('/products/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('shop_product_detail.html', product=product)


# =========================================
# ADD PRODUCT TO CART
# =========================================
@shop_bp.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = int(request.form.get('quantity', 1))

    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=quantity)
        db.session.add(cart_item)

    db.session.add(CompanyActivity(
        company_id=product.company_id,
        action='CART_ADD',
        description=f'User {current_user.username} added {quantity} x {product.name} to cart'
    ))

    db.session.commit()
    flash(f'Added {quantity} x "{product.name}" to cart.', 'success')
    return redirect(url_for('shop.products'))


# =========================================
# VIEW CART
# =========================================
@shop_bp.route('/cart')
@login_required
def cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    subtotal = sum((item.product.sale_price or item.product.price) * item.quantity for item in cart_items)
    shipping_fee = 0.0
    total = subtotal + shipping_fee
    return render_template(
        'shop_cart.html',
        cart_items=cart_items,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        total=total
    )


# =========================================
# UPDATE CART ITEM QUANTITY
# =========================================
@shop_bp.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    cart_item = CartItem.query.get_or_404(item_id)
    if cart_item.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('shop.cart'))

    quantity = int(request.form.get('quantity', 1))
    if quantity <= 0:
        db.session.delete(cart_item)
        flash(f'Removed {cart_item.product.name} from cart.', 'info')
    else:
        cart_item.quantity = quantity
        flash(f'Updated quantity for {cart_item.product.name}.', 'success')

    db.session.commit()
    return redirect(url_for('shop.cart'))


# =========================================
# REMOVE ITEM FROM CART
# =========================================
@shop_bp.route('/cart/remove/<int:item_id>')
@login_required
def remove_from_cart(item_id):
    cart_item = CartItem.query.get_or_404(item_id)
    if cart_item.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('shop.cart'))

    db.session.delete(cart_item)
    db.session.add(CompanyActivity(
        company_id=cart_item.product.company_id,
        action='CART_REMOVE',
        description=f'User {current_user.username} removed {cart_item.product.name} from cart'
    ))

    db.session.commit()
    flash('Item removed from cart.', 'info')
    return redirect(url_for('shop.cart'))


# =========================================
# CHECKOUT PAGE
# =========================================
@shop_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('shop.products'))

    if request.method == 'POST':
        company_id = cart_items[0].product.company_id
        if any(item.product.company_id != company_id for item in cart_items):
            flash('Please checkout items from one company at a time.', 'danger')
            return redirect(url_for('shop.cart'))

        subtotal = sum((item.product.sale_price or item.product.price) * item.quantity for item in cart_items)
        total_weight_grams = sum((item.product.weight_grams or 0) * item.quantity for item in cart_items)
        distance_km = float(request.form.get('distance_km', 0) or 0)
        rate_per_gram = float(os.getenv("SHIPPING_RATE_PER_GRAM", "0.5") or 0.5)
        rate_per_km = float(os.getenv("SHIPPING_RATE_PER_KM", "10") or 10)
        shipping_fee = (total_weight_grams * rate_per_gram) + (distance_km * rate_per_km)
        discount = 0.0
        discount_customer = DiscountCustomer.query.filter_by(
            buyer_id=current_user.id,
            company_id=company_id,
            approved=True
        ).first()
        if discount_customer and discount_customer.discount_rate:
            discount = subtotal * (discount_customer.discount_rate / 100.0)

        total_amount = max(subtotal - discount, 0) + shipping_fee
        order = Order(
            buyer_id=current_user.id,
            company_id=company_id,
            total_amount=total_amount,
            delivery_country=request.form.get('country', '').strip(),
            delivery_state=request.form.get('state', '').strip(),
            delivery_area=request.form.get('area', '').strip(),
            delivery_bus_stop=request.form.get('bus_stop', '').strip(),
            delivery_address=request.form.get('address', '').strip(),
            delivery_phone=request.form.get('delivery_phone', '').strip(),
            delivery_map_url=request.form.get('map_url', '').strip(),
            delivery_distance_km=distance_km,
            shipping_fee=shipping_fee,
            total_weight_grams=total_weight_grams
        )
        db.session.add(order)
        db.session.commit()

        for item in cart_items:
            item_price = item.product.sale_price or item.product.price
            order_item = OrderItem(order_id=order.id, product_id=item.product.id,
                                   quantity=item.quantity, price=item_price)
            db.session.add(order_item)
            db.session.delete(item)  # Remove item from cart

        db.session.add(CompanyActivity(
            company_id=order.company_id,
            action='ORDER_PLACED',
            description=f'User {current_user.username} placed order #{order.id}'
        ))

        db.session.commit()
        flash('Order placed successfully! Proceed to payment.', 'success')
        log_activity(current_user.id, "ORDER_PLACED", f"Order #{order.id} placed", company_id=order.company_id)
        notify_user(
            current_user,
            "Order Placed",
            f"Your order #{order.id} was placed successfully. Total: ₦{order.total_amount:,.0f}.",
            f"Order #{order.id} placed. Total: ₦{order.total_amount:,.0f}."
        )
        return redirect(url_for('payments.payment_page', order_id=order.id))

    subtotal = sum((item.product.sale_price or item.product.price) * item.quantity for item in cart_items)
    total_weight_grams = sum((item.product.weight_grams or 0) * item.quantity for item in cart_items)
    rate_per_gram = float(os.getenv("SHIPPING_RATE_PER_GRAM", "0.5") or 0.5)
    rate_per_km = float(os.getenv("SHIPPING_RATE_PER_KM", "10") or 10)
    shipping_fee = 0.0
    total = subtotal + shipping_fee
    company = cart_items[0].product.company if cart_items else None
    store_lat = company.pickup_lat if company and company.pickup_lat is not None else 0
    store_lng = company.pickup_lng if company and company.pickup_lng is not None else 0
    return render_template(
        'checkout.html',
        cart_items=cart_items,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        total=total,
        total_weight_grams=total_weight_grams,
        rate_per_gram=rate_per_gram,
        rate_per_km=rate_per_km,
        store_lat=store_lat,
        store_lng=store_lng,
        company=company
    )


# =========================================
# BUYER: ORDERS
# =========================================
@shop_bp.route('/orders')
@login_required
def orders():
    orders = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('buyer_orders.html', orders=orders)


@shop_bp.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('shop.orders'))
    return render_template('buyer_order_detail.html', order=order)


# =========================================
# BUYER: DISCOUNT REQUEST
# =========================================
@shop_bp.route('/discounts/request/<int:company_id>')
@login_required
def request_discount(company_id):
    existing = DiscountRequest.query.filter_by(
        buyer_id=current_user.id,
        company_id=company_id,
        status='pending'
    ).first()
    if existing:
        flash('Discount request already pending.', 'info')
        return redirect(url_for('shop.products'))

    request_item = DiscountRequest(buyer_id=current_user.id, company_id=company_id)
    db.session.add(request_item)
    db.session.add(CompanyActivity(
        company_id=company_id,
        action='DISCOUNT_REQUESTED',
        description=f'Buyer {current_user.username} requested discount'
    ))
    db.session.commit()
    log_activity(current_user.id, "DISCOUNT_REQUESTED", f"Discount requested for company {company_id}", company_id=company_id)
    flash('Discount request submitted.', 'success')
    return redirect(url_for('shop.products'))


# =========================================
# BUYER: SUBMIT PRODUCT REVIEW
# =========================================
@shop_bp.route('/reviews/submit', methods=['POST'])
@login_required
def submit_review():
    product_id = request.form.get('product_id', '').strip()
    rating = request.form.get('rating', '').strip()
    review = request.form.get('review', '').strip()
    next_url = request.form.get('next', '').strip()

    if not product_id.isdigit():
        flash('Invalid product.', 'danger')
        return redirect(url_for('shop.products'))
    if rating not in {'1', '2', '3', '4', '5'}:
        flash('Please select a rating.', 'danger')
        return redirect(url_for('shop.products'))
    if not review:
        flash('Please write a review.', 'danger')
        return redirect(url_for('shop.products'))

    product = Product.query.get(int(product_id))
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('shop.products'))

    existing_review = ProductReview.query.filter_by(
        product_id=product.id,
        user_id=current_user.id
    ).first()
    if existing_review:
        existing_review.rating = int(rating)
        existing_review.review_text = review
    else:
        db.session.add(ProductReview(
            product_id=product.id,
            user_id=current_user.id,
            rating=int(rating),
            review_text=review
        ))

    avg_rating, review_count = db.session.query(
        func.avg(ProductReview.rating),
        func.count(ProductReview.id)
    ).filter(ProductReview.product_id == product.id).first()
    product.rating_avg = round(float(avg_rating or 4.0), 1)
    product.rating_count = int(review_count or 0)

    admins = User.query.filter_by(role='admin').all()
    subject = f"New Product Review: {product.name}"
    body = (
        f"Product: {product.name}\n"
        f"Product ID: {product.id}\n"
        f"Company ID: {product.company_id}\n"
        f"Reviewer: {current_user.username} ({current_user.email})\n"
        f"Rating: {rating}/5\n\n"
        f"Review:\n{review}\n"
    )
    for admin in admins:
        send_email(admin.email, subject, body, enabled=True)

    db.session.commit()
    flash('Review submitted. Thank you!', 'success')
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect(url_for('shop.products'))


# =========================================
# BUYER: WALLET
# =========================================
@shop_bp.route('/wallet', methods=['GET', 'POST'])
@login_required
def wallet():
    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        if amount <= 0:
            flash('Invalid amount.', 'danger')
            return redirect(url_for('shop.wallet'))

        current_user.wallet_balance += amount
        db.session.add(WalletTransaction(
            user_id=current_user.id,
            amount=amount,
            tx_type='credit',
            description='Wallet top-up'
        ))
        db.session.commit()
        log_activity(current_user.id, "WALLET_TOPUP", f"Wallet topup ₦{amount:,.0f}", company_id=current_user.company_id)
        flash('Wallet topped up successfully.', 'success')
        return redirect(url_for('shop.wallet'))

    transactions = WalletTransaction.query.filter_by(user_id=current_user.id).order_by(WalletTransaction.created_at.desc()).all()
    return render_template('buyer_wallet.html', transactions=transactions)
