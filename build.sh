#!/usr/bin/env bash
# Build script for Render.com deployment

set -o errexit

echo "📦 Installing system dependencies..."

# Update package list
apt-get update -y

# Install dependencies from Aptfile if it exists
if [ -f Aptfile ]; then
    echo "📋 Installing packages from Aptfile..."
    xargs apt-get install -y < Aptfile
fi

echo "🐍 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🔧 Setting up Chrome/Chromium paths..."

# Create symlinks for chromedriver if needed
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
fi

# Create necessary directories
mkdir -p thumbnails
mkdir -p Audios

echo "✅ Build complete!"
