#!/usr/bin/env python3
"""
YouTube Auto-Downloader
Automatically search for songs on YouTube, extract video URLs, and download thumbnails and audio
"""

import os
import sys
import time
import re
import subprocess
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests
import concurrent.futures
import threading
import json

# Import the existing thumbnail downloader
from quick_thumbnail_downloader import QuickThumbnailDownloader
# Import Supabase uploader
from supabase_uploader import SupabaseUploader

class YouTubeAutoDownloader:
    def __init__(self, thumbnail_folder="thumbnails", audio_folder="Audios", enable_supabase=True):
        self.thumbnail_folder = Path(thumbnail_folder)
        self.thumbnail_folder.mkdir(parents=True, exist_ok=True)
        self.audio_folder = Path(audio_folder)
        self.audio_folder.mkdir(parents=True, exist_ok=True)
        self.driver = None
        self.lock = threading.Lock()
        
        # Supabase configuration
        self.enable_supabase = enable_supabase
        self.supabase_uploader = None
        if enable_supabase:
            self.init_supabase()
    
    def init_supabase(self):
        """Initialize Supabase uploader with credentials"""
        try:
            # Supabase credentials (same as we used before)
            SUPABASE_URL = "https://aekvevvuanwzmjealdkl.supabase.co"
            SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFla3ZldnZ1YW53em1qZWFsZGtsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwMzExMjksImV4cCI6MjA3MTYwNzEyOX0.PZxoGAnv0UUeCndL9N4yYj0bgoSiDodcDxOPHZQWTxI"
            
            self.supabase_uploader = SupabaseUploader(SUPABASE_URL, SUPABASE_KEY)
            print("✅ Supabase uploader initialized successfully")
        except Exception as e:
            print(f"⚠️ Supabase initialization failed: {str(e)[:50]}...")
            print("📝 Downloads will work, but uploads will be skipped")
            self.enable_supabase = False

    def setup_browser(self):
        """Setup Chrome browser with options"""
        print("🚀 Setting up Chrome browser...")
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("✅ Browser setup complete!")
        except Exception as e:
            print(f"❌ Failed to setup browser: {e}")
            print("💡 Make sure Chrome/Chromium is installed and chromedriver is in PATH")
            return False
        return True

    def get_song_list(self):
        """Get list of songs from user input (supports pasting multiple lines)"""
        print("\n🎵 Paste your song list (format: '1. Song Name' on separate lines OR all in one line like '1. A2. B3. C'):")
        print("💡 Example:")
        print("   1. Shape of you")
        print("   2. See you again")
        print("   3. Blinding lights")
        print("📝 After pasting, press Enter on an empty line to finish\n")

        songs = []

        print("📝 Paste your songs below (press Enter on an empty line to finish):")

        # Read pasted lines until the user hits Enter on an empty line
        try:
            buffer_lines = []
            while True:
                try:
                    line = input()
                except EOFError:
                    break
                # Empty line means finish
                if line.strip() == "":
                    break
                buffer_lines.append(line)

            # Join all lines into a single buffer string
            buffer = "\n".join(buffer_lines).strip()

            if not buffer:
                print("❌ No input received!")
                return []

            # Handle the case where all songs are pasted in one line without spaces
            # e.g., "1. Rangin2. Don't Worry3. Aasha4. Uff5. Falling Apart6. All I ever dreamed7. Live in Rangashala8. Kheladi"
            if not '\n' in buffer and re.search(r'\d+\.\s*\w', buffer):
                # Split the single line input into separate songs
                # Pattern explanation:
                # (\d+\.) - matches the number followed by a dot (e.g., "1.", "2.", etc.)
                # ([^0-9]*?)- matches any characters except digits, non-greedy
                # (?=\d+\.|$) - positive lookahead for the next number or end of string
                parts = re.findall(r'(\d+\.)\s*([^0-9]*?)(?=\d+\.|$)', buffer)
                
                if parts:
                    for _, title in parts:
                        song_name = title.strip()
                        # Normalize internal whitespace
                        song_name = re.sub(r"\s+", " ", song_name)
                        if song_name:
                            songs.append(song_name)
                            print(f"   ✅ Added: {song_name}")
                else:
                    # Fallback if regex doesn't work
                    # Manually split by looking for patterns like "1.", "2.", etc.
                    song_parts = re.split(r'(\d+\.\s*)', buffer)
                    if len(song_parts) > 1:
                        # Process the split parts
                        i = 1
                        while i < len(song_parts):
                            if re.match(r'\d+\.\s*', song_parts[i]):
                                # This is a number marker
                                if i + 1 < len(song_parts):
                                    song_name = song_parts[i + 1].strip()
                                    song_name = re.sub(r"\s+", " ", song_name)
                                    # Check if the next part starts with a number (next song)
                                    if song_name and not re.match(r'^\d+\.', song_name):
                                        songs.append(song_name)
                                        print(f"   ✅ Added: {song_name}")
                            i += 2
            else:
                # Handle multi-line input or normally formatted input
                # If user pasted everything in one line like: 1. A2. B3. C ...
                # or in multiple lines, handle both by extracting numbered items
                # Pattern: capture text after each "N." up to the next number or end
                numbered_item_regex = re.compile(r"\b(\d+)\.\s*([^\d].*?)(?=\s*\d+\.|$)", re.DOTALL)
                matches = numbered_item_regex.findall(buffer)

                if matches:
                    for _, title in matches:
                        song_name = title.strip()
                        # Normalize internal whitespace
                        song_name = re.sub(r"\s+", " ", song_name)
                        if song_name:
                            songs.append(song_name)
                            print(f"   ✅ Added: {song_name}")
                else:
                    # Fallback: parse per-line if user provided one title per line with numbers
                    line_regex = re.compile(r"^\s*\d+\.\s*(.+)$")
                    for raw in buffer.splitlines():
                        m = line_regex.match(raw.strip())
                        if m:
                            song_name = re.sub(r"\s+", " ", m.group(1).strip())
                            if song_name:
                                songs.append(song_name)
                                print(f"   ✅ Added: {song_name}")

        except KeyboardInterrupt:
            print("\n❌ Operation cancelled by user")
            return []
        except Exception as e:
            print(f"❌ Error reading input: {e}")
            return []

        if not songs:
            print("❌ No valid songs found!")
            print("💡 Please paste songs in format: '1. Song Name'")
            return []

        # Show summary of detected songs
        print(f"\n🎵 {len(songs)} Songs detected ✅")
        print("=" * 40)
        print("📝 Song List:")
        for i, song in enumerate(songs, 1):
            print(f"   {i}. {song}")
        print("=" * 40)

        return songs

    def search_youtube(self, song_name, retry_attempt=0, max_retries=1):
        """Search for song on YouTube and return video URL with retry logic
        
        Args:
            song_name: Name of the song to search for
            retry_attempt: Current retry attempt number
            max_retries: Maximum number of retry attempts
        """
        try:
            # Format song name for URL
            search_query = song_name.replace(' ', '+')
            search_url = f"https://www.youtube.com/results?search_query={search_query}"

            retry_text = f" (Retry {retry_attempt + 1}/{max_retries + 1})" if retry_attempt > 0 else ""
            print(f"🔍 Searching for: {song_name}{retry_text}")
            print(f"   🌐 URL: {search_url}")

            # Add page load timeout for slow connections
            self.driver.set_page_load_timeout(30)
            self.driver.get(search_url)

            # Wait for search results to load with better timeout handling
            print("   ⏳ Waiting for search results...")
            time.sleep(3)  # Increased wait time

            # Find the first video result with improved timeout handling
            try:
                # Wait longer for search results to load (increased from 10 to 15 seconds)
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "ytd-video-renderer"))
                )
                
                # More specific selector for the first video title with longer timeout
                first_video = WebDriverWait(self.driver, 15).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "ytd-video-renderer ytd-thumbnail a#thumbnail"))
                )

                # Get the title of the first video
                title_element = self.driver.find_element(By.CSS_SELECTOR, "ytd-video-renderer ytd-rich-metadata-renderer:nth-of-type(1) #video-title")
                video_title = title_element.get_attribute("title") if title_element else "Unknown Title"
                
                print(f"   🎯 Found: {video_title[:60]}..." if len(video_title) > 60 else f"   🎯 Found: {video_title}")

                # Click on the first video thumbnail
                first_video.click()
                print("   🖱️  Clicked on first video")

                # Wait for video page to load and get URL
                time.sleep(2)
                current_url = self.driver.current_url

                # Check if it's a shorts URL and handle accordingly
                if self.is_shorts_url(current_url):
                    print(f"   🔄 Detected Shorts URL: {current_url}")
                    print("   🔙 Going back to search for long-form video...")
                    
                    # Go back to search results
                    self.driver.back()
                    time.sleep(2)
                    
                    # Try to find a non-shorts video
                    return self.find_long_form_video()
                else:
                    # Extract clean YouTube URL for regular videos
                    video_id = self.extract_video_id(current_url)
                    if video_id:
                        clean_url = f"https://www.youtube.com/watch?v={video_id}"
                        print(f"   ✅ Video URL: {clean_url}")
                        return clean_url
                    else:
                        print(f"   ❌ Could not extract video ID from: {current_url}")
                        return None

            except TimeoutException:
                print("   ❌ Timeout waiting for video results")
                
                # Retry logic for timeout failures
                if retry_attempt < max_retries:
                    print(f"   🔄 Retrying search due to timeout ({retry_attempt + 1}/{max_retries})...")
                    time.sleep(5)  # Longer wait before retry on timeout
                    return self.search_youtube(song_name, retry_attempt + 1, max_retries)
                else:
                    print(f"   ❌ All timeout retries failed for: {song_name}")
                    return None
            except Exception as e:
                print(f"   ❌ Error clicking video: {e}")
                # Try alternative selector
                try:
                    print("   🔧 Trying alternative method...")
                    first_video_alt = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a#video-title"))
                    )
                    video_title = first_video_alt.get_attribute("title") or "Unknown Title"
                    print(f"   🎯 Found: {video_title[:60]}..." if len(video_title) > 60 else f"   🎯 Found: {video_title}")
                    first_video_alt.click()
                    print("   🖱️  Clicked on first video (alternative method)")
                    
                    time.sleep(2)
                    current_url = self.driver.current_url
                    
                    # Check if alternative method also got shorts
                    if self.is_shorts_url(current_url):
                        print(f"   🔄 Alternative method also got Shorts: {current_url}")
                        print("   🔙 Going back to search for long-form video...")
                        
                        # Go back to search results
                        self.driver.back()
                        time.sleep(2)
                        
                        # Try to find a non-shorts video
                        return self.find_long_form_video()
                    else:
                        video_id = self.extract_video_id(current_url)
                        if video_id:
                            clean_url = f"https://www.youtube.com/watch?v={video_id}"
                            print(f"   ✅ Video URL: {clean_url}")
                            return clean_url
                        else:
                            print(f"   ❌ Could not extract video ID from: {current_url}")
                            return None
                except Exception as e2:
                    print(f"   ❌ Alternative method also failed: {e2}")
                    return None

        except Exception as e:
            print(f"❌ Error searching YouTube: {e}")
            
            # Retry logic for failed searches
            if retry_attempt < max_retries:
                print(f"   🔄 Retrying search ({retry_attempt + 1}/{max_retries})...")
                time.sleep(3)  # Wait before retry
                return self.search_youtube(song_name, retry_attempt + 1, max_retries)
            else:
                print(f"   ❌ All search attempts failed for: {song_name}")
                return None

    def extract_video_id(self, url):
        """Extract video ID from YouTube URL"""
        # Handle both regular videos and shorts
        video_id_pattern = r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})'
        match = re.search(video_id_pattern, url)
        return match.group(1) if match else None
    
    def is_shorts_url(self, url):
        """Check if URL is a YouTube Shorts URL"""
        return '/shorts/' in url
    
    def find_long_form_video(self, skip_count=0):
        """Find and click on a long-form (non-shorts) video from search results
        
        Args:
            skip_count: Number of videos to skip (for retry attempts)
        """
        try:
            if skip_count > 0:
                print(f"   🔍 Searching for alternative videos (skipping first {skip_count})...")
            else:
                print("   🔍 Searching for long-form videos...")
            
            # Wait for search results to be available with longer timeout
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ytd-video-renderer"))
            )
            
            # Find all video links on the page
            video_links = self.driver.find_elements(By.CSS_SELECTOR, "ytd-video-renderer a#video-title")
            
            print(f"   📋 Found {len(video_links)} video results to check")
            
            # Start from skip_count to try different videos
            start_index = skip_count
            end_index = min(len(video_links), start_index + 10)
            
            # Try each video link until we find a non-shorts one
            for i in range(start_index, end_index):
                try:
                    link = video_links[i]
                    # Get the href to check if it's a shorts URL before clicking
                    href = link.get_attribute('href')
                    if href and '/shorts/' in href:
                        print(f"   ⏭️ Skipping Shorts video [{i+1}]: {href}")
                        continue
                    
                    # Get video title
                    title = link.get_attribute('title') or link.text or "Unknown Title"
                    print(f"   🎯 Trying video [{i+1}]: {title[:60]}..." if len(title) > 60 else f"   🎯 Trying video [{i+1}]: {title}")
                    
                    # Click on this video
                    self.driver.execute_script("arguments[0].click();", link)
                    print(f"   🖱️ Clicked on video [{i+1}]")
                    
                    # Wait for page to load
                    time.sleep(3)
                    current_url = self.driver.current_url
                    
                    # Check if this is a shorts URL
                    if self.is_shorts_url(current_url):
                        print(f"   🔄 Video [{i+1}] is also Shorts: {current_url}")
                        print(f"   🔙 Going back to try next video...")
                        self.driver.back()
                        time.sleep(2)
                        continue
                    else:
                        # Found a regular video!
                        video_id = self.extract_video_id(current_url)
                        if video_id:
                            clean_url = f"https://www.youtube.com/watch?v={video_id}"
                            print(f"   ✅ Found long-form video [{i+1}]: {clean_url}")
                            return clean_url
                        else:
                            print(f"   ❌ Could not extract video ID from: {current_url}")
                            self.driver.back()
                            time.sleep(2)
                            continue
                            
                except Exception as e:
                    print(f"   ⚠️ Error with video [{i+1}]: {str(e)[:50]}...")
                    try:
                        self.driver.back()
                        time.sleep(2)
                    except:
                        pass
                    continue
            
            print("   ❌ No long-form videos found in search results")
            return None
            
        except Exception as e:
            print(f"   ❌ Error finding long-form video: {str(e)[:50]}...")
            return None
    
    def retry_age_restricted_video(self, song_name, max_retries=3):
        """Retry finding alternative uploads when age-restricted video is encountered
        
        Args:
            song_name: Original song name to search for
            max_retries: Maximum number of retry attempts
            
        Returns:
            tuple: (success, video_url) - success is bool, video_url is string or None
        """
        print(f"\n🔁 AGE-RESTRICTED VIDEO DETECTED")
        print(f"   🎵 Song: {song_name}")
        print(f"   🔍 Searching for alternative uploads...")
        
        # Generate alternative search terms
        search_variations = self.generate_search_variations(song_name)
        
        for retry_attempt in range(max_retries):
            try:
                print(f"\n   🔄 Retry {retry_attempt + 1}/{max_retries}")
                
                # Try different search variation for each retry
                if retry_attempt < len(search_variations):
                    search_term = search_variations[retry_attempt]
                    print(f"   🔍 Searching: '{search_term}'")
                    
                    # Navigate to new search
                    search_query = search_term.replace(' ', '+')
                    search_url = f"https://www.youtube.com/results?search_query={search_query}"
                    self.driver.get(search_url)
                    time.sleep(2)
                    
                    # Try to find a non-restricted video using our existing method
                    # Skip more videos each retry to get different results
                    skip_count = retry_attempt * 2  # Skip 0, 2, 4 videos respectively
                    alternative_url = self.find_long_form_video(skip_count=skip_count)
                    
                    if alternative_url:
                        print(f"   ✅ Found alternative video: {alternative_url}")
                        return True, alternative_url
                    else:
                        print(f"   ❌ Retry {retry_attempt + 1} failed - no suitable video found")
                else:
                    print(f"   ⚠️ No more search variations available")
                    break
                    
            except Exception as e:
                print(f"   ❌ Retry {retry_attempt + 1} error: {str(e)[:50]}...")
                continue
        
        print(f"   ❌ All retry attempts failed for: {song_name}")
        return False, None
    
    def generate_search_variations(self, song_name):
        """Generate alternative search terms for finding different uploads
        
        Args:
            song_name: Original song name
            
        Returns:
            list: List of alternative search terms
        """
        variations = []
        
        # Remove "official" and "By [Artist]" patterns to get broader results
        base_name = song_name
        
        # Remove common patterns
        patterns_to_remove = [
            r'\s+official\s*$',  # Remove "official" at the end
            r'\s+By\s+[^\s]+.*$',  # Remove "By Artist" pattern
            r'\s+by\s+[^\s]+.*$',  # Remove "by Artist" pattern (lowercase)
            r'\s+-\s+[^\s]+\s+Version.*$',  # Remove version info
        ]
        
        for pattern in patterns_to_remove:
            base_name = re.sub(pattern, '', base_name, flags=re.IGNORECASE)
        
        base_name = base_name.strip()
        
        # Generate variations
        variations.append(base_name)  # Clean song name
        variations.append(f"{base_name} audio")  # Add "audio"
        variations.append(f"{base_name} music")  # Add "music"
        variations.append(f"{base_name} song")  # Add "song"
        variations.append(f"{base_name} cover")  # Look for covers
        variations.append(f"{base_name} remix")  # Look for remixes
        
        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for variation in variations:
            if variation.lower() not in seen:
                seen.add(variation.lower())
                unique_variations.append(variation)
        
        return unique_variations[:5]  # Return top 5 variations

    def process_songs(self, songs):
        """Process all songs and return video URLs with song names"""
        video_data = []  # Changed from video_urls to video_data to store song names too

        print(f"\n🚀 Starting auto-download for {len(songs)} songs...")
        print("=" * 60)

        for i, song in enumerate(songs, 1):
            print(f"\n📍 Processing {i}/{len(songs)}: {song}")
            print("-" * 40)

            video_url = self.search_youtube(song)

            if video_url:
                # Store both URL and song name
                video_data.append((video_url, song))
                print(f"✅ Success: {song}")
            else:
                print(f"❌ Failed: {song}")

            # Add small delay between searches to avoid rate limiting
            if i < len(songs):
                print("⏳ Waiting 2 seconds before next search...")
                time.sleep(2)

        return video_data

    def download_thumbnails(self, video_data):
        """Download thumbnails using the existing downloader with custom naming"""
        if not video_data:
            print("❌ No video data to download thumbnails for!")
            return

        print(f"\n🖼️  Downloading thumbnails for {len(video_data)} videos...")
        print("=" * 60)

        # Use the existing thumbnail downloader but with custom implementation
        # to preserve song names for file naming
        success_count = 0
        failed_count = 0
        
        for i, (url, song_name) in enumerate(video_data, 1):
            try:
                print(f"🖼️  [{i}] Processing: {song_name}")
                print(f"   🌐 URL: {url}")
                
                # Extract video ID
                video_id = self.extract_video_id(url)
                if not video_id:
                    print(f"   ❌ [{i}] Invalid URL")
                    failed_count += 1
                    continue
                
                # Clean the song name for use as filename
                clean_song_name = re.sub(r'[^\w\s.-]', '', song_name)
                clean_song_name = re.sub(r'\s+', ' ', clean_song_name).strip()
                
                # Try different thumbnail qualities
                thumbnail_urls = [
                    f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
                    f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg", 
                    f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
                    f"https://i.ytimg.com/vi/{video_id}/default.jpg"
                ]
                
                thumbnail_saved = False
                for quality, thumb_url in zip(['maxres', 'hq', 'mq', 'default'], thumbnail_urls):
                    try:
                        response = requests.get(thumb_url, timeout=10)
                        if response.status_code == 200 and len(response.content) > 1000:
                            # Save with the song name as filename
                            filename = f"{clean_song_name}.png"
                            filepath = self.thumbnail_folder / filename
                            
                            # Avoid duplicates by adding a counter if file exists
                            counter = 1
                            original_filepath = filepath
                            while filepath.exists():
                                name_part = clean_song_name
                                filename = f"{name_part}_{counter}.png"
                                filepath = self.thumbnail_folder / filename
                                counter += 1
                            
                            with open(filepath, 'wb') as f:
                                f.write(response.content)
                            
                            print(f"   ✅ [{i}] Saved: {filename} ({quality} quality)")
                            success_count += 1
                            thumbnail_saved = True
                            break
                    except:
                        continue
                
                if not thumbnail_saved:
                    print(f"   ❌ [{i}] All thumbnail URLs failed")
                    failed_count += 1
                    
            except Exception as e:
                print(f"   💥 [{i}] Error: {str(e)[:50]}...")
                failed_count += 1

        # Print summary
        print("\n" + "=" * 60)
        print("📊 THUMBNAIL DOWNLOAD SUMMARY")
        print("=" * 60)
        print(f"✅ Successful: {success_count}/{len(video_data)}")
        print(f"❌ Failed: {failed_count}")
        print(f"📁 Saved to: {self.thumbnail_folder}")

        print(f"\n🎉 Thumbnail download complete!")
        print(f"📁 Thumbnails saved to: {self.thumbnail_folder}")

    def clean_filename(self, filename):
        """Remove special characters from filename"""
        # Remove special characters, keep only letters, numbers, spaces, dots, hyphens, underscores
        cleaned = re.sub(r'[^a-zA-Z0-9\s._-]', '', filename)
        # Replace multiple spaces with single space
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def get_audio_duration(self, file_path):
        """Get audio file duration in MM:SS format using ffprobe"""
        try:
            # Use ffprobe to get duration
            cmd = [
                'ffprobe', 
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                str(file_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration_seconds = float(data['format']['duration'])
                
                # Convert to MM:SS format
                minutes = int(duration_seconds // 60)
                seconds = int(duration_seconds % 60)
                return f"{minutes}:{seconds:02d}"
            else:
                return "Unknown"
                
        except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, ValueError):
            return "Unknown"
        except FileNotFoundError:
            # ffprobe not available, try alternative method with yt-dlp
            try:
                cmd = [
                    sys.executable, '-m', 'yt_dlp',
                    '--print', 'duration',
                    '--no-warnings',
                    str(file_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and result.stdout.strip():
                    duration_seconds = float(result.stdout.strip())
                    minutes = int(duration_seconds // 60)
                    seconds = int(duration_seconds % 60)
                    return f"{minutes}:{seconds:02d}"
            except:
                pass
            return "Unknown"

    def download_single_audio(self, url, song_name, index=None):
        """Download audio from a single YouTube URL with custom filename"""
        try:
            prefix = f"[{index}]" if index else ""
            print(f"🎵 {prefix} Starting audio download: {song_name}")
            print(f"   🌐 URL: {url}")
            
            # Clean the song name for use as filename
            clean_song_name = self.clean_filename(song_name)
            if not clean_song_name:
                clean_song_name = "audio"
            
            # Enhanced yt-dlp options for fast audio downloads and age-restricted content
            yt_dlp_options = [
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
                # Multiple player clients for better compatibility with age-restricted content
                '--extractor-args', 'youtube:player_client=android,web,ios;player_skip=webpage;include_hls_manifest=false',
                '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36',
                # Try to handle age-restricted content
                '--age-limit', '0',  # No age limit
                # Custom output template with clean song name
                '-o', str(self.audio_folder / f'{clean_song_name}.%(ext)s'),
                url
            ]
            
            start_time = time.time()
            
            # Run audio download
            result = subprocess.run(
                yt_dlp_options, 
                capture_output=True, 
                text=True, 
                timeout=300  # 5 minute timeout per video
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if result.returncode == 0:
                print(f"✅ {prefix} SUCCESS! Audio downloaded in {duration:.1f}s")
                print(f"   📁 Saved to: {self.audio_folder}")
                return True
            else:
                # Check if it's an age-restricted error
                if result.stderr and "age-restricted" in result.stderr.lower():
                    print(f"❌ {prefix} AGE-RESTRICTED: {song_name}")
                    if result.stderr:
                        print(f"   Error: {result.stderr.strip()[:100]}...")
                    return "age_restricted"
                else:
                    print(f"❌ {prefix} FAILED: {song_name}")
                    if result.stderr:
                        print(f"   Error: {result.stderr.strip()[:100]}...")
                    return False
                        
        except subprocess.TimeoutExpired:
            print(f"⏰ {prefix} TIMEOUT: {song_name} (took too long)")
            return False
            
        except Exception as e:
            print(f"💥 {prefix} ERROR: {song_name} - {str(e)}")
            return False

    def download_audio_files(self, video_data):
        """Download audio files for all videos in parallel"""
        if not video_data:
            print("❌ No video data to download audio for!")
            return

        print(f"\n🎵 Downloading audio for {len(video_data)} songs...")
        print("=" * 60)

        # Download audio files in parallel (max 3 at a time)
        max_workers = min(3, len(video_data))
        success_count = 0
        failed_count = 0
        retry_count = 0
        retry_success_songs = []  # Track songs downloaded via retry mechanism
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i, (url, song_name) in enumerate(video_data, 1):
                future = executor.submit(self.download_single_audio, url, song_name, i)
                futures.append((future, song_name, url, i))
            
            # Wait for all downloads to complete
            for future, song_name, original_url, index in futures:
                try:
                    result = future.result(timeout=300)  # 5 minute timeout
                    if result is True:
                        success_count += 1
                    elif result == "age_restricted":
                        print(f"\n🔄 ATTEMPTING RETRY for: {song_name}")
                        
                        # Setup browser for retry (if not already active)
                        if not self.driver:
                            if self.setup_browser():
                                try:
                                    # Attempt to find alternative upload
                                    retry_success, alternative_url = self.retry_age_restricted_video(song_name)
                                    
                                    if retry_success and alternative_url:
                                        print(f"   🎵 Attempting download with alternative URL...")
                                        # Try downloading with the alternative URL
                                        retry_result = self.download_single_audio(alternative_url, song_name, f"{index}R")
                                        
                                        if retry_result is True:
                                            print(f"   ✅ RETRY SUCCESS: {song_name}")
                                            success_count += 1
                                            retry_count += 1
                                            retry_success_songs.append(song_name)
                                        else:
                                            print(f"   ❌ RETRY FAILED: {song_name}")
                                            failed_count += 1
                                    else:
                                        print(f"   ❌ No alternative found: {song_name}")
                                        failed_count += 1
                                        
                                finally:
                                    # Clean up browser after retry
                                    self.cleanup()
                            else:
                                print(f"   ❌ Browser setup failed for retry: {song_name}")
                                failed_count += 1
                        else:
                            print(f"   ❌ Browser not available for retry: {song_name}")
                            failed_count += 1
                    else:
                        failed_count += 1
                        
                except concurrent.futures.TimeoutError:
                    print(f"⏰ TIMEOUT: {song_name} (took too long)")
                    failed_count += 1
                except Exception as e:
                    print(f"💥 ERROR: {song_name} - {str(e)}")
                    failed_count += 1

        # Print summary
        print("\n" + "=" * 60)
        print("📈 AUDIO DOWNLOAD SUMMARY")
        print("=" * 60)
        print(f"✅ Successful: {success_count}/{len(video_data)}")
        print(f"❌ Failed: {failed_count}")
        if retry_count > 0:
            print(f"🔄 Successful Retries: {retry_count}")
            print("\n🎵 SONGS DOWNLOADED VIA RETRY MECHANISM:")
            print("-" * 50)
            for i, song in enumerate(retry_success_songs, 1):
                print(f"   {i}. \"{song}\" was age-restricted and downloaded using retry mechanism")
        print(f"\n📁 All files saved to: {self.audio_folder}")

        print(f"\n🎉 Audio download complete!")
        print(f"📁 Audio files saved to: {self.audio_folder}")
        
        return success_count, failed_count, retry_success_songs
    
    def upload_all_audio_files(self, total_songs_requested, successful_downloads, failed_downloads, retry_songs, video_data):
        """Upload all downloaded audio files to Supabase
        
        Args:
            total_songs_requested: Total number of songs user requested
            successful_downloads: Number of successful downloads
            failed_downloads: Number of failed downloads  
            retry_songs: List of songs downloaded via retry mechanism
            video_data: List of (url, song_name) tuples in original order
            
        Returns:
            tuple: (upload_success_count, upload_failed_count, should_upload, public_urls)
        """
        # STRICT all-or-nothing policy: Only upload if ALL requested songs were downloaded
        should_upload = (successful_downloads == total_songs_requested and failed_downloads == 0)
        
        if not self.enable_supabase:
            print(f"\n⚠️ Supabase upload skipped - not enabled")
            return 0, 0, False, []
        
        if not should_upload:
            print(f"\n❌ SUPABASE UPLOAD SKIPPED")
            print(f"   Reason: {failed_downloads} song(s) failed to download")
            print(f"   Policy: Only upload when ALL songs download successfully")
            print(f"   📝 {successful_downloads} downloaded songs will NOT be uploaded")
            return 0, 0, False, []
        
        # All downloads were successful - proceed with uploads
        print(f"\n🚀 STARTING SUPABASE UPLOADS")
        print("=" * 60)
        print(f"🎉 All {successful_downloads} songs downloaded successfully!")
        print(f"📄 Proceeding with Supabase uploads...")
        
        # Build ordered list of audio files based on original video_data order
        audio_files_ordered = []
        for url, song_name in video_data:
            clean_song_name = self.clean_filename(song_name)
            if not clean_song_name:
                clean_song_name = "audio"
            
            # Find the MP3 file with this name
            mp3_file = self.audio_folder / f"{clean_song_name}.mp3"
            if mp3_file.exists():
                audio_files_ordered.append(mp3_file)
            else:
                # Check for files with counter suffix (e.g., song_1.mp3, song_2.mp3)
                counter = 1
                while True:
                    mp3_file_alt = self.audio_folder / f"{clean_song_name}_{counter}.mp3"
                    if mp3_file_alt.exists():
                        audio_files_ordered.append(mp3_file_alt)
                        break
                    counter += 1
                    if counter > 10:  # Safety limit
                        print(f"   ⚠️ Could not find audio file for: {song_name}")
                        break
        
        if not audio_files_ordered:
            print(f"   ❌ No MP3 files found in {self.audio_folder}")
            return 0, 1, should_upload, []
        
        print(f"\n🎵 Found {len(audio_files_ordered)} audio files to upload (in original order)")
        
        # Upload files using the existing Supabase uploader
        try:
            file_paths = [str(file_path) for file_path in audio_files_ordered]
            bucket_name = "Sushant-KC more"  # Your bucket name
            
            # Use the batch upload method from supabase_uploader
            results = self.supabase_uploader.upload_audio_files_batch(file_paths, bucket_name)
            
            # Count successes and failures, collect public URLs IN ORDER
            upload_success_count = 0
            upload_failed_count = 0
            public_urls = []
            
            for result in results:
                if result["success"]:
                    upload_success_count += 1
                    # Get public URL for successful uploads
                    filename = Path(result["file_path"]).name
                    public_url = self.supabase_uploader.get_public_url(filename, bucket_name)
                    if public_url:
                        public_urls.append((filename, public_url))
                else:
                    upload_failed_count += 1
            
            return upload_success_count, upload_failed_count, should_upload, public_urls
            
        except Exception as e:
            print(f"\n❌ SUPABASE UPLOAD ERROR: {str(e)}")
            return 0, len(audio_files_ordered), should_upload, []

    def cleanup(self):
        """Clean up browser resources"""
        if self.driver:
            print("\n🧹 Cleaning up browser...")
            self.driver.quit()
            self.driver = None  # Set to None to prevent reuse
            print("✅ Browser closed!")

def main():
    """Main function"""
    print("🎵" + "=" * 60)
    print("      YOUTUBE AUTO-DOWNLOADER")
    print("=" * 60 + "🎵")
    print()
    print("This program will:")
    print("1. Ask for song names in numbered format")
    print("2. Launch Chrome to search YouTube automatically")
    print("3. Extract video URLs and download thumbnails and audio")
    print()

    # Create downloader instance with both folders  
    print("🔧 Initializing YouTube Auto-Downloader...")
    downloader = YouTubeAutoDownloader(thumbnail_folder="thumbnails", audio_folder="Audios")
    print()

    try:
        # Get song list from user
        songs = downloader.get_song_list()
        if not songs:
            print("❌ No songs to process. Exiting...")
            return

        # Setup browser
        if not downloader.setup_browser():
            print("❌ Failed to setup browser. Exiting...")
            return

        # Process songs
        video_data = downloader.process_songs(songs)  # Changed from video_urls to video_data

        # Close browser immediately after getting URLs
        downloader.cleanup()
        print("🔒 Browser closed. Starting downloads...")

        if video_data:
            # Download thumbnails with custom naming
            downloader.download_thumbnails(video_data)  # Pass video_data instead of video_urls
            
            # Download audio files with custom naming
            success_count, failed_count, retry_songs = downloader.download_audio_files(video_data)
            
            # Upload to Supabase if enabled and all downloads succeeded
            upload_success, upload_failed, upload_attempted, public_urls = downloader.upload_all_audio_files(
                total_songs_requested=len(songs),
                successful_downloads=success_count, 
                failed_downloads=failed_count,
                retry_songs=retry_songs,
                video_data=video_data
            )
            
            # Final completion message
            print(f"\n🎆 FINAL COMPLETION MESSAGE")
            print("=" * 60)
            print(f"🎉 YouTube Auto-Download Complete!")
            print(f"📁 Thumbnails: {len(video_data)}/{ len(video_data)} (100%)")
            print(f"🎵 Audio Downloads: {success_count}/{len(songs)} ({int(success_count/len(songs)*100)}%)")
            
            if upload_attempted:
                if upload_success > 0:
                    print(f"🚀 Supabase Uploads: {upload_success}/{success_count} ({int(upload_success/success_count*100) if success_count > 0 else 0}%)")
                    print(f"\n✨ Successfully uploaded {upload_success} songs to Supabase!")
                else:
                    print(f"🚀 Supabase Uploads: 0/{success_count} (Failed)")
            elif failed_count > 0:
                print(f"🚀 Supabase Uploads: Skipped (due to {failed_count} download failures)")
            else:
                print(f"🚀 Supabase Uploads: Disabled")
                
            # Display public URLs if any were uploaded - SIMPLIFIED FORMAT
            if upload_attempted and public_urls:
                print(f"\n🌍 SUPABASE URLS:")
                for i, (filename, url) in enumerate(public_urls, 1):
                    print(f"{i}. {url}")
                
                # Display audio durations
                print(f"\n🎵 AUDIO DURATIONS:")
                for i, (filename, url) in enumerate(public_urls, 1):
                    # Find the corresponding local file to get duration
                    local_file_path = downloader.audio_folder / filename
                    if local_file_path.exists():
                        duration = downloader.get_audio_duration(local_file_path)
                        print(f"{i}. {duration}")
                    else:
                        print(f"{i}. Unknown")
            
            print(f"\n📁 Local files saved to:")
            print(f"   🖼️ Thumbnails: thumbnails/")
            print(f"   🎵 Audio files: Audios/")
        else:
            print("❌ No video URLs extracted. Downloads skipped.")

    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
    finally:
        # Make sure browser is closed even if there's an error
        if downloader.driver:
            downloader.cleanup()

if __name__ == "__main__":
    main()
