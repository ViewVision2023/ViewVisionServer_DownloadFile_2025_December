/**
 * SRT Gateway UI Controller
 * Manages all UI interactions and rendering
 */

class SRTGatewayUI {
    constructor(api) {
        this.api = api;
        this.sessions = [];
        this.selectedRoutes = new Set();
        this.expandedRoutes = new Set();
        this.currentScreen = 'routes';
        this.currentStatsPort = null;
        this.refreshInterval = null;
        this.charts = {};
    }

    /**
     * Initialize the application
     */
    async init() {
        this.setupEventListeners();
        this.loadServerInfo();
        this.startAutoRefresh();
        await this.loadSessions();
        this.connectWebSocket();
    }

    /**
     * Setup global event listeners
     */
    setupEventListeners() {
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => this.handleNavigation(e));
        });

        // Bulk actions
        const bulkActions = document.getElementById('bulk-actions');
        if (bulkActions) {
            bulkActions.addEventListener('change', (e) => this.handleBulkAction(e.target.value));
        }
    }

    /**
     * Load server information
     */
    async loadServerInfo() {
        try {
            const serverIP = window.location.hostname;
            const serverIPElement = document.getElementById('server-ip');
            if (serverIPElement) {
                serverIPElement.textContent = serverIP;
            }
        } catch (error) {
            console.error('Error loading server info:', error);
        }
    }

    /**
     * Handle navigation between screens
     */
    handleNavigation(event) {
        const screen = event.target.dataset.screen;
        if (!screen) return;

        this.currentScreen = screen;

        // Update active nav item
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        event.target.classList.add('active');

        // Render appropriate screen
        switch (screen) {
            case 'routes':
                this.renderRoutes();
                break;
            case 'create':
                this.openCreateSessionModal();
                break;
            case 'system':
                this.renderSystemStats();
                break;
            case 'settings':
                this.renderSettings();
                break;
            default:
                console.warn('Unknown screen:', screen);
        }
    }

    /**
     * Load all sessions via AJAX
     */
    async loadSessions() {
        try {
            const data = await this.api.getSessions();
            
            if (data.ok) {
                this.sessions = data.sessions;
                if (this.currentScreen === 'routes') {
                    this.renderRoutes();
                }
            }
        } catch (error) {
            console.error('Error loading sessions:', error);
            this.showError('Failed to load routes');
        }
    }

    /**
     * Render routes screen
     */
    renderRoutes() {
        const contentArea = document.getElementById('content-area');
        
        if (this.sessions.length === 0) {
            contentArea.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📡</div>
                    <div class="empty-state-text">No routes configured</div>
                    <button class="btn btn-primary" onclick="ui.openCreateSessionModal()">Create Your First Route</button>
                </div>
            `;
            return;
        }

        const routeList = document.createElement('div');
        routeList.className = 'route-list';

        this.sessions.forEach(session => {
            const card = this.createRouteCard(session);
            routeList.appendChild(card);
        });

        contentArea.innerHTML = '';
        contentArea.appendChild(card);
        
        // Draw sparklines after rendering
        setTimeout(() => this.drawAllSparklines(), 50);
    }

    /**
     * Create a route card element
     */
    createRouteCard(session) {
        const card = document.createElement('div');
        card.className = 'route-card';
        card.dataset.port = session.rx_port;

        // Determine status class
        let statusClass = 'status-stopped';
        if (session.status === 'running') {
            statusClass = session.has_input ? 'status-running' : 'status-connecting';
        }

        const isExpanded = this.expandedRoutes.has(session.rx_port);
        
        card.innerHTML = `
            <div class="route-header" onclick="ui.toggleRouteExpand(${session.rx_port})">
                <span class="route-expand-icon">${isExpanded ? '▼' : '▶'}</span>
                <div class="route-status ${statusClass}"></div>
                <div class="route-info">
                    <div class="route-name">${this.escapeHtml(session.name)}</div>
                    <div class="route-details">
                        Source: ${session.rx_mode} Port ${session.rx_port} | ${session.routes.length} Destination(s)
                    </div>
                    <div class="bitrate-display">
                        <span class="bitrate-value">${(session.rx_bitrate || 0).toFixed(2)} Mbps</span>
                        <canvas class="sparkline" id="spark-rx-${session.rx_port}" width="100" height="25"></canvas>
                    </div>
                </div>
                <div class="route-actions">
                    <button class="btn-icon stats-btn" onclick="event.stopPropagation(); ui.openStatisticsModal(${session.rx_port})" title="View Statistics">
                        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M3 14h4V8H3zm6 0h4V3h-4zm6 0h4V10h-4z"/>
                        </svg>
                    </button>
                    <button class="btn-icon" onclick="event.stopPropagation(); ui.editSession(${session.rx_port})" title="Edit Route">
                        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 3l3 3-9 9H3v-3z"/>
                        </svg>
                    </button>
                    ${session.status === 'running' 
                        ? `<button class="btn-icon" onclick="event.stopPropagation(); ui.stopSession(${session.rx_port})" title="Stop Route">⏸</button>`
                        : `<button class="btn-icon" onclick="event.stopPropagation(); ui.startSession(${session.rx_port})" title="Start Route">▶</button>`
                    }
                    <button class="btn-icon btn-danger" onclick="event.stopPropagation(); ui.deleteSession(${session.rx_port})" title="Delete Route">🗑</button>
                </div>
            </div>
            ${isExpanded ? this.createRouteDetails(session) : ''}
        `;

        return card;
    }

    /**
     * Create route details section
     */
    createRouteDetails(session) {
        let html = '<div class="route-details-section">';
        
        // Source details
        html += `
            <div class="detail-group">
                <h4>Source Configuration</h4>
                <div class="detail-row">
                    <span class="detail-label">Mode:</span>
                    <span class="detail-value">${session.rx_mode}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Port:</span>
                    <span class="detail-value">${session.rx_port}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Bitrate:</span>
                    <span class="detail-value">${(session.rx_bitrate || 0).toFixed(2)} Mbps</span>
                </div>
            </div>
        `;

        // Destinations
        if (session.routes && session.routes.length > 0) {
            html += '<div class="detail-group"><h4>Destinations</h4>';
            session.routes.forEach((route, idx) => {
                html += `
                    <div class="destination-item">
                        <div class="destination-header">
                            <span class="destination-number">${idx + 1}</span>
                            <span class="destination-name">${this.escapeHtml(route.name || `Destination ${idx + 1}`)}</span>
                            <span class="destination-bitrate">${(route.tx_bitrate || 0).toFixed(2)} Mbps</span>
                        </div>
                        <div class="destination-details">
                            ${route.tx_ip}:${route.tx_port} (${route.tx_mode})
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        }

        html += '</div>';
        return html;
    }

    /**
     * Toggle route expansion
     */
    toggleRouteExpand(rxPort) {
        if (this.expandedRoutes.has(rxPort)) {
            this.expandedRoutes.delete(rxPort);
        } else {
            this.expandedRoutes.add(rxPort);
        }
        this.renderRoutes();
    }

    /**
     * Start a session via AJAX
     */
    async startSession(rxPort) {
        try {
            const result = await this.api.startSession(rxPort);
            if (result.ok) {
                this.showSuccess(`Route ${rxPort} started successfully`);
                await this.loadSessions();
            }
        } catch (error) {
            this.showError(`Failed to start route: ${error.message}`);
        }
    }

    /**
     * Stop a session via AJAX
     */
    async stopSession(rxPort) {
        try {
            const result = await this.api.stopSession(rxPort);
            if (result.ok) {
                this.showSuccess(`Route ${rxPort} stopped successfully`);
                await this.loadSessions();
            }
        } catch (error) {
            this.showError(`Failed to stop route: ${error.message}`);
        }
    }

    /**
     * Delete a session via AJAX
     */
    async deleteSession(rxPort) {
        if (!confirm(`Are you sure you want to delete route on port ${rxPort}?`)) {
            return;
        }

        try {
            const result = await this.api.deleteSession(rxPort);
            if (result.ok) {
                this.showSuccess(`Route ${rxPort} deleted successfully`);
                await this.loadSessions();
            }
        } catch (error) {
            this.showError(`Failed to delete route: ${error.message}`);
        }
    }

    /**
     * Edit session - open modal with existing data
     */
    async editSession(rxPort) {
        try {
            const data = await this.api.getSession(rxPort);
            if (data.ok) {
                this.openEditSessionModal(data.session);
            }
        } catch (error) {
            this.showError(`Failed to load session data: ${error.message}`);
        }
    }

    /**
     * Open create session modal
     */
    openCreateSessionModal() {
        const modal = document.getElementById('session-modal');
        if (modal) {
            modal.style.display = 'block';
            document.getElementById('modal-title').textContent = 'Create New Route';
            document.getElementById('session-form').reset();
        }
    }

    /**
     * Open edit session modal
     */
    openEditSessionModal(session) {
        const modal = document.getElementById('session-modal');
        if (modal) {
            modal.style.display = 'block';
            document.getElementById('modal-title').textContent = 'Edit Route';
            
            // Populate form with session data
            const form = document.getElementById('session-form');
            Object.keys(session).forEach(key => {
                const input = form.elements[key];
                if (input) {
                    input.value = session[key];
                }
            });
        }
    }

    /**
     * Open statistics modal
     */
    async openStatisticsModal(rxPort) {
        this.currentStatsPort = rxPort;
        const modal = document.getElementById('stats-modal');
        if (modal) {
            modal.style.display = 'block';
            await this.loadStats(rxPort);
        }
    }

    /**
     * Load statistics for a port via AJAX
     */
    async loadStats(rxPort, minutes = 5) {
        try {
            const data = await this.api.getStatsHistory(rxPort, minutes);
            if (data.ok) {
                this.renderStatsChart(data.history);
            }
        } catch (error) {
            this.showError(`Failed to load statistics: ${error.message}`);
        }
    }

    /**
     * Render system statistics
     */
    async renderSystemStats() {
        try {
            const data = await this.api.getStats();
            const contentArea = document.getElementById('content-area');
            
            contentArea.innerHTML = `
                <div class="system-stats">
                    <h2>System Statistics</h2>
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-label">Total Routes</div>
                            <div class="stat-value">${this.sessions.length}</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">Active Routes</div>
                            <div class="stat-value">${this.sessions.filter(s => s.status === 'running').length}</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">Total Bitrate</div>
                            <div class="stat-value">${this.calculateTotalBitrate().toFixed(2)} Mbps</div>
                        </div>
                    </div>
                </div>
            `;
        } catch (error) {
            this.showError(`Failed to load system stats: ${error.message}`);
        }
    }

    /**
     * Calculate total bitrate across all sessions
     */
    calculateTotalBitrate() {
        return this.sessions.reduce((total, session) => {
            return total + (session.rx_bitrate || 0);
        }, 0);
    }

    /**
     * Connect to WebSocket for real-time updates
     */
    connectWebSocket() {
        this.api.connectWebSocket(
            (data) => this.handleWebSocketMessage(data),
            (error) => console.error('WebSocket error:', error),
            () => console.log('WebSocket closed')
        );
    }

    /**
     * Handle WebSocket messages
     */
    handleWebSocketMessage(data) {
        if (data.type === 'stats_update') {
            // Update sessions with new stats
            this.loadSessions();
        }
    }

    /**
     * Start auto-refresh timer
     */
    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            if (this.currentScreen === 'routes') {
                this.loadSessions();
            } else if (this.currentScreen === 'system') {
                this.renderSystemStats();
            }
        }, 5000);
    }

    /**
     * Stop auto-refresh timer
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    /**
     * Draw all sparklines
     */
    drawAllSparklines() {
        this.sessions.forEach(session => {
            this.drawSparkline(`spark-rx-${session.rx_port}`, session.bitrate_history || []);
        });
    }

    /**
     * Draw a single sparkline
     */
    drawSparkline(canvasId, data) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        ctx.clearRect(0, 0, width, height);

        if (!data || data.length === 0) return;

        const max = Math.max(...data, 1);
        const step = width / (data.length - 1 || 1);

        ctx.strokeStyle = '#ff9f1c';
        ctx.lineWidth = 2;
        ctx.beginPath();

        data.forEach((value, index) => {
            const x = index * step;
            const y = height - (value / max) * height;
            
            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });

        ctx.stroke();
    }

    /**
     * Render statistics chart
     */
    renderStatsChart(history) {
        // Implementation for Chart.js or similar
        console.log('Rendering stats chart with history:', history);
    }

    /**
     * Render settings screen
     */
    renderSettings() {
        const contentArea = document.getElementById('content-area');
        contentArea.innerHTML = `
            <div class="settings-screen">
                <h2>Settings</h2>
                <p>Settings panel coming soon...</p>
            </div>
        `;
    }

    /**
     * Handle bulk actions
     */
    async handleBulkAction(action) {
        const selectedPorts = Array.from(this.selectedRoutes);
        
        if (selectedPorts.length === 0) {
            this.showError('No routes selected');
            return;
        }

        switch (action) {
            case 'start':
                await this.bulkStart(selectedPorts);
                break;
            case 'stop':
                await this.bulkStop(selectedPorts);
                break;
            case 'delete':
                await this.bulkDelete(selectedPorts);
                break;
        }

        this.selectedRoutes.clear();
        await this.loadSessions();
    }

    /**
     * Bulk start sessions
     */
    async bulkStart(ports) {
        const promises = ports.map(port => this.api.startSession(port));
        try {
            await Promise.all(promises);
            this.showSuccess(`Started ${ports.length} route(s)`);
        } catch (error) {
            this.showError(`Failed to start some routes: ${error.message}`);
        }
    }

    /**
     * Bulk stop sessions
     */
    async bulkStop(ports) {
        const promises = ports.map(port => this.api.stopSession(port));
        try {
            await Promise.all(promises);
            this.showSuccess(`Stopped ${ports.length} route(s)`);
        } catch (error) {
            this.showError(`Failed to stop some routes: ${error.message}`);
        }
    }

    /**
     * Bulk delete sessions
     */
    async bulkDelete(ports) {
        if (!confirm(`Delete ${ports.length} route(s)?`)) return;
        
        const promises = ports.map(port => this.api.deleteSession(port));
        try {
            await Promise.all(promises);
            this.showSuccess(`Deleted ${ports.length} route(s)`);
        } catch (error) {
            this.showError(`Failed to delete some routes: ${error.message}`);
        }
    }

    /**
     * Show success message
     */
    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    /**
     * Show error message
     */
    showError(message) {
        this.showNotification(message, 'error');
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);

        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Cleanup on destroy
     */
    destroy() {
        this.stopAutoRefresh();
        this.api.disconnectWebSocket();
    }
}

// Initialize the UI when DOM is ready
let ui;
document.addEventListener('DOMContentLoaded', () => {
    ui = new SRTGatewayUI(api);
    ui.init();
});
