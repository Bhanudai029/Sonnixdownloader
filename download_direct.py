import os
import sys
import yt_dlp
import requests
import re
import logging
import tempfile
from bs4 import BeautifulSoup
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('download_direct')

# VPNBook configuration
VPNBOOK_URL = "https://www.vpnbook.com/freevpn"
VPNBOOK_USERNAME = "vpnbook"

# Use a known working public video (YouTube Rewind 2019 - guaranteed to be public worldwide)
# Modify this to test different videos
VIDEO_URL_TO_TRY = "https://youtu.be/zgGTVaG2UiQ?si=XbtuCeSWQLAkHPo_"
BACKUP_VIDEO_URL = "https://www.youtube.com/watch?v=YE7VzlLtp-4" # YouTube Rewind 2019 - guaranteed to be public worldwide

def get_current_vpnbook_password():
    """Fetch the current VPNBook password from their website"""
    try:
        logger.info("Fetching current VPNBook password...")
        response = requests.get(VPNBOOK_URL, timeout=10)
        if response.status_code != 200:
            logger.error(f"Failed to fetch VPNBook password: HTTP {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        password_elements = soup.find_all('strong')
        
        for element in password_elements:
            text = element.text.strip()
            if re.match(r'^[a-zA-Z0-9]{5,}$', text):
                logger.info(f"Found VPNBook password: {text}")
                return text
        
        logger.error("Could not find password on VPNBook website")
        return None
    except Exception as e:
        logger.error(f"Error fetching VPNBook password: {e}")
        return None

def main():
    # Test the original video URL first
    logger.info(f"Attempting to download video: {VIDEO_URL_TO_TRY}")
    success = try_with_direct_and_proxies(VIDEO_URL_TO_TRY)
    
    # If the original failed, try the backup guaranteed public video
    if not success:
        logger.info(f"Original video failed. Trying backup guaranteed public video: {BACKUP_VIDEO_URL}")
        try_with_direct_and_proxies(BACKUP_VIDEO_URL)
        
def try_with_direct_and_proxies(video_url):
    """Try downloading with direct connection first, then with proxies"""
    try:
        # Try direct download first (no proxy)
        try:
            logger.info("Fetching video info...")
            ydl_opts = {
                'format': 'best',
                'quiet': False,
                'verbose': True,
                'no_warnings': False,
                'nocheckcertificate': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'cookiefile': 'my_cookies.txt',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                logger.info(f"Found video: {info.get('title')}")
                
            # Now do the download
            logger.info("Starting download...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            logger.info("Download completed successfully!")
            return True
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"Direct download failed: {str(e)}")
            
            # Try with VPNBook proxies
            return try_vpnbook_proxies(video_url)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

def try_vpnbook_proxies(video_url):
    """Try downloading with different VPNBook proxies"""
    password = get_current_vpnbook_password()
    if not password:
        logger.error("Failed to get VPNBook password")
        return False
    
    # VPNBook proxy servers to try
    proxy_servers = [
        "US16.vpnbook.com:80",
        "US178.vpnbook.com:80",
        "CA149.vpnbook.com:80", 
        "DE20.vpnbook.com:80",
        "FR200.vpnbook.com:80",
        "UK205.vpnbook.com:80"
    ]
    
    for server in proxy_servers:
        try:
            logger.info(f"Trying proxy: {server}")
            proxy_url = f"http://{VPNBOOK_USERNAME}:{password}@{server}"
            
            ydl_opts = {
                'format': 'best',
                'proxy': proxy_url,
                'quiet': False,
                'verbose': True,
                'no_warnings': False,
                'nocheckcertificate': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'cookies': 'my_cookies.txt',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Sec-Fetch-Mode': 'navigate'
                }
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            logger.info(f"Download successful with proxy {server}")
            return True
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"Failed with proxy {server}: {e}")
    
    logger.error("All proxies failed.")
    return False

if __name__ == "__main__":
    main() 