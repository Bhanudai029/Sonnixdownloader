import yt_dlp
import os
import sys
import logging
import argparse
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_cookies')

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

def test_with_cookie_file(video_url, cookie_file=None):
    """Test downloading video info using cookie file"""
    logger.info(f"Testing with cookie file: {cookie_file}")

    ydl_opts = {
        'quiet': False,
        'no_warnings': False,
        'skip_download': True,
        'forcejson': True,
        'nocheckcertificate': True,
    }
    
    if cookie_file and os.path.exists(cookie_file):
        ydl_opts['cookiefile'] = cookie_file
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            logger.info(f"SUCCESS with cookie file! Video title: {info.get('title')}")
            return True
    except Exception as e:
        logger.error(f"FAILED with cookie file: {str(e)}")
        return False
        
def test_with_browser_cookies(video_url, browser_name="chrome"):
    """Test downloading video info using browser cookies"""
    logger.info(f"Testing with {browser_name} browser cookies")

    ydl_opts = {
        'quiet': False,
        'no_warnings': False,
        'skip_download': True,
        'forcejson': True,
        'nocheckcertificate': True,
        'cookiesfrombrowser': (browser_name, )
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            logger.info(f"SUCCESS with {browser_name} cookies! Video title: {info.get('title')}")
            return True
    except Exception as e:
        logger.error(f"FAILED with {browser_name} cookies: {str(e)}")
        return False

def test_robust_options(video_url, cookie_file=None, user_agent=None):
    """Test with robust options that should work better for problematic videos"""
    logger.info(f"Testing with robust options")
    
    browser_name = detect_browser_from_user_agent(user_agent) if user_agent else "chrome"
    
    ydl_opts = {
        'quiet': False,
        'no_warnings': False,
        'skip_download': True,
        'forcejson': True,
        'nocheckcertificate': True,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'extractor_retries': 5,
        'ignoreerrors': True,
    }
    
    # Add user agent if provided
    if user_agent:
        ydl_opts['user_agent'] = user_agent
        ydl_opts['http_headers'] = {'User-Agent': user_agent}
    
    # Try cookiesfrombrowser first if we can detect the browser
    try:
        logger.info(f"First attempt using cookiesfrombrowser with {browser_name}")
        try_opts = ydl_opts.copy()
        try_opts['cookiesfrombrowser'] = (browser_name, )
        
        with yt_dlp.YoutubeDL(try_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            logger.info(f"SUCCESS using cookiesfrombrowser! Video title: {info.get('title')}")
            return True
    except Exception as e_browser:
        logger.warning(f"cookiesfrombrowser with {browser_name} failed: {str(e_browser)}")
        
        # Fall back to cookie file if provided
        if cookie_file and os.path.exists(cookie_file):
            logger.info("Falling back to cookie file")
            try_opts = ydl_opts.copy()
            try_opts['cookiefile'] = cookie_file
            
            try:
                with yt_dlp.YoutubeDL(try_opts) as ydl:
                    info = ydl.extract_info(video_url, download=False)
                    logger.info(f"SUCCESS using cookie file! Video title: {info.get('title')}")
                    return True
            except Exception as e_file:
                logger.error(f"Cookie file method also failed: {str(e_file)}")
        
        # Try without any cookies as last resort
        logger.info("Trying with no cookies")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                logger.info(f"SUCCESS with no cookies! Video title: {info.get('title')}")
                return True
        except Exception as e_nocookie:
            logger.error(f"All attempts failed. Last error: {str(e_nocookie)}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Test yt-dlp with different cookie methods')
    parser.add_argument('--url', default='https://www.youtube.com/watch?v=dQw4w9WgXcQ', help='YouTube URL to test')
    parser.add_argument('--cookie-file', help='Path to cookie file in Netscape format')
    parser.add_argument('--browser', default='chrome', choices=['chrome', 'firefox', 'edge', 'safari', 'opera'], help='Browser to get cookies from')
    parser.add_argument('--user-agent', help='User agent string to use')
    parser.add_argument('--test-all', action='store_true', help='Run all tests')
    args = parser.parse_args()
    
    logger.info(f"Testing yt-dlp with URL: {args.url}")
    logger.info(f"yt-dlp version: {yt_dlp.version.__version__}")
    
    success = False
    
    if args.test_all:
        # Test all methods in sequence
        logger.info("TESTING ALL METHODS")
        logger.info("-" * 50)
        
        # 1. Test with cookie file
        if args.cookie_file:
            success = test_with_cookie_file(args.url, args.cookie_file)
            logger.info(f"Cookie file test result: {'SUCCESS' if success else 'FAILED'}")
        else:
            logger.warning("Skipping cookie file test (no file provided)")
            
        # 2. Test with browser cookies
        browser_success = test_with_browser_cookies(args.url, args.browser)
        logger.info(f"Browser cookies test result: {'SUCCESS' if browser_success else 'FAILED'}")
        success = success or browser_success
        
        # 3. Test with robust options
        robust_success = test_robust_options(args.url, args.cookie_file, args.user_agent)
        logger.info(f"Robust options test result: {'SUCCESS' if robust_success else 'FAILED'}")
        success = success or robust_success
        
    else:
        # Just run the robust test which tries multiple methods
        success = test_robust_options(args.url, args.cookie_file, args.user_agent)
    
    if success:
        logger.info("At least one test method was successful!")
        sys.exit(0)
    else:
        logger.error("All test methods failed.")
        sys.exit(1)

if __name__ == "__main__":
    main() 