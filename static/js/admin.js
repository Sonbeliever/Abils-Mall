// ==============================
// admin.js
// Admin dashboard logic
// ==============================

// Admin state
window.adminProducts = [...window.productsData]; // Copy of products for admin
window.adminOrders = []; // This will come from backend eventually

// ==============================
// Initialization
// ==============================
document.addEventListener('DOMContentLoaded', () => {
    renderAdminProducts();
    setupAdminEventListeners();
    updateAdminStats();
});

// ==============================
// Render Products in Admin
// ==============================
function renderAdminProducts() {
    const container = document.getElementById('admin-products-container');
    if (!container) return;

    container.innerHTML = '';
    if (window.adminProducts.length === 0) {
        container.innerHTML = '<p>No products available.</p>';
        return;
    }

    window.adminProducts.forEach(product => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${product.id}</td>
            <td>${product.name}</td>
            <td>${product.category}</td>
            <td>${product.stock}</td>
            <td>${window.formatCurrency(product.price)}</td>
            <td>
                <button onclick="editProduct(${product.id})">Edit</button>
                <button onclick="deleteProduct(${product.id})">Delete</button>
            </td>
        `;
        container.appendChild(row);
    });
}

// ==============================
// Add/Edit/Delete Product
// ==============================
function editProduct(productId) {
    const product = window.adminProducts.find(p => p.id === productId);
    if (!product) return;

    // Populate modal/form for editing
    const form = document.getElementById('admin-product-form');
    form.dataset.editingId = productId;
    form.querySelector('#product-name').value = product.name;
    form.querySelector('#product-category').value = product.category;
    form.querySelector('#product-price').value = product.price;
    form.querySelector('#product-stock').value = product.stock;

    document.getElementById('admin-product-modal').style.display = 'block';
}

function deleteProduct(productId) {
    if (!confirm('Are you sure you want to delete this product?')) return;

    window.adminProducts = window.adminProducts.filter(p => p.id !== productId);
    renderAdminProducts();
    window.showNotification('Product deleted', 'success');
}

function saveProduct(event) {
    event.preventDefault();
    const form = event.target;
    const id = form.dataset.editingId ? parseInt(form.dataset.editingId) : Date.now();

    const productData = {
        id: id,
        name: form.querySelector('#product-name').value,
        category: form.querySelector('#product-category').value,
        price: parseFloat(form.querySelector('#product-price').value),
        stock: parseInt(form.querySelector('#product-stock').value),
        image: '', // Optional, can add image upload later
    };

    if (form.dataset.editingId) {
        // Update existing
        const index = window.adminProducts.findIndex(p => p.id === id);
        window.adminProducts[index] = { ...window.adminProducts[index], ...productData };
        window.showNotification('Product updated', 'success');
    } else {
        // Add new
        window.adminProducts.push(productData);
        window.showNotification('Product added', 'success');
    }

    form.reset();
    delete form.dataset.editingId;
    document.getElementById('admin-product-modal').style.display = 'none';
    renderAdminProducts();
    updateAdminStats();
}

// ==============================
// Admin Stats
// ==============================
function updateAdminStats() {
    const totalProducts = window.adminProducts.length;
    const totalStock = window.adminProducts.reduce((sum, p) => sum + p.stock, 0);
    const totalOrders = window.adminOrders.length;

    document.getElementById('admin-total-products').textContent = totalProducts;
    document.getElementById('admin-total-stock').textContent = totalStock;
    document.getElementById('admin-total-orders').textContent = totalOrders;
}

// ==============================
// Event Listeners
// ==============================
function setupAdminEventListeners() {
    // Add/Edit Product form
    const form = document.getElementById('admin-product-form');
    if (form) form.addEventListener('submit', saveProduct);

    // Close modal
    const modalClose = document.getElementById('admin-product-modal-close');
    if (modalClose) {
        modalClose.addEventListener('click', () => {
            document.getElementById('admin-product-modal').style.display = 'none';
        });
    }
}

// ==============================
// Expose globally
// ==============================
window.renderAdminProducts = renderAdminProducts;
window.editProduct = editProduct;
window.deleteProduct = deleteProduct;
window.saveProduct = saveProduct;
window.updateAdminStats = updateAdminStats;
