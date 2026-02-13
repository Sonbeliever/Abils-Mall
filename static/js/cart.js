// ==============================
// cart.js
// Shopping Cart Management
// ==============================

// Use the global cart array from main.js
if (!window.cart) window.cart = [];

// ==============================
// Add Product to Cart
// ==============================
function addToCart(productId) {
    const product = products.find(p => p.id === productId);
    if (!product) return;

    const existingItem = cart.find(item => item.id === productId);
    if (existingItem) {
        if (existingItem.quantity < product.stock) {
            existingItem.quantity++;
            showNotification(`${product.name} quantity updated`, 'success');
        } else {
            showNotification(`Only ${product.stock} items in stock`, 'error');
        }
    } else {
        cart.push({
            id: product.id,
            name: product.name,
            price: product.price,
            image: product.image,
            quantity: 1,
            stock: product.stock
        });
        showNotification(`${product.name} added to cart`, 'success');
    }

    saveCart();
    renderCartItems();
    updateCartCount();
}

// ==============================
// Remove Product from Cart
// ==============================
function removeFromCart(productId) {
    cart = cart.filter(item => item.id !== productId);
    saveCart();
    renderCartItems();
    updateCartCount();
    showNotification('Item removed from cart', 'success');
}

// ==============================
// Update Quantity
// ==============================
function updateQuantity(productId, newQty) {
    const item = cart.find(i => i.id === productId);
    if (!item) return;

    if (newQty <= 0) {
        removeFromCart(productId);
    } else if (newQty > item.stock) {
        item.quantity = item.stock;
        showNotification(`Only ${item.stock} items in stock`, 'error');
    } else {
        item.quantity = newQty;
        showNotification(`${item.name} quantity updated`, 'success');
    }

    saveCart();
    renderCartItems();
    updateCartCount();
}

// ==============================
// Render Cart Items
// ==============================
function renderCartItems() {
    const container = document.getElementById('cart-items');
    if (!container) return;

    container.innerHTML = '';

    if (cart.length === 0) {
        container.innerHTML = '<p>Your cart is empty.</p>';
        updateCartSummary();
        return;
    }

    cart.forEach(item => {
        const div = document.createElement('div');
        div.className = 'cart-item';
        div.innerHTML = `
            <img src="${item.image}" alt="${item.name}" class="cart-item-img">
            <div class="cart-item-info">
                <h4>${item.name}</h4>
                <p>${formatCurrency(item.price)}</p>
                <div class="cart-item-qty">
                    <button class="qty-minus">-</button>
                    <span>${item.quantity}</span>
                    <button class="qty-plus">+</button>
                </div>
                <button class="cart-item-remove">Remove</button>
            </div>
        `;
        container.appendChild(div);

        // Event listeners for dynamic buttons
        div.querySelector('.qty-minus').addEventListener('click', () => updateQuantity(item.id, item.quantity - 1));
        div.querySelector('.qty-plus').addEventListener('click', () => updateQuantity(item.id, item.quantity + 1));
        div.querySelector('.cart-item-remove').addEventListener('click', () => removeFromCart(item.id));
    });

    updateCartSummary();
}

// ==============================
// Cart Summary
// ==============================
function updateCartSummary() {
    const totalItemsEl = document.getElementById('cart-total-items');
    const totalPriceEl = document.getElementById('cart-total-price');

    const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
    const totalPrice = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);

    if (totalItemsEl) totalItemsEl.textContent = totalItems;
    if (totalPriceEl) totalPriceEl.textContent = formatCurrency(totalPrice);
}

// ==============================
// Update Cart Count (Navbar)
// ==============================
function updateCartCount() {
    const countEl = document.getElementById('cart-count');
    if (countEl) countEl.textContent = cart.reduce((sum, item) => sum + item.quantity, 0);
}

// ==============================
// Clear Cart
// ==============================
function clearCart() {
    cart = [];
    saveCart();
    renderCartItems();
    updateCartCount();
    showNotification('Cart cleared', 'success');
}

// ==============================
// Persist Cart
// ==============================
function saveCart() {
    localStorage.setItem('cart', JSON.stringify(cart));
}

function loadCart() {
    const saved = localStorage.getItem('cart');
    if (saved) cart = JSON.parse(saved);
    renderCartItems();
    updateCartCount();
}

// Load cart on startup
document.addEventListener('DOMContentLoaded', loadCart);
