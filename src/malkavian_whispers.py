"""
Malkavian Whisper Manager - Handles custom whisper audio for Malkavian playthroughs
"""
import os
import re
from typing import List, Dict, Optional


class MalkavianWhisper:
    """Represents a single Malkavian whisper slot"""

    def __init__(self, category: str, name: str, text: str, lip_path: str):
        self.category = category
        self.name = name
        self.text = text
        self.lip_path = lip_path
        self.audio_path = None  # Will be set if custom audio exists

    @property
    def display_name(self) -> str:
        """User-friendly display name"""
        return self.name.replace('_', ' ').title()

    @property
    def expected_audio_path(self) -> str:
        """Where the audio file should be placed"""
        return os.path.join(os.path.dirname(self.lip_path), f"{self.name}.wav")

    @property
    def has_audio(self) -> bool:
        """Check if custom audio exists"""
        return self.audio_path is not None and os.path.exists(self.audio_path)


class MalkavianWhisperManager:
    """Manages all Malkavian whispers"""

    def __init__(self, game_directory: str):
        self.game_directory = ""
        self.whispers_dir = ""
        self.set_game_directory(game_directory)
        self.whispers = {}  # category -> List[MalkavianWhisper]

    def set_game_directory(self, game_directory: str):
        """Update the game directory and dependent paths"""
        self.game_directory = game_directory or ""
        if self.game_directory:
            self.whispers_dir = os.path.join(
                self.game_directory,
                "Unofficial_Patch",
                "sound",
                "whispers"
            )
        else:
            self.whispers_dir = ""

    def scan_whispers(self) -> Dict[str, List[MalkavianWhisper]]:
        """
        Scan the whispers directory and load all whisper definitions

        Returns:
            Dictionary mapping category names to lists of whispers
        """
        if not self.whispers_dir or not os.path.exists(self.whispers_dir):
            print(f"Whispers directory not found: {self.whispers_dir}")
            return {}

        self.whispers = {}

        for category in os.listdir(self.whispers_dir):
            category_path = os.path.join(self.whispers_dir, category)

            if not os.path.isdir(category_path):
                continue

            category_whispers = []

            # Find all .lip files in this category
            for file in os.listdir(category_path):
                if not file.endswith('.lip'):
                    continue

                whisper_name = os.path.splitext(file)[0]
                lip_path = os.path.join(category_path, file)

                # Extract text from .lip file
                text = self._extract_text_from_lip(lip_path)

                whisper = MalkavianWhisper(category, whisper_name, text, lip_path)

                # Check if audio exists
                audio_path = whisper.expected_audio_path
                if os.path.exists(audio_path):
                    whisper.audio_path = audio_path

                category_whispers.append(whisper)

            if category_whispers:
                self.whispers[category] = sorted(category_whispers, key=lambda w: w.name)

        return self.whispers

    def _extract_text_from_lip(self, lip_path: str) -> str:
        """
        Extract the whisper text from a .lip file

        Args:
            lip_path: Path to the .lip file

        Returns:
            The whisper text
        """
        try:
            with open(lip_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Look for PLAINTEXT section
            plaintext_match = re.search(r'PLAINTEXT\s*\{([^}]+)\}', content, re.DOTALL)
            if plaintext_match:
                text = plaintext_match.group(1).strip()
                return text

            return "No text found"

        except Exception as e:
            print(f"Error reading {lip_path}: {e}")
            return "Error reading file"

    def add_whisper_audio(self, whisper: MalkavianWhisper, source_audio_path: str) -> bool:
        """
        Add custom audio for a whisper slot with volume normalization

        Args:
            whisper: The whisper to add audio for
            source_audio_path: Path to the audio file to copy

        Returns:
            True if successful
        """
        try:
            # Ensure the audio is .wav format
            if not source_audio_path.lower().endswith('.wav'):
                print(f"Audio must be .wav format, got: {source_audio_path}")
                return False

            # Load and normalize audio
            from pydub import AudioSegment

            print(f"Loading audio: {source_audio_path}")
            audio = AudioSegment.from_wav(source_audio_path)

            # Normalize to -8 dBFS (typical game audio level without clipping)
            target_dBFS = -8.0
            change_in_dBFS = target_dBFS - audio.dBFS
            normalized_audio = audio.apply_gain(change_in_dBFS)

            # Export normalized audio to destination
            dest_path = whisper.expected_audio_path
            normalized_audio.export(dest_path, format="wav")

            whisper.audio_path = dest_path
            print(f"Added whisper audio (normalized to {target_dBFS} dBFS): {dest_path}")
            return True

        except Exception as e:
            print(f"Error adding whisper audio: {e}")
            return False

    def remove_whisper_audio(self, whisper: MalkavianWhisper) -> bool:
        """
        Remove custom audio for a whisper slot

        Args:
            whisper: The whisper to remove audio from

        Returns:
            True if successful
        """
        try:
            if whisper.has_audio:
                os.remove(whisper.audio_path)
                whisper.audio_path = None
                print(f"Removed whisper audio: {whisper.expected_audio_path}")
                return True
            return False

        except Exception as e:
            print(f"Error removing whisper audio: {e}")
            return False

    def get_whisper_count(self) -> Dict[str, int]:
        """
        Get count of whispers per category

        Returns:
            Dictionary mapping category to count
        """
        return {cat: len(whispers) for cat, whispers in self.whispers.items()}

    def get_audio_count(self) -> int:
        """Get total count of whispers with custom audio"""
        return sum(1 for whispers in self.whispers.values()
                  for w in whispers if w.has_audio)

    def edit_whisper_subtitle(self, whisper: MalkavianWhisper, new_text: str) -> bool:
        """
        Edit the subtitle text for a whisper (modifies PLAINTEXT section in .lip file)

        Args:
            whisper: The whisper to edit
            new_text: New subtitle text to display

        Returns:
            True if successful
        """
        try:
            # Read current .lip file content
            with open(whisper.lip_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Replace PLAINTEXT section
            plaintext_match = re.search(r'PLAINTEXT\s*\{([^}]+)\}', content, re.DOTALL)
            if plaintext_match:
                old_plaintext_section = plaintext_match.group(0)
                new_plaintext_section = f"PLAINTEXT\n{{\n{new_text}\n}}"

                new_content = content.replace(old_plaintext_section, new_plaintext_section)

                # Write back to file
                with open(whisper.lip_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)

                # Update whisper object
                whisper.text = new_text
                print(f"Updated subtitle for {whisper.name}: '{new_text}'")
                return True
            else:
                print(f"Could not find PLAINTEXT section in {whisper.lip_path}")
                return False

        except Exception as e:
            print(f"Error editing whisper subtitle: {e}")
            return False
