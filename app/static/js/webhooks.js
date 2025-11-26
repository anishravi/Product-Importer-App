// Webhook management functionality

let webhookWebSocket = null;

document.addEventListener('DOMContentLoaded', function() {
    loadWebhooks();
    connectWebhookWebSocket();

    document.getElementById('create-webhook-btn').addEventListener('click', () => openWebhookModal());
    document.getElementById('webhook-form').addEventListener('submit', handleWebhookSubmit);
    document.getElementById('cancel-webhook-btn').addEventListener('click', closeWebhookModal);
    document.querySelector('#webhook-modal .close').addEventListener('click', closeWebhookModal);
});

function connectWebhookWebSocket() {
    // WebSocket connection for webhook test results
    // Note: In production, you might want a dedicated WebSocket endpoint for webhooks
    // For now, test results are shown immediately via the API response
}

async function loadWebhooks() {
    try {
        const response = await fetch(`${API_BASE}/webhooks`);
        if (!response.ok) throw new Error('Failed to load webhooks');

        const webhooks = await response.json();
        displayWebhooks(webhooks);

    } catch (error) {
        showToast(`Failed to load webhooks: ${error.message}`, 'error');
    }
}

function displayWebhooks(webhooks) {
    const container = document.getElementById('webhooks-list');
    
    if (webhooks.length === 0) {
        container.innerHTML = '<p>No webhooks configured. Create one to get started.</p>';
        return;
    }

    container.innerHTML = webhooks.map(webhook => `
        <div class="webhook-item" id="webhook-${webhook.id}">
            <div class="webhook-header">
                <div class="webhook-url">${webhook.url}</div>
                <div class="webhook-actions">
                    <button class="btn-primary btn-sm" onclick="testWebhook(${webhook.id})">Test</button>
                    <button class="btn-primary btn-sm" onclick="editWebhook(${webhook.id})">Edit</button>
                    <button class="btn-danger btn-sm" onclick="deleteWebhook(${webhook.id})">Delete</button>
                </div>
            </div>
            <div class="event-types">
                ${webhook.event_types.map(type => 
                    `<span class="event-badge">${type}</span>`
                ).join('')}
            </div>
            <div class="webhook-status">
                <label class="toggle-switch">
                    <input type="checkbox" ${webhook.enabled ? 'checked' : ''} 
                           onchange="toggleWebhook(${webhook.id}, this.checked)">
                    <span class="toggle-slider"></span>
                </label>
                <span>${webhook.enabled ? 'Enabled' : 'Disabled'}</span>
            </div>
            <div id="test-result-${webhook.id}" class="test-result" style="display: none;"></div>
        </div>
    `).join('');
}

function openWebhookModal(webhook = null) {
    const modal = document.getElementById('webhook-modal');
    const form = document.getElementById('webhook-form');
    const title = document.getElementById('webhook-modal-title');

    form.reset();
    document.querySelectorAll('input[name="event-type"]').forEach(cb => cb.checked = false);
    
    if (webhook) {
        title.textContent = 'Edit Webhook';
        document.getElementById('webhook-id').value = webhook.id;
        document.getElementById('webhook-url').value = webhook.url;
        document.getElementById('webhook-enabled').checked = webhook.enabled;
        
        webhook.event_types.forEach(type => {
            const checkbox = document.querySelector(`input[name="event-type"][value="${type}"]`);
            if (checkbox) checkbox.checked = true;
        });
    } else {
        title.textContent = 'Create Webhook';
    }

    modal.classList.add('show');
}

function closeWebhookModal() {
    document.getElementById('webhook-modal').classList.remove('show');
}

async function handleWebhookSubmit(e) {
    e.preventDefault();
    
    const id = document.getElementById('webhook-id').value;
    const eventTypes = Array.from(document.querySelectorAll('input[name="event-type"]:checked'))
        .map(cb => cb.value);

    if (eventTypes.length === 0) {
        showToast('Please select at least one event type', 'error');
        return;
    }

    const webhookData = {
        url: document.getElementById('webhook-url').value,
        event_types: eventTypes,
        enabled: document.getElementById('webhook-enabled').checked
    };

    try {
        const url = id ? `${API_BASE}/webhooks/${id}` : `${API_BASE}/webhooks`;
        const method = id ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(webhookData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Operation failed');
        }

        closeWebhookModal();
        loadWebhooks();
        showToast(`Webhook ${id ? 'updated' : 'created'} successfully!`);

    } catch (error) {
        showToast(`Failed: ${error.message}`, 'error');
    }
}

async function editWebhook(id) {
    try {
        const response = await fetch(`${API_BASE}/webhooks/${id}`);
        if (!response.ok) throw new Error('Failed to load webhook');

        const webhook = await response.json();
        openWebhookModal(webhook);

    } catch (error) {
        showToast(`Failed to load webhook: ${error.message}`, 'error');
    }
}

async function deleteWebhook(id) {
    if (!confirmAction('Are you sure you want to delete this webhook?')) return;

    try {
        const response = await fetch(`${API_BASE}/webhooks/${id}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Failed to delete webhook');

        loadWebhooks();
        showToast('Webhook deleted successfully!');

    } catch (error) {
        showToast(`Failed to delete: ${error.message}`, 'error');
    }
}

async function toggleWebhook(id, enabled) {
    try {
        const webhook = await fetch(`${API_BASE}/webhooks/${id}`).then(r => r.json());
        
        const response = await fetch(`${API_BASE}/webhooks/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...webhook, enabled })
        });

        if (!response.ok) throw new Error('Failed to toggle webhook');

        loadWebhooks();

    } catch (error) {
        showToast(`Failed to toggle webhook: ${error.message}`, 'error');
        loadWebhooks(); // Reload to reset state
    }
}

async function testWebhook(id) {
    const resultDiv = document.getElementById(`test-result-${id}`);
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = 'Testing webhook...';
    resultDiv.className = 'test-result';

    try {
        const response = await fetch(`${API_BASE}/webhooks/${id}/test`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Test failed');

        const result = await response.json();
        displayTestResult(id, result);

    } catch (error) {
        resultDiv.className = 'test-result error';
        resultDiv.innerHTML = `Test failed: ${error.message}`;
    }
}

function handleWebhookTestResult(webhookId, result) {
    displayTestResult(webhookId, result);
}

function displayTestResult(webhookId, result) {
    const resultDiv = document.getElementById(`test-result-${webhookId}`);
    
    if (result.success) {
        resultDiv.className = 'test-result success';
        resultDiv.innerHTML = `
            Success! Status: ${result.status_code}, 
            Response Time: ${result.response_time_ms}ms
        `;
    } else {
        resultDiv.className = 'test-result error';
        resultDiv.innerHTML = `
            Failed! ${result.error || 'Unknown error'}. 
            ${result.status_code ? `Status: ${result.status_code}` : ''}
            ${result.response_time_ms ? `Response Time: ${result.response_time_ms}ms` : ''}
        `;
    }
    
    resultDiv.style.display = 'block';
}

