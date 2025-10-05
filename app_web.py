#!/usr/bin/env python3
"""
YouTube Auto-Downloader Web UI
Flask web interface for YouTube audio and thumbnail downloader
Optimized for Render.com deployment
"""

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import os
import sys
import time
import re
import subprocess
import threading
import json
from pathlib import Path
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests
import concurrent.futures

# Import the existing modules
try:
    from quick_thumbnail_downloader import QuickThumbnailDownloader
except ImportError:
    QuickThumbnailDownloader = None

try:
    from supabase_uploader import SupabaseUploader
except ImportError:
    SupabaseUploader = None

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size

# Create screenshots folder
SCREENSHOTS_FOLDER = Path("screenshots")
SCREENSHOTS_FOLDER.mkdir(parents=True, exist_ok=True)

# Cookies path for yt-dlp (optional but recommended when YouTube challenges requests)
COOKIES_PATH = Path("cookies.txt")

def initialize_cookies_from_env() -> bool:
    """Optionally initialize cookies from base64 env var `YTDLP_COOKIES_B64`."""
    try:
        encoded = os.environ.get("YTDLP_COOKIES_B64", "").strip()
        if not encoded:
            return False
        data = base64.b64decode(encoded)
        COOKIES_PATH.write_bytes(data)
        return True
    except Exception:
        return False

# Initialize cookies once if provided via env
initialize_cookies_from_env()

# Global variables for progress tracking
download_progress = {
    'status': 'idle',  # idle, processing, completed, error
    'current_song': '',
    'progress': 0,
    'total': 0,
    'results': [],
    'logs': [],
    'screenshots': []  # List of screenshot URLs
}
progress_lock = threading.Lock()

class YouTubeAutoDownloaderWeb:
    """Modified version for web deployment with headless Chrome support"""
    
    def __init__(self, thumbnail_folder="thumbnails", audio_folder="Audios", enable_supabase=True):
        self.thumbnail_folder = Path(thumbnail_folder)
        self.thumbnail_folder.mkdir(parents=True, exist_ok=True)
        self.audio_folder = Path(audio_folder)
        self.audio_folder.mkdir(parents=True, exist_ok=True)
        self.driver = None
        self.lock = threading.Lock()
        
        # Supabase configuration
        self.enable_supabase = enable_supabase
        self.supabase_uploader = None
        if enable_supabase and SupabaseUploader:
            self.init_supabase()
    
    def log(self, message):
        """Add log message to progress tracker"""
        with progress_lock:
            download_progress['logs'].append(message)
            print(message)  # Also print to console
    
    def capture_screenshot(self, reason="error"):
        """Capture screenshot when stuck or on error"""
        try:
            if not self.driver:
                return None
            
            timestamp = int(time.time())
            filename = f"screenshot_{reason}_{timestamp}.png"
            filepath = SCREENSHOTS_FOLDER / filename
            
            # Take screenshot
            self.driver.save_screenshot(str(filepath))
            
            # Add to progress tracking
            screenshot_url = f"/screenshots/{filename}"
            with progress_lock:
                download_progress['screenshots'].append({
                    'url': screenshot_url,
                    'reason': reason,
                    'timestamp': timestamp
                })
            
            self.log(f"📸 Screenshot captured: {reason}")
            return screenshot_url
            
        except Exception as e:
            self.log(f"⚠️ Failed to capture screenshot: {str(e)[:50]}")
            return None
    
    def init_supabase(self):
        """Initialize Supabase uploader with credentials"""
        try:
            SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://aekvevvuanwzmjealdkl.supabase.co")
            SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFla3ZldnZ1YW53em1qZWFsZGtsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwMzExMjksImV4cCI6MjA3MTYwNzEyOX0.PZxoGAnv0UUeCndL9N4yYj0bgoSiDodcDxOPHZQWTxI")
            
            self.supabase_uploader = SupabaseUploader(SUPABASE_URL, SUPABASE_KEY)
            self.log("✅ Supabase uploader initialized successfully")
        except Exception as e:
            self.log(f"⚠️ Supabase initialization failed: {str(e)[:50]}...")
            self.enable_supabase = False

    def setup_browser(self):
        """Setup Chrome browser with headless options for Render deployment"""
        self.log("🚀 Setting up Chrome browser (headless mode)...")
        chrome_options = Options()
        
        # Headless mode for server deployment
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--lang=en-US,en")
        
        # User agent to avoid detection
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

        try:
            # Try to use chromedriver from PATH or environment variable
            chromedriver_path = os.environ.get('CHROMEDRIVER_PATH', '/usr/bin/chromedriver')
            chrome_binary_path = os.environ.get('CHROME_BIN', '/usr/bin/chromium-browser')
            
            # Set Chrome binary location if specified
            if os.path.exists(chrome_binary_path):
                chrome_options.binary_location = chrome_binary_path
                self.log(f"📍 Using Chrome binary: {chrome_binary_path}")
            
            # Initialize driver with service
            if os.path.exists(chromedriver_path):
                service = Service(executable_path=chromedriver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                # Fallback to default PATH
                self.driver = webdriver.Chrome(options=chrome_options)
            
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.log("✅ Browser setup complete!")
            return True
            
        except Exception as e:
            self.log(f"❌ Failed to setup browser: {e}")
            self.log("💡 Make sure Chrome/Chromium and chromedriver are installed")
            return False

    def handle_consent_if_present(self):
        """Attempt to accept Google/YouTube consent dialogs if present."""
        try:
            time.sleep(2)
            current_url = self.driver.current_url.lower() if self.driver else ""
            page_source = (self.driver.page_source or "").lower()

            # Common consent pages (consent.google.com)
            if "consent" in current_url or "consent" in page_source:
                selectors = [
                    "button[aria-label*='Accept all']",
                    "button[aria-label*='I agree']",
                    "form[action*='consent'] button[type='submit']",
                    "button#L2AG",
                    "button[aria-label*='Accept']",
                ]
                for css in selectors:
                    try:
                        btn = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, css))
                        )
                        self.driver.execute_script("arguments[0].click();", btn)
                        self.log("✅ Accepted Google consent dialog")
                        time.sleep(2)
                        return True
                    except Exception:
                        continue

            # YouTube consent bump inside the page
            yt_selectors = [
                "tp-yt-paper-button[aria-label*='I agree']",
                "tp-yt-paper-button[aria-label*='Accept all']",
                "button[aria-label*='I agree']",
            ]
            for css in yt_selectors:
                try:
                    btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, css))
                    )
                    self.driver.execute_script("arguments[0].click();", btn)
                    self.log("✅ Accepted YouTube consent dialog")
                    time.sleep(2)
                    return True
                except Exception:
                    continue

        except Exception as e:
            self.log(f"⚠️ Consent handling failed: {str(e)[:60]}")
        return False

    def parse_song_list(self, song_input):
        """Parse song list from text input (supports various formats)"""
        songs = []
        
        if not song_input or not song_input.strip():
            return songs
        
        buffer = song_input.strip()
        
        # Handle the case where all songs are in one line without spaces
        if '\n' not in buffer and re.search(r'\d+\.\s*\w', buffer):
            parts = re.findall(r'(\d+\.)\s*([^0-9]*?)(?=\d+\.|$)', buffer)
            if parts:
                for _, title in parts:
                    song_name = re.sub(r"\s+", " ", title.strip())
                    if song_name:
                        songs.append(song_name)
        else:
            # Handle multi-line input or normally formatted input
            numbered_item_regex = re.compile(r"\b(\d+)\.\s*([^\d].*?)(?=\s*\d+\.|$)", re.DOTALL)
            matches = numbered_item_regex.findall(buffer)
            
            if matches:
                for _, title in matches:
                    song_name = re.sub(r"\s+", " ", title.strip())
                    if song_name:
                        songs.append(song_name)
            else:
                # Fallback: parse per-line
                line_regex = re.compile(r"^\s*\d+\.\s*(.+)$")
                for raw in buffer.splitlines():
                    m = line_regex.match(raw.strip())
                    if m:
                        song_name = re.sub(r"\s+", " ", m.group(1).strip())
                        if song_name:
                            songs.append(song_name)
        
        return songs

    def search_youtube(self, song_name, retry_attempt=0, max_retries=2):
        """Search for song on YouTube using direct HTTP requests (fastest & most reliable!)"""
        try:
            retry_text = f" (Retry {retry_attempt + 1}/{max_retries + 1})" if retry_attempt > 0 else ""
            self.log(f"🔍 Searching for: {song_name}{retry_text}")
            
            # Use direct HTTP request to YouTube search - much faster than yt-dlp search!
            search_query = song_name.replace(' ', '+')
            search_url = f"https://www.youtube.com/results?search_query={search_query}"
            
            self.log("   📡 Using direct HTTP search (no yt-dlp needed)...")
            
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
                
                # Make request with timeout
                response = requests.get(search_url, headers=headers, timeout=15)
                
                if response.status_code != 200:
                    self.log(f"   ❌ HTTP {response.status_code}")
                    if retry_attempt < max_retries:
                        time.sleep(3)
                        return self.search_youtube(song_name, retry_attempt + 1, max_retries)
                    return None
                
                # Extract video ID from HTML using regex (faster than BeautifulSoup)
                # Look for: "videoId":"VIDEO_ID"
                import re
                video_id_pattern = r'"videoId":"([a-zA-Z0-9_-]{11})"'
                matches = re.findall(video_id_pattern, response.text)
                
                if not matches:
                    self.log("   ❌ No video IDs found in response")
                    if retry_attempt < max_retries:
                        time.sleep(3)
                        return self.search_youtube(song_name, retry_attempt + 1, max_retries)
                    return None
                
                # Get first non-shorts video
                for video_id in matches[:10]:
                    # Skip shorts (usually start with certain patterns or are too short)
                    if len(video_id) == 11:  # Valid YouTube video ID
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        self.log(f"   ✅ Found: {video_url}")
                        return video_url
                
                self.log("   ❌ No valid video found")
                return None
                    
            except requests.Timeout:
                self.log("   ⏰ HTTP timeout (15s)")
                if retry_attempt < max_retries:
                    time.sleep(2)
                    return self.search_youtube(song_name, retry_attempt + 1, max_retries)
                return None
            except Exception as e:
                self.log(f"   ❌ Search error: {str(e)[:100]}")
                if retry_attempt < max_retries:
                    time.sleep(2)
                    return self.search_youtube(song_name, retry_attempt + 1, max_retries)
                return None
                
        except Exception as e:
            self.log(f"❌ Unexpected error: {str(e)[:150]}")
            if retry_attempt < max_retries:
                time.sleep(3)
                return self.search_youtube(song_name, retry_attempt + 1, max_retries)
            return None

    def extract_video_id(self, url):
        """Extract video ID from YouTube URL"""
        video_id_pattern = r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})'
        match = re.search(video_id_pattern, url)
        return match.group(1) if match else None
    
    def is_shorts_url(self, url):
        """Check if URL is a YouTube Shorts URL"""
        return '/shorts/' in url
    
    def find_long_form_video(self, skip_count=0):
        """Find and click on a long-form (non-shorts) video from search results"""
        try:
            self.log(f"   🔍 Searching for long-form videos...")
            
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ytd-video-renderer"))
            )
            
            video_links = self.driver.find_elements(By.CSS_SELECTOR, "ytd-video-renderer a#video-title")
            self.log(f"   📋 Found {len(video_links)} video results")
            
            start_index = skip_count
            end_index = min(len(video_links), start_index + 10)
            
            for i in range(start_index, end_index):
                try:
                    link = video_links[i]
                    href = link.get_attribute('href')
                    if href and '/shorts/' in href:
                        continue
                    
                    title = link.get_attribute('title') or "Unknown"
                    self.log(f"   🎯 Trying video [{i+1}]: {title[:50]}...")
                    
                    self.driver.execute_script("arguments[0].click();", link)
                    time.sleep(3)
                    current_url = self.driver.current_url
                    
                    if not self.is_shorts_url(current_url):
                        video_id = self.extract_video_id(current_url)
                        if video_id:
                            clean_url = f"https://www.youtube.com/watch?v={video_id}"
                            self.log(f"   ✅ Found long-form video: {clean_url}")
                            return clean_url
                    
                    self.driver.back()
                    time.sleep(2)
                except:
                    continue
            
            self.log("   ❌ No long-form videos found")
            return None
            
        except Exception as e:
            self.log(f"   ❌ Error finding long-form video: {str(e)[:50]}")
            return None

    def clean_filename(self, filename):
        """Remove special characters from filename"""
        cleaned = re.sub(r'[^a-zA-Z0-9\s._-]', '', filename)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def download_single_thumbnail(self, url, song_name):
        """Download thumbnail for a single video"""
        try:
            video_id = self.extract_video_id(url)
            if not video_id:
                return False
            
            clean_song_name = self.clean_filename(song_name)
            
            thumbnail_urls = [
                f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
                f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            ]
            
            for quality, thumb_url in zip(['maxres', 'hq'], thumbnail_urls):
                try:
                    response = requests.get(thumb_url, timeout=10)
                    if response.status_code == 200 and len(response.content) > 1000:
                        filename = f"{clean_song_name}.png"
                        filepath = self.thumbnail_folder / filename
                        
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        
                        self.log(f"   ✅ Thumbnail saved: {filename}")
                        return True
                except:
                    continue
            
            return False
        except:
            return False

    def download_single_audio(self, url, song_name):
        """Download audio from a single YouTube URL"""
        try:
            self.log(f"🎵 Starting audio download: {song_name}")
            
            clean_song_name = self.clean_filename(song_name)
            if not clean_song_name:
                clean_song_name = "audio"
            
            yt_dlp_options = [
                sys.executable, '-m', 'yt_dlp',
                '--extract-audio',
                '--audio-format', 'mp3',
                '--audio-quality', '192K',
                '--no-playlist',
                '--no-warnings',
                '--ignore-errors',
                '--no-check-certificate',
                '--prefer-insecure',
                '--concurrent-fragments', '4',
                '--extractor-args', 'youtube:player_client=android,web,ios;player_skip=webpage',
                '--user-agent', 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36',
                '-o', str(self.audio_folder / f'{clean_song_name}.%(ext)s'),
                url
            ]

            # Add cookies if available
            if COOKIES_PATH.exists():
                yt_dlp_options[0:0] = []  # keep structure
                yt_dlp_options.insert(3, '--cookies')
                yt_dlp_options.insert(4, str(COOKIES_PATH))
                self.log("   🍪 Using cookies.txt for download")
            
            result = subprocess.run(
                yt_dlp_options,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                self.log(f"✅ Audio downloaded: {song_name}")
                return True
            else:
                self.log(f"❌ Failed to download: {song_name}")
                # Log the actual error from yt-dlp
                if result.stderr:
                    error_lines = result.stderr.strip().split('\n')
                    # Log last few lines of error (most relevant)
                    for line in error_lines[-5:]:
                        if line.strip():
                            self.log(f"   Error: {line[:150]}")
                if result.stdout:
                    stdout_lines = result.stdout.strip().split('\n')
                    # Log last few lines of stdout
                    for line in stdout_lines[-3:]:
                        if line.strip():
                            self.log(f"   Output: {line[:150]}")
                return False
                
        except subprocess.TimeoutExpired:
            self.log(f"⏰ Timeout: Download took too long (>5 min)")
            return False
        except Exception as e:
            self.log(f"💥 Error: {str(e)[:200]}")
            return False

    def cleanup(self):
        """Clean up browser resources"""
        if self.driver:
            self.log("🧹 Cleaning up browser...")
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

# Global downloader instance
downloader = None

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index_web.html')

@app.route('/api/process', methods=['POST'])
def process_songs():
    """Process songs from the web interface"""
    global downloader, download_progress
    
    try:
        data = request.get_json()
        song_input = data.get('songs', '')
        
        # Reset progress
        with progress_lock:
            download_progress = {
                'status': 'processing',
                'current_song': '',
                'progress': 0,
                'total': 0,
                'results': [],
                'logs': []
            }
        
        # Initialize downloader
        downloader = YouTubeAutoDownloaderWeb(
            thumbnail_folder="thumbnails",
            audio_folder="Audios",
            enable_supabase=False  # Disable for web version
        )
        
        # Parse songs
        songs = downloader.parse_song_list(song_input)
        
        if not songs:
            with progress_lock:
                download_progress['status'] = 'error'
                download_progress['logs'].append("❌ No valid songs found!")
            return jsonify({'success': False, 'message': 'No valid songs found'})
        
        with progress_lock:
            download_progress['total'] = len(songs)
            download_progress['logs'].append(f"📝 Found {len(songs)} songs to process")
        
        # Start processing in background thread
        thread = threading.Thread(target=process_in_background, args=(songs,))
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'total': len(songs)})
        
    except Exception as e:
        with progress_lock:
            download_progress['status'] = 'error'
            download_progress['logs'].append(f"💥 Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

def process_in_background(songs):
    """Background processing of songs"""
    global downloader, download_progress
    
    try:
        video_data = []
        
        # Search for each song (using yt-dlp, no browser needed!)
        for i, song in enumerate(songs, 1):
            with progress_lock:
                download_progress['current_song'] = song
                download_progress['progress'] = i
            
            downloader.log(f"\n📍 Processing {i}/{len(songs)}: {song}")
            video_url = downloader.search_youtube(song)
            
            if video_url:
                video_data.append((video_url, song))
                with progress_lock:
                    download_progress['results'].append({
                        'song': song,
                        'url': video_url,
                        'status': 'found'
                    })
            else:
                with progress_lock:
                    download_progress['results'].append({
                        'song': song,
                        'url': None,
                        'status': 'failed'
                    })
            
            time.sleep(1)  # Small delay between searches
        
        # Download thumbnails and audio
        success_count = 0
        for url, song_name in video_data:
            downloader.download_single_thumbnail(url, song_name)
            if downloader.download_single_audio(url, song_name):
                success_count += 1
        
        with progress_lock:
            download_progress['status'] = 'completed'
            download_progress['logs'].append(f"\n🎉 Process complete! {success_count}/{len(songs)} songs downloaded")
        
    except Exception as e:
        with progress_lock:
            download_progress['status'] = 'error'
            download_progress['logs'].append(f"💥 Error: {str(e)}")

@app.route('/api/upload_cookies', methods=['POST'])
def upload_cookies():
    """Upload a cookies.txt file to use with yt-dlp."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file provided'}), 400
        file = request.files['file']
        if not file.filename:
            return jsonify({'success': False, 'message': 'Empty filename'}), 400
        data = file.read()
        # very basic validation: must contain "youtube.com"
        if b'youtube.com' not in data and b'VISITOR_INFO1_LIVE' not in data:
            # still allow, but warn
            pass
        COOKIES_PATH.write_bytes(data)
        with progress_lock:
            download_progress['logs'].append('🍪 cookies.txt uploaded')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/paste_cookies', methods=['POST'])
def paste_cookies():
    """Accept raw Netscape cookies text and save to cookies.txt."""
    try:
        payload = request.get_json(silent=True) or {}
        text = payload.get('cookies', '')
        if not text.strip():
            return jsonify({'success': False, 'message': 'Empty cookies text'}), 400
        # Normalize line endings and write
        COOKIES_PATH.write_text(text.replace('\r\n', '\n'), encoding='utf-8')
        with progress_lock:
            download_progress['logs'].append('🍪 cookies.txt saved from pasted text')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/progress')
def get_progress():
    """Get current progress"""
    with progress_lock:
        return jsonify(download_progress)

@app.route('/api/reset', methods=['POST'])
def reset_progress():
    """Reset progress"""
    global download_progress
    with progress_lock:
        download_progress = {
            'status': 'idle',
            'current_song': '',
            'progress': 0,
            'total': 0,
            'results': [],
            'logs': [],
            'screenshots': []
        }
    return jsonify({'success': True})

@app.route('/screenshots/<filename>')
def serve_screenshot(filename):
    """Serve screenshot files"""
    return send_from_directory(SCREENSHOTS_FOLDER, filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
