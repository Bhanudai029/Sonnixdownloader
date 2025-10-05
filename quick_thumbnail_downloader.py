#!/usr/bin/env python3
"""
Quick Thumbnail Downloader
Instantly download thumbnails from YouTube URLs
"""

import os
import re
import requests
from pathlib import Path
from dotenv import load_dotenv
import concurrent.futures
import threading

# Load environment variables
load_dotenv()

class QuickThumbnailDownloader:
    def __init__(self, thumbnail_folder):
        self.thumbnail_folder = Path(thumbnail_folder)
        self.thumbnail_folder.mkdir(parents=True, exist_ok=True)
        self.success_count = 0
        self.failed_count = 0
        self.lock = threading.Lock()
    
    def clean_filename(self, filename):
        """Remove special characters from filename"""
        cleaned = re.sub(r'[^a-zA-Z0-9\s._-]', '', filename)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    def extract_video_id(self, url):
        """Extract video ID from YouTube URL"""
        video_id_pattern = r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
        match = re.search(video_id_pattern, url)
        return match.group(1) if match else None
    
    def get_video_title_api(self, video_id):
        """Get video title using YouTube API"""
        api_key = os.getenv('YOUTUBE_API_KEY')
        if not api_key:
            return f"video_{video_id}"
            
        try:
            api_url = f'https://www.googleapis.com/youtube/v3/videos'
            params = {
                'id': video_id,
                'key': api_key,
                'part': 'snippet',
                'fields': 'items(snippet(title))'
            }
            
            response = requests.get(api_url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('items'):
                    title = data['items'][0]['snippet']['title']
                    return self.clean_filename(title)
            return f"video_{video_id}"
        except:
            return f"video_{video_id}"
    
    def download_thumbnail(self, url, index):
        """Download thumbnail for a single video"""
        try:
            print(f"🖼️  [{index}] Processing: {url}")
            
            # Extract video ID
            video_id = self.extract_video_id(url)
            if not video_id:
                print(f"❌ [{index}] Invalid URL")
                with self.lock:
                    self.failed_count += 1
                return
            
            # Get title
            video_title = self.get_video_title_api(video_id)
            print(f"   🏷️  Title: {video_title[:50]}..." if len(video_title) > 50 else f"   🏷️  Title: {video_title}")
            
            # Try different thumbnail qualities
            thumbnail_urls = [
                f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
                f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg", 
                f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
                f"https://i.ytimg.com/vi/{video_id}/default.jpg"
            ]
            
            for quality, thumb_url in zip(['maxres', 'hq', 'mq', 'default'], thumbnail_urls):
                try:
                    response = requests.get(thumb_url, timeout=10)
                    if response.status_code == 200 and len(response.content) > 1000:
                        # Save as PNG with clean filename
                        filename = f"{video_title}.png"
                        filepath = self.thumbnail_folder / filename
                        
                        # Avoid duplicates
                        counter = 1
                        while filepath.exists():
                            filename = f"{video_title}_{counter}.png"
                            filepath = self.thumbnail_folder / filename
                            counter += 1
                        
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        
                        print(f"   ✅ [{index}] Saved: {filename} ({quality} quality)")
                        with self.lock:
                            self.success_count += 1
                        return
                except:
                    continue
                    
            print(f"   ❌ [{index}] All thumbnail URLs failed")
            with self.lock:
                self.failed_count += 1
            
        except Exception as e:
            print(f"   💥 [{index}] Error: {str(e)[:50]}...")
            with self.lock:
                self.failed_count += 1
    
    def download_multiple(self, urls):
        """Download thumbnails for multiple URLs in parallel"""
        print(f"🚀 Starting thumbnail download for {len(urls)} videos...")
        print(f"📁 Thumbnail folder: {self.thumbnail_folder}")
        print("=" * 60)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i, url in enumerate(urls, 1):
                future = executor.submit(self.download_thumbnail, url, i)
                futures.append(future)
            
            # Wait for all downloads to complete
            concurrent.futures.wait(futures)
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 THUMBNAIL DOWNLOAD SUMMARY")
        print("=" * 60)
        print(f"✅ Successful: {self.success_count}/{len(urls)}")
        print(f"❌ Failed: {self.failed_count}")
        print(f"📁 Saved to: {self.thumbnail_folder}")
        
        return self.success_count, self.failed_count

def main():
    """Main function"""
    # Your URLs
    urls = [
        "https://youtu.be/HJLb9XrEwKQ?si=naxnnAotUvCfeSds",
        "https://youtu.be/SozKiKhQP6Q?si=5JNVbpUXDVMGA530"
    ]
    
    # Thumbnail folder
    thumbnail_folder = os.path.join(os.path.expanduser("~"), "Downloads")
    
    print("🖼️" + "=" * 60)
    print("    QUICK THUMBNAIL DOWNLOADER")
    print("=" * 60 + "🖼️")
    print()
    
    downloader = QuickThumbnailDownloader(thumbnail_folder)
    success, failed = downloader.download_multiple(urls)
    
    if success > 0:
        print(f"\n🎉 {success} thumbnails downloaded successfully!")
        print(f"📁 Check folder: {thumbnail_folder}")

if __name__ == "__main__":
    main()