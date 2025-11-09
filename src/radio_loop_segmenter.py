"""
Radio Loop Segmenter - Analyzes and splits radio loops into editable segments
"""
import os
import json
from typing import List, Dict, Optional
from pydub import AudioSegment
from pydub.silence import detect_silence
from src.radio_segments_manual import get_manual_segments


class RadioLoopSegment:
    """Represents a single segment within a radio loop"""

    def __init__(self, loop_name: str, index: int, segment_type: str, label: str,
                 start_sec: float, end_sec: float, duration_sec: float,
                 start_ms: int, end_ms: int,
                 original_start_sec: float = None, original_end_sec: float = None,
                 original_duration_sec: float = None,
                 original_start_ms: int = None, original_end_ms: int = None):
        self.loop_name = loop_name  # e.g., "radio_loop_1"
        self.index = index
        self.segment_type = segment_type  # 'jingle', 'commercial', 'dialogue'
        self.label = label  # Human-readable label
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.duration_sec = duration_sec
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.cached_audio_path = None  # Path to extracted segment audio file

        # Preserve original timing data separately so we can always reference the untouched loop
        self.original_start_sec = start_sec if original_start_sec is None else original_start_sec
        self.original_end_sec = end_sec if original_end_sec is None else original_end_sec
        self.original_duration_sec = duration_sec if original_duration_sec is None else original_duration_sec
        self.original_start_ms = start_ms if original_start_ms is None else original_start_ms
        self.original_end_ms = end_ms if original_end_ms is None else original_end_ms
        self.original_missing = False

    @property
    def unique_id(self) -> str:
        """Unique identifier for this segment"""
        return f"{self.loop_name}_seg_{self.index:02d}_{self.segment_type}"

    @property
    def track_filename(self) -> str:
        """Filename to show in the GUI as if it's a separate track"""
        return f"{self.loop_name}_segment_{self.index:02d}.mp3"

    @property
    def display_name(self) -> str:
        """Display name for GUI"""
        loop_num = self.loop_name.replace('radio_loop_', '')
        type_icon = {
            'jingle': '🎵',
            'commercial': '📻',
            'dialogue': '🗣️',
            'political': '🎙️',
            'radio_content': '📡',
            'music': '🎸'
        }.get(self.segment_type, '🎙️')

        # Use the actual label if available, otherwise fall back to generic label
        if self.label:
            return f"Radio Loop {loop_num} - {type_icon} {self.label} ({int(self.duration_sec)}s)"
        else:
            type_label = {
                'jingle': 'Jingle',
                'commercial': 'Commercial',
                'dialogue': 'Deb Dialogue',
                'political': 'Political Ad',
                'radio_content': 'Radio Content',
                'music': 'Music Track'
            }.get(self.segment_type, 'Segment')
            return f"Radio Loop {loop_num} - {type_icon} {type_label} #{self.index + 1} ({int(self.duration_sec)}s)"

    def to_dict(self) -> dict:
        return {
            'loop_name': self.loop_name,
            'index': self.index,
            'segment_type': self.segment_type,
            'label': self.label,
            'start_sec': self.start_sec,
            'end_sec': self.end_sec,
            'duration_sec': self.duration_sec,
            'start_ms': self.start_ms,
            'end_ms': self.end_ms,
            'original_start_sec': self.original_start_sec,
            'original_end_sec': self.original_end_sec,
            'original_duration_sec': self.original_duration_sec,
            'original_start_ms': self.original_start_ms,
            'original_end_ms': self.original_end_ms,
            'unique_id': self.unique_id,
            'track_filename': self.track_filename,
            'display_name': self.display_name
        }

    @classmethod
    def from_dict(cls, data: dict):
        original_start_ms = data.get('original_start_ms')
        original_end_ms = data.get('original_end_ms')
        original_start_sec = data.get('original_start_sec')
        original_end_sec = data.get('original_end_sec')
        original_duration_sec = data.get('original_duration_sec')

        segment = cls(
            loop_name=data['loop_name'],
            index=data['index'],
            segment_type=data['segment_type'],
            label=data['label'],
            start_sec=data['start_sec'],
            end_sec=data['end_sec'],
            duration_sec=data['duration_sec'],
            start_ms=data['start_ms'],
            end_ms=data['end_ms'],
            original_start_sec=original_start_sec,
            original_end_sec=original_end_sec,
            original_duration_sec=original_duration_sec,
            original_start_ms=original_start_ms,
            original_end_ms=original_end_ms
        )

        if original_start_ms is None or original_end_ms is None:
            segment.original_missing = True

        return segment


class RadioLoopSegmenter:
    """Analyzes radio loop files and extracts segment information"""

    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_cache_path(self, loop_filename: str) -> str:
        """Get cache file path for a radio loop"""
        base_name = os.path.splitext(loop_filename)[0]
        return os.path.join(self.cache_dir, f"{base_name}_segments.json")

    def analyze_radio_loop(self, audio_path: str) -> List[RadioLoopSegment]:
        """
        Analyze a radio loop file and detect segments

        Args:
            audio_path: Path to the radio loop MP3 file

        Returns:
            List of RadioLoopSegment objects
        """
        loop_filename = os.path.basename(audio_path)
        loop_name = os.path.splitext(loop_filename)[0]

        print(f"Analyzing radio loop: {loop_filename}")

        audio = None
        duration_ms = None

        # Check cache first
        cache_path = self.get_cache_path(loop_filename)
        if os.path.exists(cache_path):
            print(f"  Loading from cache: {cache_path}")
            segments = self.load_segments_from_cache(cache_path)

            # Older cache files might not include original timing data
            if any(getattr(seg, "original_missing", False) for seg in segments):
                if audio is None:
                    audio = AudioSegment.from_file(audio_path)
                    duration_ms = len(audio)

                manual_segments_data = get_manual_segments(loop_name, duration_ms)
                if manual_segments_data:
                    manual_map = {seg_data['index']: seg_data for seg_data in manual_segments_data}
                    for segment in segments:
                        manual = manual_map.get(segment.index)
                        if manual:
                            segment.original_start_sec = manual['start_sec']
                            segment.original_end_sec = manual['end_sec']
                            segment.original_duration_sec = manual['duration_sec']
                            segment.original_start_ms = manual['start_ms']
                            segment.original_end_ms = manual['end_ms']
                            segment.original_missing = False

                    # Persist upgraded cache so future runs have complete data
                    self.save_segments_to_cache(segments, cache_path)

            return segments

        # Analyze the audio
        if audio is None:
            audio = AudioSegment.from_file(audio_path)
            duration_ms = len(audio)

        duration_sec = duration_ms / 1000

        print(f"  Duration: {duration_sec:.1f}s ({duration_sec/60:.1f} minutes)")

        # Try manual segments first
        manual_segments_data = get_manual_segments(loop_name, duration_ms)

        if manual_segments_data:
            print(f"  Using MANUAL segment data ({len(manual_segments_data)} segments)")
            segments = []

            for seg_data in manual_segments_data:
                segment = RadioLoopSegment(
                    loop_name=loop_name,
                    index=seg_data['index'],
                    segment_type=seg_data['segment_type'],
                    label=seg_data['label'],
                    start_sec=seg_data['start_sec'],
                    end_sec=seg_data['end_sec'],
                    duration_sec=seg_data['duration_sec'],
                    start_ms=seg_data['start_ms'],
                    end_ms=seg_data['end_ms']
                )
                segments.append(segment)

        else:
            # Fall back to automatic detection
            print(f"  No manual data found, using AUTOMATIC detection...")

            # Detect silence boundaries (1+ second silences)
            silence_thresh = audio.dBFS - 14
            min_silence_len = 1000  # 1 second

            silent_ranges = detect_silence(
                audio,
                min_silence_len=min_silence_len,
                silence_thresh=silence_thresh,
                seek_step=50
            )

            # Build segments from silence ranges
            segments = []
            last_end = 0

            for start, end in silent_ranges:
                if last_end < start:
                    segment_start = last_end / 1000
                    segment_end = start / 1000
                    duration = segment_end - segment_start

                    # Classify segment type by duration
                    if duration < 15:
                        seg_type = 'jingle'
                        label = f"Jingle {len(segments) + 1}"
                    elif duration < 60:
                        seg_type = 'commercial'
                        label = f"Commercial {len(segments) + 1}"
                    else:
                        seg_type = 'dialogue'
                        label = f"Deb Dialogue {len(segments) + 1}"

                    segment = RadioLoopSegment(
                        loop_name=loop_name,
                        index=len(segments),
                        segment_type=seg_type,
                        label=label,
                        start_sec=segment_start,
                        end_sec=segment_end,
                        duration_sec=duration,
                        start_ms=last_end,
                        end_ms=start
                    )

                    segments.append(segment)

                last_end = end

            # Last segment
            if last_end < len(audio):
                segment_start = last_end / 1000
                segment_end = len(audio) / 1000
                duration = segment_end - segment_start

                if duration < 15:
                    seg_type = 'jingle'
                    label = f"Jingle {len(segments) + 1}"
                elif duration < 60:
                    seg_type = 'commercial'
                    label = f"Commercial {len(segments) + 1}"
                else:
                    seg_type = 'dialogue'
                    label = f"Deb Dialogue {len(segments) + 1}"

                segment = RadioLoopSegment(
                    loop_name=loop_name,
                    index=len(segments),
                    segment_type=seg_type,
                    label=label,
                    start_sec=segment_start,
                    end_sec=segment_end,
                    duration_sec=duration,
                    start_ms=last_end,
                    end_ms=len(audio)
                )

                segments.append(segment)

        print(f"  Detected {len(segments)} segments")

        # Save to cache
        self.save_segments_to_cache(segments, cache_path)

        return segments

    def save_segments_to_cache(self, segments: List[RadioLoopSegment], cache_path: str):
        """Save segment data to cache file"""
        data = {
            'loop_name': segments[0].loop_name if segments else None,
            'total_segments': len(segments),
            'cache_version': 2,
            'segments': [seg.to_dict() for seg in segments]
        }

        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"  Cached to: {cache_path}")

    def load_segments_from_cache(self, cache_path: str) -> List[RadioLoopSegment]:
        """Load segments from cache file"""
        with open(cache_path, 'r') as f:
            data = json.load(f)

        return [RadioLoopSegment.from_dict(seg_data) for seg_data in data['segments']]

    def extract_segment_audio(self, audio_path: str, segment: RadioLoopSegment) -> AudioSegment:
        """
        Extract a specific segment's audio from the radio loop

        Args:
            audio_path: Path to the radio loop MP3
            segment: RadioLoopSegment to extract

        Returns:
            AudioSegment containing just that segment
        """
        audio = AudioSegment.from_file(audio_path)
        return audio[segment.start_ms:segment.end_ms]

    def reassemble_radio_loop(self, original_audio_path: str, segments: List[RadioLoopSegment],
                              replacements: Dict[str, AudioSegment]) -> AudioSegment:
        """
        Reassemble a radio loop with segment replacements

        Args:
            original_audio_path: Path to original radio loop
            segments: List of all segments in order
            replacements: Dict mapping segment unique_id to replacement AudioSegment

        Returns:
            Complete reassembled AudioSegment
        """
        print(f"Reassembling radio loop: {os.path.basename(original_audio_path)}")

        original_audio = AudioSegment.from_file(original_audio_path)
        combined = AudioSegment.empty()

        for segment in segments:
            if segment.unique_id in replacements:
                # Use replacement audio
                replacement = replacements[segment.unique_id]
                print(f"  [{segment.index}] Using REPLACEMENT: {segment.label} ({len(replacement)/1000:.1f}s)")
                combined += replacement
            else:
                # Use original segment
                original_segment = original_audio[segment.original_start_ms:segment.original_end_ms]
                print(f"  [{segment.index}] Using ORIGINAL: {segment.label} ({len(original_segment)/1000:.1f}s)")
                combined += original_segment

        print(f"  Total reassembled duration: {len(combined)/1000:.1f}s")
        return combined

    def calculate_new_segment_timings(self, segments: List[RadioLoopSegment],
                                      replacements: Dict[str, AudioSegment],
                                      original_audio_path: str) -> List[dict]:
        """
        Calculate new segment timings after reassembly with replacements

        Args:
            segments: Original segment list
            replacements: Dict mapping segment unique_id to replacement AudioSegment
            original_audio_path: Path to original loop (for extracting original durations)

        Returns:
            List of dicts with new start_ms, end_ms for each segment in order
        """
        original_audio = AudioSegment.from_file(original_audio_path)
        new_timings = []
        current_position_ms = 0

        for segment in segments:
            if segment.unique_id in replacements:
                # Use replacement duration
                duration_ms = len(replacements[segment.unique_id])
            else:
                # Use original segment duration
                original_segment = original_audio[segment.original_start_ms:segment.original_end_ms]
                duration_ms = len(original_segment)

            new_timings.append({
                'index': segment.index,
                'label': segment.label,
                'start_ms': current_position_ms,
                'end_ms': current_position_ms + duration_ms,
                'duration_ms': duration_ms
            })

            current_position_ms += duration_ms

        return new_timings
