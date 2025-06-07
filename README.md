# FreeYTZone - YouTube Video Downloader

A robust YouTube video downloader application built with Flask and yt-dlp, designed to handle YouTube's rate limiting and content restrictions.

## Features

- Download YouTube videos in various qualities (including 480p, 720p, 1080p, and 2K)
- Download audio-only MP3 files
- View video details (title, channel, subscribers, likes, views, etc.)
- Enhanced display for YouTube Shorts thumbnails (single frame, no blur)
- Higher quality channel logo downloads
- Support for cookies to access age-restricted or private content
- User-Agent customization for improved success rates
- VPNBook proxy integration for bypassing geo-restrictions (if configured)
- **NEW**: Improved error handling with proper HTTP status codes
- **NEW**: Enhanced browser cookie handling
- **NEW**: Smart retries with network timeout settings

## Installation

1. Clone the repository:
```bash
git clone https://github.com/SandeshBro-ux/Backupfreeytzone.git
cd Backupfreeytzone
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your environment variables by creating a `.env` file:
```
YOUTUBE_API_KEY=your_youtube_api_key
USE_VPNBOOK=True
VPNBOOK_COUNTRY=US
VPNBOOK_PROTOCOL=http
```

4. Run the application:
```bash
python app.py
```

The application will be available at http://localhost:5000

## Deployment

This application can be deployed on platforms like Render. When deploying:

1. Set the environment variables in your deployment platform
2. Make sure FFmpeg is available in the deployment environment
3. Configure the build command to install dependencies

## Usage

### Web Interface

1. Open the application in your browser
2. Paste a YouTube URL in the input field
3. Click "Get Info" to fetch video details
4. Select your desired quality from the dropdown (including MP3, thumbnail, and logo)
5. Click "Download" to start the download

### For restricted content:

1. Paste your browser cookies in the "Cookies" textarea
2. Paste your browser's User-Agent in the "User-Agent" textarea
3. Follow the same steps as above

## Getting Cookies and User-Agent

For best results when downloading restricted content:

1. **Cookies**:
   - Install a cookie export extension in your browser
   - Visit YouTube and log in
   - Export cookies in Netscape format
   - Paste the content in the application's cookie textarea

2. **User-Agent**:
   - Visit [whatsmyuseragent.org](https://whatsmyuseragent.org/)
   - Copy your browser's User-Agent string
   - Paste it in the application's User-Agent textarea

**Important**: The User-Agent must match the browser used to export the cookies.

## Error Handling

The application now has improved error handling with proper HTTP status codes:

- **HTTP 200**: Successful video info fetch or download
- **HTTP 404**: Video is unavailable (provides specific reasons)
- **HTTP 429**: Rate limiting detected
- **HTTP 500**: Server error

When a video is reported as unavailable, the app will now provide possible reasons:
- The video may be private or deleted
- The video may be geo-blocked
- The video may require age verification

## Troubleshooting

### HTTP Error 429 (Too Many Requests)

If you encounter rate limiting:

1. Try using fresh cookies from a logged-in YouTube account
2. Ensure the User-Agent matches the browser used for cookies
3. Wait some time before retrying
4. Try using the VPNBook proxy functionality (if configured)

### "Content Unavailable" Errors

1. Verify the video exists and is publicly available
2. Try using cookies from a logged-in account
3. Ensure your IP/proxy isn't blocked by YouTube
4. Check if the content is region-restricted

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for educational purposes only. Only download content that you have the right to download. Respect YouTube's Terms of Service and copyright laws.

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