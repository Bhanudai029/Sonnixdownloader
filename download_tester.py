import os
import sys
import time
import logging
import argparse
from proxy_download import download_youtube_video

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('download_tester')

def read_cookies_file(path):
    """Read cookies from a file"""
    if not os.path.exists(path):
        logger.error(f"Cookie file not found: {path}")
        return None
        
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading cookie file: {e}")
        return None

def download_demo():
    """Run a demo with hardcoded values for testing"""
    video_url = "https://youtu.be/zgGTVaG2UiQ?si=XbtuCeSWQLAkHPo_"  # Squid Game Season 3 trailer
    output_dir = "downloads"
    cookies_path = "my_cookies.txt"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Read cookies if file exists
    cookies_content = read_cookies_file(cookies_path) if os.path.exists(cookies_path) else None
    
    # Download with cookies but no proxy first
    logger.info("=== Testing Direct Download with Cookies ===")
    result1 = download_youtube_video(
        video_url=video_url, 
        output_dir=output_dir,
        quality="best", 
        cookies_content=cookies_content,
        use_vpnbook=False
    )
    
    if result1["success"]:
        logger.info(f"Direct download successful: {result1['file_path']}")
    else:
        logger.error(f"Direct download failed: {result1['error']}")
    
    # Wait a moment before trying VPNBook method
    time.sleep(2)
    
    # Now try with VPNBook proxies
    logger.info("\n=== Testing VPNBook Proxy Download ===")
    result2 = download_youtube_video(
        video_url=video_url, 
        output_dir=output_dir,
        quality="best", 
        cookies_content=cookies_content,
        use_vpnbook=True
    )
    
    if result2["success"]:
        logger.info(f"VPNBook download successful: {result2['file_path']}")
    else:
        logger.error(f"VPNBook download failed: {result2['error']}")
    
    # Summary
    logger.info("\n=== Download Test Summary ===")
    logger.info(f"Direct download: {'✓ SUCCESS' if result1['success'] else '✗ FAILED'}")
    logger.info(f"VPNBook download: {'✓ SUCCESS' if result2['success'] else '✗ FAILED'}")

def main():
    parser = argparse.ArgumentParser(description="YouTube Download Tester")
    parser.add_argument("--url", help="YouTube video URL to download")
    parser.add_argument("--quality", default="best", help="Video quality (best, 1080p, 720p, mp3, etc.)")
    parser.add_argument("--cookies", help="Path to cookies file")
    parser.add_argument("--output", default="downloads", help="Output directory")
    parser.add_argument("--demo", action="store_true", help="Run with demo values")
    
    args = parser.parse_args()
    
    if args.demo:
        download_demo()
        return
        
    if not args.url:
        logger.error("No URL provided. Use --url or --demo")
        parser.print_help()
        return
        
    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)
    
    # Read cookies if file provided
    cookies_content = read_cookies_file(args.cookies) if args.cookies else None
    
    # Download with both methods
    logger.info("=== Testing Direct Download ===")
    result1 = download_youtube_video(
        video_url=args.url, 
        output_dir=args.output,
        quality=args.quality, 
        cookies_content=cookies_content,
        use_vpnbook=False
    )
    
    if result1["success"]:
        logger.info(f"Direct download successful: {result1['file_path']}")
    else:
        logger.error(f"Direct download failed: {result1['error']}")
        
        # If direct download fails, try with VPNBook
        logger.info("\n=== Testing VPNBook Proxy Download ===")
        result2 = download_youtube_video(
            video_url=args.url, 
            output_dir=args.output,
            quality=args.quality, 
            cookies_content=cookies_content,
            use_vpnbook=True
        )
        
        if result2["success"]:
            logger.info(f"VPNBook download successful: {result2['file_path']}")
        else:
            logger.error(f"VPNBook download failed: {result2['error']}")

if __name__ == "__main__":
    main() 