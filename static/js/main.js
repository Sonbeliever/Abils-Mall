// ==============================
// main.js
// Abils Mall - Complete SPA logic
// ==============================

// ==============================
// Global State
// ==============================
window.cart = [];
window.productsData = window.productsData || []; // From products.js
window.usersData = window.usersData || []; // All users
window.adminData = window.adminData || { companies: [], orders: [] }; // Admin records
window.managerData = window.managerData || []; // Managers for companies
window.currentUser = null; // Logged-in user

// ==============================
// Utility Functions
// ==============================
window.formatCurrency = function(amount) {
    return "₦" + Number(amount).toLocaleString();
};

window.showNotification = function(message, type = "info") {
    const container = document.getElementById("notification") || document.body;
    const notif = document.createElement("div");
    notif.className = `notification ${type}`;
    notif.textContent = message;
    container.appendChild(notif);
    setTimeout(() => notif.remove(), 3000);
};

window.generateStarRating = function(rating) {
    let stars = "";
    for (let i = 1; i <= 5; i++) stars += i <= rating ? "★" : "☆";
    return `<span class="stars">${stars}</span>`;
};

// ==============================
// Initialization
// ==============================
document.addEventListener("DOMContentLoaded", () => {
    loadCart();
    renderProducts(window.productsData);
    renderCart();
    updateCartCount();
    setupPageLinks();
    setupModeToggle();
    setupCategoryFilters();
});

// ==============================
// Page Switching
// ==============================
function showPage(pageId) {
    document.querySelectorAll(".page-section").forEach(sec => sec.classList.remove("active"));
    const page = document.getElementById(`${pageId}-page`);
    if (page) page.classList.add("active");
}

// ==============================
// Dark Mode Toggle
// ==============================
function setupModeToggle() {
    const btn = document.getElementById("mode-toggle");
    if (!btn) return;
    btn.addEventListener("click", () => {
        document.body.classList.toggle("dark-mode");
        const icon = btn.querySelector("i");
        const text = btn.querySelector("span");
        if (document.body.classList.contains("dark-mode")) {
            icon.className = "fas fa-sun";
            text.textContent = "Light Mode";
        } else {
            icon.className = "fas fa-moon";
            text.textContent = "Dark Mode";
        }
    });
}

// ==============================
// Product Rendering
// ==============================
function renderProducts(filteredProducts = window.productsData) {
    const container = document.getElementById("products-container");
    if (!container) return;
    container.innerHTML = "";

    filteredProducts.forEach(product => {
        const card = document.createElement("div");
        card.className = "product-card";
        card.innerHTML = `
            ${product.badge ? `<div class="product-badge">${product.badge}</div>` : ""}
            <img src="${product.image}" alt="${product.name}" class="product-img" onclick="openProductModal(${product.id})">
            <h3 onclick="openProductModal(${product.id})" style="cursor:pointer">${product.name}</h3>
            <div class="product-price">${window.formatCurrency(product.price)}</div>
            <div class="product-rating">${window.generateStarRating(product.rating)}</div>
            <button onclick="addToCart(${product.id})">Add to Cart</button>
        `;
        container.appendChild(card);
    });
}

// ==============================
// Product Modal
// ==============================
function openProductModal(productId) {
    const product = window.productsData.find(p => p.id === productId);
    if (!product) return;

    const modal = document.getElementById("product-modal-content");
    modal.innerHTML = `
        <div class="modal-left">
            <img src="${product.images[0]}" id="modal-main-img">
            <div class="modal-thumbs">
                ${product.images.map((img, i) => `<img src="${img}" class="${i === 0 ? 'active' : ''}" onclick="changeModalImage('${img}', this)">`).join("")}
            </div>
        </div>
        <div class="modal-right">
            <h2>${product.name}</h2>
            <p>${product.description}</p>
            <div>${window.formatCurrency(product.price)}</div>
            <div>${window.generateStarRating(product.rating)}</div>
            <button onclick="addToCart(${product.id}); closeProductModal();">Add to Cart</button>
            <button onclick="buyNow(${product.id})">Buy Now</button>
        </div>
    `;
    document.getElementById("product-modal").style.display = "block";
}

function closeProductModal() {
    document.getElementById("product-modal").style.display = "none";
}

function changeModalImage(src, el) {
    document.getElementById("modal-main-img").src = src;
    document.querySelectorAll(".modal-thumbs img").forEach(t => t.classList.remove("active"));
    el.classList.add("active");
}

function buyNow(productId) {
    window.cart = [];
    addToCart(productId);
    closeProductModal();
    showPage("checkout");
}

// ==============================
// Cart Functions
// ==============================
function addToCart(productId) {
    const product = window.productsData.find(p => p.id === productId);
    if (!product) return;

    const existing = window.cart.find(i => i.id === productId);
    if (existing) {
        if (existing.quantity < product.stock) existing.quantity++;
        else { showNotification(`Only ${product.stock} in stock`, "error"); return; }
    } else window.cart.push({ ...product, quantity: 1 });

    saveCart();
    updateCartCount();
    renderCart();
    showNotification(`${product.name} added to cart`, "success");
}

function removeFromCart(productId) {
    window.cart = window.cart.filter(i => i.id !== productId);
    saveCart();
    updateCartCount();
    renderCart();
}

function updateCartQuantity(productId, qty) {
    const item = window.cart.find(i => i.id === productId);
    if (!item) return;
    item.quantity = Math.min(Math.max(parseInt(qty) || 1, 1), item.stock);
    saveCart();
    updateCartCount();
    renderCart();
}

// ==============================
// Cart Rendering & Summary
// ==============================
function renderCart() {
    const container = document.getElementById("cart-items");
    if (!container) return;
    container.innerHTML = "";
    if (!window.cart.length) { container.innerHTML = "<p>Your cart is empty.</p>"; updateSummary(); return; }

    window.cart.forEach(item => {
        const row = document.createElement("div");
        row.className = "cart-item";
        row.innerHTML = `
            <div class="cart-item-info">
                <img src="${item.image}" alt="${item.name}">
                <div><h4>${item.name}</h4><p>${window.formatCurrency(item.price)}</p></div>
            </div>
            <div class="cart-item-actions">
                <input type="number" min="1" max="${item.stock}" value="${item.quantity}" onchange="updateCartQuantity(${item.id}, this.value)">
                <button onclick="removeFromCart(${item.id})">Remove</button>
            </div>
        `;
        container.appendChild(row);
    });

    updateSummary();
}

function updateSummary() {
    const subtotalEl = document.getElementById("subtotal");
    const shippingEl = document.getElementById("shipping");
    const taxEl = document.getElementById("tax");
    const totalEl = document.getElementById("total");

    let subtotal = window.cart.reduce((sum, i) => sum + i.price * i.quantity, 0);
    let shipping = subtotal > 0 ? 1000 : 0;
    let tax = subtotal * 0.075;
    let total = subtotal + shipping + tax;

    if (subtotalEl) subtotalEl.textContent = window.formatCurrency(subtotal);
    if (shippingEl) shippingEl.textContent = window.formatCurrency(shipping);
    if (taxEl) taxEl.textContent = window.formatCurrency(tax);
    if (totalEl) totalEl.textContent = window.formatCurrency(total);

    const checkoutItems = document.getElementById("checkout-items");
    if (checkoutItems) checkoutItems.innerHTML = window.cart.map(i => `<div class="checkout-item"><span>${i.name} x ${i.quantity}</span><span>${window.formatCurrency(i.price*i.quantity)}</span></div>`).join("");
}

// ==============================
// SPA Navigation
// ==============================
function setupPageLinks() {
    document.querySelectorAll("[data-page]").forEach(link => {
        link.addEventListener("click", e => {
            const page = link.dataset.page;
            if(page) showPage(page);
            e.preventDefault();
        });
    });
}

// ==============================
// Category Filters
// ==============================
function setupCategoryFilters() {
    document.querySelectorAll(".category-card").forEach(card => {
        card.addEventListener("click", () => {
            const category = card.querySelector("h4")?.textContent || "All";
            filterByCategory(category);
        });
    });
}

function filterByCategory(category) {
    if(category === "All") renderProducts(window.productsData);
    else renderProducts(window.productsData.filter(p => p.category === category));
    showNotification(`Showing ${category} products`, "success");
}

// ==============================
// Shipping Calculator
// ==============================
function calculateShipping() {
    const state = document.getElementById("shipping-state")?.value;
    const city = document.getElementById("shipping-city")?.value;
    if(!state || !city){ showNotification("Enter state and city", "error"); return; }
    const cost = 1500;
    const resultEl = document.getElementById("shipping-result");
    const resultText = document.getElementById("shipping-result-text");
    if(resultEl && resultText){ resultText.textContent = `Shipping to ${city}, ${state} is ${window.formatCurrency(cost)}`; resultEl.style.display="block"; }
}

// ==============================
// Expose Globals
// ==============================
window.showPage = showPage;
window.addToCart = addToCart;
window.removeFromCart = removeFromCart;
window.updateCartQuantity = updateCartQuantity;
window.renderCart = renderCart;
window.updateSummary = updateSummary;
window.filterByCategory = filterByCategory;
window.calculateShipping = calculateShipping;
window.openProductModal = openProductModal;
window.closeProductModal = closeProductModal;
window.buyNow = buyNow;
