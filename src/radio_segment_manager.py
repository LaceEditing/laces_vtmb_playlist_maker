"""
Radio Segment Manager - Manages radio loop segment metadata and assignments
"""
import os
import json
from typing import Dict, List, Optional
from src.radio_loop_segmenter import RadioLoopSegment, RadioLoopSegmenter


class RadioSegmentManager:
    """Manages segment metadata for all radio loops"""

    def __init__(self, game_directory: str):
        self.segmenter = RadioLoopSegmenter()
        self.segments_by_loop = {}  # loop_name -> List[RadioLoopSegment]
        self.segment_map = {}  # unique_id -> RadioLoopSegment
        self.segment_cache_dir = os.path.join("cache", "radio_segments")
        os.makedirs(self.segment_cache_dir, exist_ok=True)
        self.set_game_directory(game_directory)

    def set_game_directory(self, game_directory: str):
        """Update the game directory used for lookups"""
        self.game_directory = game_directory or ""

    def scan_radio_loops(self, radio_dir: str) -> List[RadioLoopSegment]:
        """
        Scan all radio loop files in a directory and detect segments

        Args:
            radio_dir: Path to radio directory

        Returns:
            Flat list of all segments from all loops
        """
        all_segments = []

        if not os.path.exists(radio_dir):
            return all_segments

        from pydub import AudioSegment as PyDubSegment

        # Find all radio_loop_*.mp3 files
        for filename in os.listdir(radio_dir):
            if filename.lower().startswith('radio_loop_') and filename.lower().endswith('.mp3'):
                audio_path = os.path.join(radio_dir, filename)

                # Analyze this loop
                segments = self.segmenter.analyze_radio_loop(audio_path)

                loop_name = os.path.splitext(filename)[0]
                self.segments_by_loop[loop_name] = segments

                # Load the full loop audio for extraction
                print(f"  Extracting segments from {loop_name}...")
                full_loop = PyDubSegment.from_file(audio_path)

                # Extract and cache each segment
                for segment in segments:
                    # Extract this segment's audio
                    segment_audio = full_loop[segment.start_ms:segment.end_ms]

                    # Create a descriptive cached filename
                    cached_filename = self._get_cached_segment_filename(segment)
                    cached_path = os.path.join(self.segment_cache_dir, cached_filename)

                    # Export the segment to cache with retry logic for file locks
                    import time
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            segment_audio.export(
                                cached_path,
                                format='mp3',
                                bitrate='128k',
                                parameters=["-ar", str(full_loop.frame_rate)]
                            )
                            break  # Success!
                        except PermissionError as e:
                            if attempt < max_retries - 1:
                                # File might be locked, wait a moment and retry
                                print(f"    Cache file locked, retrying ({attempt + 1}/{max_retries})...")
                                time.sleep(0.5)
                            else:
                                # Final attempt failed, skip this segment cache
                                print(f"    Warning: Could not cache {cached_filename} (file locked)")
                                cached_path = None  # Mark as uncached
                                break

                    # Store the cached path in the segment
                    segment.cached_audio_path = cached_path

                    all_segments.append(segment)
                    self.segment_map[segment.unique_id] = segment

        print(f"  Cached {len(all_segments)} individual segments")
        return all_segments

    def _get_cached_segment_filename(self, segment: RadioLoopSegment) -> str:
        """
        Generate a descriptive filename for a cached segment

        Returns something like:
        - "Loop1_Deb1_169s.mp3"
        - "Loop2_Commercial_Butter_31s.mp3"
        - "Loop3_Political_RobertThorn_57s.mp3"
        """
        loop_num = segment.loop_name.replace('radio_loop_', '')

        # Use label if available for more descriptive names
        if segment.label:
            # Clean label for filename (remove spaces and special chars)
            clean_label = segment.label.replace(' ', '').replace("'", "").replace('(', '').replace(')', '').replace('-', '')
            filename = f"Loop{loop_num}_{clean_label}_{int(segment.duration_sec)}s.mp3"
        else:
            # Fall back to type-based naming
            if segment.segment_type == 'dialogue':
                type_name = 'DebDialogue'
            elif segment.segment_type == 'commercial':
                type_name = 'Commercial'
            elif segment.segment_type == 'political':
                type_name = 'Political'
            elif segment.segment_type == 'radio_content':
                type_name = 'RadioContent'
            elif segment.segment_type == 'music':
                type_name = 'Music'
            else:  # jingle
                type_name = 'Jingle'

            filename = f"Loop{loop_num}_{type_name}_{segment.index + 1}_{int(segment.duration_sec)}s.mp3"

        return filename

    def get_segment_by_id(self, unique_id: str) -> Optional[RadioLoopSegment]:
        """Get a segment by its unique ID"""
        return self.segment_map.get(unique_id)

    def get_loop_segments(self, loop_name: str) -> List[RadioLoopSegment]:
        """Get all segments for a specific radio loop"""
        return self.segments_by_loop.get(loop_name, [])

    def get_original_loop_path(self, loop_name: str) -> str:
        """
        Get the path to the original radio loop file

        Args:
            loop_name: e.g., "radio_loop_1"

        Returns:
            Full path to the loop file
        """
        # Check Unofficial Patch first
        unofficial_path = os.path.join(
            self.game_directory,
            "Unofficial_Patch", "sound", "radio",
            f"{loop_name}.mp3"
        )
        if os.path.exists(unofficial_path):
            return unofficial_path

        # Check base game
        base_path = os.path.join(
            self.game_directory,
            "Vampire", "sound", "radio",
            f"{loop_name}.mp3"
        )
        if os.path.exists(base_path):
            return base_path

        return None

    def get_segment_game_path(self, segment: RadioLoopSegment) -> str:
        """
        Get the game file path for this segment (virtual path)

        This creates a virtual path that the playlist system can reference
        Format: "Vampire\\sound\\radio\\radio_loop_1\\segment_05.virtual"
        """
        return os.path.join(
            "Vampire", "sound", "radio",
            segment.loop_name,
            f"segment_{segment.index:02d}.virtual"
        )
