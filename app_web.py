#!/usr/bin/env python3
"""
YouTube Song Search Web Interface
Simple Flask app to search YouTube songs and get video URLs
"""

from flask import Flask, render_template, request, jsonify, send_file
import os
import re
import requests
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import uuid
import threading
import gc
import weakref
from contextlib import contextmanager
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

# Create a global session with connection pooling and retry logic
_http_session = None

def get_http_session():
    """Get or create a shared HTTP session with retry logic."""
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        _http_session.mount("http://", adapter)
        _http_session.mount("https://", adapter)
    return _http_session

# Create data folders
DOWNLOADS_FOLDER = Path("downloaded_audios")
DOWNLOADS_FOLDER.mkdir(parents=True, exist_ok=True)
DEBUG_FOLDER = Path("debug_artifacts")
DEBUG_FOLDER.mkdir(parents=True, exist_ok=True)
ENABLE_EZCONV_DEBUG = os.environ.get("ENABLE_EZCONV_DEBUG", "0") == "1"

# Limit concurrency to reduce memory pressure
_download_lock = threading.Lock()

# Memory optimization: Use weak references for temporary objects
_active_drivers = weakref.WeakSet()

@contextmanager
def memory_efficient_context():
    """Context manager for memory-efficient operations."""
    try:
        yield
    finally:
        # Force garbage collection after operations
        gc.collect()

def cleanup_memory():
    """Aggressive memory cleanup."""
    # Close any remaining drivers
    for driver in list(_active_drivers):
        try:
            driver.quit()
        except Exception:
            pass
    _active_drivers.clear()
    
    # Force garbage collection
    gc.collect()

def parse_song_list(song_input: str) -> list[str]:
    """Parse numbered song list from text input."""
    songs: list[str] = []
    if not song_input or not song_input.strip():
        return songs
    buffer = song_input.strip()
    # Handle single-line input like "1. A 2. B 3. C"
    if "\n" not in buffer and re.search(r"\d+\.\s*\w", buffer):
        parts = re.findall(r"(\d+\.)\s*([^0-9]*?)(?=\d+\.|$)", buffer)
        if parts:
            for _, title in parts:
                song_name = re.sub(r"\s+", " ", title.strip())
                if song_name:
                    songs.append(song_name)
    # Handle multi-line input or if single-line parsing yielded nothing
    if not songs:
        numbered_item_regex = re.compile(r"\b(\d+)\.\s*([^\d].*?)(?=\s*\d+\.|$)", re.DOTALL)
        matches = numbered_item_regex.findall(buffer)
        if matches:
            for _, title in matches:
                song_name = re.sub(r"\s+", " ", title.strip())
                if song_name:
                    songs.append(song_name)
        else:
            line_regex = re.compile(r"^\s*\d+\.\s*(.+)$")
            for raw in buffer.splitlines():
                m = line_regex.match(raw.strip())
                if m:
                    song_name = re.sub(r"\s+", " ", m.group(1).strip())
                    if song_name:
                        songs.append(song_name)
    return songs

def is_shorts_url(video_id: str, html_content: str) -> bool:
    """Check if video ID belongs to a shorts video by looking for '/shorts/VIDEOID' in HTML."""
    return f"/shorts/{video_id}" in html_content

def search_youtube_video(song_name: str, max_retries: int = 2) -> str | None:
    """Search YouTube for a song and return long-form video URL."""
    try:
        search_query = song_name.replace(" ", "+")
        search_url = f"https://www.youtube.com/results?search_query={search_query}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
        # Use session with connection pooling and shorter timeout
        session = get_http_session()
        response = session.get(search_url, headers=headers, timeout=8)
        if response.status_code != 200:
            print(f"YouTube search failed with status {response.status_code}")
            return None
        video_id_pattern = r'"videoId":"([a-zA-Z0-9_-]{11})"'
        matches = re.findall(video_id_pattern, response.text)
        if not matches:
            print(f"No video IDs found for: {song_name}")
            return None
        for video_id in matches[:15]:
            if f"/shorts/{video_id}" in response.text:
                continue
            if len(video_id) == 11:
                return f"https://www.youtube.com/watch?v={video_id}"
        return None
    except requests.Timeout:
        print(f"Timeout searching for: {song_name}")
        return None
    except requests.ConnectionError as e:
        print(f"Connection error for {song_name}: {str(e)[:100]}")
        return None
    except Exception as e:
        print(f"Error searching for {song_name}: {str(e)[:100]}")
        return None
                
@app.route("/")
def index():
    return render_template("index_web.html")

def setup_selenium_driver():
    """Setup headless Chrome driver for Selenium with aggressive memory optimization."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1024,768")  # Smaller window
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    # Aggressive memory optimization flags
    chrome_options.add_argument("--memory-pressure-off")
    chrome_options.add_argument("--max_old_space_size=512")  # Limit V8 heap
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-features=TranslateUI")
    chrome_options.add_argument("--disable-ipc-flooding-protection")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--disable-translate")
    chrome_options.add_argument("--hide-scrollbars")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--disable-permissions-api")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--single-process")  # Single process mode for lower memory
    chrome_options.add_argument("--no-zygote")  # Disable zygote process

    # Light anti-automation adjustments
    try:
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    except Exception:
        pass

    prefs = {
        "download.default_directory": str(DOWNLOADS_FOLDER.absolute()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        # Block images to save memory/bandwidth
        "profile.managed_default_content_settings.images": 2,
        # Block notifications/popups where possible
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.popups": 2,
        # Additional memory optimizations
        "profile.default_content_setting_values.plugins": 2,
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.media_stream": 2,
        "profile.default_content_setting_values.automatic_downloads": 2,
        "profile.default_content_setting_values.midi_sysex": 2,
        "profile.default_content_setting_values.push_messaging": 2,
        "profile.default_content_setting_values.mixed_script": 2,
        "profile.default_content_setting_values.unsandboxed_plugins": 2,
        "profile.default_content_setting_values.ppapi_broker": 2,
        # Disable hardware acceleration
        "hardware_acceleration_mode": 0,
        # Reduce memory usage
        "profile.content_settings.exceptions.automatic_downloads": {},
        "profile.content_settings.exceptions.notifications": {},
        "profile.content_settings.exceptions.geolocation": {},
        "profile.content_settings.exceptions.media_stream": {},
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # Additional memory/perf flags
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--media-cache-size=0")
    chrome_options.add_argument("--disk-cache-size=0")
    chrome_options.add_argument("--aggressive-cache-discard")
    chrome_options.add_argument("--enable-low-res-tiling")
    chrome_options.add_argument("--disable-background-mode")
    chrome_options.add_argument("--disable-client-side-phishing-detection")
    chrome_options.add_argument("--disable-component-update")
    chrome_options.add_argument("--disable-domain-reliability")
    chrome_options.add_argument("--disable-features=AudioServiceOutOfProcess")
    chrome_options.add_argument("--disable-hang-monitor")
    chrome_options.add_argument("--disable-prompt-on-repost")
    chrome_options.add_argument("--disable-rtc-smoothness-algorithm")
    chrome_options.add_argument("--disable-speech-api")
    chrome_options.add_argument("--disable-speech-synthesis-api")
    chrome_options.add_argument("--disable-webgl")
    chrome_options.add_argument("--disable-webgl2")
    chrome_options.add_argument("--force-color-profile=srgb")
    chrome_options.add_argument("--metrics-recording-only")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--no-pings")
    chrome_options.add_argument("--no-service-autorun")
    chrome_options.add_argument("--password-store=basic")
    chrome_options.add_argument("--use-mock-keychain")
    chrome_options.add_argument("--disable-component-extensions-with-background-pages")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")

    try:
        chromedriver_path = os.environ.get("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
        chrome_binary_path = os.environ.get("CHROME_BIN", "/usr/bin/chromium-browser")

        if os.path.exists(chrome_binary_path):
            chrome_options.binary_location = chrome_binary_path

        if os.path.exists(chromedriver_path):
            service = Service(executable_path=chromedriver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
        
        # Track driver for cleanup
        _active_drivers.add(driver)
        return driver
    except Exception as e:
        print(f"Error setting up Selenium driver: {e}")
        cleanup_memory()  # Cleanup on error
        return None
            
def save_debug(driver, debug_dir: Path, label: str) -> None:
    """Save page HTML and screenshot for debugging."""
    if not ENABLE_EZCONV_DEBUG:
        return
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
        html_path = debug_dir / f"{label}.html"
        png_path = debug_dir / f"{label}.png"
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(driver.page_source)
        try:
            driver.save_screenshot(str(png_path))
        except Exception:
            pass
        print(f"[DEBUG] Saved {label} HTML -> {html_path}")
        print(f"[DEBUG] Saved {label} PNG  -> {png_path}")
    except Exception as e:
        print(f"[DEBUG] Failed saving debug artifacts ({label}): {e}")

def try_click(driver, element) -> bool:
    """Attempt multiple strategies to click an element reliably."""
    try:
        element.click()
        return True
    except Exception:
        pass
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.2)
        element.click()
        return True
    except Exception:
        pass
    try:
        driver.execute_script("arguments[0].click();", element)
        return True
    except Exception:
        return False

def handle_consent_and_popups(driver) -> None:
    """Try to accept cookie banners and close ad popups if any."""
    selectors = [
        (By.ID, "onetrust-accept-btn-handler"),
        (By.CSS_SELECTOR, "button#onetrust-accept-btn-handler"),
        (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]")
    ]
    for by, sel in selectors:
        try:
            btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((by, sel)))
            if try_click(driver, btn):
                print("[DEBUG] Cookie/consent banner accepted")
                break
        except Exception:
            pass

    # Close extra windows (ads)
    try:
        main = driver.current_window_handle
        for handle in driver.window_handles:
            if handle != main:
                driver.switch_to.window(handle)
                driver.close()
        driver.switch_to.window(main)
    except Exception:
        pass

@app.route("/api/download-audio", methods=["POST"])
def download_audio():
    """Download audio from YouTube via ezconv.com automation."""
    with memory_efficient_context():
        data = request.get_json()
        youtube_url = data.get("youtube_url", "")
        if not youtube_url:
            return jsonify({"success": False, "message": "No YouTube URL provided"})
        print(f"Starting audio download for: {youtube_url}")
        debug_id = uuid.uuid4().hex[:8]
        debug_dir = DEBUG_FOLDER / f"job_{debug_id}"
        if not _download_lock.acquire(blocking=False):
            return jsonify({"success": False, "message": "Server busy. Please try again in a moment."})
        driver = None
        try:
            driver = setup_selenium_driver()
            if not driver:
                return jsonify({"success": False, "message": "Failed to initialize browser"})
            print("Navigating to ezconv.com...")
            driver.get("https://ezconv.com/v820")
            time.sleep(2)
            save_debug(driver, debug_dir, "01_loaded")
            handle_consent_and_popups(driver)
            save_debug(driver, debug_dir, "02_after_consent")
            print("Looking for URL input field...")
            url_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
            )
            url_input.clear()
            url_input.send_keys(youtube_url)
            try:
                driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
                    "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                    url_input,
                )
            except Exception:
                pass
            print("YouTube URL pasted")
            save_debug(driver, debug_dir, "03_url_filled")
            print("Looking for Convert button...")
            convert_locators = [
                (By.XPATH, "//button[@id=':R1ajalffata:']"),
                (By.XPATH, "//button[contains(normalize-space(), 'Convert')]"),
                (By.XPATH, "//*[self::button or self::a][contains(translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'CONVERT')]")
            ]
            convert_button = None
            for by, sel in convert_locators:
                try:
                    convert_button = WebDriverWait(driver, 6).until(
                        EC.element_to_be_clickable((by, sel))
                    )
                    break
                except Exception:
                    continue
            if not convert_button:
                save_debug(driver, debug_dir, "04_convert_not_found")
                return jsonify({"success": False, "message": "Could not find Convert button", "debug_id": debug_id})
            if not try_click(driver, convert_button):
                save_debug(driver, debug_dir, "04_convert_click_failed")
                return jsonify({"success": False, "message": "Failed to click Convert button", "debug_id": debug_id})
            print("Convert button clicked")
            time.sleep(1)
            handle_consent_and_popups(driver)
            save_debug(driver, debug_dir, "05_after_convert_click")
            print("Waiting for conversion to complete...")
            download_button = None
            max_wait_time = 90
            try:
                dl_locators = [
                    (By.XPATH, "//button[normalize-space()='Download MP3']"),
                    (By.XPATH, "//a[normalize-space()='Download MP3']"),
                    (By.XPATH, "//*[self::a or self::button][contains(translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'DOWNLOAD MP3')]")
                ]
                for seconds_elapsed in range(max_wait_time):
                    found = False
                    for by, sel in dl_locators:
                        try:
                            elem = driver.find_element(by, sel)
                            download_button = elem
                            found = True
                            break
                        except Exception:
                            pass
                    if not found:
                        try:
                            frames = driver.find_elements(By.TAG_NAME, "iframe")
                            for frame in frames:
                                driver.switch_to.frame(frame)
                                for by, sel in dl_locators:
                                    try:
                                        elem = driver.find_element(by, sel)
                                        download_button = elem
                                        found = True
                                        break
                                    except Exception:
                                        pass
                                driver.switch_to.default_content()
                                if found:
                                    break
                        except Exception:
                            driver.switch_to.default_content()
                    if found:
                        print(f"✅ Download MP3 control appeared after {seconds_elapsed + 1} seconds!")
                        break
                    time.sleep(1)
                    if (seconds_elapsed + 1) % 5 == 0:
                        print(f"   ⏳ Still converting... ({seconds_elapsed + 1}s elapsed)")
                if not download_button:
                    print(f"❌ Timeout: Download button did not appear after {max_wait_time} seconds")
                    save_debug(driver, debug_dir, "06_timeout_no_download")
                    return jsonify({"success": False, "message": f"Conversion timeout after {max_wait_time} seconds", "debug_id": debug_id})
                time.sleep(1)
                try:
                    download_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//*[self::a or self::button][contains(translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'DOWNLOAD MP3')]")
                    ))
                except Exception:
                    pass
                print("Download button is clickable, getting download link...")
                download_link = download_button.get_attribute("href")
                if not download_link:
                    onclick = download_button.get_attribute("onclick")
                    if onclick:
                        print(f"Found onclick: {onclick}")
                    try:
                        parent = download_button.find_element(By.XPATH, "..")
                        download_link = parent.get_attribute("href")
                    except Exception:
                        pass
                if not download_link:
                    download_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='download'], a[download]")
                    if download_links:
                        download_link = download_links[0].get_attribute("href")
                        print(f"Found download link via CSS selector: {download_link}")
                print("Clicking Download MP3 button...")
                if not try_click(driver, download_button):
                    driver.execute_script("arguments[0].click();", download_button)
                time.sleep(3)
                time.sleep(2)
                current_url = driver.current_url
                print(f"Current URL after click: {current_url}")
                if "download" in current_url.lower() or ".mp3" in current_url.lower():
                    download_link = current_url
                    print(f"Download link from redirect: {download_link}")
                if not download_link:
                    print("Looking for download links on page...")
                    download_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='download'], a[href*='.mp3'], a[download]")
                    if download_links:
                        download_link = download_links[0].get_attribute("href")
                        print(f"Found download link: {download_link}")
                if not download_link:
                    print("Trying to extract download URL from page source...")
                    page_source = driver.page_source
                    mp3_pattern = r'(https?://[^\s<>"]+\.mp3[^\s<>"]*)'
                    matches = re.findall(mp3_pattern, page_source)
                    if matches:
                        download_link = matches[0]
                        print(f"Extracted download link from source: {download_link}")
                if download_link:
                    print(f"Final download link: {download_link}")
                    download_link = download_link.replace("&amp;", "&")
                    print("Starting download via requests...")
                    session = requests.Session()
                    session.headers.update({
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                        "Referer": current_url,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    })
                    try:
                        for c in driver.get_cookies():
                            session.cookies.set(c.get("name"), c.get("value"))
                    except Exception:
                        pass
                    response = session.get(download_link, stream=True, timeout=60, allow_redirects=True)
                    response.raise_for_status()
                    filename = f"audio_{uuid.uuid4().hex[:8]}.mp3"
                    filepath = DOWNLOADS_FOLDER / filename
                    print(f"Saving to: {filepath}")
                    with open(filepath, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    print(f"Audio downloaded successfully: {filename}")
                    return jsonify({
                        "success": True,
                        "audio_url": f"/audio/{filename}",
                        "filename": filename,
                        "debug_id": debug_id,
                    })
                else:
                    print("ERROR: Could not find any download link")
                    save_debug(driver, debug_dir, "07_no_download_link")
                    return jsonify({"success": False, "message": "Could not find download link after conversion", "debug_id": debug_id})
            except Exception as e:
                print(f"Error finding download button: {str(e)}")
                save_debug(driver, debug_dir, "08_exception")
                return jsonify({"success": False, "message": f"Download button not found: {str(e)[:100]}", "debug_id": debug_id})
        except Exception as e:
            print(f"Error during automation: {str(e)}")
            return jsonify({"success": False, "message": f"Automation error: {str(e)[:100]}", "debug_id": debug_id})
        finally:
            try:
                if driver:
                    driver.quit()
                    _active_drivers.discard(driver)
            except Exception:
                pass
            cleanup_memory()
            _download_lock.release()

@app.route("/audio/<filename>")
def serve_audio(filename):
    try:
        filepath = DOWNLOADS_FOLDER / filename
        if filepath.exists():
            return send_file(filepath, mimetype="audio/mpeg")
        else:
            return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/search", methods=["POST"])
def search_songs():
    with memory_efficient_context():
        try:
            data = request.get_json()
            song_input = data.get("songs", "")
            songs = parse_song_list(song_input)
            if not songs:
                return jsonify({"success": False, "message": "No valid songs found! Please use format: 1. Song Name"})
            results = []
            for i, song in enumerate(songs, 1):
                print(f"Searching {i}/{len(songs)}: {song}")
                video_url = search_youtube_video(song)
                results.append({"number": i, "song": song, "url": video_url, "status": "success" if video_url else "failed"})
                if i < len(songs):
                    time.sleep(0.5)
                    if i % 3 == 0:
                        gc.collect()
            return jsonify({"success": True, "total": len(songs), "results": results})
        except Exception as e:
            return jsonify({"success": False, "message": f"Error: {str(e)}"})

@app.route("/api/cleanup", methods=["POST"])
def cleanup_endpoint():
    """Manual memory cleanup endpoint."""
    try:
        cleanup_memory()
        return jsonify({"success": True, "message": "Memory cleanup completed"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Cleanup error: {str(e)}"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
