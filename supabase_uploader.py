"""
Supabase Storage Uploader
Utility functions for uploading files to Supabase Storage
"""

import os
from supabase import create_client
from pathlib import Path
from typing import Optional
from urllib.parse import quote

class SupabaseUploader:
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize Supabase client"""
        try:
            # Updated for latest Supabase client API
            self.supabase = create_client(supabase_url, supabase_key)
        except Exception as e:
            # Fallback for older API if needed
            from supabase import Client
            self.supabase = Client(supabase_url, supabase_key)

        # Buckets (configurable via env)
        self.audio_bucket = os.environ.get("SUPABASE_AUDIO_BUCKET", "audio-files")
        self.thumbnail_bucket = os.environ.get("SUPABASE_THUMBNAIL_BUCKET", "thumbnails")

    def upload_audio_file(self, file_path: str, bucket_name: str = "audio-files",
                         file_name: Optional[str] = None) -> dict:
        """
        Upload an audio file to Supabase Storage

        Args:
            file_path: Path to the local audio file
            bucket_name: Name of the Supabase storage bucket
            file_name: Optional custom filename (uses original name if not provided)

        Returns:
            dict: Upload response containing file information
        """
        try:
            # Ensure file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Audio file not found: {file_path}")

            # Generate filename if not provided
            if not file_name:
                file_name = Path(file_path).name

            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # Upload to Supabase Storage
            response = self.supabase.storage.from_(bucket_name).upload(
                path=file_name,
                file=file_content,
                file_options={
                    "content-type": self._get_audio_content_type(file_path),
                    "cache-control": "3600",
                    "upsert": "false"  # Don't overwrite existing files
                }
            )

            print(f"✅ Successfully uploaded: {file_name}")
            return response

        except Exception as e:
            print(f"❌ Error uploading {file_path}: {str(e)}")
            raise

    def upload_audio(self, file_path: str, display_name: Optional[str] = None) -> Optional[str]:
        """Upload a single audio file and return its public URL."""
        try:
            file_name = Path(file_path).name if not display_name else display_name
            with open(file_path, 'rb') as f:
                file_content = f.read()

            self.supabase.storage.from_(self.audio_bucket).upload(
                path=file_name,
                file=file_content,
                file_options={
                    "content-type": self._get_audio_content_type(file_path),
                    "cache-control": "3600",
                    "upsert": "false"
                }
            )

            return self.get_public_url(file_name, self.audio_bucket)
        except Exception as e:
            print(f"❌ Audio upload failed for {file_path}: {str(e)}")
            return ""

    def upload_thumbnail(self, file_path: str, display_name: Optional[str] = None) -> Optional[str]:
        """Upload a single thumbnail image and return its public URL."""
        try:
            file_name = Path(file_path).name if not display_name else display_name
            with open(file_path, 'rb') as f:
                file_content = f.read()

            self.supabase.storage.from_(self.thumbnail_bucket).upload(
                path=file_name,
                file=file_content,
                file_options={
                    "content-type": self._get_image_content_type(file_path),
                    "cache-control": "3600",
                    "upsert": "false"
                }
            )

            return self.get_public_url(file_name, self.thumbnail_bucket)
        except Exception as e:
            print(f"❌ Thumbnail upload failed for {file_path}: {str(e)}")
            return ""

    def upload_audio_files_batch(self, file_paths: list, bucket_name: str = "audio-files") -> list:
        """
        Upload multiple audio files to Supabase Storage

        Args:
            file_paths: List of paths to audio files
            bucket_name: Name of the Supabase storage bucket

        Returns:
            list: List of upload responses
        """
        results = []

        print(f"\n🎵 Uploading {len(file_paths)} audio files to Supabase...")
        print("=" * 60)

        for i, file_path in enumerate(file_paths, 1):
            try:
                print(f"📤 [{i}/{len(file_paths)}] Uploading: {Path(file_path).name}")

                response = self.upload_audio_file(file_path, bucket_name)
                results.append({
                    "file_path": file_path,
                    "success": True,
                    "response": response
                })

            except Exception as e:
                print(f"❌ [{i}/{len(file_paths)}] Failed to upload: {Path(file_path).name}")
                results.append({
                    "file_path": file_path,
                    "success": False,
                    "error": str(e)
                })

        # Print summary
        success_count = sum(1 for r in results if r["success"])
        print("\n" + "=" * 60)
        print("📊 SUPABASE UPLOAD SUMMARY")
        print("=" * 60)
        print(f"✅ Successful: {success_count}/{len(file_paths)}")
        print(f"❌ Failed: {len(file_paths) - success_count}")

        return results

    def get_public_url(self, file_name: str, bucket_name: str = "audio-files") -> str:
        """
        Get the public URL for a file in Supabase Storage with proper URL encoding

        Args:
            file_name: Name of the file
            bucket_name: Name of the storage bucket

        Returns:
            str: Properly URL-encoded public URL of the file
        """
        try:
            # Get the raw public URL from Supabase (handle dict or str return types)
            raw = self.supabase.storage.from_(bucket_name).get_public_url(file_name)
            if isinstance(raw, dict):
                if 'publicUrl' in raw:
                    raw_url = raw['publicUrl']
                elif 'data' in raw and isinstance(raw['data'], dict) and 'publicUrl' in raw['data']:
                    raw_url = raw['data']['publicUrl']
                else:
                    raw_url = str(raw)
            else:
                raw_url = str(raw)
            
            # Clean up any trailing query parameters (like '?' at the end)
            if raw_url.endswith('?'):
                raw_url = raw_url[:-1]
            
            # The raw URL typically looks like:
            # https://project.supabase.co/storage/v1/object/public/bucket name/file name.mp3
            # We need to encode the bucket name and file name parts
            
            # Split the URL to get the base part and the path part
            if '/storage/v1/object/public/' in raw_url:
                base_url, path_part = raw_url.split('/storage/v1/object/public/', 1)
                
                # Split the path into bucket and file parts
                path_parts = path_part.split('/', 1)
                if len(path_parts) == 2:
                    bucket_part, file_part = path_parts
                    
                    # URL encode both bucket name and file name
                    encoded_bucket = quote(bucket_part)
                    encoded_file = quote(file_part)
                    
                    # Reconstruct the properly encoded URL
                    encoded_url = f"{base_url}/storage/v1/object/public/{encoded_bucket}/{encoded_file}"
                    return encoded_url
            
            # Fallback: return the raw URL if parsing fails
            return raw_url
            
        except Exception as e:
            print(f"❌ Error getting public URL for {file_name}: {str(e)}")
            return ""

    def _get_audio_content_type(self, file_path: str) -> str:
        """Get the appropriate content type for audio files"""
        extension = Path(file_path).suffix.lower()

        content_types = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.m4a': 'audio/m4a',
            '.aac': 'audio/aac',
            '.ogg': 'audio/ogg',
            '.flac': 'audio/flac'
        }

        return content_types.get(extension, 'application/octet-stream')

    def _get_image_content_type(self, file_path: str) -> str:
        """Get the appropriate content type for image files"""
        extension = Path(file_path).suffix.lower()

        content_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp'
        }

        return content_types.get(extension, 'application/octet-stream')

    def list_files(self, bucket_name: str = "audio-files") -> list:
        """
        List all files in a Supabase storage bucket

        Args:
            bucket_name: Name of the storage bucket

        Returns:
            list: List of files in the bucket
        """
        try:
            response = self.supabase.storage.from_(bucket_name).list()
            return response
        except Exception as e:
            print(f"❌ Error listing files: {str(e)}")
            return []
