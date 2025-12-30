#!/bin/bash

set -e

VERSION="6.5"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║        SRT Gateway v${VERSION} - Installation                    ║"
echo "║       Production Ready + Adaptive Buffer Support              ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Check Ubuntu/Debian
if [ ! -f /etc/os-release ]; then
    echo "❌ Cannot detect OS"
    exit 1
fi

source /etc/os-release
if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
    echo "❌ This script requires Ubuntu or Debian"
    exit 1
fi

echo "✅ Detected: $PRETTY_NAME"
echo "📌 Installing SRT Gateway v${VERSION}"
echo ""

# Update and install dependencies
echo "📦 Installing system dependencies..."
apt-get update -qq

# Install dependencies (libsrt1.5-openssl provides the SRT library + headers)
apt-get install -y python3 python3-pip python3-dev sqlite3 libsrt1.5-openssl curl build-essential gcc

# Install Python packages with --ignore-installed flag to avoid conflicts
echo "📦 Installing Python packages..."
pip3 install --ignore-installed fastapi uvicorn websockets --break-system-packages

# Stop existing services if running
echo "🛑 Stopping existing services (if any)..."
systemctl stop srt-gateway 2>/dev/null || true
systemctl stop srt-gateway-web 2>/dev/null || true

# Backup existing database if it exists
if [ -f /opt/srt-gateway/gateway.db ]; then
    echo "💾 Backing up existing database..."
    cp /opt/srt-gateway/gateway.db /opt/srt-gateway/gateway.db.backup.$(date +%s)
fi

# Create directory structure
echo "📁 Creating directory structure..."
mkdir -p /opt/srt-gateway/static
mkdir -p /opt/srt-gateway/logs

# Copy files
echo "📄 Copying files..."
cp -f srt_router.py /opt/srt-gateway/
cp -f api.py /opt/srt-gateway/
cp -f ui.html /opt/srt-gateway/static/index.html
chmod +x /opt/srt-gateway/srt_router.py
chmod +x /opt/srt-gateway/api.py

# Build and install C extension for real statistics
echo "🔧 Building SRT statistics C extension..."
if [ -d "srt_stats_extension" ]; then
    cp -r srt_stats_extension /opt/srt-gateway/
    cd /opt/srt-gateway/srt_stats_extension
    chmod +x build.sh
    
    # Search for SRT headers in common locations
    SRT_HEADER=""
    for path in /usr/include/srt/srt.h /usr/local/include/srt/srt.h /opt/srt/include/srt/srt.h; do
        if [ -f "$path" ]; then
            SRT_HEADER="$path"
            echo "✅ Found SRT headers at: $path"
            break
        fi
    done
    
    if [ -z "$SRT_HEADER" ]; then
        echo "⚠️  WARNING: SRT headers not found in standard locations!"
        echo "   Attempting to build from installed libsrt package..."
        echo "   If build fails, you may need to install SRT from source."
    fi
    
    # Build the C extension
    echo "   Building C extension..."
    ./build.sh
    BUILD_STATUS=$?
    
    if [ $BUILD_STATUS -ne 0 ]; then
        echo "❌ ERROR: C extension build failed (exit code: $BUILD_STATUS)"
        echo ""
        echo "   SOLUTION: You need to install SRT development files."
        echo "   Run these commands:"
        echo ""
        echo "   # Install from SRT official repository"
        echo "   apt-get install -y git cmake"
        echo "   cd /tmp"
        echo "   git clone https://github.com/Haivision/srt.git"
        echo "   cd srt"
        echo "   ./configure"
        echo "   make"
        echo "   make install"
        echo "   ldconfig"
        echo ""
        echo "   Then re-run this install script."
        cd - > /dev/null
        exit 1
    fi
    
    # Verify the .so file was created
    if [ ! -f srt_stats.*.so ]; then
        echo "❌ ERROR: Build succeeded but .so file not found!"
        cd - > /dev/null
        exit 1
    fi
    
    # Copy to gateway directory
    cp srt_stats.*.so /opt/srt-gateway/
    if [ ! -f /opt/srt-gateway/srt_stats.*.so ]; then
        echo "❌ ERROR: Failed to copy .so file to /opt/srt-gateway/"
        cd - > /dev/null
        exit 1
    fi
    
    echo "✅ C extension built and installed successfully"
    cd - > /dev/null
else
    echo "❌ ERROR: srt_stats_extension directory not found!"
    exit 1
fi

# Create version file
echo "${VERSION}" > /opt/srt-gateway/VERSION

# Initialize database
echo "🗄️  Initializing database..."
sqlite3 /opt/srt-gateway/gateway.db << 'EOSQL'
CREATE TABLE IF NOT EXISTS sessions (
    rx_port INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    rx_mode TEXT DEFAULT 'listener',
    rx_host TEXT DEFAULT '0.0.0.0',
    rx_remote_port INTEGER,
    rx_streamid TEXT,
    rx_maxbw INTEGER DEFAULT 0,
    latency INTEGER NOT NULL,
    buffer_size INTEGER NOT NULL,
    enable_arq INTEGER DEFAULT 1,
    passphrase TEXT,
    status TEXT DEFAULT 'running',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_rx_port INTEGER NOT NULL,
    tx_port INTEGER NOT NULL,
    tx_mode TEXT DEFAULT 'listener',
    tx_host TEXT DEFAULT '0.0.0.0',
    tx_remote_port INTEGER,
    tx_streamid TEXT,
    tx_maxbw INTEGER,
    latency INTEGER NOT NULL,
    buffer_size INTEGER NOT NULL,
    passphrase TEXT,
    status TEXT DEFAULT 'running',
    FOREIGN KEY (session_rx_port) REFERENCES sessions(rx_port) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_routes_session ON routes(session_rx_port);
EOSQL

# Copy Adaptive Buffer migration script if available
if [ -f migrate_adaptive_buffer.py ]; then
    echo "🔧 Installing Adaptive Buffer support..."
    cp -f migrate_adaptive_buffer.py /opt/srt-gateway/
    cd /opt/srt-gateway
    python3 migrate_adaptive_buffer.py || echo "⚠️  AB migration had warnings (may already exist)"
    cd - > /dev/null
    echo "✅ Adaptive Buffer schema migration completed"
    
    # Copy rollback script if available
    if [ -f rollback_adaptive_buffer.sh ]; then
        cp -f rollback_adaptive_buffer.sh /opt/srt-gateway/
        chmod +x /opt/srt-gateway/rollback_adaptive_buffer.sh
        echo "✅ Adaptive Buffer rollback script installed"
    fi
else
    echo "ℹ️  Adaptive Buffer not found - installing base gateway only"
fi

echo "✅ Database initialized at /opt/srt-gateway/gateway.db"

# Create systemd service for SRT Router
echo "⚙️  Creating SRT Router service..."
cat > /etc/systemd/system/srt-gateway.service << EOSERVICE
[Unit]
Description=SRT Gateway Router v${VERSION}
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/srt-gateway
ExecStart=/usr/bin/python3 /opt/srt-gateway/srt_router.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOSERVICE

# Create systemd service for Web API
echo "⚙️  Creating Web API service..."
cat > /etc/systemd/system/srt-gateway-web.service << EOSERVICE
[Unit]
Description=SRT Gateway Web API v${VERSION}
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/srt-gateway
ExecStart=/usr/bin/python3 /opt/srt-gateway/api.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOSERVICE

# Reload systemd
echo "🔄 Reloading systemd..."
systemctl daemon-reload

# Enable and start services
echo "🚀 Starting services..."
systemctl enable srt-gateway 2>/dev/null || true
systemctl enable srt-gateway-web 2>/dev/null || true
systemctl restart srt-gateway
systemctl restart srt-gateway-web

# Wait a moment for services to start
sleep 3

# Check status
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ SRT Gateway v${VERSION} Installation Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Service Status:"
systemctl is-active --quiet srt-gateway && echo "  ✅ SRT Gateway Router: Running" || echo "  ❌ SRT Gateway Router: Failed"
systemctl is-active --quiet srt-gateway-web && echo "  ✅ Web Dashboard: Running" || echo "  ❌ Web Dashboard: Failed"
echo ""
echo "📂 Installation:"
echo "   Version: ${VERSION}"
echo "   Directory: /opt/srt-gateway/"
echo "   Database: /opt/srt-gateway/gateway.db"
echo ""
echo "🌐 Access Dashboard:"
echo "   http://$(hostname -I | awk '{print $1}')"
echo ""
echo "📝 Manage Services:"
echo "   sudo systemctl status srt-gateway        # Check router status"
echo "   sudo systemctl status srt-gateway-web    # Check web status"
echo "   sudo systemctl restart srt-gateway       # Restart router"
echo "   sudo systemctl restart srt-gateway-web   # Restart web"
echo ""
echo "📋 View Logs:"
echo "   sudo journalctl -u srt-gateway -f        # Router logs"
echo "   sudo journalctl -u srt-gateway-web -f    # Web logs"
echo ""
echo "🔥 Firewall Configuration:"
echo "   sudo ufw allow 1024:65500/udp  # Allow all SRT ports"
echo "   sudo ufw allow 80/tcp          # Allow web dashboard"
echo "   sudo ufw enable                # Enable firewall"
echo ""
echo "✨ Next Steps:"
echo "   1. Configure firewall (see above)"
echo "   2. Open dashboard: http://$(hostname -I | awk '{print $1}')"
echo "   3. Click + button to create your first session"
echo "   4. Configure any ports you want!"
echo "   5. Connect your Makito encoders/decoders"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Ready for production! Enjoy your SRT Gateway!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
