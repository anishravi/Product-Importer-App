// File upload functionality with WebSocket progress tracking

let currentUploadTaskId = null;
let uploadWebSocket = null;

document.addEventListener('DOMContentLoaded', function() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const progressContainer = document.getElementById('upload-progress');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const progressDetails = document.getElementById('progress-details');
    const uploadErrors = document.getElementById('upload-errors');
    const uploadResult = document.getElementById('upload-result');

    // Drag and drop handlers
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file && file.name.endsWith('.csv')) {
            handleFileUpload(file);
        } else {
            showToast('Please upload a CSV file', 'error');
        }
    });

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFileUpload(file);
        }
    });
});

async function handleFileUpload(file) {
    const formData = new FormData();
    formData.append('file', file);

    const progressContainer = document.getElementById('upload-progress');
    const uploadResult = document.getElementById('upload-result');
    const uploadErrors = document.getElementById('upload-errors');

    // Reset UI
    progressContainer.style.display = 'block';
    uploadResult.innerHTML = '';
    uploadErrors.innerHTML = '';
    updateProgress(0, 0, 0);

    try {
        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }

        const task = await response.json();
        currentUploadTaskId = task.task_id;

        // Connect WebSocket for progress updates
        connectWebSocket(task.task_id);

        // Also poll for status as fallback
        pollUploadStatus(task.task_id);

    } catch (error) {
        showToast(`Upload failed: ${error.message}`, 'error');
        document.getElementById('upload-progress').style.display = 'none';
        uploadResult.innerHTML = `<div class="result-message error">Upload failed: ${error.message}</div>`;
    }
}

function connectWebSocket(taskId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${taskId}`;
    
    uploadWebSocket = new WebSocket(wsUrl);

    uploadWebSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'progress') {
            updateProgress(data.progress, data.processed, data.total);
            if (data.errors && data.errors.length > 0) {
                displayErrors(data.errors);
            }
        } else if (data.type === 'complete') {
            handleUploadComplete(data.success, data.message);
        }
    };

    uploadWebSocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        // Fallback to polling
        pollUploadStatus(taskId);
    };

    uploadWebSocket.onclose = () => {
        console.log('WebSocket closed');
    };
}

async function pollUploadStatus(taskId) {
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/upload/task/${taskId}`);
            if (!response.ok) return;

            const task = await response.json();
            
            updateProgress(
                task.progress,
                task.processed_rows,
                task.total_rows
            );

            if (task.errors) {
                try {
                    const errors = JSON.parse(task.errors);
                    displayErrors(errors);
                } catch (e) {
                    // Ignore parse errors
                }
            }

            if (task.status === 'completed' || task.status === 'failed') {
                clearInterval(interval);
                if (uploadWebSocket) {
                    uploadWebSocket.close();
                }
                
                handleUploadComplete(
                    task.status === 'completed',
                    task.status === 'completed' 
                        ? `Successfully processed ${task.processed_rows} products`
                        : task.errors || 'Upload failed'
                );
            }
        } catch (error) {
            console.error('Error polling status:', error);
        }
    }, 2000);
}

function updateProgress(progress, processed, total) {
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const progressDetails = document.getElementById('progress-details');

    progressFill.style.width = `${progress}%`;
    progressText.textContent = `${progress.toFixed(1)}%`;
    progressDetails.textContent = `${processed} / ${total} rows processed`;
}

function displayErrors(errors) {
    const uploadErrors = document.getElementById('upload-errors');
    uploadErrors.innerHTML = errors.slice(0, 10).map(err => 
        `<div class="error-item">Row ${err.row || 'N/A'}: ${err.error}</div>`
    ).join('');
    
    if (errors.length > 10) {
        uploadErrors.innerHTML += `<div class="error-item">... and ${errors.length - 10} more errors</div>`;
    }
}

function handleUploadComplete(success, message) {
    const uploadResult = document.getElementById('upload-result');
    const progressContainer = document.getElementById('upload-progress');
    
    if (success) {
        uploadResult.innerHTML = `<div class="result-message success">${message}</div>`;
        showToast('Upload completed successfully!', 'success');
        
        // Refresh products if on products tab
        if (document.getElementById('products-tab').classList.contains('active')) {
            loadProducts();
        }
    } else {
        uploadResult.innerHTML = `<div class="result-message error">${message}</div>`;
        showToast('Upload failed', 'error');
    }
    
    // Hide progress after a delay
    setTimeout(() => {
        progressContainer.style.display = 'none';
    }, 5000);
    
    currentUploadTaskId = null;
}

