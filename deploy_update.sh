#!/bin/bash

# Quick update script for SRT Gateway
# Updates code files without reinstalling system dependencies

set -e

echo "🔄 SRT Gateway Update Script"
echo "================================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

echo "⏸️  Stopping services..."
systemctl stop srt-gateway 2>/dev/null || true
systemctl stop srt-gateway-web 2>/dev/null || true

echo "🗑️  Removing old files..."
rm -f /opt/srt-gateway/srt_router.py
rm -f /opt/srt-gateway/api.py
rm -f /opt/srt-gateway/static/index.html

echo "📄 Copying new files..."
cp -f srt_router.py /opt/srt-gateway/
cp -f api.py /opt/srt-gateway/
cp -f ui.html /opt/srt-gateway/static/index.html

echo "🔧 Setting permissions..."
chmod +x /opt/srt-gateway/srt_router.py
chmod +x /opt/srt-gateway/api.py

echo "▶️  Starting services..."
systemctl start srt-gateway
systemctl start srt-gateway-web

echo ""
echo "✅ Update complete!"
echo ""
echo "Check status:"
echo "  systemctl status srt-gateway"
echo "  systemctl status srt-gateway-web"
echo ""
echo "View logs:"
echo "  journalctl -u srt-gateway -f"
