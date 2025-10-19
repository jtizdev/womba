// Womba Web UI - Main Application Logic

// State Management
const state = {
    currentPage: 'dashboard',
    history: [],
    config: {},
    stats: {
        totalTests: 0,
        totalStories: 0,
        timeSaved: 0,
        successRate: 100
    }
};

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    loadDashboard();
    checkAPIStatus();
    setupGenerateForm();
    
    // Load data every 30 seconds
    setInterval(loadDashboard, 30000);
});

// Navigation
function initNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const page = link.dataset.page;
            navigateToPage(page);
        });
    });
}

function navigateToPage(pageName) {
    // Update nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
        if (link.dataset.page === pageName) {
            link.classList.add('active');
        }
    });
    
    // Update pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    document.getElementById(`${pageName}-page`).classList.add('active');
    
    // Load page-specific data
    if (pageName === 'dashboard') {
        loadDashboard();
    } else if (pageName === 'history') {
        loadHistory();
    }
    
    state.currentPage = pageName;
}

// API Status Check
async function checkAPIStatus() {
    try {
        const response = await fetch('/api/v1/health');
        const statusBadge = document.getElementById('apiStatus');
        
        if (response.ok) {
            statusBadge.innerHTML = '<span class="status-dot"></span><span>API Connected</span>';
        } else {
            statusBadge.innerHTML = '<span class="status-dot" style="background: #f44336;"></span><span>API Error</span>';
        }
    } catch (error) {
        const statusBadge = document.getElementById('apiStatus');
        statusBadge.innerHTML = '<span class="status-dot" style="background: #f44336;"></span><span>API Offline</span>';
    }
}

// Dashboard
async function loadDashboard() {
    try {
        // Load stats
        const statsResponse = await fetch('/api/v1/stats');
        if (statsResponse.ok) {
            const stats = await statsResponse.json();
            updateStats(stats);
        }
        
        // Load recent activity
        const historyResponse = await fetch('/api/v1/history?limit=5');
        if (historyResponse.ok) {
            const history = await historyResponse.json();
            updateRecentActivity(history);
        }
        
        // Update charts
        updateCharts();
    } catch (error) {
        console.error('Failed to load dashboard:', error);
    }
}

function updateStats(stats) {
    document.getElementById('totalTests').textContent = stats.total_tests || 0;
    document.getElementById('totalStories').textContent = stats.total_stories || 0;
    document.getElementById('timeSaved').textContent = `${stats.time_saved || 0}h`;
    document.getElementById('successRate').textContent = `${stats.success_rate || 100}%`;
    
    state.stats = stats;
}

function updateRecentActivity(history) {
    const activityList = document.getElementById('recentActivity');
    
    if (!history || history.length === 0) {
        activityList.innerHTML = '<div class="activity-empty"><p>No recent activity. Generate your first test plan!</p></div>';
        return;
    }
    
    activityList.innerHTML = history.map(item => `
        <div class="activity-item">
            <div class="activity-icon">${item.status === 'success' ? '✅' : '❌'}</div>
            <div class="activity-content">
                <div class="activity-title">${item.story_key}: ${item.test_count || 0} test cases generated</div>
                <div class="activity-meta">
                    ${new Date(item.created_at).toLocaleString()} • 
                    ${item.duration ? `${item.duration}s` : 'N/A'}
                </div>
            </div>
        </div>
    `).join('');
    
    state.history = history;
}

function updateCharts() {
    // Tests Over Time Chart
    const testsCtx = document.getElementById('testsOverTimeChart');
    if (testsCtx && !testsCtx.chart) {
        testsCtx.chart = new Chart(testsCtx, {
            type: 'line',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'Test Cases Generated',
                    data: [5, 8, 12, 7, 15, 10, 9],
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 5
                        }
                    }
                }
            }
        });
    }
    
    // Test Types Chart
    const typesCtx = document.getElementById('testTypesChart');
    if (typesCtx && !typesCtx.chart) {
        typesCtx.chart = new Chart(typesCtx, {
            type: 'doughnut',
            data: {
                labels: ['UI Tests', 'API Tests', 'Integration', 'Unit Tests'],
                datasets: [{
                    data: [35, 40, 15, 10],
                    backgroundColor: [
                        '#667eea',
                        '#764ba2',
                        '#4caf50',
                        '#ff9800'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
}

// Generate Form
function setupGenerateForm() {
    const form = document.getElementById('generateForm');
    const generateCodeCheckbox = document.getElementById('generateCode');
    const repoPathGroup = document.getElementById('repoPathGroup');
    
    generateCodeCheckbox.addEventListener('change', (e) => {
        repoPathGroup.style.display = e.target.checked ? 'block' : 'none';
    });
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleGenerate();
    });
}

async function handleGenerate() {
    const storyKey = document.getElementById('storyKey').value.trim();
    const uploadToZephyr = document.getElementById('uploadToZephyr').checked;
    const generateCode = document.getElementById('generateCode').checked;
    const repoPath = document.getElementById('repoPathInput').value.trim();
    
    if (!storyKey) {
        alert('Please enter a story key');
        return;
    }
    
    // Show progress
    document.getElementById('generateProgress').style.display = 'block';
    document.getElementById('generateResults').style.display = 'none';
    
    try {
        // Step 1: Collecting context
        updateProgressStep(1, 'active', 'Collecting context...', 33);
        
        const requestBody = {
            story_key: storyKey,
            upload_to_zephyr: uploadToZephyr
        };
        
        if (generateCode && repoPath) {
            requestBody.repo_path = repoPath;
        }
        
        const response = await fetch('/api/v1/test-plans/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) {
            throw new Error('Generation failed');
        }
        
        // Step 2: Generating tests
        updateProgressStep(1, 'complete', 'Context collected', 33);
        updateProgressStep(2, 'active', 'Generating tests...', 66);
        
        const result = await response.json();
        
        // Step 3: Upload (if enabled)
        updateProgressStep(2, 'complete', 'Tests generated', 66);
        
        if (uploadToZephyr) {
            updateProgressStep(3, 'active', 'Uploading to Zephyr...', 100);
            await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate upload
            updateProgressStep(3, 'complete', 'Uploaded successfully', 100);
        } else {
            updateProgressStep(3, 'complete', 'Skipped', 100);
        }
        
        // Show results
        displayResults(result);
        
        // Reload dashboard
        setTimeout(() => {
            loadDashboard();
        }, 2000);
        
    } catch (error) {
        alert('Error: ' + error.message);
        document.getElementById('generateProgress').style.display = 'none';
    }
}

function updateProgressStep(stepNum, status, message, progress) {
    const step = document.getElementById(`step${stepNum}`);
    const statusEl = step.querySelector('.step-status');
    
    step.classList.remove('active', 'complete');
    step.classList.add(status);
    statusEl.textContent = message;
    
    document.getElementById('progressFill').style.width = `${progress}%`;
}

function displayResults(result) {
    const resultsSection = document.getElementById('generateResults');
    const resultsContent = document.getElementById('resultsContent');
    
    resultsContent.innerHTML = `
        <div class="result-item">
            <strong>Story Key:</strong> ${result.story || 'N/A'}
        </div>
        <div class="result-item">
            <strong>Test Cases Generated:</strong> ${result.test_cases?.length || 0}
        </div>
        ${result.zephyr_ids ? `
        <div class="result-item">
            <strong>Zephyr Test IDs:</strong> ${result.zephyr_ids.join(', ')}
        </div>
        ` : ''}
        ${result.test_cases ? `
        <div class="result-item">
            <strong>Test Cases:</strong>
            <ul style="margin-top: 10px; padding-left: 20px;">
                ${result.test_cases.map(tc => `<li>${tc.title || tc.name}</li>`).join('')}
            </ul>
        </div>
        ` : ''}
    `;
    
    resultsSection.style.display = 'block';
}

// History Page
async function loadHistory() {
    try {
        const response = await fetch('/api/v1/history');
        if (!response.ok) {
            throw new Error('Failed to load history');
        }
        
        const history = await response.json();
        displayHistoryTable(history);
    } catch (error) {
        console.error('Failed to load history:', error);
    }
}

function displayHistoryTable(history) {
    const tbody = document.getElementById('historyTableBody');
    
    if (!history || history.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="6">No history available</td></tr>';
        return;
    }
    
    tbody.innerHTML = history.map(item => `
        <tr>
            <td><strong>${item.story_key}</strong></td>
            <td>${new Date(item.created_at).toLocaleDateString()}</td>
            <td>${item.test_count || 0}</td>
            <td>
                <span class="status-badge-table ${item.status}">
                    ${item.status === 'success' ? '✅ Success' : '❌ Failed'}
                </span>
            </td>
            <td>${item.duration ? `${item.duration}s` : 'N/A'}</td>
            <td>
                <button class="btn-small" onclick="viewHistoryDetails('${item.id}')">View</button>
            </td>
        </tr>
    `).join('');
}

async function viewHistoryDetails(id) {
    try {
        const response = await fetch(`/api/v1/history/${id}`);
        if (response.ok) {
            const details = await response.json();
            alert(JSON.stringify(details, null, 2));
        }
    } catch (error) {
        console.error('Failed to load history details:', error);
    }
}

// Search and Filter
document.getElementById('searchHistory')?.addEventListener('input', (e) => {
    filterHistory(e.target.value);
});

document.getElementById('filterStatus')?.addEventListener('change', (e) => {
    filterHistory(null, e.target.value);
});

function filterHistory(searchTerm = null, status = null) {
    const rows = document.querySelectorAll('.history-table tbody tr:not(.empty-row)');
    
    rows.forEach(row => {
        const storyKey = row.querySelector('td:first-child').textContent.toLowerCase();
        const rowStatus = row.querySelector('.status-badge-table').classList.contains('success') ? 'success' : 'failed';
        
        let showRow = true;
        
        if (searchTerm && !storyKey.includes(searchTerm.toLowerCase())) {
            showRow = false;
        }
        
        if (status && status !== 'all' && rowStatus !== status) {
            showRow = false;
        }
        
        row.style.display = showRow ? '' : 'none';
    });
}

