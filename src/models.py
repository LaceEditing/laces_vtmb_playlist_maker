"""
Data models for the VTMB Playlist Maker
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from enum import Enum
import json


class PlaybackMode(Enum):
    """Playback mode for playlists"""
    SEQUENTIAL = "sequential"
    RANDOM = "random"  # maintained for backwards compatibility
    SHUFFLE = "shuffle"


class LocationType(Enum):
    """Common location types in VTMB"""
    CLUB = "Club"
    SEWER = "Sewer"
    HOUSE = "House"
    HAVEN = "Haven"
    DOWNTOWN = "Downtown"
    COMBAT = "Combat"
    AMBIENT = "Ambient"
    CUSTOM = "Custom"


@dataclass
class AudioFile:
    """Represents an audio file in a playlist"""
    path: str
    filename: str
    duration: Optional[float] = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class Playlist:
    """Represents a playlist for a specific location"""
    name: str
    location_type: str
    game_file_path: str = ""  # The original game file to replace (optional until assigned)
    audio_files: List[AudioFile] = field(default_factory=list)
    playback_mode: str = PlaybackMode.SEQUENTIAL.value
    enabled: bool = True
    description: str = ""
    crossfade_enabled: bool = False
    crossfade_duration: int = 2000  # milliseconds

    def to_dict(self):
        return {
            'name': self.name,
            'location_type': self.location_type,
            'game_file_path': self.game_file_path,
            'audio_files': [af.to_dict() for af in self.audio_files],
            'playback_mode': self.playback_mode,
            'enabled': self.enabled,
            'description': self.description,
            'crossfade_enabled': self.crossfade_enabled,
            'crossfade_duration': self.crossfade_duration
        }

    @classmethod
    def from_dict(cls, data):
        audio_files = [AudioFile.from_dict(af) for af in data.get('audio_files', [])]
        playback_mode = data.get('playback_mode', PlaybackMode.SEQUENTIAL.value)
        if playback_mode == PlaybackMode.RANDOM.value:
            playback_mode = PlaybackMode.SHUFFLE.value
        return cls(
            name=data['name'],
            location_type=data['location_type'],
            game_file_path=data.get('game_file_path', ''),
            audio_files=audio_files,
            playback_mode=playback_mode,
            enabled=data.get('enabled', True),
            description=data.get('description', ''),
            crossfade_enabled=data.get('crossfade_enabled', False),
            crossfade_duration=data.get('crossfade_duration', 2000)
        )


@dataclass
class AppConfig:
    """Application configuration"""
    game_directory: str = ""
    backup_directory: str = "./backups"
    output_format: str = "mp3"
    output_bitrate: str = "192k"
    playlists: List[Playlist] = field(default_factory=list)
    audio_library: List[AudioFile] = field(default_factory=list)  # User's imported audio files
    last_backup_time: Optional[str] = None

    def to_dict(self):
        return {
            'game_directory': self.game_directory,
            'backup_directory': self.backup_directory,
            'output_format': self.output_format,
            'output_bitrate': self.output_bitrate,
            'playlists': [p.to_dict() for p in self.playlists],
            'audio_library': [af.to_dict() for af in self.audio_library],
            'last_backup_time': self.last_backup_time
        }

    @classmethod
    def from_dict(cls, data):
        playlists = [Playlist.from_dict(p) for p in data.get('playlists', [])]
        audio_library = [AudioFile.from_dict(af) for af in data.get('audio_library', [])]
        return cls(
            game_directory=data.get('game_directory', ''),
            backup_directory=data.get('backup_directory', './backups'),
            output_format=data.get('output_format', 'mp3'),
            output_bitrate=data.get('output_bitrate', '192k'),
            playlists=playlists,
            audio_library=audio_library,
            last_backup_time=data.get('last_backup_time')
        )

    def save(self, filepath: str = 'config.json'):
        """Save configuration to file"""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str = 'config.json'):
        """Load configuration from file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except FileNotFoundError:
            return cls()
