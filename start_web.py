#!/usr/bin/env python3
"""
Quick start script for local development
Run this to test the web interface locally
"""

import os
import sys

def main():
    print("=" * 60)
    print("🚀 Starting YouTube Auto Downloader Web Interface")
    print("=" * 60)
    print()
    
    # Check if required modules are installed
    try:
        import flask
        import selenium
        print("✅ Flask installed")
        print("✅ Selenium installed")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("\n💡 Install dependencies:")
        print("   pip install -r requirements.txt")
        sys.exit(1)
    
    # Check if Chrome/Chromium is available
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        
        print("✅ Testing Chrome/Chromium...")
        driver = webdriver.Chrome(options=options)
        driver.quit()
        print("✅ Chrome/Chromium is working!")
    except Exception as e:
        print(f"⚠️ Chrome/Chromium test failed: {e}")
        print("💡 Make sure Chrome or Chromium is installed")
        print("   The app will still start but may not work properly")
    
    print()
    print("🌐 Starting web server...")
    print("📍 URL: http://localhost:5000")
    print("⏹️  Press Ctrl+C to stop")
    print()
    print("-" * 60)
    
    # Start the Flask app
    os.system(f"{sys.executable} app_web.py")

if __name__ == "__main__":
    main()
