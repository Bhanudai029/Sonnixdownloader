#!/usr/bin/env bash
# Build script for Render.com deployment

set -o errexit

echo "📦 Build script starting..."

# Create necessary directories
echo "📁 Creating download directories..."
mkdir -p thumbnails
mkdir -p Audios

echo "🔧 Setting up Chrome/Chromium paths..."

# Check for chromedriver
if [ -f /usr/bin/chromedriver ]; then
    echo "✅ Chromedriver found at /usr/bin/chromedriver"
    export CHROMEDRIVER_PATH=/usr/bin/chromedriver
fi

# Check for chromium
if [ -f /usr/bin/chromium-browser ]; then
    echo "✅ Chromium found at /usr/bin/chromium-browser"
    export CHROME_BIN=/usr/bin/chromium-browser
elif [ -f /usr/bin/chromium ]; then
    echo "✅ Chromium found at /usr/bin/chromium"
    export CHROME_BIN=/usr/bin/chromium
else
    echo "⚠️ Chromium not found - will be installed via Aptfile"
fi

echo "✅ Build complete!"
