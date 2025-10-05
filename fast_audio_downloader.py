#!/usr/bin/env python3
"""
Fast Terminal YouTube Audio Downloader
Quickly download MP3 audio from multiple YouTube URLs
"""

import os
import sys
import subprocess
import time
from pathlib import Path
import concurrent.futures
import threading
import re
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class FastYTAudioDownloader:
    def __init__(self, output_folder, thumbnail_folder=None):
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
        # Thumbnail folder setup
        if thumbnail_folder:
            self.thumbnail_folder = Path(thumbnail_folder)
            self.thumbnail_folder.mkdir(parents=True, exist_ok=True)
        else:
            self.thumbnail_folder = None
            
        self.download_count = 0
        self.success_count = 0
        self.failed_urls = []
        self.lock = threading.Lock()
        
        # Enhanced yt-dlp options for fast audio downloads
        self.yt_dlp_options = [
            sys.executable, '-m', 'yt_dlp',
            '--extract-audio',
            '--audio-format', 'mp3',
            '--audio-quality', '192K',
            '--no-playlist',
            '--no-warnings',
            '--ignore-errors',
            '--no-check-certificate',
            '--prefer-insecure',
            '--concurrent-fragments', '4',  # Faster fragment downloads
            '--throttled-rate', '100K',      # Minimum download rate
            # Enhanced YouTube extractor arguments for speed
            '--extractor-args', 'youtube:player_client=android;player_skip=webpage;include_hls_manifest=false',
            '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36',
            # Simple output template
            '-o', str(self.output_folder / '%(title)s.%(ext)s')
        ]
    
    def clean_filename_simple(self, filename):
        """Remove special characters from filename"""
        import re
        # Remove special characters, keep only letters, numbers, spaces, dots, hyphens, underscores
        cleaned = re.sub(r'[^a-zA-Z0-9\s._-]', '', filename)
        # Replace multiple spaces with single space
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    def extract_video_id(self, url):
        """Extract video ID from YouTube URL"""
        video_id_pattern = r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
        match = re.search(video_id_pattern, url)
        return match.group(1) if match else None
    
    def get_video_title_api(self, video_id):
        """Get video title using YouTube API (fastest method)"""
        api_key = os.getenv('YOUTUBE_API_KEY')
        if not api_key:
            return None
            
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
                    return self.clean_filename_simple(title)
            return None
        except Exception as e:
            print(f"   ⚠️ API title extraction failed: {str(e)[:30]}...")
            return None
    
    def download_thumbnail_permanent(self, url, video_title, video_id):
        """Download thumbnail permanently as PNG"""
        if not self.thumbnail_folder:
            return False
            
        try:
            clean_title = self.clean_filename_simple(video_title) if video_title != "Unknown" else f"video_{video_id}"
            if not clean_title:
                clean_title = f"video_{video_id}"
                
            # Try different thumbnail qualities
            thumbnail_urls = [
                f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
                f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg", 
                f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
                f"https://i.ytimg.com/vi/{video_id}/default.jpg"
            ]
            
            for thumb_url in thumbnail_urls:
                try:
                    response = requests.get(thumb_url, timeout=10)
                    if response.status_code == 200 and len(response.content) > 1000:
                        # Save as PNG with clean filename
                        filename = f"{clean_title}.png"
                        filepath = self.thumbnail_folder / filename
                        
                        # Avoid duplicates
                        counter = 1
                        while filepath.exists():
                            filename = f"{clean_title}_{counter}.png"
                            filepath = self.thumbnail_folder / filename
                            counter += 1
                        
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        
                        print(f"   🖼️  Thumbnail saved: {filename}")
                        return True
                except:
                    continue
                    
            print(f"   ⚠️ All thumbnail URLs failed")
            return False
            
        except Exception as e:
            print(f"   ⚠️ Thumbnail download error: {str(e)[:30]}...")
            return False
    
    def download_thumbnail_fast(self, url, video_title):
        """Fast background thumbnail download"""
        def _download_thumb():
            try:
                clean_title = self.clean_filename_simple(video_title)
                if not clean_title:
                    clean_title = "thumbnail"
                
                # Faster thumbnail command
                thumbnail_cmd = [
                    sys.executable, '-m', 'yt_dlp',
                    '--write-thumbnail',
                    '--skip-download',
                    '--no-warnings',
                    '--ignore-errors',
                    '--extractor-args', 'youtube:player_client=android',  # Faster client
                    '-o', str(self.thumbnail_folder / f'{clean_title}.%(ext)s'),
                    url
                ]
                
                result = subprocess.run(
                    thumbnail_cmd,
                    capture_output=True,
                    text=True,
                    timeout=15  # Reduced timeout for speed
                )
                
                if result.returncode == 0:
                    thumbnail_files = list(self.thumbnail_folder.glob(f'{clean_title}.*'))
                    if thumbnail_files:
                        print(f"   🖼️  Thumbnail saved: {thumbnail_files[0].name}")
                        return
                print(f"   ⚠️ Thumbnail download failed")
            except:
                print(f"   ⚠️ Thumbnail timeout/error")
        
        # Run thumbnail download in background thread
        import threading
        thumb_thread = threading.Thread(target=_download_thumb)
        thumb_thread.daemon = True
        thumb_thread.start()
    
    def rename_downloaded_files(self):
        """Rename any files with special characters"""
        for file_path in self.output_folder.glob('*.mp3'):
            original_name = file_path.name
            clean_name = self.clean_filename_simple(original_name)
            
            if original_name != clean_name:
                new_path = file_path.parent / clean_name
                # Avoid conflicts
                counter = 1
                while new_path.exists():
                    name_part = clean_name.rsplit('.', 1)[0]
                    ext_part = clean_name.rsplit('.', 1)[1]
                    new_path = file_path.parent / f"{name_part}_{counter}.{ext_part}"
                    counter += 1
                
                try:
                    file_path.rename(new_path)
                    print(f"🔧 Renamed: {original_name} → {new_path.name}")
                except Exception as e:
                    print(f"⚠️ Could not rename {original_name}: {e}")
        """Rename any files with special characters"""
        for file_path in self.output_folder.glob('*.mp3'):
            original_name = file_path.name
            clean_name = self.clean_filename_simple(original_name)
            
            if original_name != clean_name:
                new_path = file_path.parent / clean_name
                # Avoid conflicts
                counter = 1
                while new_path.exists():
                    name_part = clean_name.rsplit('.', 1)[0]
                    ext_part = clean_name.rsplit('.', 1)[1]
                    new_path = file_path.parent / f"{name_part}_{counter}.{ext_part}"
                    counter += 1
                
                try:
                    file_path.rename(new_path)
                    print(f"🔧 Renamed: {original_name} → {new_path.name}")
                except Exception as e:
                    print(f"⚠️ Could not rename {original_name}: {e}")
    
    def download_single_audio(self, url, index=None):
        """Download audio from a single YouTube URL and its thumbnail"""
        try:
            prefix = f"[{index}]" if index else ""
            print(f"🎵 {prefix} Starting download: {url}")
            
            # Extract video ID and get title using API (fastest method)
            video_id = self.extract_video_id(url)
            video_title = "Unknown"
            
            if video_id:
                # Fast API title extraction
                api_title = self.get_video_title_api(video_id)
                if api_title:
                    video_title = api_title
                    print(f"   🏷️  Title: {video_title[:60]}..." if len(video_title) > 60 else f"   🏷️  Title: {video_title}")
                    
                    # Download thumbnail immediately using direct URLs
                    if self.thumbnail_folder:
                        print(f"   🖼️  Downloading thumbnail...")
                        # Run in background thread for speed
                        def _download_thumb():
                            self.download_thumbnail_permanent(url, video_title, video_id)
                        
                        import threading
                        thumb_thread = threading.Thread(target=_download_thumb)
                        thumb_thread.daemon = True
                        thumb_thread.start()
            
            # Start audio download immediately
            cmd = self.yt_dlp_options + [url]
            start_time = time.time()
            
            # Run audio download
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300  # 5 minute timeout per video
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            with self.lock:
                self.download_count += 1
                
                if result.returncode == 0:
                    self.success_count += 1
                    print(f"✅ {prefix} SUCCESS! Downloaded in {duration:.1f}s")
                    
                    if "has already been downloaded" in result.stdout:
                        print(f"   📁 File already existed")
                    else:
                        print(f"   📁 Saved to: {self.output_folder}")
                else:
                    self.failed_urls.append(url)
                    print(f"❌ {prefix} FAILED: {url}")
                    if result.stderr:
                        print(f"   Error: {result.stderr.strip()[:100]}...")
                        
        except subprocess.TimeoutExpired:
            with self.lock:
                self.download_count += 1
                self.failed_urls.append(url)
            print(f"⏰ {prefix} TIMEOUT: {url} (took too long)")
            
        except Exception as e:
            with self.lock:
                self.download_count += 1
                self.failed_urls.append(url)
            print(f"💥 {prefix} ERROR: {url} - {str(e)}")
    
    def download_multiple_parallel(self, urls, max_workers=3):
        """Download multiple URLs in parallel"""
        print(f"🚀 Starting parallel download of {len(urls)} videos...")
        print(f"📁 Output folder: {self.output_folder}")
        print(f"🔧 Max parallel downloads: {max_workers}")
        print("=" * 60)
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i, url in enumerate(urls, 1):
                future = executor.submit(self.download_single_audio, url, i)
                futures.append(future)
            
            # Wait for all downloads to complete
            concurrent.futures.wait(futures)
                    
            # Clean filenames after downloads
            print("\n🔧 Cleaning filenames (removing special characters)...")
            self.rename_downloaded_files()
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 DOWNLOAD SUMMARY")
        print("=" * 60)
        print(f"✅ Successful: {self.success_count}/{len(urls)}")
        print(f"❌ Failed: {len(self.failed_urls)}")
        print(f"⏱️  Total time: {total_duration:.1f} seconds")
        print(f"📁 Output folder: {self.output_folder}")
        
        if self.failed_urls:
            print(f"\n❌ Failed URLs:")
            for url in self.failed_urls:
                print(f"   {url}")
        
        return self.success_count, len(self.failed_urls)

def main():
    """Main function for terminal-based downloader"""
    
    # Output folders
    output_folder = r"C:\Users\baral\OneDrive\Desktop\Spotifyxutsav\music-streaming-app\Audios"
    thumbnail_folder = r"C:\Users\baral\OneDrive\Desktop\Spotifyxutsav\music-streaming-app\images"
    
    print("🎵" + "=" * 60)
    print("    FAST YOUTUBE AUDIO DOWNLOADER")
    print("=" * 60 + "🎵")
    print(f"📁 Download folder: {output_folder}")
    print(f"🖼️  Thumbnail folder: {thumbnail_folder}")
    print("🔧 Using latest yt-dlp with enhanced YouTube bypass")
    print("⚡ Parallel downloads for maximum speed")
    print()
    
    # Check if yt-dlp is available
    try:
        result = subprocess.run([sys.executable, '-m', 'yt_dlp', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ yt-dlp version: {result.stdout.strip()}")
        else:
            print("❌ yt-dlp not available! Please install: pip install yt-dlp")
            return
    except Exception as e:
        print(f"❌ Error checking yt-dlp: {e}")
        return
    
    print()
    
    downloader = FastYTAudioDownloader(output_folder, thumbnail_folder)
    
    while True:
        print("📝 Enter YouTube URLs (paste up to 10 URLs, one per line)")
        print("   Press Enter twice when done, or type 'quit' to exit")
        print("   Example: https://youtu.be/dQw4w9WgXcQ")
        print("-" * 40)
        
        urls = []
        empty_count = 0
        
        while len(urls) < 10:
            try:
                url = input(f"URL {len(urls)+1}: ").strip()
                
                if url.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    return
                
                if not url:
                    empty_count += 1
                    if empty_count >= 2 or len(urls) > 0:
                        break
                    continue
                
                empty_count = 0
                
                # Basic URL validation
                if 'youtube.com' in url or 'youtu.be' in url:
                    urls.append(url)
                    print(f"   ✅ Added ({len(urls)}/10)")
                else:
                    print("   ❌ Please enter a valid YouTube URL")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                return
        
        if not urls:
            print("❌ No URLs provided!")
            continue
        
        print(f"\n🎯 Ready to download {len(urls)} audio files!")
        
        # Ask for parallel download preference
        try:
            parallel = input("💨 Use parallel downloads for speed? (Y/n): ").strip().lower()
            if parallel in ['n', 'no']:
                max_workers = 1
                print("🐌 Using sequential downloads")
            else:
                max_workers = min(3, len(urls))  # Max 3 parallel
                print(f"⚡ Using {max_workers} parallel downloads")
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            return
        
        print()
        
        # Start downloads
        try:
            success, failed = downloader.download_multiple_parallel(urls, max_workers)
            
            if success > 0:
                print(f"\n🎉 {success} audio files downloaded successfully!")
                print(f"🎵 Check your music folder: {output_folder}")
            
            if failed > 0:
                retry = input(f"\n🔄 Retry {failed} failed downloads? (y/N): ").strip().lower()
                if retry in ['y', 'yes']:
                    print("🔄 Retrying failed downloads...")
                    failed_downloader = FastYTAudioDownloader(output_folder, thumbnail_folder)
                    failed_downloader.download_multiple_parallel(downloader.failed_urls, 1)
        
        except KeyboardInterrupt:
            print("\n⏹️  Download interrupted!")
        
        # Reset for next batch
        downloader.download_count = 0
        downloader.success_count = 0
        downloader.failed_urls = []
        
        print("\n" + "=" * 60)
        continue_download = input("🔄 Download another batch? (Y/n): ").strip().lower()
        if continue_download in ['n', 'no']:
            print("👋 Happy listening! 🎵")
            break
        print()

if __name__ == "__main__":
    main()