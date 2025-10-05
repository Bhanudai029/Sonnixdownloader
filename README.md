# FreeYTZone

A powerful YouTube video and audio downloader web application built with Flask and yt-dlp.

## Features

- Download YouTube videos in multiple qualities (8K, 4K, 2K, 1080p, 720p, 480p, 360p)
- Extract audio as MP3 from YouTube videos
- Support for YouTube Shorts with proper aspect ratio handling
- Support for private and restricted videos with cookie-based authentication
- Real-time video info display (title, channel, views, likes, comments, etc.)
- Automatic thumbnail and channel logo display

## Requirements

- Python 3.8+
- FFmpeg (installed and available in PATH)
- YouTube Data API key (for extended video info)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/SandeshBro-ux/freeytzone.git
   cd freeytzone
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with your YouTube API key:
   ```
   YOUTUBE_API_KEY=your_api_key_here
   ```

4. Run the application:
   ```
   python app.py
   ```

5. Open a web browser and navigate to `http://localhost:5000`

## How to Use

1. Enter a YouTube URL (regular video or Shorts)
2. View video details and available quality options
3. Select your preferred quality (or MP3 for audio only)
4. Wait for download to complete
5. Click on the download link to save the file

## Advanced Features

- **Cookie Support**: Paste your YouTube cookies to download private or restricted videos
- **Proxy Support**: Add a proxy URL in the `.env` file to bypass regional restrictions
- **Error Handling**: Robust error handling for unavailable videos and rate limiting

## Technical Details

- Uses a robust 3-step download process for reliable high-quality downloads
- Optimized thumbnail processing for both regular videos (16:9) and Shorts (9:16)
- Circular channel logos with transparency
- Secure file handling to prevent directory traversal attacks

## Recent Improvements

### 🖼️ Enhanced Thumbnail Loading
- **Fixed**: Videos like Ed Sheeran's "Shape of You" now load thumbnails correctly
- **Improvement**: Implemented multi-tier fallback system:
  1. `maxresdefault.jpg` (1280x720) - Best quality
  2. `hqdefault.jpg` (480x360) - High quality fallback
  3. `mqdefault.jpg` (320x180) - Medium quality fallback
  4. `default.jpg` (120x90) - Last resort
- **Result**: No more broken thumbnail images, always shows best available quality

### 🎥 Improved Quality Detection
- **Fixed**: "Best Available Quality" now shows accurate information
- **Improvement**: Enhanced algorithm that:
  - Analyzes actual video formats from yt-dlp when available
  - Uses intelligent fallback system with YouTube API data
  - Detects quality from video titles (4K, 2K, 1080p, Full HD keywords)
  - Shows detailed descriptions like "4K (2160p)" and "1080p (Full HD)"
  - Builds accurate list of truly available download qualities
  - Handles YouTube's bot detection gracefully
- **Result**: More precise quality selection and better user information
- **Examples**: 
  - Videos with "4K Remaster" in title → "4K (2160p)" max quality
  - HD videos → "1080p (Full HD)" or "720p (HD)" based on analysis

### 🎨 Better Error Handling
- **Fixed**: Broken image placeholders when thumbnails fail
- **Improvement**: Added client-side error handling with attractive gradient placeholders
- **Result**: Professional appearance even when thumbnails are unavailable

## YouTube Auto-Downloader (Command Line Tool)

A command-line tool that automatically searches for songs on YouTube and downloads their thumbnails.

### Features

- 🎵 Interactive song input with numbered list format
- 🌐 Automatic Chrome/Chromium browser control
- 🔍 YouTube search automation
- 📱 Click first video result automatically
- 🖼️ Batch thumbnail download using the existing thumbnail downloader
- ⚡ Fast parallel processing

### Usage

1. Install additional dependencies:
   ```
   pip install selenium
   ```

2. Run the auto-downloader:
   ```
   python youtube_auto_downloader.py
   ```

3. **Paste your songs** (supports multi-line input):
   ```
   📝 Paste your songs below (press Enter twice when done):
   1. Shape of you
   2. See you again
   3. Blinding lights
   4. Hotel California
   5. Bohemian Rhapsody
   ```

   **Methods to finish input:**
   - **Option 1**: Press Enter twice (recommended for Windows)
   - **Option 2**: Press Ctrl+Z then Enter (Windows)
   - **Option 3**: Press Ctrl+D (Linux/Mac)

4. The program will:
   - Launch Chrome browser
   - Search each song on YouTube
   - Click the first video result
   - Extract the video URL
   - Download thumbnails using the existing thumbnail downloader

### Input Format

The program expects songs in this format:
```
1. Song Name
2. Another Song Name
3. Third Song
```

### Output

- Thumbnails are saved to a `thumbnails` folder in the current directory
- Each thumbnail is named after the video title
- Program shows progress and success/failure statistics

### Requirements

- Chrome or Chromium browser installed
- Selenium WebDriver (automatically managed by Selenium Manager)

## 🚀 YouTube Auto-Downloader Web UI (NEW!)

A modern web interface for batch downloading YouTube audio and thumbnails, optimized for Render.com deployment.

### Features

- ✨ Beautiful modern web interface
- 🎯 Real-time progress tracking with live logs
- 🔄 Batch processing of multiple songs
- 🖼️ Automatic thumbnail downloads
- 🎵 High-quality MP3 audio extraction (192K)
- 🚫 YouTube Shorts detection and skipping
- ☁️ Cloud-ready for Render.com deployment
- 🤖 Headless Chrome support for server environments

### Quick Start (Local Testing)

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the web interface:
   ```bash
   python start_web.py
   ```
   Or directly:
   ```bash
   python app_web.py
   ```

3. Open browser: `http://localhost:5000`

4. Paste your song list and click "Start Download"!

### Deploy to Render.com

See the detailed [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for step-by-step instructions.

**Quick Deploy:**

1. Push code to GitHub:
   ```bash
   git add .
   git commit -m "Add web UI"
   git push origin main
   ```

2. On Render.com:
   - Click "New +" → "Web Service"
   - Connect your repository
   - Render will auto-detect settings from `render.yaml`
   - Click "Create Web Service"

3. Wait 5-10 minutes for deployment

4. Access your app at the provided URL!

### Files for Web UI

- `app_web.py` - Flask web application (Render-optimized)
- `templates/index_web.html` - Modern responsive UI
- `youtube_auto_downloader_original.py` - Original CLI version (backup)
- `render.yaml` - Render service configuration
- `Aptfile` - System dependencies (Chromium, FFmpeg)
- `build.sh` - Build script for deployment
- `Procfile` - Process configuration
- `runtime.txt` - Python version specification

### Web UI vs CLI Version

| Feature | CLI Version | Web UI Version |
|---------|-------------|----------------|
| Interface | Command line | Modern web browser |
| Chrome Mode | Visible window | Headless (server) |
| Progress | Console output | Real-time web updates |
| Deployment | Local only | Cloud-ready |
| Multiple Users | No | Yes |
| Progress Tracking | Basic | Advanced with logs |

## License

MIT License

## Project Structure

```
/
|-- app.py                  # Main Flask application
|-- requirements.txt        # Python dependencies
|-- .env                    # Environment variables (for API key)
|-- templates/
|   |-- index.html          # Frontend HTML template
|-- cookies/                # Temporary storage for uploaded cookie files (created automatically)
|-- downloads/              # Temporary storage for downloaded videos (created automatically)
|-- youtube_auto_downloader.py # Command-line auto-downloader tool
|-- quick_thumbnail_downloader.py # Thumbnail downloader utility
|-- fast_audio_downloader.py # Fast audio downloader utility
|-- proxy_download.py       # Proxy download utility
|-- test_*.py              # Various test files
|-- README.md               # This file
```

## Notes

-   The `cookies` and `downloads` directories are created automatically by the application if they don't exist. Cookie files are temporarily stored per video ID and then deleted after a successful download. Downloaded files are served from the `downloads` directory.
-   This application is for personal and educational purposes only. Always respect copyright laws and YouTube's Terms of Service when downloading content. 