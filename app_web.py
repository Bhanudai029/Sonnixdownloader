#!/usr/bin/env python3
"""
YouTube Song Search Web Interface
Simple Flask app to search YouTube songs and get video URLs
"""

from flask import Flask, render_template, request, jsonify
import os
import re
import requests
import time

app = Flask(__name__)

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

