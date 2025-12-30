#!/bin/bash
#
# Build and Install SRT Statistics C Extension
# Run this on your server (172.104.20.239)
#

set -e  # Exit on error

echo "========================================="
echo "SRT Statistics C Extension Builder"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Warning: Not running as root. Some operations may fail."
    echo ""
fi

# Check for required packages
echo "📦 Checking prerequisites..."

check_command() {
    if command -v $1 &> /dev/null; then
        echo "  ✓ $1 found"
        return 0
    else
        echo "  ✗ $1 not found"
        return 1
    fi
}

check_file() {
    if [ -f "$1" ]; then
        echo "  ✓ $1 exists"
        return 0
    else
        echo "  ✗ $1 not found"
        return 1
    fi
}

MISSING_DEPS=0

check_command gcc || MISSING_DEPS=1
check_command python3 || MISSING_DEPS=1
check_file /usr/include/srt/srt.h || MISSING_DEPS=1

echo ""

if [ $MISSING_DEPS -eq 1 ]; then
    echo "❌ Missing dependencies detected!"
    echo ""
    echo "Install them with:"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install -y build-essential python3-dev libsrt-dev"
    echo ""
    exit 1
fi

echo "✓ All prerequisites satisfied"
echo ""

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build/
rm -f srt_stats.*.so
rm -f srt_stats.c~
echo "  ✓ Cleaned"
echo ""

# Build the extension
echo "🔨 Building C extension..."
python3 setup.py build_ext --inplace

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Build failed!"
    exit 1
fi

echo ""
echo "✓ Build successful"
echo ""

# Test the module
echo "🧪 Testing module..."
python3 << 'EOF'
import sys

try:
    import srt_stats
    print("  ✓ Module imports successfully")
    
    # Test constants
    assert srt_stats.SRTS_CONNECTED == 5
    print("  ✓ Constants defined correctly")
    
    # Test invalid socket (should raise RuntimeError)
    try:
        stats = srt_stats.get_stats(999999)
        print("  ✗ ERROR: Should have raised RuntimeError for invalid socket")
        sys.exit(1)
    except RuntimeError:
        print("  ✓ Error handling works correctly")
    
    print("\n✓ All tests passed")
    
except ImportError as e:
    print(f"  ✗ Failed to import module: {e}")
    sys.exit(1)
except Exception as e:
    print(f"  ✗ Test failed: {e}")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Tests failed!"
    exit 1
fi

echo ""

# Find the built module
MODULE_FILE=$(find . -name "srt_stats.*.so" | head -1)

if [ -z "$MODULE_FILE" ]; then
    echo "❌ Could not find built module file"
    exit 1
fi

echo "📍 Module location: $MODULE_FILE"
echo ""

# Installation instructions
echo "========================================="
echo "✅ Build Complete!"
echo "========================================="
echo ""
echo "The module is ready to use."
echo ""
echo "To use in your gateway:"
echo "  1. Keep the .so file in this directory"
echo "  2. Add this directory to Python path, or"
echo "  3. Copy srt_stats.*.so to /opt/srt-gateway/"
echo ""
echo "Test with:"
echo "  python3 -c 'import srt_stats; print(srt_stats.SRTS_CONNECTED)'"
echo ""
echo "Example usage:"
echo "  import srt_stats"
echo "  stats = srt_stats.get_stats(socket_id)"
echo "  print(f\"RTT: {stats['msRTT']}ms\")"
echo ""
