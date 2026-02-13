// ==============================
// products.js
// Product data and rendering functions
// ==============================

// ==============================
// Product Data (24 items example, add remaining items as needed)
// ==============================
window.productsData = [
    {
        id: 1,
        name: "Wireless Bluetooth Headphones with Noise Cancellation",
        price: 6985,
        originalPrice: 134985,
        image: "/static/images/headphones.jpg", // optional local path
        images: [
            "/static/images/headphones.jpg",
            "/static/images/headphones1.jpg",
            "/static/images/headphones2.jpg"
        ],
        category: "Electronics",
        badge: "Bestseller",
        rating: 4.5,
        ratingCount: 1243,
        description: "Premium wireless headphones with active noise cancellation, 30-hour battery life, and superior sound quality. Perfect for music lovers and professionals.",
        specifications: {
            "Battery Life": "30 hours",
            "Connectivity": "Bluetooth 5.0",
            "Noise Cancellation": "Active",
            "Water Resistance": "IPX4",
            "Weight": "250g",
            "Color": "Black"
        },
        stock: 45
    },
    {
        id: 2,
        name: "Smart Watch Fitness Tracker with Heart Rate Monitor",
        price: 14985,
        originalPrice: 194985,
        image: "/static/images/smartwatch.jpg",
        images: [
            "/static/images/smartwatch.jpg",
            "/static/images/smartwatch1.jpg"
        ],
        category: "Electronics",
        badge: "New",
        rating: 4.2,
        ratingCount: 856,
        description: "Advanced smartwatch with fitness tracking, heart rate monitoring, sleep tracking, and smartphone notifications.",
        specifications: {
            "Display": "1.3\" AMOLED",
            "Battery Life": "7 days",
            "Water Resistance": "5 ATM",
            "GPS": "Built-in",
            "Sensors": "Heart Rate, SpO2, Accelerometer",
            "Compatibility": "iOS & Android"
        },
        stock: 32
    },
    // Add remaining 22 products here following the same format
];

// ==============================
// Utility Functions
// ==============================
window.formatCurrency = function(amount) {
    return `₦${amount.toLocaleString()}`;
};

window.generateStarRating = function(rating) {
    const fullStars = Math.floor(rating);
    const halfStar = rating % 1 >= 0.5 ? 1 : 0;
    const emptyStars = 5 - fullStars - halfStar;
    return '★'.repeat(fullStars) + (halfStar ? '½' : '') + '☆'.repeat(emptyStars);
};

window.showNotification = function(message, type='info') {
    // Simple alert, replace with custom toast if needed
    alert(message);
};

// ==============================
// Render Products
// ==============================
window.renderProducts = function(filteredProducts = window.productsData) {
    const container = document.getElementById('products-container');
    if (!container) return;
    container.innerHTML = '';

    filteredProducts.forEach(product => {
        const card = document.createElement('div');
        card.className = 'product-card';
        card.innerHTML = `
            ${product.badge ? `<div class="product-badge ${product.badge.toLowerCase().includes('sale') ? 'sale' : product.badge.toLowerCase().includes('new') ? 'new' : 'hot'}">${product.badge}</div>` : ''}
            <img src="${product.image}" alt="${product.name}" class="product-img" onclick="openProductModal(${product.id})">
            <div class="product-info">
                <h3 class="product-title" onclick="openProductModal(${product.id})" style="cursor:pointer;">${product.name}</h3>
                <div class="product-price">
                    <span class="current-price">${formatCurrency(product.price)}</span>
                    ${product.originalPrice ? `<span class="original-price">${formatCurrency(product.originalPrice)}</span>` : ''}
                </div>
                <div class="product-rating">
                    ${generateStarRating(product.rating)}
                    <span class="rating-count">(${product.ratingCount})</span>
                </div>
                <div class="product-actions">
                    <button class="btn-add-cart" onclick="event.stopPropagation(); addToCart(${product.id})">Add to Cart</button>
                    <button class="btn-view-details" onclick="event.stopPropagation(); openProductModal(${product.id})">View Details</button>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
};

// ==============================
// Filter by Category
// ==============================
window.filterByCategory = function(category) {
    if (category === 'All') {
        renderProducts(window.productsData);
    } else {
        const filtered = window.productsData.filter(product => product.category === category);
        renderProducts(filtered);
    }
    showNotification(`Showing ${category === 'All' ? 'all' : category} products`, 'success');
};

// ==============================
// Product Modal Functions
// ==============================
window.openProductModal = function(productId) {
    const product = window.productsData.find(p => p.id === productId);
    if (!product) return;

    const modalContent = document.getElementById('product-modal-content');
    if (!modalContent) return;

    modalContent.innerHTML = `
        <div class="product-modal-body">
            <div class="product-modal-images">
                <img src="${product.images[0]}" alt="${product.name}" class="product-modal-main-img" id="main-product-img">
                <div class="product-modal-thumbs">
                    ${product.images.map((img, i) => `
                        <img src="${img}" alt="View ${i+1}" class="product-modal-thumb ${i===0?'active':''}" onclick="changeProductImage('${img}', this)">
                    `).join('')}
                </div>
            </div>
            <div class="product-modal-details">
                <h1 class="product-modal-title">${product.name}</h1>
                <div class="product-modal-price">
                    ${formatCurrency(product.price)}
                    ${product.originalPrice ? `<span style="text-decoration: line-through; color: var(--text-light); margin-left:10px;">${formatCurrency(product.originalPrice)}</span>` : ''}
                </div>
                <div class="product-rating" style="margin: 15px 0;">
                    ${generateStarRating(product.rating)}
                    <span class="rating-count">(${product.ratingCount} reviews)</span>
                    <span style="margin-left:10px; color: var(--success-color); font-weight:600;">${product.stock} in stock</span>
                </div>
                <p class="product-modal-description">${product.description}</p>
                <div class="product-modal-specs">
                    <h4>Product Specifications</h4>
                    ${Object.entries(product.specifications).map(([k,v])=>`<div class="spec-item"><span>${k}</span><span>${v}</span></div>`).join('')}
                </div>
                <div class="product-modal-actions">
                    <button class="btn-modal-add-cart" onclick="addToCartFromModal(${product.id})"><i class="fas fa-shopping-cart"></i> Add to Cart</button>
                    <button class="btn-modal-add-cart" style="background-color: var(--secondary-color); color: var(--text-color);" onclick="buyNow(${product.id})"><i class="fas fa-bolt"></i> Buy Now</button>
                </div>
            </div>
        </div>
    `;

    document.getElementById('product-modal').style.display = 'block';
};

window.closeProductModal = function() {
    const modal = document.getElementById('product-modal');
    if (modal) modal.style.display = 'none';
};

window.changeProductImage = function(src, thumbElement) {
    const mainImg = document.getElementById('main-product-img');
    if (mainImg) mainImg.src = src;

    document.querySelectorAll('.product-modal-thumb').forEach(t => t.classList.remove('active'));
    thumbElement.classList.add('active');
};

window.addToCartFromModal = function(productId) {
    addToCart(productId);
    closeProductModal();
};

window.buyNow = function(productId) {
    cart = [];
    addToCart(productId);
    closeProductModal();
    showPage('checkout');
};
