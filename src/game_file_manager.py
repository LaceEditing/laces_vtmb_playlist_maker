"""
Game file management module for backing up and replacing VTMB audio files
"""
import errno
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from src.utils import SUPPORTED_AUDIO_FORMATS


class GameFileManager:
    """Manages game files, backups, and replacements"""

    def __init__(self, game_directory: str = "", backup_directory: str = "./backups"):
        self.game_directory = game_directory
        self.backup_directory = backup_directory

    def set_game_directory(self, directory: str) -> bool:
        """Set and validate the game directory"""
        if os.path.isdir(directory):
            self.game_directory = directory
            return True
        return False

    def find_audio_files(self, search_patterns: List[str] = None) -> List[str]:
        """
        Find audio files in the game directory

        Args:
            search_patterns: List of patterns to search for (e.g., ['*.mp3', '*.wav'])

        Returns:
            List of file paths relative to game directory
        """
        if not self.game_directory or not os.path.exists(self.game_directory):
            return []

        audio_extensions = SUPPORTED_AUDIO_FORMATS
        found_files = []

        for root, dirs, files in os.walk(self.game_directory):
            for file in files:
                _, ext = os.path.splitext(file.lower())
                if ext in audio_extensions:
                    full_path = os.path.join(root, file)
                    # Get relative path from game directory
                    rel_path = os.path.relpath(full_path, self.game_directory)
                    found_files.append(rel_path)

        return sorted(found_files)

    def backup_file(self, relative_path: str) -> tuple[bool, str]:
        """
        Backup a single game file

        Args:
            relative_path: Path relative to game directory

        Returns:
            Tuple of (success, backup_path or error_message)
        """
        if not self.game_directory:
            return False, "Game directory not set"

        source_path = os.path.join(self.game_directory, relative_path)

        if not os.path.exists(source_path):
            return False, f"Source file not found: {source_path}"

        # Create backup directory structure
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_base = os.path.join(self.backup_directory, timestamp)

        # Preserve directory structure in backup
        backup_path = os.path.join(backup_base, relative_path)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)

        try:
            shutil.copy2(source_path, backup_path)
            return True, backup_path
        except Exception as e:
            return False, f"Backup failed: {str(e)}"

    def backup_all_audio_files(self) -> tuple[bool, str]:
        """
        Backup all audio files in the game directory

        Returns:
            Tuple of (success, message)
        """
        audio_files = self.find_audio_files()

        if not audio_files:
            return False, "No audio files found in game directory"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_base = os.path.join(self.backup_directory, f"full_backup_{timestamp}")

        success_count = 0
        failed_files = []

        for rel_path in audio_files:
            source_path = os.path.join(self.game_directory, rel_path)
            backup_path = os.path.join(backup_base, rel_path)

            os.makedirs(os.path.dirname(backup_path), exist_ok=True)

            try:
                shutil.copy2(source_path, backup_path)
                success_count += 1
            except Exception as e:
                failed_files.append(f"{rel_path}: {str(e)}")

        if failed_files:
            return False, f"Backed up {success_count} files, {len(failed_files)} failed:\n" + "\n".join(failed_files)

        return True, f"Successfully backed up {success_count} audio files to {backup_base}"

    def replace_game_file(self, relative_path: str, new_file_path: str,
                         create_backup: bool = True) -> tuple[bool, str]:
        """
        Replace a game file with a new one

        Args:
            relative_path: Path relative to game directory (the file to replace)
            new_file_path: Path to the new file
            create_backup: Whether to backup the original first

        Returns:
            Tuple of (success, message)
        """
        if not self.game_directory:
            return False, "Game directory not set"

        target_path = os.path.join(self.game_directory, relative_path)

        if not os.path.exists(new_file_path):
            return False, f"New file not found: {new_file_path}"

        # Create backup if requested and file exists
        if create_backup and os.path.exists(target_path):
            success, msg = self.backup_file(relative_path)
            if not success:
                return False, f"Backup failed: {msg}"

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        if os.path.exists(target_path):
            try:
                os.chmod(target_path, 0o666)
            except Exception:
                # If we cannot change permissions, continue anyway
                pass

        last_error = None
        for attempt in range(5):
            try:
                shutil.copy2(new_file_path, target_path)
                return True, f"Successfully replaced {relative_path}"
            except PermissionError as e:
                last_error = e
            except OSError as e:
                if e.errno not in (errno.EACCES, errno.EPERM, errno.EBUSY):
                    return False, f"Failed to replace file: {str(e)}"
                last_error = e
            except Exception as e:
                return False, f"Failed to replace file: {str(e)}"

            # Brief backoff to allow other processes to release the file
            time.sleep(0.3 * (attempt + 1))

        if last_error:
            return False, (
                f"Failed to replace file: {last_error}. "
                "The original file may be in use. Close the game or related applications and try again."
            )

        return False, "Failed to replace file for an unknown reason."

    def restore_from_backup(self, backup_directory: str) -> tuple[bool, str]:
        """
        Restore files from a backup directory

        Args:
            backup_directory: Path to backup directory

        Returns:
            Tuple of (success, message)
        """
        if not self.game_directory:
            return False, "Game directory not set"

        if not os.path.exists(backup_directory):
            return False, f"Backup directory not found: {backup_directory}"

        restored_count = 0
        failed_files = []

        for root, dirs, files in os.walk(backup_directory):
            for file in files:
                backup_file_path = os.path.join(root, file)
                rel_path = os.path.relpath(backup_file_path, backup_directory)
                target_path = os.path.join(self.game_directory, rel_path)

                os.makedirs(os.path.dirname(target_path), exist_ok=True)

                try:
                    shutil.copy2(backup_file_path, target_path)
                    restored_count += 1
                except Exception as e:
                    failed_files.append(f"{rel_path}: {str(e)}")

        if failed_files:
            return False, f"Restored {restored_count} files, {len(failed_files)} failed:\n" + "\n".join(failed_files)

        return True, f"Successfully restored {restored_count} files from backup"

    def list_backups(self) -> List[dict]:
        """
        List available backups

        Returns:
            List of backup info dictionaries
        """
        if not os.path.exists(self.backup_directory):
            return []

        backups = []
        for item in os.listdir(self.backup_directory):
            backup_path = os.path.join(self.backup_directory, item)
            if os.path.isdir(backup_path):
                stat = os.stat(backup_path)
                backups.append({
                    'name': item,
                    'path': backup_path,
                    'created': datetime.fromtimestamp(stat.st_ctime),
                    'size': self._get_directory_size(backup_path)
                })

        return sorted(backups, key=lambda x: x['created'], reverse=True)

    def _get_directory_size(self, path: str) -> int:
        """Get total size of a directory in bytes"""
        total = 0
        try:
            for root, dirs, files in os.walk(path):
                for file in files:
                    filepath = os.path.join(root, file)
                    if os.path.exists(filepath):
                        total += os.path.getsize(filepath)
        except Exception:
            pass
        return total

    def validate_game_directory(self, directory: str) -> tuple[bool, str]:
        """
        Validate if a directory is a valid VTMB game directory

        Returns:
            Tuple of (is_valid, message)
        """
        if not os.path.exists(directory):
            return False, "Directory does not exist"

        if not os.path.isdir(directory):
            return False, "Path is not a directory"

        # Look for common VTMB files/folders
        # Note: Users can override this, but we'll provide helpful validation
        common_indicators = [
            'vampire.exe',
            'Vampire',
            'sound',
            'music'
        ]

        found_indicators = []
        for indicator in common_indicators:
            check_path = os.path.join(directory, indicator)
            if os.path.exists(check_path):
                found_indicators.append(indicator)

        if found_indicators:
            return True, f"Looks like a game directory (found: {', '.join(found_indicators)})"

        return True, "Directory exists (couldn't confirm it's VTMB, but you can proceed)"
