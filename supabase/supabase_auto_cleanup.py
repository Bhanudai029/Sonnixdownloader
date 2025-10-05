#!/usr/bin/env python3
"""
Supabase Auto Cleanup (Interactive)
Lists audio files added within the last 12 hours and lets you:
  - Delete all (type yes)
  - Or type one or more item numbers (e.g., "2" or "1,3") to delete selectively
"""

import os
from datetime import datetime, timedelta, timezone
from supabase import create_client
from pathlib import Path

class SupabaseAutoCleanup:
    def __init__(self, supabase_url: str, supabase_key: str, bucket_name: str):
        """Initialize Supabase client"""
        self.supabase = create_client(supabase_url, supabase_key)
        self.bucket_name = bucket_name
        print(f"✅ Connected to Supabase")
        print(f"📦 Bucket: {bucket_name}")
    
    def get_recent_files(self, hours: int = 12):
        """
        Get list of files added within the last N hours
        
        Args:
            hours: Number of hours to look back (default: 12)
            
        Returns:
            list: List of file objects that were added within the specified time
        """
        try:
            print(f"\n🔍 Checking for files added within the last {hours} hours...")
            
            # List all files in the bucket
            files = self.supabase.storage.from_(self.bucket_name).list()
            
            if not files:
                print("   ℹ️ No files found in bucket")
                return []
            
            print(f"   📋 Found {len(files)} total files in bucket")
            
            # Calculate cutoff time (current time - hours)
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            print(f"   ⏰ Cutoff time: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"   📅 Current time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            recent_files = []
            for file in files:
                # Get file metadata including creation time
                file_name = file['name']
                
                # Parse the created_at or updated_at timestamp
                created_at_str = file.get('created_at') or file.get('updated_at')
                
                if created_at_str:
                    # Parse ISO format timestamp
                    # Handle both with and without timezone info
                    try:
                        if created_at_str.endswith('Z'):
                            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        elif '+' in created_at_str or created_at_str.count('-') > 2:
                            created_at = datetime.fromisoformat(created_at_str)
                        else:
                            # Assume UTC if no timezone info
                            created_at = datetime.fromisoformat(created_at_str).replace(tzinfo=timezone.utc)
                        
                        # Check if file was created after cutoff time
                        if created_at > cutoff_time:
                            time_diff = datetime.now(timezone.utc) - created_at
                            hours_ago = time_diff.total_seconds() / 3600
                            recent_files.append({
                                'name': file_name,
                                'created_at': created_at,
                                'hours_ago': hours_ago
                            })
                            print(f"   ✓ {file_name} - Added {hours_ago:.1f} hours ago")
                    except Exception as e:
                        print(f"   ⚠️ Could not parse timestamp for {file_name}: {e}")
                else:
                    print(f"   ⚠️ No timestamp found for {file_name}")
            
            return recent_files
            
        except Exception as e:
            print(f"❌ Error listing files: {str(e)}")
            return []
    
    def delete_files(self, file_list: list, dry_run: bool = False):
        """
        Delete files from Supabase bucket
        
        Args:
            file_list: List of file objects to delete (with 'name' key)
            dry_run: If True, only show what would be deleted without actually deleting
            
        Returns:
            tuple: (success_count, failed_count)
        """
        if not file_list:
            print("\n✅ No files to delete!")
            return 0, 0
        
        print(f"\n🗑️  {'DRY RUN - Would delete' if dry_run else 'Deleting'} {len(file_list)} file(s)...")
        print("=" * 60)
        
        success_count = 0
        failed_count = 0
        
        for i, file_info in enumerate(file_list, 1):
            file_name = file_info['name']
            hours_ago = file_info.get('hours_ago', 0)
            
            try:
                if dry_run:
                    print(f"[{i}/{len(file_list)}] Would delete: {file_name} (added {hours_ago:.1f}h ago)")
                    success_count += 1
                else:
                    print(f"[{i}/{len(file_list)}] Deleting: {file_name} (added {hours_ago:.1f}h ago)")
                    
                    # Delete file from Supabase
                    self.supabase.storage.from_(self.bucket_name).remove([file_name])
                    
                    print(f"   ✅ Deleted successfully")
                    success_count += 1
                    
            except Exception as e:
                print(f"   ❌ Failed to delete: {str(e)}")
                failed_count += 1
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 DELETION SUMMARY")
        print("=" * 60)
        if dry_run:
            print(f"✓ Would delete: {success_count} file(s)")
        else:
            print(f"✅ Successfully deleted: {success_count}/{len(file_list)}")
            print(f"❌ Failed: {failed_count}")
        
        return success_count, failed_count
    
    def auto_cleanup(self, hours: int = 12, dry_run: bool = False):
        """
        Main cleanup function that finds and deletes recent files
        
        Args:
            hours: Number of hours to look back (default: 12)
            dry_run: If True, only show what would be deleted
        """
        print("🧹" + "=" * 60)
        print("      SUPABASE AUTO CLEANUP")
        print("=" * 60 + "🧹")
        
        if dry_run:
            print("⚠️  DRY RUN MODE - No files will actually be deleted")
        
        # Get recent files
        recent_files = self.get_recent_files(hours)
        
        if not recent_files:
            print("\n✅ No recent files found to delete!")
            print(f"   All files in the bucket are older than {hours} hours")
            return
        
        # Delete files
        success, failed = self.delete_files(recent_files, dry_run)
        
        if not dry_run and success > 0:
            print(f"\n🎉 Cleanup complete! Deleted {success} file(s) from Supabase")


def main():
    """Main function"""
    # Supabase credentials (same as in youtube_auto_downloader.py)
    SUPABASE_URL = "https://aekvevvuanwzmjealdkl.supabase.co"
    SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFla3ZldnZ1YW53em1qZWFsZGtsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwMzExMjksImV4cCI6MjA3MTYwNzEyOX0.PZxoGAnv0UUeCndL9N4yYj0bgoSiDodcDxOPHZQWTxI"
    BUCKET_NAME = "Sushant-KC more"
    
    # Configuration
    HOURS_THRESHOLD = 12  # Delete files added within the last 12 hours
    DRY_RUN = False  # Set to True to preview what would be deleted without actually deleting

    print("\n⚙️  Configuration:")
    print(f"   Time threshold: {HOURS_THRESHOLD} hours")
    print(f"   Dry run mode: {'Yes' if DRY_RUN else 'No'}")
    print()

    # Initialize cleanup tool
    try:
        cleanup = SupabaseAutoCleanup(SUPABASE_URL, SUPABASE_KEY, BUCKET_NAME)
        
        # 1) List recent files
        recent_files = cleanup.get_recent_files(hours=HOURS_THRESHOLD)

        if not recent_files:
            print("\n✅ No recent files found to delete!")
            print(f"   All files in the bucket are older than {HOURS_THRESHOLD} hours")
            return

        # Display numbered list (show song names without extension)
        print("\n📜 Files added within the last 12 hours:")
        for idx, info in enumerate(recent_files, 1):
            display_name = Path(info['name']).stem
            print(f"{idx}. {display_name}")

        # 2) Ask to delete all
        print("\n⚠️  WARNING: This will permanently delete from Supabase!")
        answer = input("Delete ALL of the above? (yes/no): ").strip().lower()

        if answer in ['yes', 'y']:
            cleanup.delete_files(recent_files, dry_run=DRY_RUN)
            return

        # 3) Ask for manual selection when user says no
        print("Type the number(s) to delete (e.g., 2 or 1,3). Press Enter to cancel.")
        selection = input("Number(s) to delete: ").strip()

        if not selection:
            print("❌ Operation cancelled by user")
            return

        # Parse numbers
        try:
            numbers = [int(x) for x in selection.replace(' ', '').split(',') if x]
        except ValueError:
            print("❌ Invalid input. Please enter number(s) like 2 or 1,3")
            return

        # Validate range and build selection
        chosen = []
        for n in numbers:
            if 1 <= n <= len(recent_files):
                chosen.append(recent_files[n - 1])
            else:
                print(f"⚠️  Ignoring invalid number: {n}")

        if not chosen:
            print("❌ Nothing selected to delete")
            return

        # Confirm and delete selected
        names_preview = ', '.join(Path(f['name']).stem for f in chosen)
        confirm_one = input(f"Delete selected: {names_preview}? (yes/no): ").strip().lower()
        if confirm_one not in ['yes', 'y']:
            print("❌ Operation cancelled by user")
            return

        cleanup.delete_files(chosen, dry_run=DRY_RUN)

    except Exception as e:
        print(f"\n💥 Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
