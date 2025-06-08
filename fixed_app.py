@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    quality = data.get('quality', 'best')
    cookies_content = data.get('cookies_content')
    user_agent = request.headers.get('User-Agent')
    video_id, is_shorts = extract_video_id(url)
    
    if not video_id:
        return jsonify({'error': 'Invalid URL provided'}), 400

    download_dir = os.path.join(os.getcwd(), app.config['DOWNLOAD_FOLDER'])
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    cookie_file_path = None
    if cookies_content:
        cookie_file_path = create_cookie_file(cookies_content, video_id)

    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        app.logger.error("FFmpeg not found in PATH. Cannot merge video/audio or convert audio.")
        # Clean up cookie file before returning
        if cookie_file_path and os.path.exists(cookie_file_path):
            try:
                os.remove(cookie_file_path)
            except OSError as e:
                app.logger.error(f"Error removing cookie file {cookie_file_path}: {e}")
        return jsonify({'error': 'Server error: FFmpeg is not installed or not in system\'s PATH.'}), 500

    # Determine target height for format selection
    target_height = 0
    quality_str = quality.replace('p', '').replace('K', '000' if 'K' in quality else '')
    if quality_str.isdigit():
        target_height = int(quality_str)
    elif quality == 'best': # Treat 'best' as a very high target for fetching
        target_height = 9999 # effectively 'best'

    # Use a temporary directory for intermediate files
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            yt_dlp_base_cmd = [sys.executable, '-m', 'yt_dlp']

            # Add common yt-dlp options
            if user_agent:
                yt_dlp_base_cmd.extend(['--user-agent', user_agent])
            if cookie_file_path:
                yt_dlp_base_cmd.extend(['--cookies', cookie_file_path])
            if EFFECTIVE_YTDLP_PROXY_URL:
                yt_dlp_base_cmd.extend(['--proxy', EFFECTIVE_YTDLP_PROXY_URL])

            # --- MP3 Specific Download Logic ---
            if quality == 'mp3':
                app.logger.info("--- 🚀 Downloading MP3 Audio Only ---")
                mp3_opts = yt_dlp_base_cmd + [
                    '-f', 'bestaudio/best',
                    '--extract-audio',
                    '--audio-format', 'mp3',
                    '--audio-quality', '192K',
                    '-o', os.path.join(download_dir, '%(title)s.%(ext)s'),
                    url
                ]
                process_mp3 = subprocess.run(mp3_opts, check=True, capture_output=True, text=True)
                app.logger.info(f"MP3 STDOUT: \n{process_mp3.stdout}")
                app.logger.error(f"MP3 STDERR: \n{process_mp3.stderr}")

                # Determine the filename by finding the newest MP3 in the directory
                download_dir_abs = os.path.join(os.getcwd(), download_dir)
                list_of_files = [f for f in os.listdir(download_dir_abs) if f.endswith('.mp3')]
                if not list_of_files:
                    raise Exception(f"Failed to find MP3 file after download. STDOUT: {process_mp3.stdout}, STDERR: {process_mp3.stderr}")

                final_filename = max(list_of_files, key=lambda f: os.path.getctime(os.path.join(download_dir_abs, f)))
                app.logger.info(f"✅✅✅ MP3 Download complete! ✅✅✅")
                app.logger.info(f"Final MP3 file saved to: {final_filename}")

                return jsonify({
                    'success': True,
                    'filename': final_filename,
                    'download_url': f"/downloads/{final_filename}"
                })
            
            # --- Video Download Logic ---
            else:
                # --- Step 1: Download Video-Only Stream ---
                app.logger.info(f"--- Step 1 of 3: Downloading video stream for {quality} ---\n")
                video_format_string = f'bestvideo[height<={target_height}]' if target_height > 0 else 'bestvideo'
                video_opts = yt_dlp_base_cmd + [
                    '-f', video_format_string,
                    '-o', os.path.join(temp_dir, 'video.%(ext)s'),
                    url
                ]
                process_video = subprocess.run(video_opts, check=True, capture_output=True, text=True) # Capture output for debugging
                app.logger.info(f"Video STDOUT: \n{process_video.stdout}")
                app.logger.error(f"Video STDERR: \n{process_video.stderr}")
                video_file = next((os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.startswith('video.')), None)
                if not video_file:
                    raise Exception(f"Failed to download video stream. STDOUT: {process_video.stdout}, STDERR: {process_video.stderr}")
                app.logger.info(f"✅ Video stream downloaded to: {video_file}")

                # --- Step 2: Download Audio-Only Stream ---
                app.logger.info(f"\n--- Step 2 of 3: Downloading audio stream ---\n")
                audio_opts = yt_dlp_base_cmd + [
                    '-f', 'bestaudio',
                    '-o', os.path.join(temp_dir, 'audio.%(ext)s'),
                    url
                ]
                process_audio = subprocess.run(audio_opts, check=True, capture_output=True, text=True) # Capture output for debugging
                app.logger.info(f"Audio STDOUT: \n{process_audio.stdout}")
                app.logger.error(f"Audio STDERR: \n{process_audio.stderr}")
                audio_file = next((os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.startswith('audio.')), None)
                if not audio_file:
                    raise Exception(f"Failed to download audio stream. STDOUT: {process_audio.stdout}, STDERR: {process_audio.stderr}")
                app.logger.info(f"✅ Audio stream downloaded to: {audio_file}")

                # --- Step 3: Merge and Convert Audio with FFmpeg ---
                app.logger.info(f"\n--- Step 3 of 3: Merging video and converting audio to MP3 ---\n")
                # Get video title for the final filename from yt-dlp\'s info_dict
                try:
                    # Use a separate, minimal yt-dlp instance just for info extraction to avoid conflicts
                    ydl_info = yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True, 'simulate': True}).extract_info(url, download=False)
                    title = ydl_info.get('title', 'video')
                except Exception as info_e:
                    app.logger.warning(f"Could not get video title for filename: {info_e}. Using \'video\'.")
                    title = 'video'

                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).rstrip()
                final_output_path = os.path.join(download_dir, f"{safe_title}_{quality}.mp4")
                
                merge_opts = [
                    ffmpeg_path,
                    '-i', video_file,
                    '-i', audio_file,
                    '-c:v', 'copy',       # Copy video stream without re-encoding
                    '-c:a', 'mp3',        # Convert audio stream to MP3
                    '-b:a', '192k',       # Set high-quality audio bitrate
                    '-y',                 # Overwrite output file without asking
                    final_output_path
                ]
                process_merge = subprocess.run(merge_opts, check=True, capture_output=True, text=True) # Capture output for debugging
                app.logger.info(f"Merge STDOUT: \n{process_merge.stdout}")
                app.logger.error(f"Merge STDERR: \n{process_merge.stderr}")

                final_filename = os.path.basename(final_output_path)
                app.logger.info(f"✅✅✅ Download and conversion complete! ✅✅✅")
                app.logger.info(f"Final file saved to: {final_filename}")

                return jsonify({
                    'success': True,
                    'filename': final_filename,
                    'download_url': f"/downloads/{final_filename}"
                })

        except subprocess.CalledProcessError as e:
            app.logger.error(f"Command failed with exit code {e.returncode}: {e.cmd}")
            app.logger.error(f"STDOUT: {e.stdout}")
            app.logger.error(f"STDERR: {e.stderr}")
            return jsonify({'error': f'Download process failed. Details in server logs.'}), 500
        except Exception as e:
            app.logger.error(f"An unexpected error occurred during download: {str(e)}")
            error_lower = str(e).lower()

            if "http error 429" in error_lower or "too many requests" in error_lower:
                return jsonify({'error': 'YouTube is rate-limiting requests from this server. Please provide fresh cookies or try again later.'}), 429

            video_unavailable_patterns = [
                "video unavailable", "this video is unavailable", "content unavailable", 
                "not available in your country", "has been removed", "private video"
            ]
            
            if any(pattern in error_lower for pattern in video_unavailable_patterns):
                return jsonify({'error': 'This video is unavailable. It may be private, deleted, or region-restricted.'}), 404

            return jsonify({'error': 'An unexpected error occurred during download.'}), 500
        finally:
            # Cleanup is handled by tempfile.TemporaryDirectory() automatically for temp_dir
            # Only need to clean up the cookie file
            if cookie_file_path and os.path.exists(cookie_file_path):
                try:
                    os.remove(cookie_file_path)
                except OSError as e:
                    app.logger.error(f"Error removing cookie file {cookie_file_path}: {e}") 