/**
 * SRT Gateway API Module
 * Handles all AJAX requests to the backend API
 */

class SRTGatewayAPI {
    constructor(baseURL = '/api') {
        this.baseURL = baseURL;
        this.wsConnection = null;
        this.wsCallbacks = [];
    }

    /**
     * Generic AJAX request handler with error handling
     */
    async request(endpoint, options = {}) {
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, config);
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({ message: 'Request failed' }));
                throw new Error(error.message || `HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    /**
     * GET request
     */
    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }

    /**
     * POST request
     */
    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * PUT request
     */
    async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    /**
     * DELETE request
     */
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    // ==================== Session Management ====================

    /**
     * Get all sessions
     */
    async getSessions() {
        return this.get('/sessions');
    }

    /**
     * Get specific session by RX port
     */
    async getSession(rxPort) {
        return this.get(`/sessions/${rxPort}`);
    }

    /**
     * Create a new session
     */
    async createSession(sessionData) {
        return this.post('/sessions', sessionData);
    }

    /**
     * Update an existing session
     */
    async updateSession(rxPort, sessionData) {
        return this.put(`/sessions/${rxPort}`, sessionData);
    }

    /**
     * Delete a session
     */
    async deleteSession(rxPort) {
        return this.delete(`/sessions/${rxPort}`);
    }

    /**
     * Start a session
     */
    async startSession(rxPort) {
        return this.post(`/sessions/${rxPort}/start`, {});
    }

    /**
     * Stop a session
     */
    async stopSession(rxPort) {
        return this.post(`/sessions/${rxPort}/stop`, {});
    }

    // ==================== Route Management ====================

    /**
     * Get route by ID
     */
    async getRoute(routeId) {
        return this.get(`/routes/${routeId}`);
    }

    /**
     * Create a new route
     */
    async createRoute(routeData) {
        return this.post('/routes', routeData);
    }

    /**
     * Update a route
     */
    async updateRoute(routeId, routeData) {
        return this.put(`/routes/${routeId}`, routeData);
    }

    /**
     * Stop a route
     */
    async stopRoute(routeId) {
        return this.post(`/routes/${routeId}/stop`, {});
    }

    // ==================== Statistics ====================

    /**
     * Get current statistics
     */
    async getStats() {
        return this.get('/stats');
    }

    /**
     * Get statistics history for a port
     */
    async getStatsHistory(rxPort, minutes = 5) {
        return this.get(`/stats/history/${rxPort}?minutes=${minutes}`);
    }

    // ==================== WebSocket ====================

    /**
     * Connect to WebSocket for real-time updates
     */
    connectWebSocket(onMessage, onError, onClose) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsURL = `${protocol}//${window.location.host}/ws`;

        this.wsConnection = new WebSocket(wsURL);

        this.wsConnection.onopen = () => {
            console.log('WebSocket connected');
        };

        this.wsConnection.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (onMessage) onMessage(data);
                this.wsCallbacks.forEach(callback => callback(data));
            } catch (error) {
                console.error('WebSocket message error:', error);
            }
        };

        this.wsConnection.onerror = (error) => {
            console.error('WebSocket error:', error);
            if (onError) onError(error);
        };

        this.wsConnection.onclose = () => {
            console.log('WebSocket disconnected');
            if (onClose) onClose();
            // Attempt to reconnect after 5 seconds
            setTimeout(() => this.connectWebSocket(onMessage, onError, onClose), 5000);
        };
    }

    /**
     * Register a callback for WebSocket messages
     */
    onWebSocketMessage(callback) {
        this.wsCallbacks.push(callback);
    }

    /**
     * Disconnect WebSocket
     */
    disconnectWebSocket() {
        if (this.wsConnection) {
            this.wsConnection.close();
            this.wsConnection = null;
        }
    }
}

// Export the API instance
const api = new SRTGatewayAPI();
