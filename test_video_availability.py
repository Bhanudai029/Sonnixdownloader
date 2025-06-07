#!/usr/bin/env python3
import sys
import yt_dlp
import argparse

def check_video_availability(url, cookies_file=None, use_netrc=False, user_agent=None):
    """
    Check if a YouTube video is available using yt-dlp.
    
    Args:
        url: YouTube video URL
        cookies_file: Path to cookies file (optional)
        use_netrc: Whether to use .netrc file for authentication
        user_agent: Custom User-Agent string
    
    Returns:
        tuple: (is_available, error_message, error_type)
    """
    print(f"Testing URL: {url}")
    
    # Set up yt-dlp options
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
        'ignoreerrors': False,  # Don't ignore errors to get proper error messages
        'logtostderr': False,
        'retries': 1,           # Only try once
        'socket_timeout': 15    # 15 seconds timeout
    }
    
    if cookies_file:
        print(f"Using cookies from: {cookies_file}")
        ydl_opts['cookiefile'] = cookies_file
    
    if use_netrc:
        print("Using .netrc for authentication")
        ydl_opts['usenetrc'] = True
    
    if user_agent:
        print(f"Using custom User-Agent: {user_agent}")
        ydl_opts['user_agent'] = user_agent
        ydl_opts['http_headers'] = {'User-Agent': user_agent}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
        if info_dict:
            print("\n===== VIDEO IS AVAILABLE =====")
            print(f"Title: {info_dict.get('title', 'Unknown')}")
            print(f"Channel: {info_dict.get('channel', 'Unknown')}")
            print(f"Duration: {info_dict.get('duration', 0)} seconds")
            print(f"View count: {info_dict.get('view_count', 'Unknown')}")
            formats_count = len(info_dict.get('formats', []))
            print(f"Available formats: {formats_count}")
            return True, None, None
    
    except yt_dlp.utils.DownloadError as e:
        error_message = str(e)
        error_type = "UNKNOWN"
        
        print("\n===== VIDEO IS UNAVAILABLE =====")
        print(f"Error: {error_message}")
        
        # Determine error type
        error_lower = error_message.lower()
        if "video unavailable" in error_lower or "content isn't available" in error_lower:
            error_type = "UNAVAILABLE"
            print("Type: Video is unavailable (deleted, private, etc.)")
        elif "age" in error_lower or "confirm your age" in error_lower:
            error_type = "AGE_RESTRICTED"
            print("Type: Age restricted content")
        elif "geo" in error_lower or "not available in your country" in error_lower:
            error_type = "GEO_RESTRICTED"
            print("Type: Geo-restricted content")
        elif "429" in error_lower or "too many requests" in error_lower:
            error_type = "RATE_LIMITED"
            print("Type: YouTube is rate limiting requests (HTTP 429)")
        else:
            print("Type: Other error")
        
        return False, error_message, error_type
    
    except Exception as e:
        print(f"\n===== GENERAL ERROR =====\nError: {str(e)}")
        return False, str(e), "GENERAL_ERROR"

def main():
    parser = argparse.ArgumentParser(description="Test YouTube video availability with yt-dlp")
    parser.add_argument("url", help="YouTube video URL to check")
    parser.add_argument("--cookies", "-c", help="Path to cookies file in Netscape format")
    parser.add_argument("--netrc", "-n", action="store_true", help="Use .netrc file for authentication")
    parser.add_argument("--user-agent", "-u", help="Custom User-Agent string")
    
    args = parser.parse_args()
    
    if not args.url:
        print("Please provide a YouTube URL")
        sys.exit(1)
    
    is_available, error_message, error_type = check_video_availability(
        args.url,
        cookies_file=args.cookies,
        use_netrc=args.netrc,
        user_agent=args.user_agent
    )
    
    # Exit with status code 0 if available, 1 if unavailable
    sys.exit(0 if is_available else 1)

if __name__ == "__main__":
    main() 