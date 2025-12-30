#!/bin/bash
#
# Deploy SRT Stats Extension to Production Server
# Run this from your local machine
#

SERVER="root@172.104.20.239"
REMOTE_DIR="/opt/srt-gateway"

echo "========================================="
echo "Deploying SRT Stats Extension"
echo "========================================="
echo ""

# Upload the extension files
echo "📤 Uploading extension files..."
scp -r srt_stats_extension ${SERVER}:${REMOTE_DIR}/

echo ""
echo "🔨 Building on server..."
ssh ${SERVER} << 'ENDSSH'
cd /opt/srt-gateway/srt_stats_extension

# Install dependencies if needed
if [ ! -f /usr/include/srt/srt.h ]; then
    echo "Installing libsrt-dev..."
    apt-get update
    apt-get install -y libsrt-dev build-essential python3-dev
fi

# Run build script
chmod +x build.sh
./build.sh

# Copy the built module to parent directory
cp srt_stats.*.so ../

echo ""
echo "✓ Extension built and installed"
ENDSSH

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================="
    echo "✅ Deployment Successful!"
    echo "========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Update srt_router.py to use srt_stats module"
    echo "  2. Test with: ssh ${SERVER} 'cd /opt/srt-gateway && python3 -c \"import srt_stats; print(srt_stats.SRTS_CONNECTED)\"'"
    echo "  3. Restart gateway: ssh ${SERVER} 'systemctl restart srt-gateway'"
    echo ""
else
    echo ""
    echo "❌ Deployment failed!"
    exit 1
fi
