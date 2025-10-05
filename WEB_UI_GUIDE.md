# 🚀 YouTube Auto Downloader - Web UI Complete Guide

## 📋 Quick Overview

This is a web interface for batch downloading YouTube audio and thumbnails, optimized for **Render.com** deployment with headless Chrome support.

---

## 🎯 Quick Start

### Local Testing (3 Steps)
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start server
python start_web.py

# 3. Open browser at http://localhost:5000
```

### Deploy to Render (3 Steps)
```bash
# 1. Push to GitHub
git add .
git commit -m "Deploy web UI"
git push origin main

# 2. On Render.com
- Click "New +" → "Web Service"
- Connect your repository
- Click "Create Web Service" (auto-detects from render.yaml)

# 3. Wait 5-10 minutes, then access your URL!
```

---

## 📁 File Overview

### Core Files
- **`app_web.py`** - Flask web app (Render-optimized with headless Chrome)
- **`templates/index_web.html`** - Modern responsive UI
- **`youtube_auto_downloader_original.py`** - Original CLI backup

### Render Configuration
- **`render.yaml`** - Service config (auto-detected by Render)
- **`Aptfile`** - System packages (Chromium, FFmpeg)
- **`build.sh`** - Build script
- **`Procfile`** - Process command
- **`runtime.txt`** - Python 3.11.0

### Helper
- **`start_web.py`** - Local testing script

---

## ⚙️ Render.yaml Configuration

The `render.yaml` file is properly configured with:

✅ **Service Type**: Web service with Python environment  
✅ **Build Command**: `./build.sh` (installs Chromium + dependencies)  
✅ **Start Command**: `gunicorn app_web:app` (production WSGI server)  
✅ **Environment Variables**: Chrome paths, Python version, port  
✅ **Disk Storage**: 1GB for downloads  
✅ **Region**: Oregon (free tier available)  

**Key Environment Variables Set:**
```yaml
CHROME_BIN=/usr/bin/chromium-browser
CHROMEDRIVER_PATH=/usr/bin/chromedriver
PORT=10000
PYTHON_VERSION=3.11.0
```

---

## 🔧 Chromium Setup for Render

The app is configured to launch Chrome correctly in Render's environment:

### Chrome Options (in app_web.py)
```python
chrome_options.add_argument("--headless=new")          # No GUI
chrome_options.add_argument("--no-sandbox")            # Required for Render
chrome_options.add_argument("--disable-dev-shm-usage") # Memory optimization
chrome_options.add_argument("--disable-gpu")           # Server environment
```

### System Dependencies (in Aptfile)
- `chromium-browser` - Chrome binary
- `chromium-chromedriver` - WebDriver
- `ffmpeg` - Audio processing
- All required libraries for Chrome

### Build Process (in build.sh)
1. Installs all Aptfile packages
2. Sets up Chrome/Chromedriver paths
3. Creates download directories
4. Verifies installation

**This ensures Chrome launches properly on Render! ✅**

---

## 🎮 How to Use the Web Interface

1. **Enter Songs** (numbered format):
   ```
   1. Shape of You
   2. Blinding Lights
   3. Levitating
   4. Stay
   5. Heat Waves
   ```

2. **Click "🚀 Start Download"**

3. **Watch Progress**:
   - Real-time progress bar
   - Live terminal logs
   - Current song status
   - Success/failure indicators

4. **Files Saved**:
   - Audio: `Audios/` folder (MP3, 192K)
   - Thumbnails: `thumbnails/` folder (PNG, max resolution)

---

## 🔍 Troubleshooting

### Local Testing Issues

**"Chrome not found"**
```bash
# Install Chrome/Chromium
# Windows: Download from google.com/chrome
# Mac: brew install --cask google-chrome
# Linux: sudo apt install chromium-browser
```

**"Module not found"**
```bash
pip install -r requirements.txt --upgrade
```

### Render Deployment Issues

**Build Fails**
- Check build logs in Render dashboard
- Verify all files are committed to Git
- Ensure `build.sh` syntax is correct

**Chrome Crashes**
- Already handled with `--no-sandbox` flag
- Check if memory limits exceeded (upgrade to paid tier)

**App Sleeps (Free Tier)**
- Normal behavior after 15 min inactivity
- First request takes ~30 seconds to wake up
- Upgrade to paid tier for always-on

**Downloads Timeout**
- Process smaller batches (5-10 songs)
- Free tier has limited resources
- Consider upgrading for larger batches

---

## 💡 Tips & Best Practices

### Performance
- ✅ Process 5-10 songs at a time
- ✅ Larger batches may timeout on free tier
- ✅ Downloads run in parallel (3 at once)

### Quality Settings
- Audio: 192K MP3 (adjustable in `app_web.py`)
- Thumbnails: Maximum available resolution
- Files named after song titles

### Security
- Use Render environment variables for secrets
- Don't hardcode Supabase keys in code
- Add authentication for private deployments

### Free Tier Limits
- **Sleep**: After 15 min inactivity
- **Runtime**: 750 hours/month
- **Storage**: 1 GB disk
- **Bandwidth**: 100 GB/month

---

## 🆚 CLI vs Web Comparison

| Feature | Original CLI | Web UI |
|---------|-------------|---------|
| Interface | Terminal | Browser |
| Chrome | Window opens | Headless |
| Progress | Console print | Real-time web |
| Deploy | Local only | Cloud-ready |
| Users | Single | Multiple |

**Original CLI still works!** It's backed up as `youtube_auto_downloader_original.py`

---

## 🔐 Environment Variables

### Required (Auto-set by render.yaml)
```bash
PORT=10000
CHROME_BIN=/usr/bin/chromium-browser
CHROMEDRIVER_PATH=/usr/bin/chromedriver
PYTHON_VERSION=3.11.0
```

### Optional (Add in Render dashboard)
```bash
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

---

## 🚀 Production Enhancements (Optional)

### Add Authentication
```python
from flask_login import LoginManager
# Protect routes with @login_required
```

### Add Rate Limiting
```python
from flask_limiter import Limiter
limiter = Limiter(app, key_func=get_remote_address)
@limiter.limit("10 per minute")
```

### Use Redis for Progress
```python
import redis
r = redis.from_url(os.environ.get("REDIS_URL"))
# Store progress in Redis instead of global dict
```

### Add File Cleanup
```python
# Cleanup files older than 24 hours
from datetime import datetime, timedelta
# Schedule cleanup task
```

---

## 📊 Success Checklist

Your deployment is successful if:

- ✅ Build completes without errors
- ✅ Service shows "Active" status
- ✅ Web interface loads at provided URL
- ✅ Songs are parsed from textarea
- ✅ Chrome launches in headless mode
- ✅ YouTube searches work
- ✅ Audio downloads complete
- ✅ Thumbnails download
- ✅ Progress updates in real-time
- ✅ Logs appear in web console

---

## 🎓 Technical Details

### App Architecture
- **Flask**: Web framework
- **Gunicorn**: Production WSGI server (2 workers, 300s timeout)
- **Selenium**: Browser automation
- **yt-dlp**: Video/audio extraction
- **Threading**: Background processing

### Chrome Setup
- Headless mode for servers
- Anti-detection measures
- Proper timeouts and retries
- YouTube Shorts detection

### Download Process
1. Parse song list from user input
2. Launch headless Chrome
3. Search YouTube for each song
4. Extract video URL
5. Download thumbnail (max resolution)
6. Download audio (192K MP3)
7. Skip YouTube Shorts
8. Handle age-restricted videos

---

## 📞 Support & Resources

- **Render Docs**: https://render.com/docs
- **Selenium Docs**: https://selenium-python.readthedocs.io/
- **yt-dlp**: https://github.com/yt-dlp/yt-dlp
- **Flask**: https://flask.palletsprojects.com/

---

## ⚡ What's Special About This Setup

✅ **Render-Optimized**: Everything configured for smooth deployment  
✅ **Chrome Works**: Proper headless setup with `--no-sandbox`  
✅ **Auto-Detected**: render.yaml makes deployment one-click  
✅ **Real-Time**: Live progress updates via REST API  
✅ **Production-Ready**: Gunicorn, proper error handling  
✅ **Original Preserved**: CLI version backed up and working  

---

## 🎉 You're All Set!

Your YouTube Auto Downloader is ready for Render deployment with proper Chromium configuration!

**Quick Deploy:** Just push to GitHub, connect on Render, and click deploy!

---

*Made for Render.com deployment • MIT License • 2025*
