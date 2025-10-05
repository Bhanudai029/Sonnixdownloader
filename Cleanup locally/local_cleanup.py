#!/usr/bin/env python3
"""
Local Cleanup Script
Automatically delete all images and audio files from local directories
"""

import os
from pathlib import Path
from datetime import datetime

class LocalCleanup:
    def __init__(self, directories: list):
        """
        Initialize cleanup tool with directories to clean
        
        Args:
            directories: List of directory paths to clean
        """
        self.directories = [Path(d) for d in directories]
        self.total_files = 0
        self.total_size = 0
        
    def get_all_files(self):
        """
        Get all files from specified directories
        
        Returns:
            dict: Dictionary with directory as key and list of files as value
        """
        all_files = {}
        
        print("🔍 Scanning directories for files...")
        print("=" * 60)
        
        for directory in self.directories:
            if not directory.exists():
                print(f"⚠️  Directory not found: {directory}")
                continue
            
            if not directory.is_dir():
                print(f"⚠️  Not a directory: {directory}")
                continue
            
            # Get all files in directory
            files = []
            for file_path in directory.iterdir():
                if file_path.is_file():
                    files.append(file_path)
                    self.total_files += 1
                    self.total_size += file_path.stat().st_size
            
            all_files[directory] = files
            print(f"📁 {directory.name}: {len(files)} file(s)")
        
        print("=" * 60)
        print(f"📊 Total files found: {self.total_files}")
        print(f"💾 Total size: {self.format_size(self.total_size)}")
        
        return all_files
    
    def format_size(self, size_bytes: int) -> str:
        """
        Format file size in human-readable format
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            str: Formatted size string
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
    
    def list_files_preview(self, all_files: dict, max_preview: int = 10):
        """
        Show a preview of files that will be deleted
        
        Args:
            all_files: Dictionary of directory to files mapping
            max_preview: Maximum number of files to preview per directory
        """
        print("\n📋 Files to be deleted (preview):")
        print("=" * 60)
        
        for directory, files in all_files.items():
            if not files:
                continue
                
            print(f"\n📂 {directory}:")
            
            # Show up to max_preview files
            for i, file_path in enumerate(files[:max_preview], 1):
                size = file_path.stat().st_size
                modified_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                print(f"   {i}. {file_path.name}")
                print(f"      Size: {self.format_size(size)} | Modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Show how many more files
            if len(files) > max_preview:
                remaining = len(files) - max_preview
                print(f"   ... and {remaining} more file(s)")
    
    def delete_all_files(self, all_files: dict, dry_run: bool = False):
        """
        Delete all files from directories
        
        Args:
            all_files: Dictionary of directory to files mapping
            dry_run: If True, only show what would be deleted
            
        Returns:
            tuple: (success_count, failed_count)
        """
        if self.total_files == 0:
            print("\n✅ No files to delete!")
            return 0, 0
        
        print(f"\n{'🔍 DRY RUN - Would delete' if dry_run else '🗑️  Deleting'} {self.total_files} file(s)...")
        print("=" * 60)
        
        success_count = 0
        failed_count = 0
        freed_space = 0
        
        for directory, files in all_files.items():
            if not files:
                continue
            
            print(f"\n📂 Processing: {directory.name}")
            
            for i, file_path in enumerate(files, 1):
                try:
                    file_size = file_path.stat().st_size
                    
                    if dry_run:
                        print(f"   [{i}/{len(files)}] Would delete: {file_path.name} ({self.format_size(file_size)})")
                        success_count += 1
                        freed_space += file_size
                    else:
                        print(f"   [{i}/{len(files)}] Deleting: {file_path.name} ({self.format_size(file_size)})", end="")
                        file_path.unlink()
                        print(" ✅")
                        success_count += 1
                        freed_space += file_size
                        
                except Exception as e:
                    print(f" ❌")
                    print(f"      Error: {str(e)}")
                    failed_count += 1
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 CLEANUP SUMMARY")
        print("=" * 60)
        
        if dry_run:
            print(f"✓ Would delete: {success_count} file(s)")
            print(f"✓ Would free: {self.format_size(freed_space)}")
        else:
            print(f"✅ Successfully deleted: {success_count}/{self.total_files}")
            print(f"❌ Failed: {failed_count}")
            print(f"💾 Space freed: {self.format_size(freed_space)}")
        
        return success_count, failed_count
    
    def cleanup(self, dry_run: bool = False, show_preview: bool = True):
        """
        Main cleanup function
        
        Args:
            dry_run: If True, only show what would be deleted
            show_preview: If True, show preview of files before deleting
        """
        print("🧹" + "=" * 60)
        print("      LOCAL CLEANUP TOOL")
        print("=" * 60 + "🧹")
        print()
        
        if dry_run:
            print("⚠️  DRY RUN MODE - No files will actually be deleted")
            print()
        
        # Get all files
        all_files = self.get_all_files()
        
        if self.total_files == 0:
            print("\n✅ No files found to delete!")
            return
        
        # Show preview if requested
        if show_preview:
            self.list_files_preview(all_files)
        
        # Delete files
        success, failed = self.delete_all_files(all_files, dry_run)
        
        if not dry_run and success > 0:
            print(f"\n🎉 Cleanup complete! Deleted {success} file(s)")


def main():
    """Main function"""
    # Directories to clean
    DIRECTORIES_TO_CLEAN = [
        r"C:\Users\baral\OneDrive\Desktop\yt final\thumbnails",
        r"C:\Users\baral\OneDrive\Desktop\yt final\Audios"
    ]
    
    # Configuration
    DRY_RUN = False  # Set to True to preview what would be deleted without actually deleting
    SHOW_PREVIEW = True  # Set to True to show preview of files before deleting
    
    print("\n⚙️  Configuration:")
    print(f"   Directories to clean:")
    for directory in DIRECTORIES_TO_CLEAN:
        print(f"      - {directory}")
    print(f"   Dry run mode: {'Yes' if DRY_RUN else 'No'}")
    print(f"   Show preview: {'Yes' if SHOW_PREVIEW else 'No'}")
    print()
    
    # Initialize cleanup tool
    cleanup = LocalCleanup(DIRECTORIES_TO_CLEAN)
    
    # Get file count first for confirmation
    temp_files = cleanup.get_all_files()
    
    if cleanup.total_files == 0:
        print("\n✅ No files to delete!")
        return
    
    # Confirmation prompt if not in dry run mode
    if not DRY_RUN:
        print("\n⚠️  WARNING: This will permanently delete all files in the specified directories!")
        confirmation = input(f"\n   Delete {cleanup.total_files} file(s) ({cleanup.format_size(cleanup.total_size)})? (yes/no): ").strip().lower()
        
        if confirmation not in ['yes', 'y']:
            print("❌ Operation cancelled by user")
            return
        
        print("\n🚀 Starting cleanup...\n")
    
    # Run cleanup
    try:
        # Create new instance to reset counters
        cleanup = LocalCleanup(DIRECTORIES_TO_CLEAN)
        cleanup.cleanup(dry_run=DRY_RUN, show_preview=SHOW_PREVIEW)
        
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user (Ctrl+C)")
    except Exception as e:
        print(f"\n💥 Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
