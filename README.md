# VTMB Playlist Maker

A modern, user-friendly tool for creating custom music playlists for **Vampire: The Masquerade - Bloodlines**. Replace in-game music with your own tracks while maintaining automatic backup and restore capabilities.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- **Modern Dark UI**: Beautiful, intuitive interface built with customtkinter
- **Custom Playlists**: Create playlists for specific locations (Clubs, Sewers, Houses, etc.)
- **Multiple Playback Modes**: Sequential, Random, or Shuffle
- **Automatic Audio Processing**: Combines your tracks into seamless audio files
- **Smart Backup System**: Automatically backs up original game files before making changes
- **Easy Restore**: One-click restoration from any backup
- **Format Support**: Works with MP3, WAV, OGG, FLAC, M4A, AAC, and WMA files
- **Playlist Management**: Save, edit, and organize multiple playlists
- **Game Directory Detection**: Smart validation of VTMB installation

## Screenshots

```
┌─────────────────────────────────────────────┐
│         🎵 VTMB Playlist Maker              │
├─────────────────────────────────────────────┤
│ + New Playlist  ⚙️ Settings  💾 Backup      │
│                           ✨ Apply Playlists │
├─────────────────────────────────────────────┤
│ Your Playlists                              │
│ ┌─────────────────────────────────────────┐ │
│ │ ☑ Downtown Club Music     (12 songs)    │ │
│ │   Location: Club | Mode: shuffle        │ │
│ │                        [Edit] [Delete]  │ │
│ └─────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────┐ │
│ │ ☑ Sewer Ambience         (5 songs)     │ │
│ │   Location: Sewer | Mode: random       │ │
│ │                        [Edit] [Delete]  │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.8 or higher
- VTMB installed on your system
- FFmpeg (required for audio processing)

### Install FFmpeg

**Windows:**
1. Download from [ffmpeg.org](https://ffmpeg.org/download.html)
2. Extract and add to your PATH, or install via chocolatey:
   ```bash
   choco install ffmpeg
   ```

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

### Setup VTMB Playlist Maker

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/vtmb-playlist-maker.git
   cd vtmb-playlist-maker
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv

   # On Windows:
   venv\Scripts\activate

   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python main.py
   ```

## Usage Guide

### First-Time Setup

1. **Launch the application**:
   ```bash
   python main.py
   ```

2. **Configure game directory**:
   - Click "⚙️ Settings"
   - Browse to your VTMB installation folder (e.g., `C:\Program Files (x86)\Steam\steamapps\common\Vampire The Masquerade - Bloodlines`)
   - Set a backup directory (default: `./backups`)
   - Click "Save"

3. **Create a backup** (IMPORTANT):
   - Click "💾 Backup" to backup all original game audio files
   - This allows you to restore the original music at any time

### Creating a Playlist

1. Click **"+ New Playlist"**

2. Fill in the details:
   - **Playlist Name**: e.g., "Downtown Club Music"
   - **Location Type**: Select the type of location (Club, Sewer, House, etc.)
   - **Game Music File**: Browse and select the game audio file you want to replace
   - **Playback Mode**:
     - **Sequential**: Plays songs in order, then loops
     - **Random**: Randomly selects songs each time
     - **Shuffle**: Shuffles once, then repeats the shuffled order

3. **Add audio files**:
   - Click "Add Files"
   - Select one or more audio files from your computer
   - Supported formats: MP3, WAV, OGG, FLAC, M4A, AAC, WMA

4. Click **"Save"**

### Applying Playlists

1. Enable the playlists you want to use (checkboxes)
2. Click **"✨ Apply Playlists"**
3. Confirm the operation
4. Wait for processing to complete
5. Launch VTMB and enjoy your custom music!

### Restoring Original Music

1. Click **"🔄 Restore"**
2. Select the backup you want to restore from
3. Confirm the restoration
4. Your original game files will be restored

## How It Works

1. **Audio Processing**: The tool takes your selected audio files and combines them into a single audio file based on your chosen playback mode, targeting approximately 1 hour of continuous music (configurable).

2. **File Replacement**: The generated audio file replaces the specified game audio file in your VTMB installation directory.

3. **Automatic Backup**: Before replacing any file, the original is automatically backed up with a timestamp, allowing for easy restoration.

4. **Format Conversion**: All audio files are automatically converted to the appropriate format for the game.

## Project Structure

```
vtmb-playlist-maker/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── config.json            # User configuration (auto-generated)
├── src/
│   ├── __init__.py
│   ├── models.py          # Data models
│   ├── audio_processor.py # Audio processing logic
│   ├── game_file_manager.py # File backup/restore
│   ├── gui.py             # User interface
│   └── utils.py           # Utility functions
├── backups/               # Backup directory (auto-generated)
└── .gitignore
```

## Configuration

The application stores configuration in `config.json`:

```json
{
  "game_directory": "C:/Games/VTMB",
  "backup_directory": "./backups",
  "output_format": "mp3",
  "output_bitrate": "192k",
  "playlists": [...],
  "last_backup_time": "2024-01-15T10:30:00"
}
```

## Tips & Best Practices

1. **Always create a backup first** before applying playlists
2. **Test with one playlist** before creating multiple
3. **Match the audio format** to the original game file when possible
4. **Keep audio files organized** in a dedicated folder for easy access
5. **Use high-quality audio** (192kbps or higher) for best results
6. **Create multiple backups** before major changes

## Common Locations in VTMB

Here are common music files you might want to replace:

- **Clubs**: `music/clubs/*.mp3` - Downtown and Hollywood club music
- **Combat**: `music/combat/*.mp3` - Battle music
- **Ambient**: `music/ambient/*.mp3` - Background atmosphere
- **Havens**: `music/haven/*.mp3` - Your safe house music
- **Downtown**: `music/downtown/*.mp3` - Downtown area music

*Note: Exact paths may vary depending on your VTMB version. Use the file browser in the playlist editor to explore available files.*

## Troubleshooting

### "FFmpeg not found" error
- Ensure FFmpeg is installed and in your system PATH
- Restart the application after installing FFmpeg

### "Invalid game directory" warning
- Make sure you're pointing to the root VTMB installation folder
- Look for folders like `vampire`, `sound`, or `music` to confirm

### Audio not playing in-game
- Verify the game file path is correct
- Check that the playlist is enabled (checkbox)
- Ensure the generated audio file was created successfully
- Try restoring from backup and re-applying

### Application won't start
- Check Python version: `python --version` (should be 3.8+)
- Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`
- Check for error messages in the console

## Development

### Running from source

```bash
git clone https://github.com/yourusername/vtmb-playlist-maker.git
cd vtmb-playlist-maker
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```

### Building a Standalone Executable

Want to create a one-file executable with FFmpeg bundled? See **[BUILD.md](BUILD.md)** for comprehensive instructions.

**Quick build:**

```bash
# Install build dependencies
pip install -r requirements-dev.txt

# Download FFmpeg binaries
python download_ffmpeg.py

# Build the executable
python build.py
```

Your standalone executable will be in `dist/` - ready to distribute with no dependencies required!

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built for the VTMB community
- Uses [customtkinter](https://github.com/TomSchimansky/CustomTkinter) for the modern UI
- Audio processing powered by [pydub](https://github.com/jiaaro/pydub)
- Inspired by content creators who need copyright-free music solutions

## Disclaimer

This tool is for personal use only. Make sure you have the rights to use any music you add to the game. The developers are not responsible for any copyright violations or damage to game files. Always backup your game files before using this tool.

---

**Enjoy your custom VTMB soundtrack!** 🎵🧛
