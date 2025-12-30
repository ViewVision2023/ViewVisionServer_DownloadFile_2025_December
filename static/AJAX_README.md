# SRT Gateway - AJAX JavaScript Implementation

## Overview

This implementation provides a complete AJAX-based frontend for the SRT Gateway application. All data operations are performed asynchronously without page reloads, providing a smooth, modern user experience.

## File Structure

```
static/
├── ajax.html           # Main HTML page with AJAX
├── css/
│   └── styles.css      # Complete styling
└── js/
    ├── api.js          # AJAX API layer
    ├── ui.js           # UI controller
    ├── forms.js        # Form handling
    └── utils.js        # Utility functions
```

## JavaScript Modules

### 1. API Module (`api.js`)

**Purpose**: Handles all HTTP requests to the backend API

**Features**:
- RESTful API wrapper with error handling
- WebSocket connection management
- Automatic reconnection on disconnect
- Promise-based async/await interface

**Methods**:
```javascript
// Sessions
api.getSessions()              // GET /api/sessions
api.getSession(rxPort)         // GET /api/sessions/{port}
api.createSession(data)        // POST /api/sessions
api.updateSession(port, data)  // PUT /api/sessions/{port}
api.deleteSession(port)        // DELETE /api/sessions/{port}
api.startSession(port)         // POST /api/sessions/{port}/start
api.stopSession(port)          // POST /api/sessions/{port}/stop

// Routes
api.getRoute(routeId)          // GET /api/routes/{id}
api.createRoute(data)          // POST /api/routes
api.updateRoute(id, data)      // PUT /api/routes/{id}
api.stopRoute(id)              // POST /api/routes/{id}/stop

// Statistics
api.getStats()                 // GET /api/stats
api.getStatsHistory(port, min) // GET /api/stats/history/{port}

// WebSocket
api.connectWebSocket(onMessage, onError, onClose)
api.onWebSocketMessage(callback)
api.disconnectWebSocket()
```

**Example Usage**:
```javascript
// Load all sessions
const data = await api.getSessions();
if (data.ok) {
    console.log(data.sessions);
}

// Create a new session
try {
    const result = await api.createSession({
        name: "My Stream",
        rx_mode: "listener",
        rx_port: 8000,
        routes: [...]
    });
    console.log('Session created!');
} catch (error) {
    console.error('Failed:', error.message);
}
```

### 2. UI Controller (`ui.js`)

**Purpose**: Manages all UI rendering and user interactions

**Features**:
- Dynamic content rendering
- Real-time updates via WebSocket
- Auto-refresh functionality
- Modal management
- Notification system

**Key Methods**:
```javascript
// Initialization
ui.init()

// Session Management
ui.loadSessions()
ui.startSession(rxPort)
ui.stopSession(rxPort)
ui.deleteSession(rxPort)
ui.editSession(rxPort)

// UI Rendering
ui.renderRoutes()
ui.renderSystemStats()
ui.renderSettings()

// Modals
ui.openCreateSessionModal()
ui.openEditSessionModal(session)
ui.openStatisticsModal(rxPort)

// Notifications
ui.showSuccess(message)
ui.showError(message)
ui.showNotification(message, type)

// Bulk Operations
ui.handleBulkAction(action)
ui.bulkStart(ports)
ui.bulkStop(ports)
ui.bulkDelete(ports)
```

**Example Usage**:
```javascript
// Initialize the UI
ui.init();

// Start a session
await ui.startSession(8000);

// Show success message
ui.showSuccess('Route started successfully');
```

### 3. Forms Module (`forms.js`)

**Purpose**: Handles form submissions and validations

**Features**:
- Form validation
- Dynamic route field management
- Create/Edit mode handling
- Data serialization

**Key Methods**:
```javascript
// Form Handling
forms.handleSessionSubmit(event)
forms.validateSessionData(data)

// Route Fields
forms.addRouteField()
forms.removeRouteField(index)

// Modals
forms.openCreateModal()
forms.openEditModal(rxPort)
forms.closeModal(modal)

// Data Management
forms.collectRoutes(formData)
forms.populateForm(session)
forms.resetForm()
```

**Example Usage**:
```javascript
// Add a destination route field
forms.addRouteField();

// Open edit modal
await forms.openEditModal(8000);
```

### 4. Utils Module (`utils.js`)

**Purpose**: Provides utility functions and helpers

**Features**:
- Data formatting
- Validation helpers
- Browser utilities
- Local storage wrapper
- File import/export

**Key Functions**:
```javascript
// Formatting
Utils.formatBytes(bytes)
Utils.formatBitrate(bitrate)
Utils.formatTimestamp(timestamp)
Utils.formatDuration(seconds)

// Validation
Utils.isValidIP(ip)
Utils.isValidPort(port)

// Data Operations
Utils.deepClone(obj)
Utils.sortBy(array, key, ascending)
Utils.filterBySearch(array, term, keys)

// Storage
Utils.storage.set(key, value)
Utils.storage.get(key, defaultValue)
Utils.sessionStorage.set(key, value)

// File Operations
Utils.exportSessions(sessions)
Utils.importSessions(file)
Utils.downloadFile(data, filename, type)

// Misc
Utils.copyToClipboard(text)
Utils.debounce(func, wait)
Utils.throttle(func, limit)
```

## AJAX Request Flow

### Creating a New Session

```
1. User fills form → 2. forms.handleSessionSubmit()
                   ↓
3. Validate data → 4. api.createSession(data)
                   ↓
5. POST /api/sessions → 6. Server processes
                        ↓
7. Response received → 8. ui.showSuccess()
                       ↓
9. ui.loadSessions() → 10. Update UI
```

### Real-Time Updates

```
1. WebSocket connects → 2. api.connectWebSocket()
                        ↓
3. Server sends update → 4. ui.handleWebSocketMessage()
                         ↓
5. ui.loadSessions() → 6. UI refreshes automatically
```

## Integration with Backend

### API Endpoints Used

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/sessions` | List all sessions |
| GET | `/api/sessions/{port}` | Get session details |
| POST | `/api/sessions` | Create new session |
| PUT | `/api/sessions/{port}` | Update session |
| DELETE | `/api/sessions/{port}` | Delete session |
| POST | `/api/sessions/{port}/start` | Start session |
| POST | `/api/sessions/{port}/stop` | Stop session |
| GET | `/api/stats` | Get system stats |
| GET | `/api/stats/history/{port}` | Get historical stats |
| WS | `/ws` | WebSocket for real-time updates |

### Request/Response Format

**Create Session Request**:
```json
{
    "name": "Main Stream",
    "rx_mode": "listener",
    "rx_port": 8000,
    "rx_ip": "0.0.0.0",
    "latency": 120,
    "passphrase": "secret",
    "routes": [
        {
            "name": "Output 1",
            "tx_mode": "caller",
            "tx_ip": "192.168.1.100",
            "tx_port": 9000,
            "latency": 120,
            "passphrase": "",
            "fec": "none"
        }
    ]
}
```

**Response**:
```json
{
    "ok": true,
    "message": "Session created successfully",
    "session": { ... }
}
```

## Features

### ✅ Implemented

- **AJAX Operations**: All CRUD operations without page reload
- **Real-Time Updates**: WebSocket connection for live data
- **Form Validation**: Client-side validation before submission
- **Error Handling**: Comprehensive error handling and user feedback
- **Notifications**: Toast-style notifications for user actions
- **Bulk Operations**: Start/stop/delete multiple routes
- **Statistics**: Real-time bitrate charts and stats
- **Responsive Design**: Mobile-friendly interface
- **Modal Dialogs**: Clean modal interfaces for forms

### 🔄 Auto-Refresh

The UI automatically refreshes every 5 seconds:
```javascript
setInterval(() => {
    if (currentScreen === 'routes') {
        ui.loadSessions();
    }
}, 5000);
```

### 📊 WebSocket Integration

Real-time updates via WebSocket:
```javascript
api.connectWebSocket(
    (data) => {
        // Handle incoming messages
        ui.loadSessions();
    }
);
```

## Usage

### Basic Setup

1. **Include Scripts in HTML**:
```html
<script src="/static/js/utils.js"></script>
<script src="/static/js/api.js"></script>
<script src="/static/js/ui.js"></script>
<script src="/static/js/forms.js"></script>
```

2. **Initialize on Page Load**:
```javascript
document.addEventListener('DOMContentLoaded', () => {
    ui.init();
});
```

### Creating a Route

```javascript
// Via UI
ui.openCreateSessionModal();

// Programmatically
const sessionData = {
    name: "My Stream",
    rx_mode: "listener",
    rx_port: 8000,
    routes: [...]
};

await api.createSession(sessionData);
await ui.loadSessions(); // Refresh UI
```

### Managing Routes

```javascript
// Start a route
await ui.startSession(8000);

// Stop a route
await ui.stopSession(8000);

// Delete a route
await ui.deleteSession(8000);

// Edit a route
await ui.editSession(8000);
```

### Bulk Operations

```javascript
// Start multiple routes
await ui.bulkStart([8000, 8001, 8002]);

// Stop multiple routes
await ui.bulkStop([8000, 8001]);
```

## Error Handling

All AJAX requests include comprehensive error handling:

```javascript
try {
    const result = await api.startSession(rxPort);
    ui.showSuccess('Route started!');
} catch (error) {
    ui.showError(`Failed to start: ${error.message}`);
}
```

## Browser Compatibility

- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support
- Mobile browsers: ✅ Responsive design

## Performance

- **Lazy Loading**: Content loaded on demand
- **Debounced Updates**: Prevents excessive API calls
- **Efficient Rendering**: Only updates changed elements
- **WebSocket**: Reduces polling overhead

## Security

- **XSS Prevention**: All user input is sanitized
- **HTTPS Ready**: Supports secure connections
- **Error Messages**: No sensitive data exposed

## Customization

### Modify Refresh Interval

```javascript
// In ui.js, change the interval (default 5000ms)
this.refreshInterval = setInterval(() => {
    this.loadSessions();
}, 10000); // 10 seconds
```

### Add Custom Notifications

```javascript
ui.showNotification('Custom message', 'info');
// Types: 'success', 'error', 'info'
```

### Extend API Methods

```javascript
// In api.js
async customEndpoint() {
    return this.get('/api/custom');
}
```

## Testing

### Test AJAX Requests

```javascript
// Open browser console
await api.getSessions();
await api.createSession({ ... });
await api.startSession(8000);
```

### Monitor WebSocket

```javascript
api.onWebSocketMessage((data) => {
    console.log('WS Message:', data);
});
```

## Troubleshooting

### Routes Not Loading
- Check browser console for errors
- Verify API endpoint is accessible
- Check network tab for failed requests

### WebSocket Not Connecting
- Ensure `/ws` endpoint is available
- Check firewall settings
- Verify WebSocket support in browser

### Forms Not Submitting
- Check form validation
- Verify all required fields
- Check console for JavaScript errors

## License

Same as parent SRT Gateway project.

## Support

For issues or questions, refer to the main README.md or check the browser console for detailed error messages.
