# FreeYTZone

A powerful YouTube video and audio downloader web application built with Flask and yt-dlp.

## Features

- Download YouTube videos in multiple qualities (8K, 4K, 2K, 1080p, 720p, 480p, 360p)
- Extract audio as MP3 from YouTube videos
- Support for YouTube Shorts with proper aspect ratio handling
- Support for private and restricted videos with cookie-based authentication
- Real-time video info display (title, channel, views, likes, comments, etc.)
- Automatic thumbnail and channel logo display

## Requirements

- Python 3.8+
- FFmpeg (installed and available in PATH)
- YouTube Data API key (for extended video info)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/SandeshBro-ux/freeytzone.git
   cd freeytzone
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with your YouTube API key:
   ```
   YOUTUBE_API_KEY=your_api_key_here
   ```

4. Run the application:
   ```
   python app.py
   ```

5. Open a web browser and navigate to `http://localhost:5000`

## How to Use

1. Enter a YouTube URL (regular video or Shorts)
2. View video details and available quality options
3. Select your preferred quality (or MP3 for audio only)
4. Wait for download to complete
5. Click on the download link to save the file

## Advanced Features

- **Cookie Support**: Paste your YouTube cookies to download private or restricted videos
- **Proxy Support**: Add a proxy URL in the `.env` file to bypass regional restrictions
- **Error Handling**: Robust error handling for unavailable videos and rate limiting

## Technical Details

- Uses a robust 3-step download process for reliable high-quality downloads
- Optimized thumbnail processing for both regular videos (16:9) and Shorts (9:16)
- Circular channel logos with transparency
- Secure file handling to prevent directory traversal attacks

## License

MIT License

## Project Structure

```
/
|-- app.py                  # Main Flask application
|-- requirements.txt        # Python dependencies
|-- .env                    # Environment variables (for API key)
|-- templates/
|   |-- index.html          # Frontend HTML template
|-- cookies/                # Temporary storage for uploaded cookie files (created automatically)
|-- downloads/              # Temporary storage for downloaded videos (created automatically)
|-- README.md               # This file
```

## Notes

-   The `cookies` and `downloads` directories are created automatically by the application if they don't exist. Cookie files are temporarily stored per video ID and then deleted after a successful download. Downloaded files are served from the `downloads` directory.
-   This application is for personal and educational purposes only. Always respect copyright laws and YouTube's Terms of Service when downloading content. 