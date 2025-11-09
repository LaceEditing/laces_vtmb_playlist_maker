"""
Utility functions for the VTMB Playlist Maker
"""
import json
import os
import platform
import winreg
from pathlib import Path
from typing import List, Optional, Dict
from src.models import Playlist, AppConfig


# Supported audio file formats across the application
SUPPORTED_AUDIO_FORMATS = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma')


def export_playlists(playlists: List[Playlist], filepath: str) -> tuple[bool, str]:
    """
    Export playlists to a JSON file for sharing

    Args:
        playlists: List of playlists to export
        filepath: Path to save the export file

    Returns:
        Tuple of (success, message)
    """
    try:
        export_data = {
            'version': '1.0',
            'playlists': [p.to_dict() for p in playlists]
        }

        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)

        return True, f"Successfully exported {len(playlists)} playlists"
    except Exception as e:
        return False, f"Export failed: {str(e)}"


def import_playlists(filepath: str) -> tuple[bool, List[Playlist], str]:
    """
    Import playlists from a JSON file

    Args:
        filepath: Path to the import file

    Returns:
        Tuple of (success, playlists, message)
    """
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        if 'playlists' not in data:
            return False, [], "Invalid playlist file format"

        playlists = [Playlist.from_dict(p) for p in data['playlists']]

        return True, playlists, f"Successfully imported {len(playlists)} playlists"
    except Exception as e:
        return False, [], f"Import failed: {str(e)}"


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def format_file_size(bytes: int) -> str:
    """Format file size in bytes to human-readable string"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} TB"


def validate_game_directory_structure(game_dir: str) -> dict:
    """
    Validate and analyze the game directory structure

    Returns:
        Dictionary with validation results and suggestions
    """
    result = {
        'valid': False,
        'audio_files_found': 0,
        'common_locations': [],
        'suggestions': []
    }

    if not os.path.exists(game_dir):
        result['suggestions'].append("Directory does not exist")
        return result

    # Look for common VTMB directory structures
    common_paths = [
        'vampire/sound',
        'sound',
        'vampire/music',
        'music',
        'Vampire/Sound',
        'Sound',
        'Vampire/Music',
        'Music'
    ]

    for path in common_paths:
        full_path = os.path.join(game_dir, path)
        if os.path.exists(full_path):
            result['common_locations'].append(path)

    # Count audio files
    audio_extensions = ['.mp3', '.wav', '.ogg']
    for root, dirs, files in os.walk(game_dir):
        for file in files:
            _, ext = os.path.splitext(file.lower())
            if ext in audio_extensions:
                result['audio_files_found'] += 1

    if result['audio_files_found'] > 0:
        result['valid'] = True
    else:
        result['suggestions'].append("No audio files found in directory")

    if result['common_locations']:
        result['suggestions'].append(f"Found common audio directories: {', '.join(result['common_locations'])}")

    return result


# Music catalog with descriptions of where tracks play in-game
# This is used to provide context - but tracks NOT in this catalog will still be discovered
MUSIC_CATALOG = {
    # Licensed Music Tracks
    "isolated": {
        "description": "The Asylum Nightclub (Chiasm - Isolated)",
        "location": "Santa Monica",
        "type": "club",
        "artist": "Chiasm"
    },
    "bloodlines": {
        "description": "Confession Club (Ministry - Bloodlines)",
        "location": "Downtown LA",
        "type": "club",
        "artist": "Ministry"
    },
    "come_alive": {
        "description": "Radio / The Glaze (Daniel Ash)",
        "location": "Chinatown",
        "type": "club",
        "artist": "Daniel Ash"
    },
    "cain": {
        "description": "The Asp Hole (Tiamat - Cain)",
        "location": "Hollywood",
        "type": "club",
        "artist": "Tiamat"
    },
    "swamped": {
        "description": "The Asp Hole / Credits (Lacuna Coil)",
        "location": "Hollywood",
        "type": "club",
        "artist": "Lacuna Coil"
    },
    "needles_eye": {
        "description": "In-game Radio Show (Die My Darling - Needle's Eye) - Unofficial Patch only",
        "location": "Other",
        "type": "radio",
        "artist": "Die My Darling",
        "note": "Radio shows are single files. Use ONE song only, not a playlist."
    },
    "die my darling": {
        "description": "In-game Radio Show (Die My Darling - Needle's Eye) - Unofficial Patch only",
        "location": "Other",
        "type": "radio",
        "artist": "Die My Darling",
        "note": "Radio shows are single files. Use ONE song only, not a playlist."
    },
    "pound": {
        "description": "The Glaze (Aerial2012)",
        "location": "Chinatown",
        "type": "club",
        "artist": "Aerial2012"
    },
    "lecher_bitch": {
        "description": "The Last Round (Genitorturers)",
        "location": "Downtown LA",
        "type": "club",
        "artist": "Genitorturers"
    },
    "smaller_god": {
        "description": "Empire Arms Hotel (Darling Violetta)",
        "location": "Downtown LA",
        "type": "ambient",
        "artist": "Darling Violetta"
    },

    # Santa Monica
    "santa_monica": {
        "description": "Santa Monica Hub - Main area theme",
        "location": "Santa Monica",
        "type": "ambient"
    },
    "beachhouse": {
        "description": "Beach House areas",
        "location": "Santa Monica",
        "type": "ambient"
    },
    "oceanhouse": {
        "description": "Ocean House Hotel (haunted mansion)",
        "location": "Santa Monica",
        "type": "ambient"
    },
    "sm_pier": {
        "description": "Santa Monica Pier",
        "location": "Santa Monica",
        "type": "ambient"
    },
    "sm_pier_1": {
        "description": "Santa Monica Pier",
        "location": "Santa Monica",
        "type": "ambient"
    },
    "sm_sewers": {
        "description": "Santa Monica Sewers",
        "location": "Santa Monica",
        "type": "ambient"
    },
    "sm_sewers_1": {
        "description": "Santa Monica Sewers",
        "location": "Santa Monica",
        "type": "ambient"
    },
    "sm_asylum": {
        "description": "The Asylum (exterior/office)",
        "location": "Santa Monica",
        "type": "ambient"
    },
    "asylum": {
        "description": "The Asylum Nightclub",
        "location": "Santa Monica",
        "type": "club"
    },
    "theAsylum": {
        "description": "The Asylum Nightclub",
        "location": "Santa Monica",
        "type": "club"
    },

    # Downtown LA
    "downtown": {
        "description": "Downtown LA Hub - Main area theme",
        "location": "Downtown LA",
        "type": "ambient"
    },
    "la_hub": {
        "description": "Downtown LA Hub",
        "location": "Downtown LA",
        "type": "ambient"
    },
    "la_hub_1": {
        "description": "Downtown LA Hub",
        "location": "Downtown LA",
        "type": "ambient"
    },
    "elizabethdane": {
        "description": "Elizabeth Dane Nightclub",
        "location": "Downtown LA",
        "type": "club"
    },
    "confession": {
        "description": "Confession Nightclub",
        "location": "Downtown LA",
        "type": "club"
    },
    "la_confession": {
        "description": "Confession Nightclub",
        "location": "Downtown LA",
        "type": "club"
    },
    "la_bradbury": {
        "description": "Bradbury Building",
        "location": "Downtown LA",
        "type": "ambient"
    },
    "la_chantry": {
        "description": "Tremere Chantry",
        "location": "Downtown LA",
        "type": "ambient"
    },
    "la_museum": {
        "description": "Museum of Natural History",
        "location": "Downtown LA",
        "type": "ambient"
    },
    "la_museum_1": {
        "description": "Museum of Natural History",
        "location": "Downtown LA",
        "type": "ambient"
    },
    "la_ventrue": {
        "description": "Ventrue Tower",
        "location": "Downtown LA",
        "type": "ambient"
    },
    "empire": {
        "description": "Empire Arms Hotel",
        "location": "Downtown LA",
        "type": "ambient"
    },
    "lastround": {
        "description": "The Last Round Bar",
        "location": "Downtown LA",
        "type": "club"
    },

    # Hollywood
    "hollywood": {
        "description": "Hollywood Hub - Main area theme",
        "location": "Hollywood",
        "type": "ambient"
    },
    "hollywood_main": {
        "description": "Hollywood Hub",
        "location": "Hollywood",
        "type": "ambient"
    },
    "vesuvius": {
        "description": "Vesuvius Nightclub",
        "location": "Hollywood",
        "type": "club"
    },
    "hw_asphole": {
        "description": "The Asp Hole Club",
        "location": "Hollywood",
        "type": "club"
    },
    "asphole": {
        "description": "The Asp Hole Club",
        "location": "Hollywood",
        "type": "club"
    },
    "hw_cemetery": {
        "description": "Hollywood Cemetery",
        "location": "Hollywood",
        "type": "ambient"
    },
    "hw_warrens": {
        "description": "The Warrens (Nosferatu haven)",
        "location": "Hollywood",
        "type": "ambient"
    },
    "warrens": {
        "description": "The Warrens (Nosferatu haven)",
        "location": "Hollywood",
        "type": "ambient"
    },
    "netcafe": {
        "description": "Internet Cafe",
        "location": "Hollywood",
        "type": "ambient"
    },

    # Chinatown
    "chinatown": {
        "description": "Chinatown Hub - Main area theme",
        "location": "Chinatown",
        "type": "ambient"
    },
    "ch_hub": {
        "description": "Chinatown Hub",
        "location": "Chinatown",
        "type": "ambient"
    },
    "ch_hub_1": {
        "description": "Chinatown Hub",
        "location": "Chinatown",
        "type": "ambient"
    },
    "glaze": {
        "description": "The Glaze Nightclub",
        "location": "Chinatown",
        "type": "club"
    },
    "glaze2": {
        "description": "The Glaze Nightclub",
        "location": "Chinatown",
        "type": "club"
    },
    "lotusblossom": {
        "description": "Lotus Blossom Restaurant",
        "location": "Chinatown",
        "type": "ambient"
    },
    "ch_temple": {
        "description": "Golden Temple",
        "location": "Chinatown",
        "type": "ambient"
    },
    "ch_zhaos": {
        "description": "Zhao's Import/Export",
        "location": "Chinatown",
        "type": "ambient"
    },

    # Combat
    "combat": {
        "description": "Generic Combat Music",
        "location": "Combat",
        "type": "combat"
    },
    "combat_1": {
        "description": "Combat Music Variant 1",
        "location": "Combat",
        "type": "combat"
    },
    "combat_2": {
        "description": "Combat Music Variant 2",
        "location": "Combat",
        "type": "combat"
    },
    "combat_boss": {
        "description": "Boss Fight Music",
        "location": "Combat",
        "type": "combat"
    },
    "action": {
        "description": "Action/Combat Music",
        "location": "Combat",
        "type": "combat"
    },

    # Sewers
    "sewers": {
        "description": "Generic Sewer Areas",
        "location": "Sewers",
        "type": "ambient"
    },
    "sewers_1": {
        "description": "Sewer Areas",
        "location": "Sewers",
        "type": "ambient"
    },
    "sewers_2": {
        "description": "Sewer Areas Variant",
        "location": "Sewers",
        "type": "ambient"
    },
    "sewers_base": {
        "description": "Sewer Base",
        "location": "Sewers",
        "type": "ambient"
    },

    # Other Locations
    "haven": {
        "description": "Your Haven (safe house)",
        "location": "Haven",
        "type": "ambient"
    },
    "downtown_haven": {
        "description": "Downtown Haven",
        "location": "Haven",
        "type": "ambient"
    },
    "hollywood_haven": {
        "description": "Hollywood Haven",
        "location": "Haven",
        "type": "ambient"
    },
    "endgame": {
        "description": "Endgame Sequences",
        "location": "Other",
        "type": "ambient"
    },
    "ming": {
        "description": "Ming Xiao Encounter",
        "location": "Other",
        "type": "ambient"
    },
    "cab": {
        "description": "Cab Ride Music",
        "location": "Other",
        "type": "ambient"
    },
    "disciplines": {
        "description": "Disciplines Menu",
        "location": "Menus & Credits",
        "type": "menu"
    },
    "elysium": {
        "description": "Elysium (Prince's chambers)",
        "location": "Other",
        "type": "ambient"
    },
    "mainmenu": {
        "description": "Main Menu Theme",
        "location": "Menus & Credits",
        "type": "menu"
    },
    "title": {
        "description": "Title Screen Theme",
        "location": "Menus & Credits",
        "type": "menu"
    },
    "titlescreen": {
        "description": "Title Screen Theme",
        "location": "Menus & Credits",
        "type": "menu"
    },
    "title_theme": {
        "description": "Alternate Title Theme",
        "location": "Menus & Credits",
        "type": "menu"
    },
    "credits": {
        "description": "Credits Theme",
        "location": "Menus & Credits",
        "type": "menu"
    },
    "endcredits": {
        "description": "Ending Credits Theme",
        "location": "Menus & Credits",
        "type": "menu"
    },
    "credits_long": {
        "description": "Extended Credits Theme",
        "location": "Menus & Credits",
        "type": "menu"
    },
    "intro": {
        "description": "Intro Cinematic",
        "location": "Menus & Credits",
        "type": "menu"
    },
    "outro": {
        "description": "Outro Cinematic",
        "location": "Menus & Credits",
        "type": "menu"
    },
    "radio": {
        "description": "In-game Radio Show - Unofficial Patch only",
        "location": "Other",
        "type": "radio",
        "note": "Radio shows are single files. Use ONE song only, not a playlist."
    },
    "radio_loop_1": {
        "description": "Radio Loop 1 - Deb of Night talk show & commercials (7 minutes)",
        "location": "Radio Shows",
        "type": "radio_loop",
        "note": "Replace with ONE long file OR a playlist. Game randomly picks from 5 loops."
    },
    "radio_loop_2": {
        "description": "Radio Loop 2 - Deb of Night talk show & commercials (7 minutes)",
        "location": "Radio Shows",
        "type": "radio_loop",
        "note": "Replace with ONE long file OR a playlist. Game randomly picks from 5 loops."
    },
    "radio_loop_3": {
        "description": "Radio Loop 3 - Deb of Night talk show & commercials (7 minutes)",
        "location": "Radio Shows",
        "type": "radio_loop",
        "note": "Replace with ONE long file OR a playlist. Game randomly picks from 5 loops."
    },
    "radio_loop_4": {
        "description": "Radio Loop 4 - Deb of Night talk show & commercials (7 minutes)",
        "location": "Radio Shows",
        "type": "radio_loop",
        "note": "Replace with ONE long file OR a playlist. Game randomly picks from 5 loops."
    },
    "radio_loop_5": {
        "description": "Radio Loop 5 - Deb of Night talk show & commercials (21 minutes)",
        "location": "Radio Shows",
        "type": "radio_loop",
        "note": "Replace with ONE long file OR a playlist. Game randomly picks from 5 loops."
    }
}


def get_music_info(filename: str) -> Optional[Dict[str, str]]:
    """
    Get information about a music file based on its filename

    Args:
        filename: Name of the music file (with or without extension)

    Returns:
        Dictionary with description, location, and type, or None if not found
    """
    # Remove extension and path
    name = os.path.splitext(os.path.basename(filename))[0].lower()

    # Try exact match first
    if name in MUSIC_CATALOG:
        return MUSIC_CATALOG[name]

    # Try partial matches
    for key, info in MUSIC_CATALOG.items():
        if key in name or name in key:
            return info

    return None


def get_all_locations() -> List[str]:
    """
    Get all unique locations from the music catalog

    Returns:
        Sorted list of unique location names
    """
    locations = set()
    for track_info in MUSIC_CATALOG.values():
        if 'location' in track_info:
            locations.add(track_info['location'])

    # Sort locations in a logical order
    location_order = ['Santa Monica', 'Downtown LA', 'Hollywood', 'Chinatown', 'Radio Shows', 'Malkavian Whispers', 'Combat', 'Haven', 'Menus & Credits', 'Other']
    sorted_locations = []

    for location in location_order:
        if location in locations:
            sorted_locations.append(location)

    # Add any remaining locations not in the predefined order
    for location in sorted(locations):
        if location not in sorted_locations:
            sorted_locations.append(location)

    return sorted_locations


def detect_steam_path() -> Optional[str]:
    """
    Detect Steam installation path on Windows

    Returns:
        Steam installation path or None if not found
    """
    if platform.system() != "Windows":
        return None

    try:
        # Try to read Steam installation path from registry
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam") as key:
            steam_path = winreg.QueryValueEx(key, "InstallPath")[0]
            return steam_path
    except (WindowsError, FileNotFoundError):
        # Try 32-bit registry
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam") as key:
                steam_path = winreg.QueryValueEx(key, "InstallPath")[0]
                return steam_path
        except (WindowsError, FileNotFoundError):
            pass

    # Fallback to default Steam location
    default_path = r"C:\Program Files (x86)\Steam"
    if os.path.exists(default_path):
        return default_path

    return None


def get_steam_library_folders(steam_path: str) -> List[str]:
    """
    Get all Steam library folders from libraryfolders.vdf

    Args:
        steam_path: Path to Steam installation

    Returns:
        List of library folder paths
    """
    libraries = [steam_path]

    vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
    if not os.path.exists(vdf_path):
        return libraries

    try:
        with open(vdf_path, 'r', encoding='utf-8') as f:
            content = f.read()

            # Parse VDF format (simple path extraction)
            import re
            paths = re.findall(r'"path"\s+"([^"]+)"', content)
            libraries.extend(paths)
    except Exception as e:
        print(f"Error reading Steam library folders: {e}")

    return libraries


def detect_gog_path() -> Optional[str]:
    """
    Detect GOG installation path on Windows

    Returns:
        GOG Games path or None if not found
    """
    if platform.system() != "Windows":
        return None

    # Common GOG installation paths
    common_paths = [
        r"C:\GOG Games",
        r"C:\Program Files (x86)\GOG Games",
        r"C:\Program Files\GOG Games",
        os.path.join(os.path.expanduser("~"), "GOG Games")
    ]

    for path in common_paths:
        if os.path.exists(path):
            return path

    # Try registry
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\GOG.com\Games") as key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, subkey_name) as subkey:
                        path = winreg.QueryValueEx(subkey, "path")[0]
                        if "Vampire" in path or "Bloodlines" in path:
                            return os.path.dirname(path)
                    i += 1
                except WindowsError:
                    break
    except (WindowsError, FileNotFoundError):
        pass

    return None


def find_vtmb_installation() -> Optional[Dict[str, str]]:
    """
    Auto-detect VTMB installation with Unofficial Patch support

    Returns:
        Dictionary with 'path', 'type' (steam/gog), and 'patch_version' or None
    """
    candidates = []

    # Check Steam libraries
    steam_path = detect_steam_path()
    if steam_path:
        libraries = get_steam_library_folders(steam_path)
        for library in libraries:
            vtmb_path = os.path.join(library, "steamapps", "common", "Vampire The Masquerade - Bloodlines")
            if os.path.exists(vtmb_path):
                candidates.append({
                    'path': vtmb_path,
                    'type': 'steam',
                    'source': 'Steam Library'
                })

    # Check GOG
    gog_path = detect_gog_path()
    if gog_path:
        vtmb_path = os.path.join(gog_path, "Vampire The Masquerade - Bloodlines")
        if os.path.exists(vtmb_path):
            candidates.append({
                'path': vtmb_path,
                'type': 'gog',
                'source': 'GOG Games'
            })

    # For each candidate, check for Unofficial Patch
    for candidate in candidates:
        path = candidate['path']

        # Check for Unofficial_Patch folder (UP 9.3+)
        unofficial_patch_path = os.path.join(path, "Unofficial_Patch")
        if os.path.exists(unofficial_patch_path):
            # Check if it has the expected structure
            sound_path = os.path.join(unofficial_patch_path, "sound")
            if os.path.exists(sound_path):
                candidate['patch_version'] = 'Unofficial_Patch (9.3+)'
                candidate['patch_path'] = unofficial_patch_path
                return candidate  # Prefer Unofficial Patch installations

        # Check for old Vampire folder structure (UP 9.2 or vanilla)
        vampire_path = os.path.join(path, "Vampire")
        if os.path.exists(vampire_path):
            sound_path = os.path.join(vampire_path, "sound")
            if os.path.exists(sound_path):
                candidate['patch_version'] = 'Vanilla or UP 9.2 or earlier'
                candidate['patch_path'] = vampire_path
                return candidate

    # Return the first candidate if no patch detected
    if candidates:
        return candidates[0]

    return None


def get_music_directories(game_path: str) -> List[Dict[str, str]]:
    """
    Get all music directories in the game installation, prioritizing Unofficial Patch

    Args:
        game_path: Path to VTMB installation

    Returns:
        List of dictionaries with 'path', 'type', and 'priority'
    """
    music_dirs = []

    # Priority 1: Unofficial_Patch folder (UP 9.3+)
    unofficial_patch = os.path.join(game_path, "Unofficial_Patch", "sound", "music")
    if os.path.exists(unofficial_patch):
        music_dirs.append({
            'path': unofficial_patch,
            'type': 'Unofficial Patch (Primary)',
            'priority': 1
        })

    # Priority 2: Vampire folder
    vampire_music = os.path.join(game_path, "Vampire", "sound", "music")
    if os.path.exists(vampire_music):
        music_dirs.append({
            'path': vampire_music,
            'type': 'Base Game',
            'priority': 2
        })

    # Priority 3: Radio directories (Deb of Night + commercials)
    unofficial_radio = os.path.join(game_path, "Unofficial_Patch", "sound", "radio")
    if os.path.exists(unofficial_radio):
        music_dirs.append({
            'path': unofficial_radio,
            'type': 'Unofficial Patch Radio',
            'priority': 3
        })

    vampire_radio = os.path.join(game_path, "Vampire", "sound", "radio")
    if os.path.exists(vampire_radio):
        music_dirs.append({
            'path': vampire_radio,
            'type': 'Base Game Radio',
            'priority': 4
        })

    # Also check for lowercase variants
    vampire_music_lower = os.path.join(game_path, "vampire", "sound", "music")
    if os.path.exists(vampire_music_lower) and vampire_music_lower.lower() != vampire_music.lower():
        music_dirs.append({
            'path': vampire_music_lower,
            'type': 'Base Game (Alt)',
            'priority': 5
        })

    return music_dirs
