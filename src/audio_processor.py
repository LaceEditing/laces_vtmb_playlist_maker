"""
Audio processing module for creating and managing playlists
"""
import os
import shutil
import subprocess
import sys
import random
from typing import List, Tuple
from pydub import AudioSegment
from pydub.utils import mediainfo
from src.models import AudioFile, Playlist, PlaybackMode
from src.utils import SUPPORTED_AUDIO_FORMATS


# Module-level FFmpeg availability flag
_ffmpeg_available = None


def get_ffmpeg_path():
    """
    Get the path to FFmpeg executable.
    Handles both development and bundled (PyInstaller) environments.
    """
    # Check if we're running as a bundled executable
    if getattr(sys, 'frozen', False):
        # Running as bundled executable
        bundle_dir = sys._MEIPASS

        # Check for FFmpeg in the bundle
        if sys.platform == 'win32':
            ffmpeg_path = os.path.join(bundle_dir, 'ffmpeg', 'bin', 'ffmpeg.exe')
            ffprobe_path = os.path.join(bundle_dir, 'ffmpeg', 'bin', 'ffprobe.exe')
        else:
            ffmpeg_path = os.path.join(bundle_dir, 'ffmpeg', 'ffmpeg')
            ffprobe_path = os.path.join(bundle_dir, 'ffmpeg', 'ffprobe')

        if os.path.exists(ffmpeg_path):
            # Set AudioSegment to use bundled FFmpeg
            AudioSegment.converter = ffmpeg_path
            AudioSegment.ffmpeg = ffmpeg_path
            AudioSegment.ffprobe = ffprobe_path
            return ffmpeg_path

    # Running in development mode or FFmpeg is in PATH
    # AudioSegment will use system FFmpeg
    return None


def check_ffmpeg_available():
    """Check if FFmpeg is actually callable. Returns (available, message)."""
    global _ffmpeg_available

    # Use the converter path pydub will use
    ffmpeg_cmd = getattr(AudioSegment, 'converter', None) or shutil.which('ffmpeg')
    if not ffmpeg_cmd:
        _ffmpeg_available = False
        return False, (
            "FFmpeg not found. It may be missing from the installation or blocked by your antivirus.\n"
            "Audio processing features require FFmpeg to work."
        )

    try:
        result = subprocess.run(
            [ffmpeg_cmd, '-version'],
            capture_output=True, timeout=10
        )
        _ffmpeg_available = result.returncode == 0
        if _ffmpeg_available:
            return True, "FFmpeg is available"
        else:
            return False, "FFmpeg was found but returned an error when tested."
    except FileNotFoundError:
        _ffmpeg_available = False
        return False, (
            "FFmpeg not found. It may be missing from the installation or blocked by your antivirus.\n"
            "Audio processing features require FFmpeg to work."
        )
    except Exception as e:
        _ffmpeg_available = False
        return False, f"FFmpeg check failed: {e}"


def is_ffmpeg_available():
    """Return cached FFmpeg availability status."""
    global _ffmpeg_available
    if _ffmpeg_available is None:
        available, _ = check_ffmpeg_available()
        return available
    return _ffmpeg_available


# Initialize FFmpeg path on module load
get_ffmpeg_path()


class AudioProcessor:
    """Handles audio file processing and playlist generation"""

    def __init__(self):
        self.supported_formats = list(SUPPORTED_AUDIO_FORMATS)

    def get_audio_duration(self, filepath: str) -> float:
        """Get duration of an audio file in seconds"""
        try:
            audio = AudioSegment.from_file(filepath)
            return len(audio) / 1000.0  # Convert milliseconds to seconds
        except Exception as e:
            print(f"Error getting duration for {filepath}: {e}")
            return 0.0

    def is_supported_format(self, filepath: str) -> bool:
        """Check if the file format is supported"""
        _, ext = os.path.splitext(filepath.lower())
        return ext in self.supported_formats

    def create_playlist_audio(self, playlist: Playlist, output_path: str,
                            target_duration: int = None, original_file_path: str = None) -> bool:
        """
        Create a single audio file from playlist

        Args:
            playlist: Playlist object containing audio files
            output_path: Where to save the generated audio
            target_duration: Target duration in seconds (None = concatenate once without looping)
            original_file_path: Path to original game file to match audio properties

        Returns:
            True if successful, False otherwise
        """
        if not playlist.audio_files:
            print(f"Playlist '{playlist.name}' has no audio files")
            return False

        try:
            # Prepare audio segments and normalize sample rates
            audio_segments = []
            target_sample_rate = 44100  # Standard sample rate for game audio
            target_channels = 2  # Stereo

            original_audio_source = None
            if original_file_path:
                import glob
                backup_dirs = []
                if os.path.exists("./backups"):
                    backup_dirs = sorted(glob.glob("./backups/*"), reverse=True)

                for backup_dir in backup_dirs:
                    for root, dirs, files in os.walk(backup_dir):
                        for file in files:
                            full_backup_path = os.path.join(root, file)
                            if os.path.basename(original_file_path).lower() == file.lower():
                                if os.path.basename(os.path.dirname(original_file_path)).lower() in root.lower():
                                    original_audio_source = full_backup_path
                                    break
                        if original_audio_source:
                            break
                    if original_audio_source:
                        break

                if not original_audio_source and os.path.exists(original_file_path):
                    original_audio_source = original_file_path

            if original_audio_source:
                try:
                    original_audio = AudioSegment.from_file(original_audio_source)
                    target_sample_rate = original_audio.frame_rate
                    target_channels = original_audio.channels
                    print(f"Matching properties: {target_sample_rate} Hz, {target_channels} channels")
                except Exception as e:
                    print(f"Warning: Could not read original file properties, using defaults")
            else:
                print(f"Using standard properties: {target_sample_rate} Hz, {target_channels} channels")

            # Load and convert all audio files
            for audio_file in playlist.audio_files:
                if not os.path.exists(audio_file.path):
                    print(f"Warning: File not found: {audio_file.path}")
                    continue

                try:
                    segment = AudioSegment.from_file(audio_file.path)

                    segment_target_dBFS = -12.0
                    segment_gain = segment_target_dBFS - segment.dBFS
                    segment = segment.apply_gain(segment_gain)

                    if segment.channels != target_channels:
                        segment = segment.set_channels(target_channels)

                    if segment.frame_rate != target_sample_rate:
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                            tmp_path = tmp.name
                        try:
                            segment.export(tmp_path, format='wav', parameters=['-ar', str(target_sample_rate)])
                            segment = AudioSegment.from_file(tmp_path)
                        finally:
                            try:
                                os.unlink(tmp_path)
                            except:
                                pass

                    audio_segments.append(segment)
                except Exception as e:
                    print(f"Error loading {audio_file.path}: {e}")
                    continue

            if not audio_segments:
                print("No valid audio files to process")
                return False

            # Generate playlist based on playback mode
            final_audio = self._generate_audio_sequence(
                audio_segments,
                playlist.playback_mode,
                target_duration
            )

            target_dBFS = -8.0
            change_in_dBFS = target_dBFS - final_audio.dBFS
            final_audio = final_audio.apply_gain(change_in_dBFS)

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            _, ext = os.path.splitext(output_path.lower())
            format_name = ext[1:] if ext else 'mp3'

            export_params = {
                'format': format_name,
                'bitrate': '128k',
                'parameters': [
                    "-ar", str(target_sample_rate),
                    "-write_xing", "0",
                ]
            }

            print(f"Creating playlist audio: {len(final_audio)/1000:.1f}s at {target_sample_rate} Hz")
            final_audio.export(output_path, **export_params)
            print(f"Successfully created: {output_path}")

            return True

        except Exception as e:
            print(f"Error creating playlist audio: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _generate_audio_sequence(self, segments: List[AudioSegment],
                                 playback_mode: str,
                                 target_duration: int) -> AudioSegment:
        """
        Generate audio sequence based on playback mode

        Args:
            segments: List of audio segments
            playback_mode: How to arrange the segments
            target_duration: Target duration in seconds (None = just concatenate once)

        Returns:
            Combined AudioSegment
        """
        if not segments:
            return AudioSegment.empty()

        # Build the sequence list first, then concatenate once
        sequence = []

        # If no target duration, just concatenate songs once in the specified mode
        if target_duration is None:
            if playback_mode == PlaybackMode.SHUFFLE.value:
                # Shuffle once
                sequence = segments.copy()
                random.shuffle(sequence)
            elif playback_mode == PlaybackMode.RANDOM.value:
                # Random mode without target duration doesn't make sense
                # Just shuffle instead (same as shuffle for one iteration)
                sequence = segments.copy()
                random.shuffle(sequence)
            else:  # SEQUENTIAL
                # Keep original order
                sequence = segments.copy()
        else:
            # Original behavior: loop to fill target duration
            target_ms = target_duration * 1000
            cycle_duration = sum(len(seg) for seg in segments)
            if cycle_duration == 0:
                return AudioSegment.empty()

            # Calculate approximately how many complete cycles we need
            num_cycles = max(1, int((target_ms / cycle_duration) + 1))

            if playback_mode == PlaybackMode.RANDOM.value:
                # Randomly select segments
                current_duration = 0
                while current_duration < target_ms:
                    segment = random.choice(segments)
                    sequence.append(segment)
                    current_duration += len(segment)

            elif playback_mode == PlaybackMode.SHUFFLE.value:
                # Shuffle once, then repeat the shuffled sequence
                shuffled = segments.copy()
                random.shuffle(shuffled)
                for _ in range(num_cycles):
                    sequence.extend(shuffled)

            else:  # SEQUENTIAL
                # Loop through segments in order
                for _ in range(num_cycles):
                    sequence.extend(segments)

        if not sequence:
            return AudioSegment.empty()

        print(f"Combining {len(sequence)} audio segments...")

        combined = sequence[0]
        for i, segment in enumerate(sequence[1:], 1):
            combined = combined + segment
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(sequence)} segments")

        if target_duration is not None:
            target_ms = target_duration * 1000
            if len(combined) > target_ms:
                combined = combined[:target_ms]

        return combined

    def validate_audio_file(self, filepath: str) -> tuple[bool, str]:
        """
        Validate an audio file

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not os.path.exists(filepath):
            return False, "File does not exist"

        if not self.is_supported_format(filepath):
            return False, f"Unsupported format. Supported: {', '.join(self.supported_formats)}"

        if not is_ffmpeg_available():
            return False, (
                "FFmpeg is not available. It may be missing from the installation "
                "or blocked by your antivirus software.\n"
                "Audio files cannot be validated without FFmpeg."
            )

        _, ext = os.path.splitext(filepath.lower())
        format_hint = ext[1:] if ext else None

        # First attempt: let pydub auto-detect
        try:
            AudioSegment.from_file(filepath)
            return True, ""
        except Exception:
            pass

        # Second attempt: try with explicit format hint (helps with
        # mislabeled or oddly-encoded files from YouTube converters)
        if format_hint:
            try:
                AudioSegment.from_file(filepath, format=format_hint)
                return True, ""
            except Exception:
                pass

        # Third attempt: try converting via raw ffmpeg to a temp WAV
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name
            try:
                ffmpeg_cmd = getattr(AudioSegment, 'converter', None) or 'ffmpeg'
                result = subprocess.run(
                    [ffmpeg_cmd, '-y', '-i', filepath, '-f', 'wav', tmp_path],
                    capture_output=True, timeout=30
                )
                if result.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                    AudioSegment.from_file(tmp_path)
                    return True, ""
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        except FileNotFoundError:
            return False, (
                "FFmpeg is not available. It may be missing from the installation "
                "or blocked by your antivirus software."
            )
        except Exception:
            pass

        return False, (
            "This audio file could not be loaded. It may be corrupted or use an "
            "unsupported codec.\nTry converting it to WAV format using a free tool "
            "like Convertio.co, then add the converted file."
        )

    def get_audio_info(self, filepath: str) -> dict:
        """Get detailed information about an audio file"""
        try:
            info = mediainfo(filepath)
            audio = AudioSegment.from_file(filepath)

            return {
                'duration': len(audio) / 1000.0,
                'channels': audio.channels,
                'sample_rate': audio.frame_rate,
                'bitrate': info.get('bit_rate', 'Unknown'),
                'format': info.get('format_name', 'Unknown')
            }
        except Exception as e:
            return {'error': str(e)}
