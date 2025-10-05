import os
import re
import json
import requests
import yt_dlp
import tempfile
import platform
import time
import shutil
from http.cookiejar import MozillaCookieJar
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image, ImageDraw
import urllib.request
import traceback
import logging
import subprocess
import sys # Added for sys.executable

# from vpn_handler import get_ytdlp_proxy_url, mark_proxy_failed

# Import our local downloaders
# from download_direct import download_with_cookies as download_direct
# from proxy_download import download_with_proxy
from test_cookies import detect_browser_from_user_agent as get_cookies_for_browser
from test_video_availability import check_video_availability as get_video_availability

# Set up logging
logging.basicConfig(level=logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logging.getLogger().addHandler(handler)

# --- Environment Variables ---
# Load environment variables from .env file
load_dotenv()

# We need a YouTube API key to get video details like subscriber count
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'cookies'
app.config['DOWNLOAD_FOLDER'] = 'downloads'
app.secret_key = os.urandom(24)

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Log to console
        logging.FileHandler('app.log', mode='a')  # Also log to file
    ]
)
# Ensure Flask's logger uses the same configuration
app.logger.setLevel(logging.INFO)
# Suppress overly verbose logs from libraries if needed
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

API_KEY = os.getenv("YOUTUBE_API_KEY")

# Get the proxy URL from environment variable
YTDLP_PROXY_URL_ENV = os.getenv("YTDLP_PROXY_URL")

if not API_KEY:
    app.logger.warning("YOUTUBE_API_KEY environment variable is not set. API dependent features may fail.")

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
if not os.path.exists(app.config['DOWNLOAD_FOLDER']):
    os.makedirs(app.config['DOWNLOAD_FOLDER'])

# Determine the effective YTDLP_PROXY_URL
EFFECTIVE_YTDLP_PROXY_URL = None

# If an explicit proxy URL was provided in environment, use that
if YTDLP_PROXY_URL_ENV:
    EFFECTIVE_YTDLP_PROXY_URL = YTDLP_PROXY_URL_ENV
    app.logger.info(f"Using proxy URL from environment variable: {YTDLP_PROXY_URL_ENV}")

# Function to determine browser type based on OS and User-Agent
def detect_browser_from_user_agent(user_agent_string):
    """
    Detect browser name from User-Agent string for cookiesfrombrowser
    """
    if not user_agent_string:
        return "chrome"  # Default to chrome
        
    ua_lower = user_agent_string.lower()
    
    if "edg" in ua_lower:
        return "edge"
    elif "chrome" in ua_lower:
        return "chrome"
    elif "firefox" in ua_lower:
        return "firefox"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        return "safari"
    elif "opera" in ua_lower:
        return "opera"
    else:
        return "chrome"  # Default to chrome

# Function to get a YouTube API service
def get_youtube_service():
    if not API_KEY:
        raise ValueError("YouTube API key is required but not set")
    return build('youtube', 'v3', developerKey=API_KEY, cache_discovery=False)

# Format numbers for display (e.g., 1000 -> 1K, 1000000 -> 1M)
def format_count(count_str):
    try:
        count = int(count_str)
        if count >= 1000000:
            return f"{count/1000000:.1f}M"
        elif count >= 1000:
            return f"{count/1000:.1f}K"
        else:
            return str(count)
    except (ValueError, TypeError):
        return "0"

def parse_duration(iso_duration):
    """Parse ISO 8601 duration format (e.g., PT1H30M15S) into a human-readable format."""
    duration = iso_duration.replace('PT', '')
    hours = 0
    minutes = 0
    seconds = 0
    
    # Extract hours
    if 'H' in duration:
        hours_part = duration.split('H')[0]
        if hours_part:
            hours = int(hours_part)
        duration = duration.split('H')[1]
    
    # Extract minutes
    if 'M' in duration:
        minutes_part = duration.split('M')[0]
        if minutes_part:
            minutes = int(minutes_part)
        duration = duration.split('M')[1]
    
    # Extract seconds
    if 'S' in duration:
        seconds_part = duration.split('S')[0]
        if seconds_part:
            seconds = int(seconds_part)
    
    # Format the duration string
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

def format_duration(seconds):
    """Format seconds into a human-readable duration format."""
    if not seconds:
        return "0:00"
        
    try:
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    except (ValueError, TypeError):
        return "0:00"

def extract_video_id(url):
    """Extract the video ID from a YouTube URL"""
    video_id = None
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',          # Standard youtube.com URLs
        r'(?:embed\/)([0-9A-Za-z_-]{11}).*',        # Embed URLs
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11}).*',    # youtu.be short URLs
        r'(?:shorts\/)([0-9A-Za-z_-]{11}).*'        # YouTube shorts URLs
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            break
    
    # Also store whether this is a Shorts URL for later use
    is_shorts = '/shorts/' in url.lower()
    
    return video_id, is_shorts

def get_youtube_quality_from_web(video_id):
    """
    Scrape YouTube webpage to detect actual available video qualities.
    This is more reliable when yt-dlp is blocked by YouTube's bot detection.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        app.logger.info(f"Attempting web scraping for video {video_id}...")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        html_content = response.text
        
        # Extract from ytInitialPlayerResponse
        player_response_pattern = r'var ytInitialPlayerResponse = ({.*?});'
        match = re.search(player_response_pattern, html_content)
        
        if match:
            try:
                player_data = json.loads(match.group(1))
                streaming_data = player_data.get('streamingData', {})
                
                # Check adaptive formats (separate video and audio streams)
                adaptive_formats = streaming_data.get('adaptiveFormats', [])
                formats = streaming_data.get('formats', [])
                
                available_heights = set()
                
                # Process adaptive formats (usually higher quality)
                for fmt in adaptive_formats:
                    if fmt.get('mimeType', '').startswith('video/') and 'height' in fmt:
                        height = fmt['height']
                        available_heights.add(height)
                        app.logger.info(f"Web scraping found adaptive format: {height}p - {fmt.get('qualityLabel', '?')}")
                
                # Process regular formats
                for fmt in formats:
                    if 'height' in fmt:
                        height = fmt['height']
                        available_heights.add(height)
                        app.logger.info(f"Web scraping found regular format: {height}p - {fmt.get('qualityLabel', '?')}")
                
                if available_heights:
                    max_height = max(available_heights)
                    sorted_heights = sorted(available_heights, reverse=True)
                    app.logger.info(f"Web scraping SUCCESS: Available resolutions for {video_id}: {sorted_heights}")
                    return max_height, sorted_heights
                    
            except json.JSONDecodeError as e:
                app.logger.warning(f"Could not parse player response JSON: {e}")
        
        # Fallback: Look for quality mentions in page content
        quality_patterns = [
            r'"qualityLabel":"([^"]*4K[^"]*)",',
            r'"qualityLabel":"([^"]*2160p[^"]*)",', 
            r'"qualityLabel":"([^"]*1440p[^"]*)",',
            r'"qualityLabel":"([^"]*1080p[^"]*)",',
            r'"qualityLabel":"([^"]*720p[^"]*)",'
        ]
        
        found_qualities = set()
        for pattern in quality_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                found_qualities.add(match)
                app.logger.info(f"Found quality label: {match}")
        
        if found_qualities:
            # Parse height from quality labels
            heights = set()
            for quality in found_qualities:
                if '4K' in quality or '2160p' in quality:
                    heights.add(2160)
                elif '1440p' in quality:
                    heights.add(1440)
                elif '1080p' in quality:
                    heights.add(1080)
                elif '720p' in quality:
                    heights.add(720)
                elif '480p' in quality:
                    heights.add(480)
                elif '360p' in quality:
                    heights.add(360)
            
            if heights:
                max_height = max(heights)
                sorted_heights = sorted(heights, reverse=True)
                app.logger.info(f"Web scraping extracted heights from quality labels: {sorted_heights}")
                return max_height, sorted_heights
        
        app.logger.warning(f"Web scraping found no quality information for {video_id}")
        return None, []
        
    except Exception as e:
        app.logger.error(f"Error scraping YouTube page for {video_id}: {e}")
        return None, []

def process_cookie_string(cookies_content_str):
    """
    Process cookie string to ensure it's properly formatted for Netscape format.
    This is critical for bypassing YouTube's bot detection when deployed.
    """
    if not cookies_content_str or not cookies_content_str.strip():
        return "" # Return empty string for empty/whitespace-only input

    normalized_content = cookies_content_str.replace('\r\n', '\n').replace('\r', '\n')
    lines = normalized_content.split('\n')
    
    output_lines = []
    header_written = False

    first_content_line_processed = False
    temp_buffer = [] # To hold lines before deciding if header needs to be prefixed

    for line_text in lines:
        stripped_line = line_text.strip()
        
        if not stripped_line:
            if first_content_line_processed: # Preserve empty lines after first content if any
                 temp_buffer.append("") 
            continue # Skip leading empty lines or multiple empty lines

        if not first_content_line_processed and stripped_line.startswith("# Netscape HTTP Cookie File"):
            output_lines.append(stripped_line) # Add header first
            header_written = True
            first_content_line_processed = True
        elif stripped_line.startswith("#"):
            # Avoid adding default header again if another comment is the first content
            if not header_written and not first_content_line_processed:
                 output_lines.append("# Netscape HTTP Cookie File")
                 header_written = True
            first_content_line_processed = True
            if not (header_written and stripped_line == "# Netscape HTTP Cookie File"):
                 temp_buffer.append(stripped_line) # Store other comments
        else: # Assumed to be a cookie data line
            if not header_written and not first_content_line_processed:
                 output_lines.append("# Netscape HTTP Cookie File")
                 header_written = True
            first_content_line_processed = True
            parts = re.split(r'\s+', stripped_line) # Split by one or more whitespace characters
            if len(parts) == 7 or len(parts) == 6: # Typical number of fields
                temp_buffer.append("\t".join(parts)) # Re-join with TABS
            else:
                temp_buffer.append(stripped_line) # Append as is if not standard structure
    
    output_lines.extend(temp_buffer)
    
    # Final check if header was missed (e.g. if input was only cookie data lines)
    if not header_written and any(line.strip() for line in output_lines):
        output_lines.insert(0, "# Netscape HTTP Cookie File")
    elif not output_lines:
        return ""

    final_str = "\n".join(output_lines)
    if final_str and not final_str.endswith('\n'): # Ensure trailing newline if there\'s content
      final_str += '\n'
      
    return final_str

def create_cookie_file(cookies_content, identifier="default"):
    """
    Create and return the path to a cookie file from cookie content.
    Uses a more secure temporary file approach that works better in deployed environments.
    """
    if not cookies_content or not cookies_content.strip():
        return None
        
    processed_cookies = process_cookie_string(cookies_content)
    if not processed_cookies.strip() or processed_cookies.strip() == "# Netscape HTTP Cookie File":
        return None
        
    # Create a temporary file that will be automatically cleaned up when closed
    cookie_file = tempfile.NamedTemporaryFile(
        prefix=f"ytdl_cookies_{identifier}_", 
        suffix=".txt",
        dir=app.config['UPLOAD_FOLDER'],
        delete=False  # We\'ll handle deletion in finally blocks
    )
    
    try:
        with open(cookie_file.name, 'w', encoding='utf-8', newline='\n') as f:
            f.write(processed_cookies)
        return cookie_file.name
    except Exception as e:
        print(f"Error creating cookie file: {e}")
        try:
            os.remove(cookie_file.name)
        except:
            pass
        return None

# Custom progress hook to log yt-dlp status
def ydl_progress_hook(d):
    if d['status'] == 'downloading':
        app.logger.info(f"YDL-HOOK: Downloading {d.get('filename')} - {d.get('_percent_str', '')} of {d.get('_total_bytes_str', '')} at {d.get('_speed_str', '')}")
    elif d['status'] == 'finished':
        app.logger.info(f"YDL-HOOK: Finished downloading {d.get('filename')}")
    elif d['status'] == 'error':
        app.logger.error(f"YDL-HOOK: Error on {d.get('filename')}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch_info', methods=['POST'])
def fetch_info():
    data = request.json
    url = data.get('url')
    video_id, is_shorts = extract_video_id(url)

    if not video_id:
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    temp_ydl_opts_for_info = {
        'quiet': False,  # Keep logging for debugging
        'no_warnings': False,
        'simulate': True,
        'extract_flat': False,
        'skip_download': True,
        'format': 'best',
        'ignoreerrors': True,
        'no_check_certificate': True,
        # Enhanced YouTube extractor arguments to bypass restrictions
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],  # Use Android and Web clients
                'player_skip': ['webpage'],  # Skip webpage extraction
                'include_hls_manifest': [False],  # Disable HLS for faster extraction
                'get_comments': [False]  # Disable comments for faster extraction
            }
        },
        # Better user agent to avoid detection
        'user_agent': 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36',
        # HTTP headers to appear more like a real browser
        'http_headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    }

    if EFFECTIVE_YTDLP_PROXY_URL:
        temp_ydl_opts_for_info['proxy'] = EFFECTIVE_YTDLP_PROXY_URL

    try:
        with yt_dlp.YoutubeDL(temp_ydl_opts_for_info) as ydl:
                    info_dict = ydl.extract_info(url, download=False)
    except Exception as e:
        app.logger.error(f"Error fetching video info with yt-dlp: {str(e)}")
        # Check for common error patterns
        error_lower = str(e).lower()
        if "video unavailable" in error_lower or "private video" in error_lower:
            return jsonify({'error': 'Video is unavailable (private, deleted, or removed).'}), 404
        if "copyright" in error_lower:
            return jsonify({'error': 'Video is unavailable due to a copyright claim.'}), 404
        if "region-blocked" in error_lower or "not available in your country" in error_lower:
            return jsonify({'error': 'Video is not available in your region.'}), 451
        return jsonify({'error': 'Failed to fetch video details. The video may be unavailable or the URL is incorrect.'}), 500

    # API call to get more details like subscribers, likes
    try:
        youtube_service = get_youtube_service()
        video_response = youtube_service.videos().list(
            part='snippet,statistics,contentDetails',
            id=video_id
        ).execute()

        if not video_response.get('items'):
            return jsonify({'error': 'Video not found via YouTube API'}), 404

        video_snippet = video_response['items'][0]['snippet']
        video_statistics = video_response['items'][0]['statistics']
        video_content_details = video_response['items'][0].get('contentDetails', {})
        channel_id = video_snippet.get('channelId')

        channel_response = youtube_service.channels().list(
            part='snippet,statistics',
            id=channel_id
        ).execute()
        
        channel_snippet = channel_response['items'][0]['snippet']
        channel_statistics = channel_response['items'][0]['statistics']
        
        # Get available formats for logging purposes
        available_formats = info_dict.get('formats', [])
        app.logger.info(f"yt-dlp returned {len(available_formats)} total formats for {video_id}")
        
        # Analyze video formats for backup/logging
        video_formats = []
        for i, format_info in enumerate(available_formats):
            format_id = format_info.get('format_id', 'unknown')
            vcodec = format_info.get('vcodec', 'none')
            height = format_info.get('height')
            
            if vcodec != 'none' and height and height > 0:
                video_formats.append({
                    'height': height,
                    'format_id': format_id,
                    'ext': format_info.get('ext', 'unknown')
                })
        
        video_formats.sort(key=lambda x: x['height'], reverse=True)
        if video_formats:
            app.logger.info(f"yt-dlp video formats (backup): {[(f['height'], f['format_id']) for f in video_formats[:3]]}")
        else:
            app.logger.info(f"yt-dlp returned no usable video formats for {video_id}")
        
        # CRITICAL FIX: Always try web scraping FIRST since it's more reliable than yt-dlp
        app.logger.info(f"🔍 Starting web scraping quality detection for {video_id} (primary method)...")
        web_max_height, web_available_heights = get_youtube_quality_from_web(video_id)
        
        if web_max_height and web_available_heights:
            max_height = web_max_height
            available_heights = web_available_heights
            app.logger.info(f"✅ Web scraping SUCCESS: Max quality {max_height}p, available: {available_heights}")
        else:
            app.logger.warning(f"⚠️ Web scraping failed, trying yt-dlp formats as backup...")
            
            # Backup: Try yt-dlp formats
            max_height = 0
            if video_formats:
                max_height = video_formats[0]['height']
                available_heights = sorted(list(set([f['height'] for f in video_formats])), reverse=True)
                app.logger.info(f"yt-dlp backup: Max quality {max_height}p, available: {available_heights}")
            else:
                app.logger.warning(f"Both web scraping and yt-dlp failed, using API fallback...")
                # Final fallback: Use YouTube API and video metadata to infer quality
                video_title = video_snippet.get('title', '').lower()
                video_definition = video_snippet.get('definition', '')
                
                # Smart quality inference based on title keywords and other factors
                if '8k' in video_title or '4320p' in video_title:
                    max_height = 2160  # Cap at 4K for practical purposes
                    app.logger.info(f"Title suggests 8K/4320p, using 4K (2160p) as max quality")
                elif '4k' in video_title or '2160p' in video_title or 'ultra hd' in video_title or 'uhd' in video_title:
                    max_height = 2160
                    app.logger.info(f"Title suggests 4K/2160p quality")
                elif '2k' in video_title or '1440p' in video_title or 'qhd' in video_title:
                    max_height = 1440
                    app.logger.info(f"Title suggests 2K/1440p quality")
                elif '1080p' in video_title or 'full hd' in video_title or 'fhd' in video_title:
                    max_height = 1080
                    app.logger.info(f"Title suggests 1080p Full HD quality")
                elif video_definition == 'hd':
                    # Most HD videos on YouTube are at least 1080p nowadays
                    max_height = 1080
                    app.logger.info(f"Using API fallback: HD definition suggests 1080p quality")
                else:
                    max_height = 720  # Conservative fallback
                    app.logger.info(f"Using API fallback: Conservative 720p quality assumption")
                
                available_heights = []
        
        # If no video formats detected but we have API data, make smart assumptions
        if not available_heights and max_height > 0:
            # Generate realistic quality options based on detected max height
            if max_height >= 2160:  # 4K
                available_heights = [2160, 1440, 1080, 720, 480, 360]
            elif max_height >= 1440:  # 2K
                available_heights = [1440, 1080, 720, 480, 360]
            elif max_height >= 1080:  # 1080p
                available_heights = [1080, 720, 480, 360]
            elif max_height >= 720:  # 720p
                available_heights = [720, 480, 360]
            else:
                available_heights = [480, 360]
            app.logger.info(f"Generated fallback heights based on max_height {max_height}: {available_heights}")
        
        app.logger.info(f"Available heights for {video_id}: {available_heights}")
        
        # Convert max height to quality string and determine available qualities more accurately
        available_qualities = []
        
        app.logger.info(f"Starting quality analysis for max_height: {max_height}")
        
        # Build available qualities based on what's actually available
        for height in available_heights:
            app.logger.info(f"Processing height: {height}")
            if height >= 4320:
                if '8K' not in available_qualities:
                    available_qualities.append('8K')
                    app.logger.info("Added 8K quality")
            elif height >= 2160:
                if '4K' not in available_qualities:
                    available_qualities.append('4K')
                    app.logger.info("Added 4K quality")
            elif height >= 1440:
                if '2K' not in available_qualities:
                    available_qualities.append('2K')
                    app.logger.info("Added 2K quality")
            elif height >= 1080:
                if '1080p' not in available_qualities:
                    available_qualities.append('1080p')
                    app.logger.info("Added 1080p quality")
            elif height >= 720:
                if '720p' not in available_qualities:
                    available_qualities.append('720p')
                    app.logger.info("Added 720p quality")
            elif height >= 480:
                if '480p' not in available_qualities:
                    available_qualities.append('480p')
                    app.logger.info("Added 480p quality")
            elif height >= 360:
                if '360p' not in available_qualities:
                    available_qualities.append('360p')
                    app.logger.info("Added 360p quality")
        
        # Ensure we always have at least 360p available
        if not available_qualities:
            available_qualities = ['360p']
            app.logger.warning("No qualities detected, defaulting to 360p")
        
        app.logger.info(f"Final available qualities for {video_id}: {available_qualities}")
        
        # Determine max quality string
        if max_height >= 4320:
            max_quality = '8K (4320p)'
        elif max_height >= 2160:
            max_quality = '4K (2160p)'
        elif max_height >= 1440:
            max_quality = '2K (1440p)'
        elif max_height >= 1080:
            max_quality = '1080p (Full HD)'
        elif max_height >= 720:
            max_quality = '720p (HD)'
        elif max_height >= 480:
            max_quality = '480p'
        elif max_height > 0:
            max_quality = f'{max_height}p'
        else:
            max_quality = '360p (Default)'  # Default
            
        app.logger.info(f"Final max quality determined for {video_id}: {max_quality}")

        # Parse duration from ISO 8601 format
        duration_iso = video_content_details.get('duration', 'PT0M0S')
        duration = parse_duration(duration_iso)

        # Construct a more detailed info object
        detailed_info = {
            'id': video_id,
            'title': video_snippet.get('title'),
            'thumbnail': video_snippet.get('thumbnails', {}).get('high', {}).get('url'),
            'channel': video_snippet.get('channelTitle'),
            'channel_name': video_snippet.get('channelTitle'),
            'channel_logo': (
                channel_snippet.get('thumbnails', {}).get('high', {}).get('url') or
                channel_snippet.get('thumbnails', {}).get('medium', {}).get('url') or
                channel_snippet.get('thumbnails', {}).get('default', {}).get('url')
            ),
            'channel_id': channel_id,
            'subscribers': format_count(channel_statistics.get('subscriberCount', '0')),
            'likes': format_count(video_statistics.get('likeCount', '0')),
            'views': format_count(video_statistics.get('viewCount', '0')),
            'comments': format_count(video_statistics.get('commentCount', '0')),
            'description': video_snippet.get('description', '') or 'No description has been added to this video.',
            'duration': duration,
            'max_quality': max_quality,
            'available_qualities': available_qualities,
            'formats': info_dict.get('formats', [])
        }
        return jsonify(detailed_info)

    except Exception as e:
        app.logger.error(f"Error fetching extended details from YouTube API: {str(e)}")
        # Fallback when API fails - try web scraping first, then yt-dlp
        
        app.logger.info(f"🔍 Fallback: Trying web scraping for {video_id}...")
        web_max_height, web_available_heights = get_youtube_quality_from_web(video_id)
        
        if web_max_height and web_available_heights:
            max_height = web_max_height
            available_heights = web_available_heights
            app.logger.info(f"✅ Web scraping SUCCESS in fallback: Max quality {max_height}p, available: {available_heights}")
        else:
            app.logger.warning(f"Web scraping failed in fallback, trying yt-dlp formats...")
            
            # Try to determine max quality from yt-dlp formats as last resort
            formats = info_dict.get('formats', [])
            
            # Analyze available video formats
            video_formats = []
            for format_info in formats:
                if format_info.get('vcodec') != 'none' and format_info.get('height'):
                    video_formats.append({
                        'height': format_info.get('height'),
                        'width': format_info.get('width'),
                        'format_id': format_info.get('format_id'),
                        'ext': format_info.get('ext'),
                        'fps': format_info.get('fps'),
                        'vbr': format_info.get('vbr', 0)
                    })
            
            # Sort by height to find the maximum available quality
            video_formats.sort(key=lambda x: x['height'], reverse=True)
            
            max_height = 0
            available_heights = []
            
            if video_formats:
                max_height = video_formats[0]['height']
                available_heights = sorted(list(set([f['height'] for f in video_formats])), reverse=True)
                app.logger.info(f"Fallback yt-dlp: Available video formats for {video_id}: {[f"{f['height']}p" for f in video_formats[:5]]}")
            else:
                app.logger.warning(f"All methods failed for {video_id}, using conservative defaults")
                max_height = 720  # Conservative default
                available_heights = [720, 480, 360]
        
        # Convert max height to quality string and determine available qualities more accurately
        available_qualities = []
        
        # Build available qualities based on what's actually available
        for height in available_heights:
            if height >= 4320:
                if '8K' not in available_qualities:
                    available_qualities.append('8K')
            elif height >= 2160:
                if '4K' not in available_qualities:
                    available_qualities.append('4K')
            elif height >= 1440:
                if '2K' not in available_qualities:
                    available_qualities.append('2K')
            elif height >= 1080:
                if '1080p' not in available_qualities:
                    available_qualities.append('1080p')
            elif height >= 720:
                if '720p' not in available_qualities:
                    available_qualities.append('720p')
            elif height >= 480:
                if '480p' not in available_qualities:
                    available_qualities.append('480p')
            elif height >= 360:
                if '360p' not in available_qualities:
                    available_qualities.append('360p')
        
        # Ensure we always have at least 360p available
        if not available_qualities:
            available_qualities = ['360p']
        
        # Determine max quality string
        if max_height >= 4320:
            max_quality = '8K (4320p)'
        elif max_height >= 2160:
            max_quality = '4K (2160p)'
        elif max_height >= 1440:
            max_quality = '2K (1440p)'
        elif max_height >= 1080:
            max_quality = '1080p (Full HD)'
        elif max_height >= 720:
            max_quality = '720p (HD)'
        elif max_height >= 480:
            max_quality = '480p'
        elif max_height > 0:
            max_quality = f'{max_height}p'
        else:
            max_quality = '360p'  # Default

        fallback_info = {
            'id': video_id,
            'title': info_dict.get('title'),
            'thumbnail': info_dict.get('thumbnail'),
            'channel': info_dict.get('uploader'),
            'channel_name': info_dict.get('uploader'),
            'description': info_dict.get('description', '') or 'No description has been added to this video.',
            'duration': format_duration(info_dict.get('duration', 0)),
            'max_quality': max_quality,
            'available_qualities': available_qualities,
            'comments': 'N/A',
            'formats': info_dict.get('formats', [])
        }
        return jsonify(fallback_info)

@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    quality = data.get('quality', 'best')
    app.logger.info(f"Received download request for URL: {url}, Quality: {quality}")
    cookies_content = data.get('cookies_content')
    user_agent = request.headers.get('User-Agent')
    video_id, is_shorts = extract_video_id(url)
    
    if not video_id:
        return jsonify({'error': 'Invalid URL provided'}), 400

    download_dir = os.path.join(os.getcwd(), app.config['DOWNLOAD_FOLDER'])
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    cookie_file_path = None
    if cookies_content:
        cookie_file_path = create_cookie_file(cookies_content, video_id)

    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        app.logger.error("FFmpeg not found in PATH. Cannot merge video/audio or convert audio.")
        # Clean up cookie file before returning
        if cookie_file_path and os.path.exists(cookie_file_path):
            try:
                os.remove(cookie_file_path)
            except OSError as e:
                app.logger.error(f"Error removing cookie file {cookie_file_path}: {e}")
        return jsonify({'error': 'Server error: FFmpeg is not installed or not in system\'s PATH.'}), 500

    # Determine target height for format selection
    target_height = 0
    quality_str = quality.replace('p', '').replace('K', '000' if 'K' in quality else '')
    if quality_str.isdigit():
        target_height = int(quality_str)
    elif quality == 'best': # Treat 'best' as a very high target for fetching
        target_height = 9999 # effectively 'best'

    # Use a temporary directory for intermediate files
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Enhanced yt-dlp base command with YouTube extractor arguments
            yt_dlp_base_cmd = [sys.executable, '-m', 'yt_dlp']

            # Add enhanced YouTube extractor arguments to bypass restrictions
            yt_dlp_base_cmd.extend([
                '--extractor-args', 'youtube:player_client=android,web;player_skip=webpage;include_hls_manifest=false'
            ])
            
            # Add common yt-dlp options
            if user_agent:
                yt_dlp_base_cmd.extend(['--user-agent', user_agent])
            else:
                # Use Android user agent for better compatibility
                yt_dlp_base_cmd.extend(['--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36'])
                
            if cookie_file_path:
                yt_dlp_base_cmd.extend(['--cookies', cookie_file_path])
            if EFFECTIVE_YTDLP_PROXY_URL:
                yt_dlp_base_cmd.extend(['--proxy', EFFECTIVE_YTDLP_PROXY_URL])

            app.logger.info(f"Checking quality for MP3 download: {quality}")
            # --- Enhanced MP3 logic with better error handling ---
            if quality == 'mp3':
                app.logger.info("--- 🚀 Starting MP3 Download Process ---")
                
                try:
                    # Step 1: Get the direct download URL for the best audio stream
                    app.logger.info("Step 1/3: Getting direct audio URL from yt-dlp...")
                    
                    # Try the most effective audio format strategies with enhanced extractor args
                    audio_format_strategies = [
                        'bestaudio',              # Generic best audio (most compatible)
                        'best[height<=480]/best', # Get best video with audio, limit to 480p for faster processing
                        'worstaudio',             # Sometimes works when best doesn't
                        'best'                    # Last resort - any format with audio
                    ]
                    
                    audio_url = None
                    successful_format = None
                    
                    for audio_format in audio_format_strategies:
                        app.logger.info(f"Trying audio format: {audio_format}")
                        
                        get_url_opts = yt_dlp_base_cmd + [
                            '-f', audio_format,
                            '--get-url',
                            '--no-warnings',
                            '--ignore-errors',           # Continue on download errors
                            '--no-check-certificate',    # Skip SSL certificate verification
                            '--prefer-insecure',         # Prefer insecure connections if needed
                            url
                        ]
                        
                        app.logger.info(f"Running command: {' '.join(get_url_opts)}")
                        process_get_url = subprocess.run(get_url_opts, capture_output=True, text=True, encoding='utf-8', timeout=30)
                        
                        app.logger.info(f"yt-dlp exit code: {process_get_url.returncode}")
                        if process_get_url.returncode == 0:
                            audio_url = process_get_url.stdout.strip()
                            if audio_url.startswith('http'):
                                successful_format = audio_format
                                app.logger.info(f"✅ Success with format '{audio_format}': {audio_url[:100]}...")
                                break
                            else:
                                app.logger.warning(f"Invalid URL with format '{audio_format}': {audio_url}")
                        else:
                            app.logger.warning(f"Failed with format '{audio_format}': {process_get_url.stderr}")
                    
                    if not audio_url or not audio_url.startswith('http'):
                        # All format strategies failed - likely YouTube blocking
                        app.logger.error("All audio format strategies failed")
                        app.logger.error(f"Last yt-dlp STDERR: {process_get_url.stderr}")
                        
                        stderr_str = str(process_get_url.stderr).lower() if process_get_url.stderr else ""
                        if "signature extraction failed" in stderr_str or "precondition check failed" in stderr_str:
                            return jsonify({
                                'error': 'YouTube is blocking audio downloads due to bot detection. To download audio from this video, please provide cookies from an active YouTube session using the cookies field above.'
                            }), 403
                        elif "requested format is not available" in stderr_str or "only images are available" in stderr_str:
                            return jsonify({
                                'error': 'Audio download not available for this video. YouTube is restricting access - try providing cookies from an active YouTube session, or this video may not have downloadable audio tracks.'
                            }), 404
                        else:
                            return jsonify({
                                'error': f'Failed to get audio URL from YouTube. This video may be restricted. Try providing cookies or contact support. Technical details: {process_get_url.stderr}'
                            }), 500

                    # Step 2: Download the audio from the URL using requests
                    app.logger.info("Step 2/3: Downloading audio stream using Python requests...")
                    temp_audio_filepath = os.path.join(temp_dir, 'downloaded_audio_stream')
                    
                    # Pass the user's User-Agent to requests to avoid being throttled
                    headers = {
                        'User-Agent': user_agent if user_agent else 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                    
                    app.logger.info(f"Downloading from URL with headers: {headers}")
                    with requests.get(audio_url, stream=True, headers=headers, timeout=60) as r:
                        r.raise_for_status()
                        app.logger.info(f"HTTP response status: {r.status_code}")
                        app.logger.info(f"Content-Type: {r.headers.get('Content-Type')}")
                        app.logger.info(f"Content-Length: {r.headers.get('Content-Length')}")
                        
                        with open(temp_audio_filepath, 'wb') as f:
                            downloaded_bytes = 0
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                                downloaded_bytes += len(chunk)
                            app.logger.info(f"Downloaded {downloaded_bytes} bytes")
                    
                    if not os.path.exists(temp_audio_filepath) or os.path.getsize(temp_audio_filepath) == 0:
                        raise Exception("Failed to download audio file or the file is empty.")
                    
                    file_size = os.path.getsize(temp_audio_filepath)
                    app.logger.info(f"✅ Temporary audio stream downloaded to: {temp_audio_filepath} (Size: {file_size} bytes)")

                    # Step 3: Use FFmpeg to convert the temporary audio file to MP3
                    app.logger.info("Step 3/3: Converting to MP3 using FFmpeg...")
                    
                    # Get video title for the final filename
                    try:
                        ydl_info = yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True, 'simulate': True}).extract_info(url, download=False)
                        title = ydl_info.get('title', 'audio')
                        app.logger.info(f"Extracted title for MP3 filename: {title}")
                    except Exception as info_e:
                        app.logger.warning(f"Could not get video title for MP3 filename: {info_e}. Using 'audio'.")
                        title = 'audio'

                    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).rstrip()
                    if not safe_title:  # Fallback if title is empty after sanitization
                        safe_title = f"audio_{video_id}"
                    
                    final_output_mp3_path = os.path.join(download_dir, f"{safe_title}.mp3")
                    app.logger.info(f"Final MP3 path: {final_output_mp3_path}")

                    ffmpeg_convert_opts = [
                        ffmpeg_path,
                        '-i', temp_audio_filepath,
                        '-vn',
                        '-c:a', 'libmp3lame',
                        '-b:a', '192k',
                        '-y',
                        final_output_mp3_path
                    ]
                    
                    app.logger.info(f"Running FFmpeg command: {' '.join(ffmpeg_convert_opts)}")
                    process_ffmpeg_convert = subprocess.run(ffmpeg_convert_opts, capture_output=True, text=True, timeout=120)
                    
                    app.logger.info(f"FFmpeg exit code: {process_ffmpeg_convert.returncode}")
                    app.logger.info(f"FFmpeg STDOUT: {process_ffmpeg_convert.stdout}")
                    app.logger.info(f"FFmpeg STDERR: {process_ffmpeg_convert.stderr}")
                    
                    if process_ffmpeg_convert.returncode != 0:
                        raise subprocess.CalledProcessError(process_ffmpeg_convert.returncode, ffmpeg_convert_opts, process_ffmpeg_convert.stdout, process_ffmpeg_convert.stderr)
                    
                    if not os.path.exists(final_output_mp3_path) or os.path.getsize(final_output_mp3_path) == 0:
                        raise Exception(f"FFmpeg conversion failed - output file missing or empty: {final_output_mp3_path}")
                    
                    final_file_size = os.path.getsize(final_output_mp3_path)
                    final_filename = os.path.basename(final_output_mp3_path)
                    
                    app.logger.info(f"✅✅✅ MP3 Download and Conversion complete! ✅✅✅")
                    app.logger.info(f"Final MP3 file: {final_filename} (Size: {final_file_size} bytes)")

                    return jsonify({
                        'success': True,
                        'filename': final_filename,
                        'download_url': f"/downloads/{final_filename}"
                    })
                    
                except subprocess.CalledProcessError as e:
                    app.logger.error(f"Subprocess failed during MP3 download:")
                    app.logger.error(f"Command: {e.cmd}")
                    app.logger.error(f"Exit code: {e.returncode}")
                    app.logger.error(f"STDOUT: {e.stdout}")
                    app.logger.error(f"STDERR: {e.stderr}")
                    
                    # Check for specific yt-dlp errors
                    stderr_str = str(e.stderr).lower() if e.stderr else ""
                    stdout_str = str(e.stdout).lower() if e.stdout else ""
                    
                    if "signature extraction failed" in stderr_str or "precondition check failed" in stderr_str:
                        return jsonify({'error': 'YouTube is blocking audio downloads. This is likely due to bot detection. Please try providing cookies from an active YouTube session.'}), 403
                    elif "video unavailable" in stderr_str or "private video" in stderr_str:
                        return jsonify({'error': 'Audio download failed: Video is unavailable or private.'}), 404
                    elif "http error 429" in stderr_str or "too many requests" in stderr_str:
                        return jsonify({'error': 'Audio download failed: YouTube is rate-limiting requests. Please try again later.'}), 429
                    else:
                        return jsonify({'error': f'Audio download failed. Error details: {e.stderr}'}), 500
                        
                except requests.exceptions.RequestException as e:
                    app.logger.error(f"HTTP request failed during MP3 download: {e}")
                    return jsonify({'error': f'Audio download failed during HTTP request: {str(e)}'}), 500
                    
                except Exception as e:
                    app.logger.error(f"Unexpected error during MP3 download: {e}")
                    app.logger.error(f"Error type: {type(e).__name__}")
                    import traceback
                    app.logger.error(f"Traceback: {traceback.format_exc()}")
                    return jsonify({'error': f'Audio download failed with unexpected error: {str(e)}'}), 500
            
            # --- Existing Video Download Logic (else block) ---
            else:
                # --- Step 1: Download Video-Only Stream ---
                app.logger.info(f"--- Step 1 of 3: Downloading video stream for {quality} ---\n")
                video_format_string = f'bestvideo[height<={target_height}]' if target_height > 0 else 'bestvideo'
                video_opts = yt_dlp_base_cmd + [
                    '-f', video_format_string,
                    '-o', os.path.join(temp_dir, 'video.%(ext)s'),
                    url
                ]
                process_video = subprocess.run(video_opts, check=True, capture_output=True, text=True) # Capture output for debugging
                app.logger.info(f"Video STDOUT: \n{process_video.stdout}")
                app.logger.error(f"Video STDERR: \n{process_video.stderr}")
                video_file = next((os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.startswith('video.')), None)
                if not video_file:
                    raise Exception(f"Failed to download video stream. STDOUT: {process_video.stdout}, STDERR: {process_video.stderr}")
                app.logger.info(f"✅ Video stream downloaded to: {video_file}")

                # --- Step 2: Download Audio-Only Stream ---
                app.logger.info(f"\n--- Step 2 of 3: Downloading audio stream ---\n")
                audio_opts = yt_dlp_base_cmd + [
                    '-f', 'bestaudio',
                    '-o', os.path.join(temp_dir, 'audio.%(ext)s'),
                    url
                ]
                process_audio = subprocess.run(audio_opts, check=True, capture_output=True, text=True) # Capture output for debugging
                app.logger.info(f"Audio STDOUT: \n{process_audio.stdout}")
                app.logger.error(f"Audio STDERR: \n{process_audio.stderr}")
                audio_file = next((os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.startswith('audio.')), None)
                if not audio_file:
                    raise Exception(f"Failed to download audio stream. STDOUT: {process_audio.stdout}, STDERR: {process_audio.stderr}")
                app.logger.info(f"✅ Audio stream downloaded to: {audio_file}")

                # --- Step 3: Merge and Convert Audio with FFmpeg ---
                app.logger.info(f"\n--- Step 3 of 3: Merging video and converting audio to MP3 ---\n")
                # Get video title for the final filename from yt-dlp's info_dict
                try:
                    # Use a separate, minimal yt-dlp instance just for info extraction to avoid conflicts
                    ydl_info = yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True, 'simulate': True}).extract_info(url, download=False)
                    title = ydl_info.get('title', 'video')
                    app.logger.info(f"Extracted title for filename: {title}")
                except Exception as info_e:
                    app.logger.warning(f"Could not get video title for filename: {info_e}. Using 'video'.")
                    title = 'video'

                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).rstrip()
                app.logger.info(f"Safe title for filename: {safe_title}")
                final_output_path = os.path.join(download_dir, f"{safe_title}_{quality}.mp4")
                app.logger.info(f"Final output path on server: {final_output_path}")
                
                merge_opts = [
                    ffmpeg_path,
                    '-i', video_file,
                    '-i', audio_file,
                    '-c:v', 'copy',       # Copy video stream without re-encoding
                    '-c:a', 'mp3',        # Convert audio stream to MP3
                    '-b:a', '192k',       # Set high-quality audio bitrate
                    '-y',                 # Overwrite output file without asking
                    final_output_path
                ]
                process_merge = subprocess.run(merge_opts, check=True, capture_output=True, text=True) # Capture output for debugging
                app.logger.info(f"Merge STDOUT: \n{process_merge.stdout}")
                app.logger.error(f"Merge STDERR: \n{process_merge.stderr}")

                final_filename = os.path.basename(final_output_path)
                app.logger.info(f"Final filename sent to frontend: {final_filename}")
                app.logger.info(f"Download URL sent to frontend: /downloads/{final_filename}")
                app.logger.info(f"✅✅✅ Download and conversion complete! ✅✅✅")
                app.logger.info(f"Final file saved to: {final_filename}")

                return jsonify({
                    'success': True,
                    'filename': final_filename,
                    'download_url': f"/downloads/{final_filename}"
                })

        except subprocess.CalledProcessError as e:
            app.logger.error(f"Command failed with exit code {e.returncode}: {e.cmd}")
            app.logger.error(f"STDOUT: {e.stdout}")
            app.logger.error(f"STDERR: {e.stderr}")
            return jsonify({'error': f'Download process failed. Details in server logs.'}), 500
        except Exception as e:
            app.logger.error(f"An unexpected error occurred during download: {str(e)}")
            error_lower = str(e).lower()

            if "http error 429" in error_lower or "too many requests" in error_lower:
                return jsonify({'error': 'YouTube is rate-limiting requests from this server. Please provide fresh cookies or try again later.'}), 429

            video_unavailable_patterns = [
                "video unavailable", "this video is unavailable", "content unavailable", 
                "not available in your country", "has been removed", "private video"
            ]
            
            if any(pattern in error_lower for pattern in video_unavailable_patterns):
                return jsonify({'error': 'This video is unavailable. It may be private, deleted, or region-restricted.'}), 404

            return jsonify({'error': 'An unexpected error occurred during download.'}), 500
        finally:
            # Cleanup is handled by tempfile.TemporaryDirectory() automatically for temp_dir
            # Only need to clean up the cookie file
            if cookie_file_path and os.path.exists(cookie_file_path):
                try:
                    os.remove(cookie_file_path)
                except OSError as e:
                    app.logger.error(f"Error removing cookie file {cookie_file_path}: {e}")

@app.route('/downloads/<filename>')
def serve_downloaded_file(filename):
    """Serves a downloaded file for the user to download."""
    directory = os.path.join(os.getcwd(), app.config['DOWNLOAD_FOLDER'])
    
    app.logger.info(f"Serving download for filename: {filename}")
    
    # Security check to prevent directory traversal
    if ".." in filename or filename.startswith(("/", "\\")):
        app.logger.warning(f"Potential directory traversal attempt blocked: {filename}")
        return "Invalid filename", 400
        
    file_path = os.path.join(directory, filename)

    if not os.path.isfile(file_path):
        app.logger.error(f"Requested file not found at path: {file_path}")
        return "File not found.", 404

    try:
        # Determine mimetype based on file extension for better browser compatibility
        mimetype = None
        if filename.lower().endswith('.mp3'):
            mimetype = 'audio/mpeg'
        elif filename.lower().endswith('.mp4'):
            mimetype = 'video/mp4'
        
        # Using send_file for more control over response headers like mimetype
        return send_file(file_path, as_attachment=True, mimetype=mimetype)
    except Exception as e:
        app.logger.error(f"Error sending file {filename}: {e}")
        return "Error serving file.", 500

@app.route('/download_thumbnail/<video_id>')
def download_thumbnail(video_id):
    # Check if this is a Shorts video using the 'is_shorts' query parameter
    is_shorts = request.args.get('is_shorts') == 'true'
    
    # List of thumbnail URLs to try in order of preference (high to low quality)
    thumbnail_urls = [
        f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",  # 1280x720
        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",     # 480x360
        f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",     # 320x180
        f"https://i.ytimg.com/vi/{video_id}/default.jpg"        # 120x90
    ]
    
    response = None
    successful_url = None
    
    # Try each thumbnail URL until one works
    for thumbnail_url in thumbnail_urls:
        try:
            response = requests.get(thumbnail_url, stream=True, timeout=10)
            if response.status_code == 200:
                successful_url = thumbnail_url
                app.logger.info(f"Successfully loaded thumbnail from: {thumbnail_url}")
                break
            else:
                app.logger.warning(f"Thumbnail not found at: {thumbnail_url} (Status: {response.status_code})")
        except requests.exceptions.RequestException as e:
            app.logger.warning(f"Failed to fetch thumbnail from {thumbnail_url}: {e}")
            continue
    
    if not response or response.status_code != 200:
        app.logger.error(f"All thumbnail URLs failed for video ID: {video_id}")
        return "Thumbnail not found", 404
    
    try:

        # Create an in-memory byte stream for the image data
        img_io = BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            img_io.write(chunk)
        img_io.seek(0)

        # Open the image using PIL
        img = Image.open(img_io).convert("RGB")  # Ensure RGB for consistency
        
        # Create filename based on whether it's a Short or regular video
        download_name = f"{video_id}_shorts_thumbnail.jpg" if is_shorts else f"{video_id}_thumbnail.jpg"
        
        original_width, original_height = img.size

        if is_shorts:
            # SHORTS PROCESSING: 9:16 vertical aspect ratio
            target_aspect_ratio = 9/16  # Vertical aspect ratio for Shorts (height/width)
            
            # Calculate dimensions for cropping to a 9:16 aspect ratio
            target_height = 1920  # Aim for a common vertical video resolution
            target_width = int(target_height * target_aspect_ratio)
            
            # Calculate the aspect ratios
            current_aspect_ratio = original_width / original_height
            
            if current_aspect_ratio > target_aspect_ratio:  # Original is wider than 9:16, need to crop width
                # Calculate the width needed to match target aspect ratio if height is kept
                new_width = int(original_height * target_aspect_ratio)
                left = (original_width - new_width) // 2
                top = 0
                right = left + new_width
                bottom = original_height
            else:  # Original is taller or same aspect ratio as 9:16, need to crop height (less common)
                # Calculate the height needed to match target aspect ratio if width is kept
                new_height = int(original_width / target_aspect_ratio)
                left = 0
                top = (original_height - new_height) // 2
                right = original_width
                bottom = top + new_height
                
            # Crop the image
            cropped_img = img.crop((left, top, right, bottom))
            
            # Resize the cropped image to the target resolution
            final_img = cropped_img.resize((target_width, target_height), Image.LANCZOS)
        else:
            # REGULAR VIDEO PROCESSING: Keep 16:9 aspect ratio
            # We will simply resize while maintaining the original aspect ratio
            # Most YouTube thumbnails are already 16:9, so usually no need to crop
            target_width = 1280  # Common width for 720p
            target_height = 720  # Height for 720p (16:9 aspect ratio)
            
            # Resize while maintaining aspect ratio
            img.thumbnail((target_width, target_height), Image.LANCZOS)
            final_img = img

        # Save the processed image to a BytesIO object
        output = BytesIO()
        final_img.save(output, format="JPEG", quality=90)  # Save as JPEG with good quality
        output.seek(0)

        return send_file(output, mimetype='image/jpeg', as_attachment=True, download_name=download_name)
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Failed to download thumbnail for {video_id}: {e}")
        return "Thumbnail not found", 404

@app.route('/download_channel_logo/<channel_id>')
def download_channel_logo(channel_id):
    try:
        youtube_service = get_youtube_service()
        channel_response = youtube_service.channels().list(
            part='snippet',
            id=channel_id
        ).execute()

        if not channel_response.get('items'):
            return "Channel not found", 404

        # Prioritize high quality, then medium, then default
        logo_url = (
            channel_response['items'][0]['snippet'].get('thumbnails', {}).get('high', {}).get('url') or
            channel_response['items'][0]['snippet'].get('thumbnails', {}).get('medium', {}).get('url') or
            channel_response['items'][0]['snippet'].get('thumbnails', {}).get('default', {}).get('url')
        )

        if not logo_url:
            return "Channel logo URL not found", 404
        
        response = requests.get(logo_url, stream=True)
        response.raise_for_status()

        # Load the image using PIL
        img_io = BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            img_io.write(chunk)
        img_io.seek(0)
        
        # Open the image and convert to RGBA (to support transparency)
        img = Image.open(img_io).convert("RGBA")
        
        # Create a circular mask
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        
        # Draw a white circle on the mask
        width, height = img.size
        center_x, center_y = width // 2, height // 2
        radius = min(center_x, center_y)
        draw.ellipse((center_x - radius, center_y - radius, 
                     center_x + radius, center_y + radius), fill=255)
        
        # Apply the mask to the image
        img.putalpha(mask)
        
        # Create a new image with a transparent background
        circular_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
        circular_img.paste(img, (0, 0), img)
        
        # Save the circular image to a BytesIO object
        output = BytesIO()
        circular_img.save(output, format="PNG")
        output.seek(0)

        # Return the circular logo as PNG (to preserve transparency)
        return send_file(output, mimetype='image/png', as_attachment=True, download_name=f"{channel_id}_circular_logo.png")
    except Exception as e:
        app.logger.error(f"Failed to download channel logo for {channel_id}: {e}")
        return "Logo not found", 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)