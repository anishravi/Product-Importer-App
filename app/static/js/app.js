// Main application logic - Tab switching and utilities

// Global state for cross-tab communication
window.appState = {
    recentUpload: false,
    lastUploadTime: null
};

document.addEventListener('DOMContentLoaded', function() {
    // Tab switching
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            
            // Remove active class from all tabs and contents
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            // Add active class to clicked tab and corresponding content
            btn.classList.add('active');
            document.getElementById(`${targetTab}-tab`).classList.add('active');
            
            // Refresh data when switching to specific tabs
            if (targetTab === 'products' && typeof loadProducts === 'function') {
                loadProducts();
                // Clear the recent upload flag and visual indicator since we've refreshed
                window.appState.recentUpload = false;
                btn.classList.remove('has-updates');
                btn.title = '';
            } else if (targetTab === 'webhooks' && typeof loadWebhooks === 'function') {
                loadWebhooks();
            }
        });
    });
});

// Utility functions
const API_BASE = 'http://localhost:8000/api';

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

function confirmAction(message) {
    return confirm(message);
}

