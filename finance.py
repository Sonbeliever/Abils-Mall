from extensions import db
from models import User, Company, Order, OrderItem, Product, CompanyActivity


def distribute_order_amount(order):
    if not order:
        return

    items = OrderItem.query.filter_by(order_id=order.id).all()
    if not items:
        return

    subtotal = sum(item.price * item.quantity for item in items)
    ratio = (order.total_amount / subtotal) if subtotal > 0 else 1.0

    for item in items:
        product = Product.query.get(item.product_id)
        item_total = item.price * item.quantity
        adjusted_total = item_total * ratio
        if not product or not product.manager_id:
            company = Company.query.get(order.company_id)
            if company:
                company.wallet_balance += adjusted_total
            continue

        manager = User.query.get(product.manager_id)
        company = Company.query.get(order.company_id)

        commission_rate = manager.commission_rate if manager and manager.commission_rate is not None else 0
        company_share = adjusted_total * (commission_rate / 100.0)
        manager_share = adjusted_total - company_share

        if company:
            company.wallet_balance += company_share
        if manager:
            manager.wallet_balance += manager_share

    db.session.add(CompanyActivity(
        company_id=order.company_id,
        action="PAYMENT_DISTRIBUTED",
        description=f"Distributed payment for order #{order.id}"
    ))
