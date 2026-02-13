// ==============================
// utils.js
// Utility helper functions
// ==============================

// Format number as currency
function formatCurrency(amount) {
    return '$' + amount.toFixed(2);
}

// Generate star rating HTML
function generateStarRating(rating) {
    let stars = '';
    for (let i = 1; i <= 5; i++) {
        if (i <= rating) stars += '★';
        else stars += '☆';
    }
    return `<span class="stars">${stars}</span>`;
}

// Show notification (success or error)
function showNotification(message, type = 'success') {
    const container = document.getElementById('notification');
    if (!container) return;

    const notif = document.createElement('div');
    notif.className = `notification ${type}`;
    notif.textContent = message;
    container.appendChild(notif);

    setTimeout(() => {
        notif.remove();
    }, 3000);
}

// Show a specific page section (for SPA behavior)
function showPage(pageId) {
    const pages = document.querySelectorAll('.page');
    pages.forEach(page => {
        page.style.display = page.id === pageId ? 'block' : 'none';
    });
}
