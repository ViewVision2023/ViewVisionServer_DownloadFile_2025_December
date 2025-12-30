# Quick Start Guide - AJAX JavaScript Interface

## 📁 Files Created

```
static/
├── ajax.html              # Main AJAX interface page
├── AJAX_README.md         # Full documentation
├── css/
│   └── styles.css         # Complete styling
└── js/
    ├── api.js             # API/AJAX layer (258 lines)
    ├── ui.js              # UI controller (658 lines)
    ├── forms.js           # Form handling (469 lines)
    └── utils.js           # Utilities (368 lines)
```

## 🚀 Quick Start

### 1. Access the AJAX Interface

Open in browser:
```
http://your-server-ip/static/ajax.html
```

Or update `api.py` to serve it as the default:
```python
@app.get("/")
def read_root():
    return FileResponse("/opt/srt-gateway/static/ajax.html")
```

### 2. Features Available

✅ **All operations via AJAX** - No page reloads!
✅ **Real-time updates** - WebSocket integration
✅ **Auto-refresh** - Updates every 5 seconds
✅ **Form validation** - Client-side validation
✅ **Notifications** - Toast-style success/error messages
✅ **Bulk operations** - Manage multiple routes at once
✅ **Responsive design** - Works on mobile devices

### 3. JavaScript API Usage

```javascript
// Load all sessions
const data = await api.getSessions();

// Create a new session
await api.createSession({
    name: "My Stream",
    rx_mode: "listener",
    rx_port: 8000,
    routes: [...]
});

// Start/Stop/Delete
await api.startSession(8000);
await api.stopSession(8000);
await api.deleteSession(8000);

// Get statistics
await api.getStatsHistory(8000, 5); // Last 5 minutes
```

### 4. Module Architecture

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │
┌──────▼──────────────────────────────────┐
│           ui.js (UI Controller)          │
│  - Renders pages                         │
│  - Handles user interactions             │
│  - Shows notifications                   │
└──────┬───────────────────┬───────────────┘
       │                   │
┌──────▼──────┐    ┌──────▼──────────┐
│  forms.js   │    │    api.js       │
│  - Form     │    │  - AJAX calls   │
│    handling │    │  - WebSocket    │
│  - Validation│    │  - Error        │
└─────────────┘    │    handling     │
                   └──────┬──────────┘
                          │
                   ┌──────▼──────────┐
                   │   Backend API   │
                   │  /api/sessions  │
                   │  /api/routes    │
                   │  /api/stats     │
                   └─────────────────┘
```

## 💡 Common Tasks

### Create a Route
1. Click "➕ Create Route" button
2. Fill in source configuration
3. Click "➕ Add Destination" for each output
4. Fill in destination details
5. Click "Save Route"
6. ✅ Route created via AJAX - no page reload!

### Manage Multiple Routes
1. Select routes using checkboxes (when implemented)
2. Choose action from "Bulk Actions" dropdown
3. Confirm operation
4. ✅ All routes updated simultaneously

### View Statistics
1. Click the 📊 icon on any route card
2. Select time range (5min, 15min, 30min, 1hr)
3. View real-time charts
4. Click "🔄 Refresh" for latest data

### Monitor Real-Time
- WebSocket automatically connects
- Status updates every 5 seconds
- Bitrate sparklines update live
- Connection status shown in sidebar

## 🔧 Customization

### Change Auto-Refresh Interval

Edit `static/js/ui.js`:
```javascript
// Line ~450
this.refreshInterval = setInterval(() => {
    if (this.currentScreen === 'routes') {
        this.loadSessions();
    }
}, 5000); // Change 5000 to desired milliseconds
```

### Add Custom API Endpoint

Edit `static/js/api.js`:
```javascript
// Add new method
async myCustomEndpoint() {
    return this.get('/api/my-endpoint');
}
```

### Customize Notifications

Edit `static/js/ui.js`:
```javascript
// Change notification duration (default 3000ms)
setTimeout(() => {
    notification.classList.remove('show');
}, 5000); // 5 seconds
```

## 📊 API Endpoints Used

| HTTP Method | Endpoint | Description |
|-------------|----------|-------------|
| GET | `/api/sessions` | List all sessions |
| GET | `/api/sessions/{port}` | Get session details |
| POST | `/api/sessions` | Create session |
| PUT | `/api/sessions/{port}` | Update session |
| DELETE | `/api/sessions/{port}` | Delete session |
| POST | `/api/sessions/{port}/start` | Start session |
| POST | `/api/sessions/{port}/stop` | Stop session |
| GET | `/api/stats/history/{port}` | Get stats history |
| WS | `/ws` | WebSocket for real-time |

## 🐛 Debugging

### Open Browser Console
- Chrome/Edge: F12 or Cmd+Option+I (Mac)
- Firefox: F12 or Cmd+Option+K (Mac)
- Safari: Cmd+Option+C (enable in preferences)

### View AJAX Requests
1. Open Developer Tools
2. Go to "Network" tab
3. Filter by "XHR" or "Fetch"
4. Click any request to see details

### Monitor WebSocket
```javascript
// In browser console
api.onWebSocketMessage((data) => {
    console.log('WebSocket received:', data);
});
```

### Test API Directly
```javascript
// In browser console
await api.getSessions();
await api.getSession(8000);
await api.startSession(8000);
```

## 📱 Mobile Support

The interface is fully responsive:
- Sidebar collapses on mobile
- Touch-friendly buttons
- Scrollable content areas
- Modal dialogs adapt to screen size

## 🔐 Security Features

- ✅ XSS prevention (all input sanitized)
- ✅ HTTPS ready
- ✅ No sensitive data in error messages
- ✅ Input validation on client and server

## ⚡ Performance

- **Lazy Loading**: Content loaded on demand
- **Debouncing**: Prevents excessive API calls  
- **Efficient Rendering**: Only updates changed elements
- **WebSocket**: Reduces polling overhead
- **Auto-reconnect**: WebSocket reconnects if dropped

## 📦 Dependencies

### Required
- Modern browser (Chrome, Firefox, Safari, Edge)
- JavaScript enabled

### Optional
- Chart.js (for advanced statistics charts)
  - Loaded from CDN in `ajax.html`
  - Can be removed if not needed

## 🎨 Theming

Colors defined in `static/css/styles.css`:
```css
:root {
    --accent-orange: #ff6b35;  /* Primary color */
    --accent-amber: #ff9f1c;   /* Secondary color */
    --bg-main: #0e0e0e;        /* Main background */
    --text-primary: #fff8f0;   /* Text color */
    /* ... more variables */
}
```

Change these values to customize the theme!

## 📖 Full Documentation

For complete documentation, see:
- `static/AJAX_README.md` - Detailed module documentation
- Browser console - Live API testing
- Network tab - Request/response inspection

## 🆘 Troubleshooting

### Routes Not Loading
```javascript
// Check in console:
await api.getSessions();
// If error, check backend is running
```

### WebSocket Not Connecting
- Check if `/ws` endpoint exists in `api.py`
- Verify no firewall blocking WebSocket
- Check browser console for errors

### Form Not Submitting
- Check browser console for validation errors
- Verify all required fields filled
- Check Network tab for failed POST request

## 🎯 Next Steps

1. ✅ Deploy to your server
2. ✅ Test all AJAX functionality
3. ✅ Customize theme if desired
4. ✅ Add more features as needed
5. ✅ Monitor performance in production

## 📝 Example: Complete Workflow

```javascript
// 1. Page loads
document.addEventListener('DOMContentLoaded', () => {
    ui.init(); // Initialize UI
});

// 2. UI loads sessions via AJAX
await ui.loadSessions();

// 3. User creates a route
ui.openCreateSessionModal();
// ... fill form ...
forms.handleSessionSubmit(event);

// 4. AJAX creates session
await api.createSession(sessionData);

// 5. Success notification
ui.showSuccess('Route created!');

// 6. Reload sessions
await ui.loadSessions();

// 7. WebSocket sends update
// UI auto-refreshes every 5 seconds
```

## ✨ Key Advantages

1. **No Page Reloads** - Smooth user experience
2. **Real-Time Updates** - Always current data
3. **Better Performance** - Only loads what's needed
4. **Modern Architecture** - Modular, maintainable code
5. **Error Handling** - Graceful error recovery
6. **User Feedback** - Clear notifications
7. **Responsive** - Works on all devices

---

**Ready to use!** Open `ajax.html` in your browser and start managing routes with AJAX! 🚀
