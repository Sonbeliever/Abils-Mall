// ==============================
// manager.js
// Manager & company logic
// ==============================

// Global state
window.companies = window.companies || []; // Each company: {id, name, managerId, products: [], sales: [], verifiedCustomers: []}
window.managers = window.managers || []; // Each manager: {id, name, email, companyId}
window.currentUser = window.currentUser || null; // Logged in user

// ==============================
// Initialization
// ==============================
document.addEventListener('DOMContentLoaded', () => {
    renderCompanies();
    renderManagerDashboard();
});

// ==============================
// Admin: Create Company
// ==============================
function createCompany(companyName, managerId) {
    if (!companyName || !managerId) return showNotification('Company name and manager required', 'error');

    const id = Date.now();
    window.companies.push({
        id,
        name: companyName,
        managerId,
        products: [],
        sales: [],
        verifiedCustomers: []
    });

    // Assign manager to this company
    const manager = window.managers.find(m => m.id === managerId);
    if (manager) manager.companyId = id;

    showNotification(`Company "${companyName}" created and manager assigned`, 'success');
    renderCompanies();
}

// ==============================
// Render Companies (Admin)
function renderCompanies() {
    const container = document.getElementById('company-list');
    if (!container) return;
    container.innerHTML = '';

    if (window.companies.length === 0) {
        container.innerHTML = '<p>No companies created yet.</p>';
        return;
    }

    window.companies.forEach(company => {
        const manager = window.managers.find(m => m.id === company.managerId);
        const div = document.createElement('div');
        div.className = 'company-card';
        div.innerHTML = `
            <h4>${company.name}</h4>
            <p>Manager: ${manager ? manager.name : 'Not assigned'}</p>
            <p>Products: ${company.products.length}</p>
            <p>Sales: ${company.sales.reduce((sum, s) => sum + s.quantity, 0)}</p>
        `;
        container.appendChild(div);
    });
}

// ==============================
// Manager Dashboard
// ==============================
function renderManagerDashboard() {
    if (!window.currentUser || window.currentUser.role !== 'manager') return;

    const company = window.companies.find(c => c.managerId === window.currentUser.id);
    if (!company) return;

    const container = document.getElementById('manager-dashboard');
    if (!container) return;

    container.innerHTML = `
        <h3>${company.name} Dashboard</h3>
        <p>Total Products: ${company.products.length}</p>
        <p>Total Sales: ${company.sales.reduce((sum, s) => sum + s.quantity, 0)}</p>
        <h4>Pending Customer Approvals</h4>
        <div id="pending-verifications"></div>
    `;

    renderPendingVerifications(company);
}

// ==============================
// Approve Regular Customers
function renderPendingVerifications(company) {
    const pendingEl = document.getElementById('pending-verifications');
    if (!pendingEl) return;
    pendingEl.innerHTML = '';

    const pendingRequests = window.usersData.filter(u => u.requestedCompanyId === company.id && !company.verifiedCustomers.includes(u.id));
    if (pendingRequests.length === 0) {
        pendingEl.innerHTML = '<p>No pending customer requests</p>';
        return;
    }

    pendingRequests.forEach(user => {
        const div = document.createElement('div');
        div.className = 'pending-user';
        div.innerHTML = `
            <span>${user.name} (${user.email})</span>
            <button onclick="approveCustomer(${company.id}, ${user.id})">Approve</button>
        `;
        pendingEl.appendChild(div);
    });
}

function approveCustomer(companyId, userId) {
    const company = window.companies.find(c => c.id === companyId);
    if (!company) return;

    if (!company.verifiedCustomers.includes(userId)) {
        company.verifiedCustomers.push(userId);
        showNotification('Customer approved for discounts', 'success');
        renderPendingVerifications(company);
    }
}

// ==============================
// Record Sale
function recordSale(companyId, productId, quantity) {
    const company = window.companies.find(c => c.id === companyId);
    if (!company) return;

    const product = company.products.find(p => p.id === productId);
    if (!product) return;

    company.sales.push({ productId, quantity, timestamp: Date.now() });
    product.stock -= quantity;
    showNotification(`Sale recorded: ${quantity} x ${product.name}`, 'success');
    renderManagerDashboard();
}

// ==============================
// Expose Globals
window.createCompany = createCompany;
window.renderCompanies = renderCompanies;
window.renderManagerDashboard = renderManagerDashboard;
window.approveCustomer = approveCustomer;
window.recordSale = recordSale;
