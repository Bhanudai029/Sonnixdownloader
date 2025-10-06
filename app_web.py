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

app = Flask(__name__)

# Create downloads folder for audio files
DOWNLOADS_FOLDER = Path("downloaded_audios")
DOWNLOADS_FOLDER.mkdir(parents=True, exist_ok=True)

def parse_song_list(song_input):
    """Parse numbered song list from text input"""
        songs = []
        
        if not song_input or not song_input.strip():
            return songs
        
        buffer = song_input.strip()
        
    # Handle single line with all songs (e.g., "1. A2. B3. C")
        if '\n' not in buffer and re.search(r'\d+\.\s*\w', buffer):
            parts = re.findall(r'(\d+\.)\s*([^0-9]*?)(?=\d+\.|$)', buffer)
            if parts:
                for _, title in parts:
                    song_name = re.sub(r"\s+", " ", title.strip())
                    if song_name:
                        songs.append(song_name)
        else:
        # Handle multi-line input
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

def is_shorts_url(video_id, html_content):
    """Check if video ID belongs to a shorts video"""
    # Look for shorts indicators in the HTML
    if f'/shorts/{video_id}' in html_content:
        return True
    return False

def search_youtube_video(song_name, max_retries=2):
    """Search YouTube for a song and return long-form video URL"""
    try:
        # Format search query
            search_query = song_name.replace(' ', '+')
            search_url = f"https://www.youtube.com/results?search_query={search_query}"
            
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                }
                
        # Make HTTP request to YouTube search
                response = requests.get(search_url, headers=headers, timeout=15)
                
                if response.status_code != 200:
                    return None
                
        # Extract video IDs from HTML
        # Pattern: "videoId":"VIDEO_ID"
                video_id_pattern = r'"videoId":"([a-zA-Z0-9_-]{11})"'
                matches = re.findall(video_id_pattern, response.text)
                
                if not matches:
                    return None
                
        # Filter out shorts and get first valid long-form video
        for video_id in matches[:15]:  # Check first 15 results
            # Check if this is a shorts video
            if f'/shorts/{video_id}' in response.text:
                continue  # Skip shorts
            
            # Valid long-form video found
            if len(video_id) == 11:
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        return video_url
                
                return None
                    
            except requests.Timeout:
                return None
            except Exception as e:
        print(f"Error searching for {song_name}: {str(e)[:100]}")
                return None
                
@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index_web.html')

def setup_selenium_driver():
    """Setup headless Chrome driver for Selenium"""
                chrome_options = Options()
    chrome_options.add_argument("--headless=new")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--window-size=1920,1080")
                chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    # Set download directory preferences (use add_experimental_option, not add_experimental_prefs)
    prefs = {
        "download.default_directory": str(DOWNLOADS_FOLDER.absolute()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    try:
        chromedriver_path = os.environ.get('CHROMEDRIVER_PATH', '/usr/bin/chromedriver')
        chrome_binary_path = os.environ.get('CHROME_BIN', '/usr/bin/chromium-browser')
        
        if os.path.exists(chrome_binary_path):
            chrome_options.binary_location = chrome_binary_path
        
        if os.path.exists(chromedriver_path):
            service = Service(executable_path=chromedriver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
                driver = webdriver.Chrome(options=chrome_options)

        return driver
    except Exception as e:
        print(f"Error setting up Selenium driver: {e}")
        return None

@app.route('/api/download-audio', methods=['POST'])
def download_audio():
    """Download audio from YouTube via ezconv.com automation"""
    try:
        data = request.get_json()
        youtube_url = data.get('youtube_url', '')
        
        if not youtube_url:
            return jsonify({'success': False, 'message': 'No YouTube URL provided'})
        
        print(f"Starting audio download for: {youtube_url}")
        
        # Setup Selenium driver
        driver = setup_selenium_driver()
        if not driver:
            return jsonify({'success': False, 'message': 'Failed to initialize browser'})
        
        try:
            # Navigate to ezconv.com
            print("Navigating to ezconv.com...")
                    driver.get("https://ezconv.com/v820")
            time.sleep(2)
            
            # Find and fill the URL input field
            print("Looking for URL input field...")
            url_input = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
                    )
            url_input.clear()
            url_input.send_keys(youtube_url)
            print("YouTube URL pasted")
            
            # Find and click the Convert button using the XPath you provided
            print("Looking for Convert button...")
            convert_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@id=':R1ajalffata:']"))
            )
            convert_button.click()
            print("Convert button clicked")
            
            # Wait for conversion to complete - check every second for Download MP3 button
            print("Waiting for conversion to complete...")
            download_button = None
            max_wait_time = 60  # Maximum 60 seconds
            
            try:
                # Check every second if the download button appears
                for seconds_elapsed in range(max_wait_time):
                    try:
                        # Check if button exists
                        download_button = driver.find_element(By.XPATH, "//button[normalize-space()='Download MP3']")
                        print(f"✅ Download MP3 button appeared after {seconds_elapsed + 1} seconds!")
                        break
                    except:
                        # Button not found yet, wait 1 second and check again
                        time.sleep(1)
                        if (seconds_elapsed + 1) % 5 == 0:  # Log every 5 seconds
                            print(f"   ⏳ Still converting... ({seconds_elapsed + 1}s elapsed)")
                
                if not download_button:
                    print(f"❌ Timeout: Download button did not appear after {max_wait_time} seconds")
                    driver.quit()
                    return jsonify({'success': False, 'message': f'Conversion timeout after {max_wait_time} seconds'})
                
                # Wait a bit more to ensure it's clickable
                        time.sleep(1)
                
                # Try to make it clickable
                download_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Download MP3']"))
                        )
                
                print(f"Download button is clickable, getting download link...")
                
                # Get download link before clicking
                download_link = download_button.get_attribute("href")
                if not download_link:
                    # Try onclick attribute
                    onclick = download_button.get_attribute("onclick")
                    if onclick:
                        print(f"Found onclick: {onclick}")
                    
                    # Try to find parent anchor tag
                    try:
                        parent = download_button.find_element(By.XPATH, "..")
                        download_link = parent.get_attribute("href")
                    except:
                        pass
                
                if not download_link:
                    # Try to find download link in page
                    download_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='download'], a[download]")
                    if download_links:
                        download_link = download_links[0].get_attribute("href")
                        print(f"Found download link via CSS selector: {download_link}")
                
                print(f"Clicking Download MP3 button...")
                driver.execute_script("arguments[0].click();", download_button)
                time.sleep(3)
                
                # Wait for potential redirect or download to start
                time.sleep(2)
                
                # Try to get download URL from current page
                    current_url = driver.current_url
                print(f"Current URL after click: {current_url}")

                    if 'download' in current_url.lower() or '.mp3' in current_url.lower():
                    download_link = current_url
                    print(f"Download link from redirect: {download_link}")
                
                if not download_link:
                    # Look for download links on the page
                    print("Looking for download links on page...")
                    download_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='download'], a[href*='.mp3'], a[download]")
                            if download_links:
                        download_link = download_links[0].get_attribute("href")
                        print(f"Found download link: {download_link}")
                
                # Try to extract from page source as last resort
                if not download_link:
                    print("Trying to extract download URL from page source...")
                    page_source = driver.page_source
                    import re
                    # Look for download URLs in the page source
                    mp3_pattern = r'(https?://[^\s<>"]+\.mp3[^\s<>"]*)'
                    matches = re.findall(mp3_pattern, page_source)
                    if matches:
                        download_link = matches[0]
                        print(f"Extracted download link from source: {download_link}")
                
                if download_link:
                    print(f"Final download link: {download_link}")
                    
                    # Clean up the URL (remove HTML entities)
                    download_link = download_link.replace('&amp;', '&')
                    
                    # Download the file using requests
                    print(f"Starting download via requests...")
                    response = requests.get(download_link, stream=True, timeout=60, allow_redirects=True)
                    response.raise_for_status()

                    # Generate unique filename
                    filename = f"audio_{uuid.uuid4().hex[:8]}.mp3"
                    filepath = DOWNLOADS_FOLDER / filename
                    
                    print(f"Saving to: {filepath}")
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)

                    print(f"Audio downloaded successfully: {filename}")
                    
                    driver.quit()

                    # Return the audio file URL
                    return jsonify({
                        'success': True,
                        'audio_url': f'/audio/{filename}',
                        'filename': filename
                    })
                else:
                    print("ERROR: Could not find any download link")
                    driver.quit()
                    return jsonify({'success': False, 'message': 'Could not find download link after conversion'})

            except Exception as e:
                print(f"Error finding download button: {str(e)}")
                driver.quit()
                return jsonify({'success': False, 'message': f'Download button not found: {str(e)[:100]}'})
        
        except Exception as e:
            print(f"Error during automation: {str(e)}")
            if driver:
                driver.quit()
            return jsonify({'success': False, 'message': f'Automation error: {str(e)[:100]}'})

        except Exception as e:
        print(f"Error in download_audio: {str(e)}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)[:100]}'})

@app.route('/audio/<filename>')
def serve_audio(filename):
    """Serve downloaded audio files"""
    try:
        filepath = DOWNLOADS_FOLDER / filename
        if filepath.exists():
            return send_file(filepath, mimetype='audio/mpeg')
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search', methods=['POST'])
def search_songs():
    """Search for songs and return video URLs"""
    try:
        data = request.get_json()
        song_input = data.get('songs', '')
        
        # Parse the song list
        songs = parse_song_list(song_input)
        
        if not songs:
            return jsonify({
                'success': False,
                'message': 'No valid songs found! Please use format: 1. Song Name'
            })
        
        # Search for each song
        results = []
        for i, song in enumerate(songs, 1):
            print(f"Searching {i}/{len(songs)}: {song}")
            
            video_url = search_youtube_video(song)
            
            results.append({
                'number': i,
                        'song': song,
                        'url': video_url,
                'status': 'success' if video_url else 'failed'
            })
            
            # Small delay between searches
            if i < len(songs):
                time.sleep(0.5)
        
        return jsonify({
            'success': True,
            'total': len(songs),
            'results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

