// ==============================
// checkout.js
// Checkout page logic
// ==============================

// Load checkout items on page load
document.addEventListener('DOMContentLoaded', () => {
    renderCheckoutItems();
    setupCheckoutForm();
});

// ==============================
// Render Checkout Items
// ==============================
function renderCheckoutItems() {
    const container = document.getElementById('checkout-items');
    if (!container) return;

    container.innerHTML = '';

    if (cart.length === 0) {
        container.innerHTML = '<p>Your cart is empty.</p>';
        updateCheckoutSummary();
        return;
    }

    cart.forEach(item => {
        const div = document.createElement('div');
        div.className = 'checkout-item';
        div.innerHTML = `
            <img src="${item.image}" alt="${item.name}" class="checkout-item-img">
            <div class="checkout-item-info">
                <h4>${item.name}</h4>
                <p>${formatCurrency(item.price)}</p>
                <div class="checkout-item-qty">
                    <button class="qty-minus">-</button>
                    <span>${item.quantity}</span>
                    <button class="qty-plus">+</button>
                </div>
                <button class="checkout-item-remove">Remove</button>
            </div>
        `;
        container.appendChild(div);

        // Event listeners
        div.querySelector('.qty-minus').addEventListener('click', () => updateQuantity(item.id, item.quantity - 1));
        div.querySelector('.qty-plus').addEventListener('click', () => updateQuantity(item.id, item.quantity + 1));
        div.querySelector('.checkout-item-remove').addEventListener('click', () => removeFromCart(item.id));
    });

    updateCheckoutSummary();
}

// ==============================
// Update Checkout Summary
// ==============================
function updateCheckoutSummary() {
    const subtotalEl = document.getElementById('subtotal');
    const shippingEl = document.getElementById('shipping');
    const taxEl = document.getElementById('tax');
    const totalEl = document.getElementById('total');

    const subtotal = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);

    // Example: flat shipping fee 1500 if subtotal > 0
    const shipping = subtotal > 0 ? 1500 : 0;

    // Tax 7.5%
    const tax = subtotal * 0.075;

    const total = subtotal + shipping + tax;

    if (subtotalEl) subtotalEl.textContent = formatCurrency(subtotal);
    if (shippingEl) shippingEl.textContent = formatCurrency(shipping);
    if (taxEl) taxEl.textContent = formatCurrency(tax);
    if (totalEl) totalEl.textContent = formatCurrency(total);
}

// ==============================
// Checkout Form Handling
// ==============================
function setupCheckoutForm() {
    const form = document.getElementById('checkout-form');
    if (!form) return;

    form.addEventListener('submit', (e) => {
        e.preventDefault();

        if (cart.length === 0) {
            showNotification('Your cart is empty', 'error');
            return;
        }

        // Collect form data
        const formData = {
            firstName: document.getElementById('first-name').value,
            lastName: document.getElementById('last-name').value,
            email: document.getElementById('email').value,
            phone: document.getElementById('phone').value,
            address: document.getElementById('address').value,
            state: document.getElementById('state').value,
            city: document.getElementById('city').value,
            paymentMethod: document.querySelector('input[name="payment"]:checked').value,
            items: cart.map(item => ({ id: item.id, name: item.name, price: item.price, quantity: item.quantity }))
        };

        // Save to localStorage or send to Flask backend via fetch
        localStorage.setItem('checkout-data', JSON.stringify(formData));

        // Optional: send to backend (Flask API)
        /*
        fetch('/checkout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        })
        .then(res => res.json())
        .then(data => {
            showNotification('Order placed successfully!', 'success');
            clearCart();
            window.location.href = '/thank-you';
        })
        .catch(err => showNotification('Error placing order', 'error'));
        */

        showNotification('Order data saved! Proceeding to payment...', 'success');
        clearCart();
        renderCheckoutItems();
        updateCheckoutSummary();
    });
}
