import os
import sys
import logging
import requests
import yt_dlp
from bs4 import BeautifulSoup
import re
import tempfile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('proxy_download')

# VPNBook URLs and configuration
VPNBOOK_URL = "https://www.vpnbook.com/freevpn"
VPNBOOK_USERNAME = "vpnbook"

def get_vpnbook_password():
    """Fetch the current VPNBook password from their website"""
    try:
        logger.info("Fetching current VPNBook password...")
        response = requests.get(VPNBOOK_URL, timeout=10)
        if response.status_code != 200:
            logger.error(f"Failed to fetch VPNBook password, status code: {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the password - it's usually in a specific format 
        # near text that says "Password:" on their website
        password_elements = soup.find_all('strong')
        for element in password_elements:
            text = element.text.strip()
            # VPNBook passwords are typically alphanumeric and 8+ characters
            if re.match(r'^[a-zA-Z0-9]{5,}$', text):
                logger.info(f"Found VPNBook password: {text}")
                return text
        
        logger.error("Could not find password on VPNBook website")
        return None
            
    except Exception as e:
        logger.error(f"Error fetching VPNBook password: {str(e)}")
        return None

def create_cookie_file(cookies_content, prefix="ytdl"):
    """Create a temporary cookie file from cookie content"""
    if not cookies_content or not cookies_content.strip():
        return None
    
    try:
        # Format the cookie file properly
        if not cookies_content.startswith("# Netscape HTTP Cookie File"):
            cookies_content = "# Netscape HTTP Cookie File\n" + cookies_content
            
        # Create a temporary file
        cookie_file = tempfile.NamedTemporaryFile(
            prefix=f"{prefix}_cookies_",
            suffix=".txt",
            delete=False
        )
        
        with open(cookie_file.name, 'w', encoding='utf-8') as f:
            f.write(cookies_content)
        
        logger.info(f"Created cookie file: {cookie_file.name}")
        return cookie_file.name
    except Exception as e:
        logger.error(f"Error creating cookie file: {str(e)}")
        return None

def download_youtube_video(video_url, output_dir=".", quality="best", cookies_content=None, user_agent=None, use_vpnbook=True):
    """
    Download a YouTube video using yt-dlp with various fallback methods.
    
    Args:
        video_url (str): URL of the YouTube video to download
        output_dir (str): Directory to save the downloaded video
        quality (str): Video quality to download ("best", "1080p", "720p", "mp3", etc.)
        cookies_content (str): Cookie content in Netscape format (optional)
        user_agent (str): User agent string (optional)
        use_vpnbook (bool): Whether to use VPNBook proxy
        
    Returns:
        dict: Result information including success status and file path or error message
    """
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Create cookie file if provided
        cookies_file = None
        if cookies_content:
            cookies_file = create_cookie_file(cookies_content)
        
        # Set default User-Agent if not provided
        if not user_agent:
            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        
        # Setup yt-dlp options
        ydl_opts = {
            'format': get_format_string(quality),
            'quiet': False,
            'verbose': True,
            'no_warnings': False,
            'nocheckcertificate': True,
            'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
            'user_agent': user_agent,
            'http_headers': {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate'
            }
        }
        
        # Add cookies file if it exists
        if cookies_file:
            ydl_opts['cookiefile'] = cookies_file
            
        # Configure audio download if mp3 requested
        if quality == 'mp3':
            ydl_opts.update({
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
            
        # Try Direct Download (no proxy)
        logger.info(f"Attempting direct download for {video_url}")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                filename = ydl.prepare_filename(info)
                logger.info(f"Download successful: {filename}")
                clean_up_cookie_file(cookies_file)
                return {
                    "success": True,
                    "file_path": filename,
                    "title": info.get('title'),
                    "method": "direct"
                }
        except yt_dlp.utils.DownloadError as e:
            logger.warning(f"Direct download failed: {str(e)}")
            
            # If direct download fails and VPNBook is enabled, try with VPNBook proxies
            if use_vpnbook:
                return try_vpnbook_proxies(video_url, ydl_opts, cookies_file)
            else:
                clean_up_cookie_file(cookies_file)
                return {"success": False, "error": f"Download failed: {str(e)}"}
                
    except Exception as e:
        logger.error(f"Unexpected error in download: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

def try_vpnbook_proxies(video_url, ydl_opts, cookies_file=None):
    """Try downloading using VPNBook proxies"""
    password = get_vpnbook_password()
    if not password:
        logger.error("Failed to get VPNBook password")
        clean_up_cookie_file(cookies_file)
        return {"success": False, "error": "Failed to get VPNBook password"}
    
    # VPNBook proxy servers (try different ones if one fails)
    proxy_servers = [
        "US16.vpnbook.com:80", 
        "US178.vpnbook.com:80",
        "CA149.vpnbook.com:80",
        "DE20.vpnbook.com:80",
        "FR200.vpnbook.com:80",
        "UK205.vpnbook.com:80"
    ]
    
    for proxy_server in proxy_servers:
        proxy_url = f"http://{VPNBOOK_USERNAME}:{password}@{proxy_server}"
        logger.info(f"Trying VPNBook proxy: {proxy_server}")
        
        # Update options with proxy
        proxy_opts = ydl_opts.copy()
        proxy_opts['proxy'] = proxy_url
        
        try:
            with yt_dlp.YoutubeDL(proxy_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                filename = ydl.prepare_filename(info)
                logger.info(f"Download successful with proxy {proxy_server}: {filename}")
                clean_up_cookie_file(cookies_file)
                return {
                    "success": True,
                    "file_path": filename,
                    "title": info.get('title'),
                    "method": f"vpnbook_proxy_{proxy_server}"
                }
        except yt_dlp.utils.DownloadError as e:
            logger.warning(f"Failed with proxy {proxy_server}: {str(e)}")
            # Continue to next proxy
    
    # If all proxies fail
    clean_up_cookie_file(cookies_file)
    return {"success": False, "error": "All VPNBook proxies failed"}

def get_format_string(quality):
    """Convert quality option to yt-dlp format string"""
    if quality == 'mp3':
        return 'bestaudio/best'
    elif quality == '2K' or quality == '1440p':
        return 'bestvideo[height<=?1440]+bestaudio/best[height<=?1440]/best'
    elif quality == '4K' or quality == '2160p':
        return 'bestvideo[height<=?2160]+bestaudio/best[height<=?2160]/best'
    elif quality == '1080p':
        return 'bestvideo[height<=?1080]+bestaudio/best[height<=?1080]/best'
    elif quality == '720p':
        return 'bestvideo[height<=?720]+bestaudio/best[height<=?720]/best'
    elif quality == '480p':
        return 'bestvideo[height<=?480]+bestaudio/best[height<=?480]/best'
    elif quality == 'best':
        return 'bestvideo+bestaudio/best'
    elif 'p' in quality:
        height = quality.replace('p', '')
        if height.isdigit():
            return f'bestvideo[height<=?{height}]+bestaudio/best[height<=?{height}]/best'
    
    # Default to 1080p if quality format is not recognized
    return 'bestvideo[height<=?1080]+bestaudio/best[height<=?1080]/best'

def clean_up_cookie_file(cookie_file):
    """Delete temporary cookie file if it exists"""
    if cookie_file and os.path.exists(cookie_file):
        try:
            os.remove(cookie_file)
            logger.info(f"Cleaned up cookie file: {cookie_file}")
        except Exception as e:
            logger.error(f"Failed to clean up cookie file: {str(e)}")

if __name__ == "__main__":
    # Example usage as a command-line tool
    if len(sys.argv) < 2:
        print("Usage: python proxy_download.py <youtube_url> [quality] [cookies_file]")
        sys.exit(1)
        
    video_url = sys.argv[1]
    quality = sys.argv[2] if len(sys.argv) > 2 else "best"
    cookies_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    cookies_content = None
    if cookies_path and os.path.exists(cookies_path):
        with open(cookies_path, 'r', encoding='utf-8') as f:
            cookies_content = f.read()
    
    result = download_youtube_video(video_url, quality=quality, cookies_content=cookies_content)
    
    if result["success"]:
        print(f"Download successful: {result['file_path']}")
        sys.exit(0)
    else:
        print(f"Download failed: {result['error']}")
        sys.exit(1) 