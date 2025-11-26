// Product management functionality

let currentPage = 1;
let pageSize = 20;
let totalPages = 1;
let filters = {};
// Modal elements (declared in module scope so handlers can access them)
let deleteAllModal, deleteAllConfirmInput, confirmDeleteAllBtn, cancelDeleteAllBtn, deleteAllModalClose;

document.addEventListener('DOMContentLoaded', function() {
    loadProducts();

    // Event listeners
    document.getElementById('create-product-btn').addEventListener('click', () => openProductModal());
    // Delete all products button opens typed-confirmation modal
    const deleteAllBtn = document.getElementById('delete-all-products-btn');
    if (deleteAllBtn) deleteAllBtn.addEventListener('click', openDeleteAllModal);

    // Modal elements for delete-all confirmation
    deleteAllModal = document.getElementById('delete-all-modal');
    deleteAllConfirmInput = document.getElementById('delete-all-confirm-input');
    confirmDeleteAllBtn = document.getElementById('confirm-delete-all-btn');
    cancelDeleteAllBtn = document.getElementById('cancel-delete-all-btn');
    deleteAllModalClose = document.getElementById('delete-all-modal-close');

    // Wire modal buttons
    if (cancelDeleteAllBtn) cancelDeleteAllBtn.addEventListener('click', closeDeleteAllModal);
    if (deleteAllModalClose) deleteAllModalClose.addEventListener('click', closeDeleteAllModal);
    if (deleteAllConfirmInput) deleteAllConfirmInput.addEventListener('input', onDeleteAllInput);
    if (confirmDeleteAllBtn) confirmDeleteAllBtn.addEventListener('click', performDeleteAll);
    document.getElementById('product-form').addEventListener('submit', handleProductSubmit);
    document.getElementById('cancel-product-btn').addEventListener('click', closeProductModal);
    document.querySelector('#product-modal .close').addEventListener('click', closeProductModal);

    document.getElementById('apply-filters-btn').addEventListener('click', applyFilters);
    document.getElementById('clear-filters-btn').addEventListener('click', clearFilters);

    document.getElementById('prev-page').addEventListener('click', () => changePage(-1));
    document.getElementById('next-page').addEventListener('click', () => changePage(1));
    document.getElementById('page-size').addEventListener('change', (e) => {
        pageSize = parseInt(e.target.value);
        currentPage = 1;
        loadProducts();
    });

    document.getElementById('select-all').addEventListener('change', toggleSelectAll);
    document.getElementById('bulk-delete-btn').addEventListener('click', handleBulkDelete);
});

async function loadProducts() {
    try {
        const params = new URLSearchParams({
            page: currentPage,
            page_size: pageSize,
            ...filters
        });

        const response = await fetch(`${API_BASE}/products?${params}`);
        if (!response.ok) throw new Error('Failed to load products');

        const data = await response.json();
        totalPages = data.total_pages;
        
        displayProducts(data.items);
        updatePagination(data.page, data.total_pages, data.total);

    } catch (error) {
        showToast(`Failed to load products: ${error.message}`, 'error');
    }
}

function displayProducts(products) {
    const tbody = document.getElementById('products-tbody');
    tbody.innerHTML = products.map(product => `
        <tr>
            <td><input type="checkbox" class="product-checkbox" value="${product.id}"></td>
            <td>${product.id}</td>
            <td>${product.sku}</td>
            <td>${product.name}</td>
            <td>${product.description || ''}</td>
            <td><span class="status-badge ${product.active ? 'active' : 'inactive'}">${product.active ? 'Active' : 'Inactive'}</span></td>
            <td>
                <button class="btn-primary btn-sm" onclick="editProduct(${product.id})">Edit</button>
                <button class="btn-danger btn-sm" onclick="deleteProduct(${product.id})">Delete</button>
            </td>
        </tr>
    `).join('');

    // Update bulk actions
    updateBulkActions();
    
    // Add checkbox listeners
    document.querySelectorAll('.product-checkbox').forEach(cb => {
        cb.addEventListener('change', updateBulkActions);
    });
}

function updatePagination(page, totalPages, total) {
    document.getElementById('page-info').textContent = `Page ${page} of ${totalPages} (${total} total)`;
    document.getElementById('prev-page').disabled = page <= 1;
    document.getElementById('next-page').disabled = page >= totalPages;
}

function changePage(delta) {
    const newPage = currentPage + delta;
    if (newPage >= 1 && newPage <= totalPages) {
        currentPage = newPage;
        loadProducts();
    }
}

function applyFilters() {
    filters = {};
    
    const sku = document.getElementById('filter-sku').value.trim();
    const name = document.getElementById('filter-name').value.trim();
    const description = document.getElementById('filter-description').value.trim();
    const active = document.getElementById('filter-active').value;

    if (sku) filters.sku = sku;
    if (name) filters.name = name;
    if (description) filters.description = description;
    if (active) filters.active = active === 'true';

    currentPage = 1;
    loadProducts();
}

function clearFilters() {
    document.getElementById('filter-sku').value = '';
    document.getElementById('filter-name').value = '';
    document.getElementById('filter-description').value = '';
    document.getElementById('filter-active').value = '';
    filters = {};
    currentPage = 1;
    loadProducts();
}

function openProductModal(product = null) {
    const modal = document.getElementById('product-modal');
    const form = document.getElementById('product-form');
    const title = document.getElementById('product-modal-title');

    form.reset();
    
    if (product) {
        title.textContent = 'Edit Product';
        document.getElementById('product-id').value = product.id;
        document.getElementById('product-sku').value = product.sku;
        document.getElementById('product-name').value = product.name;
        document.getElementById('product-description').value = product.description || '';
        document.getElementById('product-active').checked = product.active;
    } else {
        title.textContent = 'Create Product';
    }

    modal.classList.add('show');
}

function closeProductModal() {
    document.getElementById('product-modal').classList.remove('show');
}

async function handleProductSubmit(e) {
    e.preventDefault();
    
    const id = document.getElementById('product-id').value;
    const productData = {
        sku: document.getElementById('product-sku').value,
        name: document.getElementById('product-name').value,
        description: document.getElementById('product-description').value,
        active: document.getElementById('product-active').checked
    };

    try {
        const url = id ? `${API_BASE}/products/${id}` : `${API_BASE}/products`;
        const method = id ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(productData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Operation failed');
        }

        closeProductModal();
        loadProducts();
        showToast(`Product ${id ? 'updated' : 'created'} successfully!`);

    } catch (error) {
        showToast(`Failed: ${error.message}`, 'error');
    }
}

async function editProduct(id) {
    try {
        const response = await fetch(`${API_BASE}/products/${id}`);
        if (!response.ok) throw new Error('Failed to load product');

        const product = await response.json();
        openProductModal(product);

    } catch (error) {
        showToast(`Failed to load product: ${error.message}`, 'error');
    }
}

async function deleteProduct(id) {
    if (!confirmAction('Are you sure you want to delete this product?')) return;

    try {
        const response = await fetch(`${API_BASE}/products/${id}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Failed to delete product');

        loadProducts();
        showToast('Product deleted successfully!');

    } catch (error) {
        showToast(`Failed to delete: ${error.message}`, 'error');
    }
}

function toggleSelectAll(e) {
    const checkboxes = document.querySelectorAll('.product-checkbox');
    checkboxes.forEach(cb => cb.checked = e.target.checked);
    updateBulkActions();
}

function updateBulkActions() {
    const selected = document.querySelectorAll('.product-checkbox:checked');
    const bulkActions = document.getElementById('bulk-actions');
    const selectedCount = document.getElementById('selected-count');

    if (selected.length > 0) {
        bulkActions.style.display = 'flex';
        selectedCount.textContent = `${selected.length} selected`;
    } else {
        bulkActions.style.display = 'none';
    }
}

async function handleBulkDelete() {
    const selected = Array.from(document.querySelectorAll('.product-checkbox:checked'))
        .map(cb => parseInt(cb.value));

    if (selected.length === 0) return;

    if (!confirmAction(`Are you sure you want to delete ${selected.length} products? This cannot be undone.`)) return;

    try {
        const response = await fetch(`${API_BASE}/products/bulk-delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_ids: selected })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Bulk delete failed');
        }

        const result = await response.json();
        
        let message = `Successfully deleted ${result.success_count} products`;
        if (result.failure_count > 0) {
            message += `. ${result.failure_count} failed.`;
            if (result.errors.length > 0) {
                console.error('Delete errors:', result.errors);
            }
        }

        showToast(message, result.failure_count > 0 ? 'error' : 'success');
        
        // Uncheck select all
        document.getElementById('select-all').checked = false;
        loadProducts();

    } catch (error) {
        showToast(`Bulk delete failed: ${error.message}`, 'error');
    }
}

function openDeleteAllModal() {
    if (!deleteAllModal) return;
    deleteAllConfirmInput.value = '';
    confirmDeleteAllBtn.disabled = true;
    deleteAllModal.classList.add('show');
    deleteAllConfirmInput.focus();
}

function closeDeleteAllModal() {
    if (!deleteAllModal) return;
    deleteAllModal.classList.remove('show');
}

function onDeleteAllInput(e) {
    const v = (e.target.value || '').trim();
    // require exact word DELETE to enable the button
    confirmDeleteAllBtn.disabled = v !== 'DELETE';
}

async function performDeleteAll() {
    // final safety check
    if ((deleteAllConfirmInput.value || '').trim() !== 'DELETE') return;

    confirmDeleteAllBtn.disabled = true;
    confirmDeleteAllBtn.textContent = 'Deleting...';

    try {
        const response = await fetch(`${API_BASE}/products/delete-all`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || 'Delete all failed');
        }

        const result = await response.json();
        showToast(`Deleted ${result.deleted_count} products.`, 'success');
        // Reset pagination and reload
        document.getElementById('select-all').checked = false;
        currentPage = 1;
        loadProducts();
        closeDeleteAllModal();

    } catch (error) {
        showToast(`Delete all failed: ${error.message}`, 'error');
    } finally {
        confirmDeleteAllBtn.disabled = false;
        confirmDeleteAllBtn.textContent = 'Delete All';
    }
}

