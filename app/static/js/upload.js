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
            // Clear previous results
            const uploadResult = document.getElementById('upload-result');
            uploadResult.innerHTML = '';
            
            handleFileUpload(file);
        } else {
            showToast('Please upload a CSV file', 'error');
        }
    });

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            // Clear previous results
            const uploadResult = document.getElementById('upload-result');
            uploadResult.innerHTML = '';
            
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

        console.log(`Upload task started: ${task.task_id}`);

        // Connect WebSocket for progress updates (primary method)
        connectWebSocket(task.task_id);

        // Note: Removed automatic polling fallback - only use WebSocket unless it fails

    } catch (error) {
        showToast(`Upload failed: ${error.message}`, 'error');
        document.getElementById('upload-progress').style.display = 'none';
        uploadResult.innerHTML = `<div class="result-message error">Upload failed: ${error.message}</div>`;
    }
}

function connectWebSocket(taskId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${taskId}`;
    
    console.log(`Connecting to WebSocket: ${wsUrl}`);
    uploadWebSocket = new WebSocket(wsUrl);

    uploadWebSocket.onopen = () => {
        console.log('WebSocket connected successfully');
    };

    uploadWebSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('WebSocket message received:', data);
        
        if (data.type === 'connected') {
            console.log(`WebSocket connected to task ${data.task_id}`);
        } else if (data.type === 'progress') {
            updateProgress(data.progress, data.processed, data.total);
            if (data.errors && data.errors.length > 0) {
                displayErrors(data.errors);
            }
        } else if (data.type === 'complete') {
            console.log('Upload complete via WebSocket:', data);
            handleUploadComplete(data.success, data.message);
        } else if (data.type === 'pong') {
            console.log('WebSocket pong received');
        }
    };

    uploadWebSocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        showToast('Connection error - falling back to polling', 'warning');
        // Only fallback to polling if WebSocket fails
        pollUploadStatus(taskId);
    };

    uploadWebSocket.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        // Don't auto-reconnect or fallback unless there was an error
        if (event.code !== 1000) { // 1000 is normal closure
            console.log('Abnormal WebSocket close, falling back to polling');
            pollUploadStatus(taskId);
        }
    };

    // Send a ping every 30 seconds to keep connection alive
    const pingInterval = setInterval(() => {
        if (uploadWebSocket && uploadWebSocket.readyState === WebSocket.OPEN) {
            uploadWebSocket.send('ping');
        } else {
            clearInterval(pingInterval);
        }
    }, 30000);
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
    
    // Only show errors during processing, not after completion
    if (currentUploadTaskId && errors && errors.length > 0) {
        uploadErrors.innerHTML = errors.slice(0, 10).map(err => {
            // Handle different error structures
            if (err.batch_error) {
                return `<div class="error-item">System: ${err.batch_error}</div>`;
            } else if (err.error) {
                const rowText = err.row !== undefined ? `Row ${err.row}` : 'Processing';
                return `<div class="error-item">${rowText}: ${err.error}</div>`;
            } else if (typeof err === 'string') {
                return `<div class="error-item">Error: ${err}</div>`;
            } else {
                return `<div class="error-item">Unknown error occurred</div>`;
            }
        }).join('');
        
        if (errors.length > 10) {
            uploadErrors.innerHTML += `<div class="error-item">... and ${errors.length - 10} more errors</div>`;
        }
    }
}

function handleUploadComplete(success, message) {
    const uploadResult = document.getElementById('upload-result');
    const uploadErrors = document.getElementById('upload-errors');
    const progressContainer = document.getElementById('upload-progress');
    
    // Close WebSocket connection
    if (uploadWebSocket) {
        uploadWebSocket.close(1000, 'Upload completed');
        uploadWebSocket = null;
    }
    
    // Clear any processing errors since we're showing final result
    uploadErrors.innerHTML = '';
    
    if (success) {
        uploadResult.innerHTML = `<div class="result-message success">✅ ${message}</div>`;
        showToast('Upload completed successfully!', 'success');
        
        // Set global flag for recent upload
        if (window.appState) {
            window.appState.recentUpload = true;
            window.appState.lastUploadTime = Date.now();
        }
        
        // Add visual indicator to products tab
        const productsTab = document.querySelector('[data-tab="products"]');
        if (productsTab && !productsTab.classList.contains('active')) {
            productsTab.classList.add('has-updates');
            productsTab.title = 'New products available - click to view';
        }
        
        // Always refresh products data after successful upload
        // This ensures the data is ready when user switches to products tab
        if (typeof loadProducts === 'function') {
            loadProducts();
        } else {
            console.warn('loadProducts function not available');
        }
    } else {
        // Better error message handling
        let errorMessage = message || 'Upload failed';
        
        // Try to parse error message if it's JSON
        try {
            if (typeof message === 'string' && message.startsWith('[{')) {
                const errors = JSON.parse(message);
                if (Array.isArray(errors) && errors.length > 0) {
                    errorMessage = `Failed: ${errors[0].error || 'Unknown error'}`;
                    
                    // Show first few errors in detail
                    const errorDetails = errors.slice(0, 5).map(err => {
                        if (err.batch_error) {
                            return `System: ${err.batch_error}`;
                        } else if (err.error) {
                            const rowText = err.row !== undefined ? `Row ${err.row}` : 'Processing';
                            return `${rowText}: ${err.error}`;
                        } else {
                            return `Unknown error: ${JSON.stringify(err)}`;
                        }
                    }).join('<br>');
                    
                    uploadResult.innerHTML = `
                        <div class="result-message error">
                            ❌ Upload failed with ${errors.length} error(s)<br>
                            <small>${errorDetails}</small>
                            ${errors.length > 5 ? `<br><small>... and ${errors.length - 5} more errors</small>` : ''}
                        </div>
                    `;
                } else {
                    uploadResult.innerHTML = `<div class="result-message error">❌ ${errorMessage}</div>`;
                }
            } else {
                uploadResult.innerHTML = `<div class="result-message error">❌ ${errorMessage}</div>`;
            }
        } catch (e) {
            // Use original message if parsing fails
            uploadResult.innerHTML = `<div class="result-message error">❌ ${errorMessage}</div>`;
        }
        
        showToast(`Upload failed: ${errorMessage}`, 'error');
    }
    
    // Hide progress bar but keep result visible
    setTimeout(() => {
        progressContainer.style.display = 'none';
    }, 2000);
    
    currentUploadTaskId = null;
}

