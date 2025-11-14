"""
Modern GUI for VTMB Playlist Maker using customtkinter
"""
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional, List

import customtkinter as ctk
import pygame
from PIL import Image, ImageTk

from src.audio_processor import AudioProcessor, validate_ffmpeg
from src.game_file_manager import GameFileManager
from src.models import AppConfig, Playlist, AudioFile, PlaybackMode, LocationType
from src.utils import find_vtmb_installation, get_music_info, get_music_directories, get_all_locations, SUPPORTED_AUDIO_FORMATS
from src.radio_segment_manager import RadioSegmentManager
from src.malkavian_whispers import MalkavianWhisperManager


_APP_ICON_IMAGE = None
_APP_ICON_BITMAP_PATH = None
_ICON_LOAD_ATTEMPTED = False
_CUSTOM_FONT_PATH = None
_FONT_LOAD_ATTEMPTED = False


def load_custom_font():
    """Load the custom Bubblegum Sans font if available."""
    global _CUSTOM_FONT_PATH, _FONT_LOAD_ATTEMPTED
    if _FONT_LOAD_ATTEMPTED:
        return _CUSTOM_FONT_PATH

    _FONT_LOAD_ATTEMPTED = True
    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    font_path = assets_dir / "BubblegumSans-Regular.ttf"

    if font_path.exists():
        try:
            # Use Windows GDI to register the font for tkinter/CustomTkinter
            if sys.platform == 'win32':
                import ctypes
                import ctypes.wintypes
                gdi32 = ctypes.WinDLL('gdi32')
                gdi32.AddFontResourceW.argtypes = [ctypes.wintypes.LPCWSTR]
                result = gdi32.AddFontResourceW(str(font_path))
                if result > 0:
                    _CUSTOM_FONT_PATH = str(font_path)
                else:
                    _CUSTOM_FONT_PATH = None
            else:
                import pyglet.font
                pyglet.font.add_file(str(font_path))
                _CUSTOM_FONT_PATH = str(font_path)
        except Exception:
            _CUSTOM_FONT_PATH = None
    else:
        _CUSTOM_FONT_PATH = None

    return _CUSTOM_FONT_PATH


def load_app_icon():
    """Load the shared application icon once."""
    global _APP_ICON_IMAGE, _APP_ICON_BITMAP_PATH, _ICON_LOAD_ATTEMPTED
    if _ICON_LOAD_ATTEMPTED:
        return _APP_ICON_IMAGE, _APP_ICON_BITMAP_PATH

    _ICON_LOAD_ATTEMPTED = True
    assets_dir = Path(__file__).resolve().parent.parent / "assets"

    # On Windows, prioritize .ico for iconbitmap
    if sys.platform == 'win32':
        candidates = ("icon.ico", "icon.png")
    else:
        candidates = ("icon.png", "icon.ico")

    for name in candidates:
        icon_path = assets_dir / name
        if not icon_path.exists():
            continue

        try:
            # For .ico files, just store the path for iconbitmap (better on Windows)
            if icon_path.suffix.lower() == ".ico":
                _APP_ICON_BITMAP_PATH = str(icon_path)
                # Also try to create PhotoImage for iconphoto
                try:
                    with Image.open(icon_path) as img:
                        _APP_ICON_IMAGE = ImageTk.PhotoImage(img.copy())
                except Exception:
                    pass  # iconbitmap will still work
            else:
                # For PNG, create PhotoImage
                with Image.open(icon_path) as img:
                    _APP_ICON_IMAGE = ImageTk.PhotoImage(img.copy())

            return _APP_ICON_IMAGE, _APP_ICON_BITMAP_PATH
        except Exception as exc:
            print(f"Warning: Could not load icon from {icon_path}: {exc}")

    # No icon available
    _APP_ICON_IMAGE = None
    _APP_ICON_BITMAP_PATH = None
    return _APP_ICON_IMAGE, _APP_ICON_BITMAP_PATH


def apply_app_icon(window):
    """
    Apply the shared icon to the given window.
    Keeps a reference on the window to prevent garbage collection.
    """
    icon_image, icon_bitmap_path = load_app_icon()

    # On Windows, use multiple methods to ensure taskbar icon works
    if icon_bitmap_path and os.path.exists(icon_bitmap_path):
        try:
            # Method 1: iconbitmap (standard tkinter)
            window.iconbitmap(icon_bitmap_path)
            window._icon_bitmap_path = icon_bitmap_path  # noqa: W0212 - cached for children
        except Exception as e:
            print(f"Warning: Could not set iconbitmap: {e}")

        # Method 2: Set Windows taskbar icon directly (Windows-specific)
        if sys.platform == 'win32':
            try:
                import ctypes
                # Wait for window to be created
                window.update_idletasks()
                # Get window handle
                hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
                if hwnd:
                    # Load icon
                    icon_flags = 0x00000000  # LR_DEFAULTSIZE
                    hicon = ctypes.windll.user32.LoadImageW(
                        None,
                        icon_bitmap_path,
                        1,  # IMAGE_ICON
                        0, 0,  # Use default size
                        0x00000010 | icon_flags  # LR_LOADFROMFILE
                    )
                    if hicon:
                        # Set both small and large icons for better taskbar display
                        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon)  # WM_SETICON, ICON_SMALL
                        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon)  # WM_SETICON, ICON_BIG
            except Exception as e:
                # Silent fail - this is just for enhanced Windows taskbar support
                pass

    # Also set iconphoto for better cross-platform support
    if icon_image:
        try:
            window.iconphoto(True, icon_image)
            window._icon_image = icon_image  # noqa: W0212 - cached for children
        except Exception as e:
            print(f"Warning: Could not set iconphoto: {e}")


def finalize_modal(window, min_width: int = 0, min_height: int = 0):
    """Ensure modal windows have enough space to display content."""
    try:
        window.update_idletasks()
        preferred_width = window.winfo_reqwidth() + 20
        preferred_height = window.winfo_reqheight() + 20

        width = max(min_width, preferred_width)
        height = max(min_height, preferred_height)

        window.minsize(width, height)
        window.geometry(f"{width}x{height}")
    except Exception:
        pass


class PlaylistFrame(ctk.CTkFrame):
    """Frame for managing a single playlist"""

    def __init__(self, master, playlist: Playlist, on_delete, on_edit, on_update, colors=None, **kwargs):
        super().__init__(master, **kwargs)
        self.playlist = playlist
        self.on_delete = on_delete
        self.on_edit = on_edit
        self.on_update = on_update
        self.colors = colors or {}

        self.setup_ui()

    def setup_ui(self):
        # Main container with better padding
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=12, pady=8)

        # Left side - Playlist name and info
        left_frame = ctk.CTkFrame(container, fg_color="transparent")
        left_frame.pack(side="left", fill="both", expand=True)

        # Playlist name with wraplength to prevent cutoff
        song_count = len(self.playlist.audio_files)
        display_name = f"{self.playlist.name} ({song_count} songs)"

        self.name_label = ctk.CTkLabel(
            left_frame,
            text=display_name,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=self.colors.get('text', '#FFE4E4'),
            anchor="w",
            justify="left"
        )
        self.name_label.pack(side="left", fill="x", expand=True)

        # Right side - Action buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(side="right", padx=(10, 0))

        self.edit_btn = ctk.CTkButton(
            btn_frame,
            text="✏️ Edit",
            width=100,
            height=36,
            command=self.edit_playlist,
            fg_color=self.colors.get('accent', '#B22222'),
            hover_color=self.colors.get('secondary', '#DC143C'),
            text_color=self.colors.get('text', '#FFE4E4'),
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=6
        )
        self.edit_btn.pack(side="left", padx=4)

        self.delete_btn = ctk.CTkButton(
            btn_frame,
            text="🗑️ Delete",
            width=100,
            height=36,
            fg_color=self.colors.get('danger', '#8B0000'),
            hover_color=self.colors.get('danger_hover', '#A50000'),
            command=self.delete_playlist,
            text_color=self.colors.get('text', '#FFE4E4'),
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=6
        )
        self.delete_btn.pack(side="left", padx=4)

    def edit_playlist(self):
        # Use callback to edit playlist
        self.on_edit(self.playlist)

    def delete_playlist(self):
        if messagebox.askyesno("Confirm Delete", f"Delete playlist '{self.playlist.name}'?"):
            self.on_delete(self.playlist)

    def update_display(self):
        """Update the display after playlist changes"""
        song_count = len(self.playlist.audio_files)
        display_name = f"{self.playlist.name} ({song_count} songs)"
        self.name_label.configure(text=display_name)


class PlaylistEditorDialog(ctk.CTkToplevel):
    """Dialog for creating/editing playlists"""

    def __init__(self, master, playlist: Optional[Playlist] = None, game_manager: GameFileManager = None, colors: dict = None, audio_library: List[AudioFile] = None):
        super().__init__(master)

        self.playlist = playlist
        self.game_manager = game_manager
        self.audio_processor = AudioProcessor()
        self.audio_library = audio_library or []
        self.result = None
        self.colors = colors or {
            'primary': '#8B0000',
            'primary_hover': '#A50000',
            'secondary': '#DC143C',
            'accent': '#B22222',
            'danger': '#8B0000',
            'danger_hover': '#A50000',
            'bg_dark': '#1a0000',
            'bg_medium': '#2d0a0a',
            'text': '#FFE4E4',
            'text_dim': '#B88888',
        }

        # Configure window
        self.title("Edit Playlist" if playlist else "New Playlist")
        self.geometry("700x650")

        # Set dark theme colors
        self.configure(fg_color=self.colors['bg_medium'])
        apply_app_icon(self)

        # Make modal
        self.transient(master)
        self.grab_set()

        self.setup_ui()

        # Load existing data if editing
        if self.playlist:
            self.load_playlist_data()

        finalize_modal(self, min_width=720, min_height=620)

    def setup_ui(self):
        # Main container
        main_frame = ctk.CTkFrame(self, fg_color=self.colors['bg_dark'])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Playlist name
        ctk.CTkLabel(
            main_frame,
            text="Playlist Name:",
            font=ctk.CTkFont(weight="bold"),
            text_color=self.colors['text']
        ).pack(anchor="w", pady=(0, 5))
        self.name_entry = ctk.CTkEntry(
            main_frame,
            placeholder_text="e.g., Downtown Club Music",
            fg_color=self.colors['bg_medium'],
            border_color=self.colors['accent'],
            text_color=self.colors['text']
        )
        self.name_entry.pack(fill="x", pady=(0, 15))

        # Location type
        ctk.CTkLabel(
            main_frame,
            text="Location Type:",
            font=ctk.CTkFont(weight="bold"),
            text_color=self.colors['text']
        ).pack(anchor="w", pady=(0, 5))
        self.location_var = ctk.StringVar(value=LocationType.CLUB.value)
        location_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        location_frame.pack(fill="x", pady=(0, 15))

        self.location_combo = ctk.CTkComboBox(
            location_frame,
            values=[lt.value for lt in LocationType],
            variable=self.location_var,
            width=200,
            fg_color=self.colors['primary'],
            button_color=self.colors['accent'],
            button_hover_color=self.colors['secondary'],
            dropdown_fg_color=self.colors['bg_dark'],
            text_color=self.colors['text']
        )
        self.location_combo.pack(side="left")

        # Game file path
        ctk.CTkLabel(
            main_frame,
            text="Game Music File to Replace (Optional):",
            font=ctk.CTkFont(weight="bold"),
            text_color=self.colors['text']
        ).pack(anchor="w", pady=(0, 5))

        ctk.CTkLabel(
            main_frame,
            text="💡 You can assign this playlist to game tracks later",
            font=ctk.CTkFont(size=9),
            text_color=self.colors['text_dim']
        ).pack(anchor="w", pady=(0, 5))

        game_file_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        game_file_frame.pack(fill="x", pady=(0, 15))

        self.game_file_entry = ctk.CTkEntry(
            game_file_frame,
            placeholder_text="Leave blank to assign later",
            fg_color=self.colors['bg_medium'],
            border_color=self.colors['accent'],
            text_color=self.colors['text']
        )
        self.game_file_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        browse_game_btn = ctk.CTkButton(
            game_file_frame,
            text="Browse",
            width=100,
            command=self.browse_game_file,
            fg_color=self.colors['accent'],
            hover_color=self.colors['secondary'],
            text_color=self.colors['text']
        )
        browse_game_btn.pack(side="left")

        # Radio file warning (initially hidden)
        self.radio_warning_label = ctk.CTkLabel(
            main_frame,
            text="",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#FFA500",
            anchor="w",
            wraplength=600,
            justify="left"
        )
        # Don't pack it yet - we'll show it only when needed

        # Playback mode
        ctk.CTkLabel(
            main_frame,
            text="Playback Mode:",
            font=ctk.CTkFont(weight="bold"),
            text_color=self.colors['text']
        ).pack(anchor="w", pady=(0, 5))

        mode_help = ctk.CTkLabel(
            main_frame,
            text="📝 Sequential: Plays in order • Shuffle: Randomizes order each loop",
            font=ctk.CTkFont(size=9),
            text_color=self.colors['text_dim']
        )
        mode_help.pack(anchor="w", pady=(0, 5))

        self.playback_var = ctk.StringVar(value=PlaybackMode.SEQUENTIAL.value)
        playback_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        playback_frame.pack(fill="x", pady=(0, 15))

        for mode in (PlaybackMode.SEQUENTIAL, PlaybackMode.SHUFFLE):
            ctk.CTkRadioButton(
                playback_frame,
                text=mode.value.capitalize(),
                variable=self.playback_var,
                value=mode.value,
                fg_color=self.colors['secondary'],
                hover_color=self.colors['accent'],
                text_color=self.colors['text']
            ).pack(side="left", padx=10)

        # Audio files section
        audio_header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        audio_header_frame.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(
            audio_header_frame,
            text="Audio Files:",
            font=ctk.CTkFont(weight="bold"),
            text_color=self.colors['text']
        ).pack(side="left")

        ctk.CTkLabel(
            audio_header_frame,
            text="(These will be combined into ONE file)",
            font=ctk.CTkFont(size=10, slant="italic"),
            text_color=self.colors['text_dim']
        ).pack(side="left", padx=10)

        # Audio files list with scrollbar
        audio_list_frame = ctk.CTkFrame(main_frame, fg_color=self.colors['bg_medium'])
        audio_list_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.audio_listbox = tk.Listbox(
            audio_list_frame,
            bg=self.colors['bg_medium'],
            fg=self.colors['text'],
            selectmode=tk.EXTENDED,
            selectbackground=self.colors['accent'],
            selectforeground=self.colors['text']
        )
        scrollbar = ctk.CTkScrollbar(audio_list_frame, command=self.audio_listbox.yview)
        self.audio_listbox.configure(yscrollcommand=scrollbar.set)

        self.audio_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Audio file buttons
        audio_btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        audio_btn_frame.pack(fill="x", pady=(0, 20))

        ctk.CTkButton(
            audio_btn_frame,
            text="📁 Add Files",
            command=self.add_audio_files,
            fg_color=self.colors['secondary'],
            hover_color=self.colors['accent'],
            text_color=self.colors['text'],
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=5)

        if self.audio_library:
            ctk.CTkButton(
                audio_btn_frame,
                text="📚 Add from Library",
                command=self.add_from_library,
                fg_color=self.colors['accent'],
                hover_color=self.colors['secondary'],
                text_color=self.colors['text'],
                font=ctk.CTkFont(size=11)
            ).pack(side="left", padx=5)

        ctk.CTkButton(
            audio_btn_frame,
            text="🗑️ Remove Selected",
            command=self.remove_selected_files,
            fg_color=self.colors['danger'],
            hover_color=self.colors['danger_hover'],
            text_color=self.colors['text']
        ).pack(side="left", padx=5)

        # Bottom buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.cancel,
            fg_color=self.colors['bg_medium'],
            hover_color=self.colors['accent'],
            text_color=self.colors['text'],
            width=100
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="💾 Save",
            command=self.save,
            fg_color=self.colors['secondary'],
            hover_color=self.colors['accent'],
            text_color=self.colors['text'],
            width=100,
            font=ctk.CTkFont(weight="bold")
        ).pack(side="right", padx=5)

    def browse_game_file(self):
        """Browse for game files with context about where they play"""
        if not self.game_manager or not self.game_manager.game_directory:
            messagebox.showwarning("No Game Directory", "Please set the game directory in Settings first.")
            return

        # Get music directories (prioritizing Unofficial Patch)
        music_dirs = get_music_directories(self.game_manager.game_directory)
        if not music_dirs:
            messagebox.showwarning("No Music Directories",
                                 "No music directories found. Make sure the Unofficial Patch is installed.")
            return

        # Collect audio files from all directories
        audio_files = []
        for music_dir in music_dirs:
            dir_path = music_dir['path']
            dir_type = music_dir['type']

            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    if file.lower().endswith(SUPPORTED_AUDIO_FORMATS):
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, self.game_manager.game_directory)

                        # Get music info from catalog
                        music_info = get_music_info(file)

                        audio_files.append({
                            'path': rel_path,
                            'filename': file,
                            'source': dir_type,
                            'info': music_info
                        })

        if not audio_files:
            messagebox.showwarning("No Audio Files", "No audio files found in music directories.")
            return

        # Create enhanced selection dialog
        selection_dialog = ctk.CTkToplevel(self)
        selection_dialog.title("Select Game Audio File")
        selection_dialog.geometry("700x500")
        selection_dialog.configure(fg_color=self.colors['bg_medium'])
        apply_app_icon(selection_dialog)
        selection_dialog.transient(self)
        selection_dialog.grab_set()

        ctk.CTkLabel(
            selection_dialog,
            text="Select the game audio file to replace:",
            font=ctk.CTkFont(weight="bold", size=14),
            text_color=self.colors['text']
        ).pack(pady=10)

        # Info label for selection details
        info_frame = ctk.CTkFrame(selection_dialog, fg_color=self.colors['bg_dark'])
        info_frame.pack(fill="x", padx=20, pady=(0, 10))

        info_label = ctk.CTkLabel(
            info_frame,
            text="Select a file to see details",
            wraplength=650,
            font=ctk.CTkFont(size=11),
            text_color=self.colors['text_dim']
        )
        info_label.pack(pady=5)

        list_frame = ctk.CTkFrame(selection_dialog, fg_color=self.colors['bg_dark'])
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        listbox = tk.Listbox(
            list_frame,
            bg=self.colors['bg_medium'],
            fg=self.colors['text'],
            font=("Consolas", 10),
            selectbackground=self.colors['accent'],
            selectforeground=self.colors['text']
        )
        scrollbar = ctk.CTkScrollbar(list_frame, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)

        # Populate list with enhanced display
        for file_data in audio_files:
            filename = file_data['filename']
            source = file_data['source']

            # Create display text
            display_text = f"{filename} [{source}]"
            listbox.insert(tk.END, display_text)

        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_selection_change(event):
            selection = listbox.curselection()
            if selection:
                file_data = audio_files[selection[0]]
                info = file_data['info']

                if info:
                    info_text = f"📍 {info['description']} | Location: {info['location']} | Type: {info['type'].capitalize()}"
                else:
                    info_text = f"File: {file_data['path']}"

                info_label.configure(text=info_text)

        listbox.bind('<<ListboxSelect>>', on_selection_change)

        def select_file():
            selection = listbox.curselection()
            if selection:
                file_data = audio_files[selection[0]]
                self.game_file_entry.delete(0, tk.END)
                self.game_file_entry.insert(0, file_data['path'])

                # Check if this is a radio file and show warning
                info = file_data['info']
                if info and info.get('type') in ['radio', 'radio_loop'] and info.get('note'):
                    track_type = info.get('type')
                    if track_type == 'radio_loop':
                        self.radio_warning_label.configure(
                            text=f"📻 RADIO LOOP (Deb of Night): {info['note']}",
                            text_color="#00BFFF"
                        )
                    else:
                        self.radio_warning_label.configure(
                            text=f"⚠️ RADIO TRACK: {info['note']}",
                            text_color="#FFA500"
                        )
                    self.radio_warning_label.pack(anchor="w", pady=(0, 10))
                else:
                    self.radio_warning_label.pack_forget()

                selection_dialog.destroy()

        ctk.CTkButton(
            selection_dialog,
            text="Select",
            command=select_file,
            width=120,
            fg_color=self.colors['secondary'],
            hover_color=self.colors['accent'],
            text_color=self.colors['text']
        ).pack(pady=10)

        finalize_modal(selection_dialog, min_width=720, min_height=540)

    def add_audio_files(self):
        """Add audio files to the playlist"""
        filetypes = [
            ("Audio Files", "*.mp3 *.wav *.ogg *.flac *.m4a *.aac"),
            ("All Files", "*.*")
        ]

        filenames = filedialog.askopenfilenames(title="Select Audio Files", filetypes=filetypes)

        for filename in filenames:
            # Validate file
            is_valid, error = self.audio_processor.validate_audio_file(filename)
            if is_valid:
                # Get just the filename for display
                display_name = os.path.basename(filename)
                self.audio_listbox.insert(tk.END, f"{display_name} | {filename}")
            else:
                messagebox.showerror("Invalid File", f"Could not add {filename}:\n{error}")

    def add_from_library(self):
        """Add files from the audio library"""
        if not self.audio_library:
            messagebox.showinfo("Empty Library", "Audio library is empty. Import some files first!")
            return

        # Create selection dialog
        library_dialog = ctk.CTkToplevel(self)
        library_dialog.title("Add from Audio Library")
        library_dialog.geometry("500x400")
        library_dialog.configure(fg_color=self.colors['bg_medium'])
        apply_app_icon(library_dialog)
        library_dialog.transient(self)
        library_dialog.grab_set()

        ctk.CTkLabel(
            library_dialog,
            text="Select files from your Audio Library:",
            font=ctk.CTkFont(weight="bold", size=13),
            text_color=self.colors['text']
        ).pack(pady=15)

        # List with checkboxes
        list_frame = ctk.CTkScrollableFrame(
            library_dialog,
            fg_color=self.colors['bg_dark']
        )
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        selected_files = []
        checkboxes = []

        for audio_file in self.audio_library:
            var = ctk.BooleanVar()
            frame = ctk.CTkFrame(list_frame, fg_color="transparent")
            frame.pack(fill="x", pady=2)

            check = ctk.CTkCheckBox(
                frame,
                text="",
                variable=var,
                width=30,
                fg_color=self.colors['secondary'],
                hover_color=self.colors['accent']
            )
            check.pack(side="left", padx=5)

            label = ctk.CTkLabel(
                frame,
                text=f"🎵 {audio_file.filename}",
                font=ctk.CTkFont(size=11),
                text_color=self.colors['text'],
                anchor="w"
            )
            label.pack(side="left", fill="x", expand=True, padx=5)

            checkboxes.append((var, audio_file))

        def add_selected():
            count = 0
            for var, audio_file in checkboxes:
                if var.get():
                    display_name = audio_file.filename
                    self.audio_listbox.insert(tk.END, f"{display_name} | {audio_file.path}")
                    count += 1

            library_dialog.destroy()
            if count > 0:
                messagebox.showinfo("Success", f"Added {count} file(s) from library!")

        # Buttons
        btn_frame = ctk.CTkFrame(library_dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=15)

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=library_dialog.destroy,
            fg_color=self.colors['bg_medium'],
            hover_color=self.colors['accent'],
            text_color=self.colors['text']
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Add Selected",
            command=add_selected,
            fg_color=self.colors['secondary'],
            hover_color=self.colors['accent'],
            text_color=self.colors['text'],
            font=ctk.CTkFont(weight="bold")
        ).pack(side="right", padx=5)

        finalize_modal(library_dialog, min_width=540, min_height=420)

    def remove_selected_files(self):
        """Remove selected files from the list"""
        selected = self.audio_listbox.curselection()
        for index in reversed(selected):
            self.audio_listbox.delete(index)

    def load_playlist_data(self):
        """Load data from existing playlist"""
        if not self.playlist:
            return

        self.name_entry.insert(0, self.playlist.name)
        self.location_var.set(self.playlist.location_type)
        self.game_file_entry.insert(0, self.playlist.game_file_path)
        self.playback_var.set(self.playlist.playback_mode)

        # Check if this is assigned to a radio file and show warning
        if self.playlist.game_file_path:
            filename = os.path.basename(self.playlist.game_file_path)
            music_info = get_music_info(filename)
            if music_info and music_info.get('type') in ['radio', 'radio_loop'] and music_info.get('note'):
                track_type = music_info.get('type')
                if track_type == 'radio_loop':
                    self.radio_warning_label.configure(
                        text=f"📻 RADIO LOOP (Deb of Night): {music_info['note']}",
                        text_color="#00BFFF"
                    )
                else:
                    self.radio_warning_label.configure(
                        text=f"⚠️ RADIO TRACK: {music_info['note']}",
                        text_color="#FFA500"
                    )
                self.radio_warning_label.pack(anchor="w", pady=(0, 10))

        for audio_file in self.playlist.audio_files:
            display_name = audio_file.filename
            self.audio_listbox.insert(tk.END, f"{display_name} | {audio_file.path}")

    def save(self):
        """Save the playlist"""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a playlist name")
            return

        game_file = self.game_file_entry.get().strip()
        # Game file is now optional - can be assigned later via track assignment

        # Get audio files
        audio_files = []
        for i in range(self.audio_listbox.size()):
            item = self.audio_listbox.get(i)
            # Parse: "filename | full_path"
            parts = item.split(" | ", 1)
            if len(parts) == 2:
                filename, path = parts
                audio_files.append(AudioFile(path=path, filename=filename))

        if not audio_files:
            messagebox.showerror("Error", "Please add at least one audio file")
            return

        # Create or update playlist
        if self.playlist:
            self.playlist.name = name
            self.playlist.location_type = self.location_var.get()
            self.playlist.game_file_path = game_file
            self.playlist.playback_mode = self.playback_var.get()
            self.playlist.audio_files = audio_files
            self.result = self.playlist
        else:
            self.result = Playlist(
                name=name,
                location_type=self.location_var.get(),
                game_file_path=game_file,
                audio_files=audio_files,
                playback_mode=self.playback_var.get()
            )

        self.destroy()

    def cancel(self):
        """Cancel editing"""
        self.result = None
        self.destroy()


class VTMBPlaylistMakerApp(ctk.CTk):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # Initialize
        self.config = AppConfig.load()
        self.audio_processor = AudioProcessor()
        self.game_manager = GameFileManager(
            self.config.game_directory,
            self.config.backup_directory
        )
        self.radio_segment_manager = RadioSegmentManager(self.config.game_directory)
        self.whisper_manager = MalkavianWhisperManager(self.config.game_directory)

        # Configure window
        self.title("VTMB Playlist Maker")
        self.geometry("900x700")
        self.minsize(800, 600)  # Prevent window from being too small

        # Set vampire red theme
        ctk.set_appearance_mode("dark")
        self._setup_vampire_theme()
        apply_app_icon(self)

        self.setup_ui()
        self.refresh_playlists()

        # Optimize window resize performance
        self._resize_timer = None
        self.bind("<Configure>", self._on_resize)

        # Validate FFMPEG availability on startup
        self.after(100, self._validate_ffmpeg_on_startup)

        # Auto-detect game directory on first launch
        if not self.config.game_directory:
            self.auto_detect_game_directory()
        else:
            # Auto-scan on launch if game directory is set
            self.after(500, self.scan_game_tracks)  # Delay to let UI load first

    def _on_resize(self, event):
        """Handle window resize with debouncing for better performance"""
        # Only handle main window resize, not child widgets
        if event.widget != self:
            return

        # Cancel previous timer if it exists
        if self._resize_timer is not None:
            self.after_cancel(self._resize_timer)

        # Set a new timer to update after resize stops
        self._resize_timer = self.after(50, self._finish_resize)

    def _finish_resize(self):
        """Called after resize has stopped"""
        self._resize_timer = None
        # Force geometry update
        self.update_idletasks()

    def _validate_ffmpeg_on_startup(self):
        """Validate FFMPEG availability and show warning if missing"""
        is_valid, error_msg = validate_ffmpeg()
        if not is_valid:
            messagebox.showwarning(
                "FFMPEG Not Available",
                f"{error_msg}\n\n"
                "You can still use the application to browse and preview tracks, "
                "but you will not be able to generate playlist audio files until FFMPEG is installed.\n\n"
                "For PyInstaller builds: Ensure ffmpeg is bundled in the 'ffmpeg/bin/' directory.\n"
                "For development: Install FFMPEG and ensure it's in your system PATH."
            )

    def _setup_vampire_theme(self):
        """Setup custom vampire red theme"""
        # Define vampire red color palette
        self.colors = {
            'primary': '#8B0000',      # Dark red
            'primary_hover': '#A50000', # Lighter red
            'secondary': '#DC143C',    # Crimson
            'accent': '#B22222',       # Firebrick
            'danger': '#8B0000',       # Dark red for delete
            'danger_hover': '#A50000',
            'bg_dark': '#1a0000',      # Very dark red-black
            'bg_medium': '#2d0a0a',    # Dark red-brown
            'text': '#FFE4E4',         # Light pink-white
            'text_dim': '#B88888',     # Dimmed red-gray
        }

    def _init_audio_mixer(self):
        """Ensure pygame mixer is initialized and ready for playback."""
        if pygame.mixer.get_init():
            return
        try:
            pygame.mixer.init()
            pygame.mixer.music.set_volume(0.7)
        except Exception as e:
            print(f"Warning: Could not initialize audio playback: {e}")

    def setup_ui(self):
        # Header with vampire theme
        header = ctk.CTkFrame(self, height=80, corner_radius=0, fg_color=self.colors['bg_dark'])
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        # Load custom font if available
        custom_font_path = load_custom_font()
        if custom_font_path:
            title_font = ctk.CTkFont(family="Bubblegum Sans", size=28, weight="normal")
        else:
            title_font = ctk.CTkFont(size=26, weight="bold")

        title_label = ctk.CTkLabel(
            header,
            text="🦇 Lace's VTMB Playlist Maker",
            font=title_font,
            text_color=self.colors['text']
        )
        title_label.pack(pady=20)

        # Main content
        content = ctk.CTkFrame(self, fg_color=self.colors['bg_medium'])
        content.pack(fill="both", expand=True, padx=15, pady=15)

        # Top toolbar
        toolbar = ctk.CTkFrame(content, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 15))

        ctk.CTkButton(
            toolbar,
            text="⚙️ Settings",
            command=self.open_settings,
            width=100,
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_hover'],
            text_color=self.colors['text']
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            toolbar,
            text="💾 Backup",
            command=self.backup_game_files,
            width=100,
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_hover'],
            text_color=self.colors['text']
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            toolbar,
            text="🔄 Restore",
            command=self.restore_backup,
            width=100,
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_hover'],
            text_color=self.colors['text']
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            toolbar,
            text="🎵 Apply Changes",
            command=self.apply_playlists,
            fg_color=self.colors['secondary'],
            hover_color=self.colors['accent'],
            width=150,
            text_color=self.colors['text'],
            font=ctk.CTkFont(weight="bold")
        ).pack(side="right", padx=5)

        # Location selector section
        location_section = ctk.CTkFrame(content, fg_color=self.colors['bg_dark'])
        location_section.pack(fill="x", pady=(0, 15), padx=10)

        location_header = ctk.CTkFrame(location_section, fg_color="transparent")
        location_header.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            location_header,
            text="📍 Browse by Location:",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.colors['text']
        ).pack(side="left", padx=(0, 10))

        # Location dropdown (will be populated dynamically after scanning)
        self.location_var = ctk.StringVar(value="All Locations")

        self.location_dropdown = ctk.CTkComboBox(
            location_header,
            values=["All Locations"],  # Will be updated after scan
            variable=self.location_var,
            width=180,
            fg_color=self.colors['primary'],
            button_color=self.colors['accent'],
            button_hover_color=self.colors['secondary'],
            dropdown_fg_color=self.colors['bg_dark'],
            text_color=self.colors['text'],
            command=self.on_location_change
        )
        self.location_dropdown.pack(side="left", padx=5)

        # Track type filter
        ctk.CTkLabel(
            location_header,
            text="Filter:",
            font=ctk.CTkFont(size=12),
            text_color=self.colors['text']
        ).pack(side="left", padx=(15, 5))

        self.filter_var = ctk.StringVar(value="All Tracks")
        filters = ["All Tracks", "🎸 Licensed Only", "🎵 Rik Schaffer Only", "📍 By Location"]

        self.filter_dropdown = ctk.CTkComboBox(
            location_header,
            values=filters,
            variable=self.filter_var,
            width=160,
            fg_color=self.colors['accent'],
            button_color=self.colors['secondary'],
            button_hover_color=self.colors['primary'],
            dropdown_fg_color=self.colors['bg_dark'],
            text_color=self.colors['text'],
            command=self.on_filter_change
        )
        self.filter_dropdown.pack(side="left", padx=5)

        self.scan_button = ctk.CTkButton(
            location_header,
            text="🔍 Scan Game Files",
            command=self.scan_game_tracks,
            width=140,
            fg_color=self.colors['accent'],
            hover_color=self.colors['secondary'],
            text_color=self.colors['text']
        )
        self.scan_button.pack(side="left", padx=10)

        # Main split view
        main_view = ctk.CTkFrame(content, fg_color="transparent")
        main_view.pack(fill="both", expand=True, padx=10)

        # Left panel - Tracks view
        tracks_panel = ctk.CTkFrame(main_view, fg_color=self.colors['bg_dark'])
        tracks_panel.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Header with explanation
        tracks_header = ctk.CTkFrame(tracks_panel, fg_color="transparent")
        tracks_header.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            tracks_header,
            text="🎵 Game Tracks",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors['text']
        ).pack(anchor="w")

        # Explanation of how playlists work
        explanation = ctk.CTkFrame(tracks_panel, fg_color=self.colors['bg_medium'], corner_radius=8)
        explanation.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(
            explanation,
            text="💡 How It Works",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.colors['secondary']
        ).pack(anchor="w", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            explanation,
            text="Each game track below plays in a specific location. When you create a playlist\n"
                 "with multiple songs, they're combined into ONE audio file that replaces the\n"
                 "original. The game will then loop your custom mix at that location!",
            font=ctk.CTkFont(size=10),
            text_color=self.colors['text_dim'],
            justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # Scrollable tracks container
        self.tracks_container = ctk.CTkScrollableFrame(
            tracks_panel,
            fg_color=self.colors['bg_medium']
        )
        self.tracks_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Right panel - Playlists
        playlists_panel = ctk.CTkFrame(main_view, fg_color=self.colors['bg_dark'], width=400)
        playlists_panel.pack(side="right", fill="both", padx=(8, 0))
        playlists_panel.pack_propagate(False)

        # Playlists Section
        playlist_header = ctk.CTkFrame(playlists_panel, fg_color="transparent")
        playlist_header.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            playlist_header,
            text="📝 Your Playlists",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors['text']
        ).pack(side="left")

        ctk.CTkButton(
            playlist_header,
            text="+",
            width=30,
            command=self.new_playlist,
            fg_color=self.colors['secondary'],
            hover_color=self.colors['accent'],
            text_color=self.colors['text']
        ).pack(side="right")

        # Scrollable playlists container
        self.playlists_container = ctk.CTkScrollableFrame(
            playlists_panel,
            fg_color=self.colors['bg_medium']
        )
        self.playlists_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Audio Player Control Bar (at bottom of window)
        player_bar = ctk.CTkFrame(content, fg_color=self.colors['bg_dark'], height=100)
        player_bar.pack(fill="x", side="bottom", pady=(10, 0))
        player_bar.pack_propagate(False)

        # Player controls frame
        controls_frame = ctk.CTkFrame(player_bar, fg_color="transparent")
        controls_frame.pack(side="left", padx=15, pady=10)

        # Control buttons
        self.prev_btn = ctk.CTkButton(
            controls_frame,
            text="⏮",
            width=40,
            height=40,
            command=self.play_previous_track,
            fg_color=self.colors['accent'],
            hover_color=self.colors['secondary'],
            text_color=self.colors['text'],
            font=ctk.CTkFont(size=18)
        )
        self.prev_btn.pack(side="left", padx=3)

        self.play_pause_btn = ctk.CTkButton(
            controls_frame,
            text="▶",
            width=50,
            height=50,
            command=self.toggle_playback,
            fg_color=self.colors['secondary'],
            hover_color=self.colors['accent'],
            text_color=self.colors['text'],
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.play_pause_btn.pack(side="left", padx=3)

        self.stop_btn = ctk.CTkButton(
            controls_frame,
            text="⏹",
            width=40,
            height=40,
            command=self.stop_playback,
            fg_color=self.colors['accent'],
            hover_color=self.colors['secondary'],
            text_color=self.colors['text'],
            font=ctk.CTkFont(size=18)
        )
        self.stop_btn.pack(side="left", padx=3)

        self.next_btn = ctk.CTkButton(
            controls_frame,
            text="⏭",
            width=40,
            height=40,
            command=self.play_next_track,
            fg_color=self.colors['accent'],
            hover_color=self.colors['secondary'],
            text_color=self.colors['text'],
            font=ctk.CTkFont(size=18)
        )
        self.next_btn.pack(side="left", padx=3)

        # Track info and progress frame
        info_frame = ctk.CTkFrame(player_bar, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        # Current track label
        self.current_track_label = ctk.CTkLabel(
            info_frame,
            text="No track playing",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors['text'],
            anchor="w"
        )
        self.current_track_label.pack(anchor="w", pady=(5, 2))

        # Progress bar frame
        progress_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        progress_frame.pack(fill="x", pady=(0, 2))

        self.time_elapsed_label = ctk.CTkLabel(
            progress_frame,
            text="0:00",
            font=ctk.CTkFont(size=10),
            text_color=self.colors['text_dim'],
            width=40
        )
        self.time_elapsed_label.pack(side="left", padx=(0, 5))

        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            height=8,
            progress_color=self.colors['secondary']
        )
        self.progress_bar.pack(side="left", fill="x", expand=True)
        self.progress_bar.set(0)

        self.time_total_label = ctk.CTkLabel(
            progress_frame,
            text="0:00",
            font=ctk.CTkFont(size=10),
            text_color=self.colors['text_dim'],
            width=40
        )
        self.time_total_label.pack(side="left", padx=(5, 0))

        # Volume control frame
        volume_frame = ctk.CTkFrame(player_bar, fg_color="transparent")
        volume_frame.pack(side="right", padx=15, pady=10)

        ctk.CTkLabel(
            volume_frame,
            text="🔊",
            font=ctk.CTkFont(size=16),
            text_color=self.colors['text']
        ).pack(side="left", padx=(0, 8))

        self.volume_slider = ctk.CTkSlider(
            volume_frame,
            from_=0,
            to=100,
            width=120,
            height=16,
            command=self.on_volume_change,
            button_color=self.colors['secondary'],
            button_hover_color=self.colors['accent'],
            progress_color=self.colors['secondary']
        )
        self.volume_slider.pack(side="left")
        self.volume_slider.set(70)  # Default volume 70%

        # Initialize track data
        self.game_tracks = []  # Will hold discovered game tracks
        self.filtered_tracks = []  # Currently filtered tracks for navigation
        self.current_playing_track = None  # Track currently playing
        self.current_track_index = -1  # Index in filtered_tracks list
        self.is_playing = False
        self.current_track_duration = 0.0  # Cache for current track duration
        self.track_duration_cache = {}  # Cache for all track durations

        # Initialize pygame mixer for audio playback
        self._init_audio_mixer()

        # Start progress update loop
        self.update_progress()

    def scan_game_tracks(self):
        """Scan game directory for all music tracks (starts background thread)"""
        if not self.config.game_directory:
            messagebox.showwarning("No Game Directory",
                                 "Please set the game directory in Settings first.")
            return

        # Check if already scanning
        if hasattr(self, '_is_scanning') and self._is_scanning:
            messagebox.showinfo("Scan In Progress", "A scan is already in progress. Please wait...")
            return

        # Stop any playing audio before scanning to prevent file locks
        if self.current_playing_track:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()  # Explicitly unload to release file handles
                self.current_playing_track = None
                self.is_playing = False
                if hasattr(self, 'play_pause_btn'):
                    self.play_pause_btn.configure(text="▶")
            except:
                pass

        # Start scanning in background thread
        self._is_scanning = True
        if hasattr(self, 'scan_button'):
            self.scan_button.configure(state="disabled", text="⏳ Scanning...")
        self._scan_progress_dialog = ScanProgressDialog(self, colors=self.colors)
        thread = threading.Thread(target=self._scan_game_tracks_thread, daemon=True)
        thread.start()

    def _scan_game_tracks_thread(self):
        """Background thread for scanning game tracks"""
        import time

        # Give Windows time to release file handles
        time.sleep(0.2)

        try:
            # Get music directories
            music_dirs = get_music_directories(self.config.game_directory)
            if not music_dirs:
                def _show_warning():
                    messagebox.showwarning("No Music Directories",
                                         "No music directories found. Make sure the Unofficial Patch is installed.")
                    self._scan_progress_dialog.close()
                    self._is_scanning = False
                    if hasattr(self, 'scan_button'):
                        self.scan_button.configure(state="normal", text="🔍 Scan Game Files")
                self.after(0, _show_warning)
                return

            self._scan_progress_dialog.update_status("Scanning music directories...")

            tracks_by_path: dict[str, dict] = {}
            radio_segments_added = 0

            # Collect all audio files
            for music_dir in music_dirs:
                dir_path = music_dir['path']
                dir_type = music_dir['type']
                priority = music_dir.get('priority', 99)
                display_path = dir_path
                if self.config.game_directory:
                    try:
                        display_path = os.path.relpath(dir_path, self.config.game_directory)
                    except ValueError:
                        # Fallback if paths are on different drives
                        display_path = dir_path
                self._scan_progress_dialog.update_status(f"Scanning {display_path}...")

                for root, dirs, files in os.walk(dir_path):
                    for file in files:
                        if file.lower().endswith(SUPPORTED_AUDIO_FORMATS):
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, self.config.game_directory)
                            normalized_key = rel_path.replace("\\", "/").lower()

                            # Get music info from catalog
                            music_info = get_music_info(file)

                            track_data = {
                                'filename': file,
                                'path': rel_path,
                                'full_path': full_path,
                                'source': dir_type,
                                'source_priority': priority,
                                'info': music_info,
                                'override_sources': [],
                                'alternate_paths': []
                            }

                            existing = tracks_by_path.get(normalized_key)
                            if not existing:
                                tracks_by_path[normalized_key] = track_data
                            else:
                                if priority < existing.get('source_priority', 99):
                                    alt_paths = existing.get('alternate_paths', [])
                                    alt_paths.append(existing['path'])
                                    track_data['alternate_paths'] = list(dict.fromkeys(alt_paths))

                                    overrides = existing.get('override_sources', [])
                                    overrides.append(existing['source'])
                                    track_data['override_sources'] = list(dict.fromkeys(overrides))

                                    tracks_by_path[normalized_key] = track_data
                                else:
                                    overrides = existing.setdefault('override_sources', [])
                                    if dir_type not in overrides:
                                        overrides.append(dir_type)

                                    alt_paths = existing.setdefault('alternate_paths', [])
                                    if rel_path not in alt_paths:
                                        alt_paths.append(rel_path)

            self.game_tracks = sorted(tracks_by_path.values(), key=lambda t: t['filename'].lower())

            # Also scan radio loops and add segments as individual tracks
            for music_dir in music_dirs:
                if 'Radio' in music_dir['type']:  # This is a radio directory
                    radio_display = music_dir['path']
                    if self.config.game_directory:
                        try:
                            radio_display = os.path.relpath(music_dir['path'], self.config.game_directory)
                        except ValueError:
                            radio_display = music_dir['path']
                    self._scan_progress_dialog.update_status(f"Analyzing {radio_display}...")
                    segments = self.radio_segment_manager.scan_radio_loops(music_dir['path'])

                    for segment in segments:
                        # Use the cached segment audio for preview (not the full loop!)
                        preview_path = segment.cached_audio_path if segment.cached_audio_path else self.radio_segment_manager.get_original_loop_path(segment.loop_name)

                        # Use the segment's actual label with type prefix for clarity
                        loop_num = segment.loop_name.replace('radio_loop_', '')

                        # Add type prefix based on segment type
                        if segment.segment_type == 'dialogue':
                            display_label = f"Deb - {segment.label}"
                        elif segment.segment_type == 'commercial':
                            display_label = f"Commercial - {segment.label}"
                        elif segment.segment_type == 'political':
                            display_label = f"Political Ad - {segment.label}"
                        elif segment.segment_type == 'music':
                            display_label = f"Music - {segment.label}"
                        else:
                            display_label = segment.label

                        # Clean for filename use
                        clean_label = display_label.replace(' ', '_').replace("'", "").replace('(', '').replace(')', '').replace('-', '')
                        friendly_name = f"Loop{loop_num}_{clean_label}.mp3"

                        # Create a track entry for this segment
                        segment_track = {
                            'filename': friendly_name,
                            'path': self.radio_segment_manager.get_segment_game_path(segment),
                            'full_path': preview_path,  # Use cached segment for preview!
                            'source': music_dir['type'],
                            'source_priority': music_dir.get('priority', 99),
                            'info': {
                                'description': segment.display_name,
                                'location': 'Radio Shows',
                                'type': 'radio_segment',
                                'note': f"This is segment {segment.index + 1} of {segment.loop_name}. Your playlist replaces just this segment."
                            },
                            'override_sources': [],
                            'alternate_paths': [],
                            'is_radio_segment': True,
                            'radio_segment': segment  # Store the segment object
                        }

                        self.game_tracks.append(segment_track)
                        radio_segments_added += 1

            # Re-sort to include segments
            self.game_tracks = sorted(self.game_tracks, key=lambda t: t['filename'].lower())

            total_tracks = len(self.game_tracks)
            regular_tracks = total_tracks - radio_segments_added

            # Schedule UI updates on main thread
            def _complete_scan():
                self._scan_progress_dialog.close()
                self._is_scanning = False
                if hasattr(self, 'scan_button'):
                    self.scan_button.configure(state="normal", text="🔍 Scan Game Files")

                messagebox.showinfo(
                    "Scan Complete",
                    f"Found {regular_tracks} music tracks + {radio_segments_added} radio segments\n"
                    f"Total: {total_tracks} editable tracks in the game directory."
                )

                self.update_location_dropdown()
                self.refresh_tracks()

            self.after(0, _complete_scan)

        except Exception as e:
            # Handle any errors during scan
            def _show_error():
                self._scan_progress_dialog.close()
                self._is_scanning = False
                if hasattr(self, 'scan_button'):
                    self.scan_button.configure(state="normal", text="🔍 Scan Game Files")
                messagebox.showerror(
                    "Scan Error",
                    f"An error occurred while scanning:\n\n{str(e)}\n\nPlease check that your game directory is correct and accessible."
                )
            self.after(0, _show_error)

    def update_location_dropdown(self):
        """Update location dropdown based on scanned tracks"""
        # Get all unique locations from scanned tracks
        locations_in_tracks = set()
        for track in self.game_tracks:
            if track['info'] and 'location' in track['info']:
                locations_in_tracks.add(track['info']['location'])

        catalog_order = get_all_locations()
        sorted_locations = ["All Locations"]

        for location in catalog_order:
            if location in locations_in_tracks:
                sorted_locations.append(location)

        # Always add Malkavian Whispers to the dropdown (special location for whisper management)
        if "Malkavian Whispers" not in sorted_locations:
            sorted_locations.append("Malkavian Whispers")

        # Add any remaining locations not in the predefined order
        for location in sorted(locations_in_tracks):
            if location not in sorted_locations:
                sorted_locations.append(location)

        # Update dropdown values
        self.location_dropdown.configure(values=sorted_locations)

        # Reset to "All Locations" if current value is not in the new list
        current_value = self.location_var.get()
        if current_value not in sorted_locations:
            self.location_var.set("All Locations")

    def on_location_change(self, choice):
        """Handle location dropdown change"""
        self.refresh_tracks()

    def on_filter_change(self, choice):
        """Handle filter dropdown change"""
        self.refresh_tracks()

    def refresh_tracks(self):
        """Refresh the tracks display based on selected location and filter"""
        # Clear existing
        for widget in self.tracks_container.winfo_children():
            widget.destroy()

        # Check for special locations first (before filtering)
        selected_location = self.location_var.get()

        # Display Malkavian Whispers if that location is selected
        if selected_location == "Malkavian Whispers":
            self.display_malkavian_whispers()
            return

        if not self.game_tracks:
            self.filtered_tracks = []
            ctk.CTkLabel(
                self.tracks_container,
                text="No tracks loaded.\nClick 'Scan Game Files' to discover tracks.",
                font=ctk.CTkFont(size=12),
                text_color=self.colors['text_dim']
            ).pack(pady=30)
            return

        # Start with all tracks
        filtered_tracks = self.game_tracks

        # Apply track type filter first
        selected_filter = self.filter_var.get()
        if selected_filter == "🎸 Licensed Only":
            # Show only tracks with artist attribution (licensed music)
            filtered_tracks = [
                t for t in filtered_tracks
                if t['info'] and t['info'].get('artist')
            ]
        elif selected_filter == "🎵 Rik Schaffer Only":
            # Show only tracks WITHOUT artist attribution (original score)
            filtered_tracks = [
                t for t in filtered_tracks
                if not t['info'] or not t['info'].get('artist')
            ]

        # Then apply location filter
        if selected_location != "All Locations" and selected_filter == "📍 By Location":
            filtered_tracks = [
                t for t in filtered_tracks
                if t['info'] and t['info'].get('location') == selected_location
            ]
        elif selected_location != "All Locations" and selected_filter == "All Tracks":
            filtered_tracks = [
                t for t in filtered_tracks
                if t['info'] and t['info'].get('location') == selected_location
            ]

        if not filtered_tracks:
            self.filtered_tracks = []
            filter_desc = selected_filter if selected_filter != "All Tracks" else ""
            location_desc = selected_location if selected_location != "All Locations" else ""
            desc_parts = [p for p in [filter_desc, location_desc] if p]
            description = " - ".join(desc_parts) if desc_parts else "these filters"

            ctk.CTkLabel(
                self.tracks_container,
                text=f"No tracks found for {description}",
                font=ctk.CTkFont(size=12),
                text_color=self.colors['text_dim']
            ).pack(pady=30)
            return

        # Store filtered tracks for player navigation
        self.filtered_tracks = filtered_tracks

        # Add special explanation for Radio Shows location
        if selected_location == "Radio Shows":
            explanation_frame = ctk.CTkFrame(
                self.tracks_container,
                fg_color=self.colors['bg_dark'],
                corner_radius=8
            )
            explanation_frame.pack(fill="x", padx=5, pady=(0, 15))

            ctk.CTkLabel(
                explanation_frame,
                text="📻 About Radio Shows",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#00BFFF",
                anchor="w"
            ).pack(anchor="w", padx=15, pady=(10, 5))

            explanation_text = (
                "These are the Deb of Night talk radio loops that play randomly in the game.\n\n"
                "• Each file contains Deb of Night dialogue + commercials already mixed together\n"
                "• The game randomly selects one of the 5 loops to play\n"
                "• You can replace them with music, podcasts, comedy, or your own content\n"
                "• Use ONE long file OR create a playlist that gets combined into one loop"
            )

            ctk.CTkLabel(
                explanation_frame,
                text=explanation_text,
                font=ctk.CTkFont(size=11),
                text_color=self.colors['text'],
                anchor="w",
                justify="left",
                wraplength=600
            ).pack(anchor="w", padx=15, pady=(5, 15))

        # Group tracks by type for better organization
        tracks_by_type = {}
        for track in filtered_tracks:
            track_type = track['info'].get('type', 'other') if track['info'] else 'uncategorized'
            if track_type not in tracks_by_type:
                tracks_by_type[track_type] = []
            tracks_by_type[track_type].append(track)

        # Define type order and labels
        type_order = ['radio_segment', 'radio_loop', 'club', 'combat', 'ambient', 'radio', 'menu', 'other', 'uncategorized']
        type_labels = {
            'radio_segment': '🎙️ Radio Show Segments (Individual Deb/Commercial Segments)',
            'radio_loop': '📻 Radio Show Loops (Full Loops - Advanced)',
            'club': '🎭 Nightclubs & Bars',
            'combat': '⚔️ Combat Music',
            'ambient': '🌆 Ambient & Locations',
            'radio': '📻 Radio Tracks',
            'menu': '📜 Menus & Credits',
            'other': '🎵 Other Tracks',
            'uncategorized': '❓ Uncategorized'
        }

        # Display tracks grouped by type
        for track_type in type_order:
            if track_type in tracks_by_type:
                # Category header
                header_frame = ctk.CTkFrame(
                    self.tracks_container,
                    fg_color=self.colors['bg_dark'],
                    corner_radius=6
                )
                header_frame.pack(fill="x", padx=5, pady=(10, 5))

                ctk.CTkLabel(
                    header_frame,
                    text=type_labels.get(track_type, track_type.capitalize()),
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=self.colors['secondary']
                ).pack(anchor="w", padx=10, pady=6)

                # Display tracks in this category
                for track in tracks_by_type[track_type]:
                    self.create_track_card(track)

    def display_malkavian_whispers(self):
        """Display Malkavian whisper management interface"""
        # Scan whispers
        whispers = self.whisper_manager.scan_whispers()

        if not whispers:
            ctk.CTkLabel(
                self.tracks_container,
                text="No Malkavian whispers found.\nMake sure the Unofficial Patch is installed.",
                font=ctk.CTkFont(size=12),
                text_color=self.colors['text_dim']
            ).pack(pady=30)
            return

        # Add explanation header
        explanation_frame = ctk.CTkFrame(
            self.tracks_container,
            fg_color=self.colors['bg_dark'],
            corner_radius=8
        )
        explanation_frame.pack(fill="x", padx=5, pady=(0, 15))

        ctk.CTkLabel(
            explanation_frame,
            text="🗣️ About Malkavian Whispers",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#9370DB",  # Medium purple
            anchor="w"
        ).pack(anchor="w", padx=15, pady=(10, 5))

        explanation_text = (
            "When playing as a Malkavian, you'll hear random whispers/hallucinations as you explore.\n\n"
            "• The game has 39 empty whisper slots across 8 categories (ambiguous, danger, deluded, etc.)\n"
            "• You can record custom .wav audio for any whisper slot\n"
            "• You can edit the subtitle text that appears when your whisper plays\n"
            "• Custom whispers add personality and immersion to your Malkavian playthrough!"
        )

        ctk.CTkLabel(
            explanation_frame,
            text=explanation_text,
            font=ctk.CTkFont(size=11),
            text_color=self.colors['text'],
            anchor="w",
            justify="left",
            wraplength=600
        ).pack(anchor="w", padx=15, pady=(5, 15))

        # Display whispers grouped by category
        category_order = ['ambiguous', 'danger', 'deluded', 'distrust', 'gibberish', 'lying', 'quest', 'threat']

        for category in category_order:
            if category in whispers:
                category_whispers = whispers[category]

                # Category header
                audio_count = sum(1 for w in category_whispers if w.has_audio)
                header_frame = ctk.CTkFrame(
                    self.tracks_container,
                    fg_color=self.colors['bg_dark'],
                    corner_radius=6
                )
                header_frame.pack(fill="x", padx=5, pady=(10, 5))

                ctk.CTkLabel(
                    header_frame,
                    text=f"🗣️ {category.upper()} ({len(category_whispers)} whispers, {audio_count} with audio)",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=self.colors['secondary']
                ).pack(anchor="w", padx=10, pady=6)

                # Display whispers in this category
                for whisper in category_whispers:
                    self.create_whisper_card(whisper)

    def create_whisper_card(self, whisper):
        """Create a card widget for a Malkavian whisper"""
        card = ctk.CTkFrame(
            self.tracks_container,
            fg_color=self.colors['bg_dark'],
            corner_radius=8
        )
        card.pack(fill="x", padx=5, pady=5)

        # Whisper info section
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(fill="x", padx=10, pady=8)

        # Whisper name
        name_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        name_frame.pack(fill="x")

        # Display name with audio status indicator
        audio_status = "🔊" if whisper.has_audio else "🔇"
        name_label = ctk.CTkLabel(
            name_frame,
            text=f"{audio_status} {whisper.display_name}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors['text'],
            anchor="w"
        )
        name_label.pack(side="top", anchor="w")

        # Whisper text (subtitle)
        text_label = ctk.CTkLabel(
            name_frame,
            text=f'   "{whisper.text}"',
            font=ctk.CTkFont(size=10),
            text_color=self.colors['text_dim'],
            anchor="w",
            wraplength=500,
            justify="left"
        )
        text_label.pack(side="top", anchor="w", pady=(2, 0))

        # Category badge
        category_label = ctk.CTkLabel(
            name_frame,
            text=f"[{whisper.category}]",
            font=ctk.CTkFont(size=9),
            text_color="#9370DB",  # Medium purple
            anchor="w"
        )
        category_label.pack(side="top", anchor="w", pady=(2, 0))

        # Buttons section
        buttons_frame = ctk.CTkFrame(card, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=10, pady=(0, 8))

        # Edit Subtitle button
        edit_subtitle_btn = ctk.CTkButton(
            buttons_frame,
            text="Edit Subtitle",
            width=100,
            height=28,
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_hover'],
            command=lambda: self.edit_whisper_subtitle(whisper)
        )
        edit_subtitle_btn.pack(side="left", padx=(0, 5))

        # Add/Replace Audio button
        if whisper.has_audio:
            audio_btn_text = "Replace Audio"
            audio_btn_color = self.colors['accent']
        else:
            audio_btn_text = "Add Audio"
            audio_btn_color = self.colors['primary']

        audio_btn = ctk.CTkButton(
            buttons_frame,
            text=audio_btn_text,
            width=100,
            height=28,
            fg_color=audio_btn_color,
            hover_color=self.colors['primary_hover'],
            command=lambda: self.add_whisper_audio(whisper)
        )
        audio_btn.pack(side="left", padx=5)

        # Play button (only if audio exists)
        if whisper.has_audio:
            play_btn = ctk.CTkButton(
                buttons_frame,
                text="▶ Play",
                width=80,
                height=28,
                fg_color=self.colors['secondary'],
                hover_color=self.colors['primary_hover'],
                command=lambda: self.play_whisper_audio(whisper)
            )
            play_btn.pack(side="left", padx=5)

            # Remove Audio button
            remove_btn = ctk.CTkButton(
                buttons_frame,
                text="Remove",
                width=80,
                height=28,
                fg_color="#B22222",  # Firebrick red
                hover_color="#8B0000",  # Dark red
                command=lambda: self.remove_whisper_audio(whisper)
            )
            remove_btn.pack(side="left", padx=5)

    def create_track_card(self, track):
        """Create a card widget for a game track"""
        card = ctk.CTkFrame(
            self.tracks_container,
            fg_color=self.colors['bg_dark'],
            corner_radius=8
        )
        card.pack(fill="x", padx=5, pady=5)

        # Track info section
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(fill="x", padx=10, pady=8)

        # Track name and description
        name_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        name_frame.pack(fill="x")

        if track['info']:
            track_label = ctk.CTkLabel(
                name_frame,
                text=f"🎵 {track['filename']}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=self.colors['text'],
                anchor="w",
                wraplength=520,
                justify="left"
            )
            track_label.pack(side="top", anchor="w")

            desc_label = ctk.CTkLabel(
                name_frame,
                text=f"   {track['info']['description']}",
                font=ctk.CTkFont(size=10),
                text_color=self.colors['text_dim'],
                anchor="w",
                wraplength=520,
                justify="left"
            )
            desc_label.pack(side="top", anchor="w", pady=(2, 0))
        else:
            track_label = ctk.CTkLabel(
                name_frame,
                text=f"🎵 {track['filename']}",
                font=ctk.CTkFont(size=12),
                text_color=self.colors['text'],
                anchor="w",
                wraplength=520,
                justify="left"
            )
            track_label.pack(side="top", anchor="w")

        # Source badge
        source_label = ctk.CTkLabel(
            name_frame,
            text=f"[{track['source']}]",
            font=ctk.CTkFont(size=9),
            text_color=self.colors['accent'],
            anchor="w"
        )
        source_label.pack(side="top", anchor="w", pady=(2, 0))

        # Show special note for radio tracks, radio loops, and radio segments
        if track['info'] and track['info'].get('note'):
            track_type = track['info'].get('type', '')
            if track_type in ['radio', 'radio_loop', 'radio_segment']:
                # Different styling for each type
                if track_type == 'radio_segment':
                    # Radio segments - purple/magenta
                    segment = track.get('radio_segment')
                    if segment:
                        if segment.segment_type == 'dialogue':
                            icon = "🗣️"
                            color = "#FF69B4"  # Hot pink for Deb dialogue
                        elif segment.segment_type == 'commercial':
                            icon = "📻"
                            color = "#00CED1"  # Dark turquoise for commercials
                        elif segment.segment_type == 'political':
                            icon = "🎙️"
                            color = "#FFD700"  # Gold for political ads
                        elif segment.segment_type == 'radio_content':
                            icon = "📡"
                            color = "#808080"  # Gray for non-editable radio content
                        elif segment.segment_type == 'music':
                            icon = "🎸"
                            color = "#FF1493"  # Deep pink for licensed music tracks
                        else:  # jingle
                            icon = "🎵"
                            color = "#9370DB"  # Medium purple for jingles
                    else:
                        icon = "🎙️"
                        color = "#BA55D3"  # Medium orchid
                elif track_type == 'radio_loop':
                    icon = "📻"
                    color = "#00BFFF"  # Light blue for radio loops
                else:  # regular radio
                    icon = "⚠️"
                    color = "#FFA500"  # Orange for regular radio

                radio_note = ctk.CTkLabel(
                    name_frame,
                    text=f"{icon} {track['info']['note']}",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=color,
                    anchor="w",
                    wraplength=520,
                    justify="left"
                )
                radio_note.pack(side="top", anchor="w", pady=(6, 0))

        if track.get('override_sources'):
            override_list = ", ".join(track['override_sources'])
            alt_paths = track.get('alternate_paths') or []
            note_lines = [
                f"🩸 Active override from {track['source']} (also found in: {override_list}).",
                f"Replace '{track['path']}' to change the in-game music."
            ]
            if alt_paths:
                alt_paths_display = ", ".join(alt_paths[:3])
                if len(alt_paths) > 3:
                    alt_paths_display += ", ..."
                note_lines.append(f"Other copies located at: {alt_paths_display}")

            ctk.CTkLabel(
                name_frame,
                text="\n".join(note_lines),
                font=ctk.CTkFont(size=9),
                text_color=self.colors['text_dim'],
                anchor="w",
                wraplength=520,
                justify="left"
            ).pack(side="top", anchor="w", pady=(4, 0))

        # Action buttons
        button_frame = ctk.CTkFrame(card, fg_color="transparent")
        button_frame.pack(fill="x", padx=10, pady=(0, 8))

        # Find assigned playlist
        assigned_playlist = self.find_playlist_for_track(track['path'])
        if assigned_playlist:
            status_label = ctk.CTkLabel(
                button_frame,
                text=f"✓ Using: {assigned_playlist.name}",
                font=ctk.CTkFont(size=10),
                text_color=self.colors['secondary']
            )
            status_label.pack(side="left", padx=5)

        # Play button
        play_icon = "▶️" if self.current_playing_track != track['full_path'] else "⏸️"
        ctk.CTkButton(
            button_frame,
            text=play_icon,
            width=35,
            height=24,
            command=lambda t=track: self.toggle_play_track(t),
            fg_color=self.colors['secondary'],
            hover_color=self.colors['accent'],
            text_color=self.colors['text'],
            font=ctk.CTkFont(size=12)
        ).pack(side="right", padx=2)

        # Check if this is a non-editable radio_content segment
        is_radio_content = False
        segment = track.get('radio_segment')
        if segment and segment.segment_type == 'radio_content':
            is_radio_content = True

        # Assign button (disabled for radio_content segments)
        assign_btn = ctk.CTkButton(
            button_frame,
            text="🎵 Assign",
            width=80,
            height=24,
            command=lambda t=track: self.assign_playlist_to_track(t),
            fg_color=self.colors['primary'] if not is_radio_content else "#555555",
            hover_color=self.colors['primary_hover'] if not is_radio_content else "#555555",
            text_color=self.colors['text'] if not is_radio_content else "#888888",
            font=ctk.CTkFont(size=10),
            state="disabled" if is_radio_content else "normal"
        )
        assign_btn.pack(side="right", padx=2)

    def toggle_play_track(self, track):
        """Play or pause the selected track"""
        self._init_audio_mixer()
        if not pygame.mixer.get_init():
            return

        try:
            if self.current_playing_track == track['full_path']:
                # Stop current track
                pygame.mixer.music.stop()
                self.current_playing_track = None
                self.is_playing = False
                self.play_pause_btn.configure(text="▶")
                self.current_track_label.configure(text="No track playing")
            else:
                # Play new track
                pygame.mixer.music.load(track['full_path'])
                pygame.mixer.music.play()
                self.current_playing_track = track['full_path']
                self.is_playing = True
                self.play_pause_btn.configure(text="⏸")

                # Cache track duration to avoid reloading every second
                if track['full_path'] not in self.track_duration_cache:
                    try:
                        sound = pygame.mixer.Sound(track['full_path'])
                        self.track_duration_cache[track['full_path']] = sound.get_length()
                    except:
                        self.track_duration_cache[track['full_path']] = 0.0
                self.current_track_duration = self.track_duration_cache.get(track['full_path'], 0.0)

                # Update current track index in filtered list
                try:
                    self.current_track_index = self.filtered_tracks.index(track)
                except ValueError:
                    self.current_track_index = -1

                # Update track label
                track_name = track['info']['description'] if track['info'] else track['filename']
                self.current_track_label.configure(text=f"🎵 {track_name}")

            # Note: We don't need to refresh_tracks() here anymore - removed for performance

        except Exception as e:
            messagebox.showerror("Playback Error",
                               f"Could not play audio file:\n{str(e)}\n\n"
                               f"Make sure the file is a valid audio format.")

    def toggle_playback(self):
        """Toggle play/pause for current track"""
        self._init_audio_mixer()
        if not pygame.mixer.get_init():
            return

        if self.current_playing_track is None:
            # No track selected, play first track if available
            if self.filtered_tracks:
                self.toggle_play_track(self.filtered_tracks[0])
        else:
            # Pause or unpause current track
            if self.is_playing:
                pygame.mixer.music.pause()
                self.is_playing = False
                self.play_pause_btn.configure(text="▶")
            else:
                pygame.mixer.music.unpause()
                self.is_playing = True
                self.play_pause_btn.configure(text="⏸")

    def stop_playback(self):
        """Stop current playback"""
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
        self.current_playing_track = None
        self.is_playing = False
        self.current_track_index = -1
        self.play_pause_btn.configure(text="▶")
        self.current_track_label.configure(text="No track playing")
        self.progress_bar.set(0)
        self.time_elapsed_label.configure(text="0:00")
        self.time_total_label.configure(text="0:00")
        self.refresh_tracks()

    def play_previous_track(self):
        """Play the previous track in the filtered list"""
        if not self.filtered_tracks:
            return

        if self.current_track_index <= 0:
            # Wrap around to last track
            self.current_track_index = len(self.filtered_tracks) - 1
        else:
            self.current_track_index -= 1

        self.toggle_play_track(self.filtered_tracks[self.current_track_index])

    def play_next_track(self):
        """Play the next track in the filtered list"""
        if not self.filtered_tracks:
            return

        if self.current_track_index >= len(self.filtered_tracks) - 1:
            # Wrap around to first track
            self.current_track_index = 0
        else:
            self.current_track_index += 1

        self.toggle_play_track(self.filtered_tracks[self.current_track_index])

    def on_volume_change(self, value):
        """Handle volume slider change"""
        volume = float(value) / 100.0
        self._init_audio_mixer()
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(volume)

    def update_progress(self):
        """Update progress bar and time labels"""
        if not pygame.mixer.get_init():
            self.after(1000, self.update_progress)
            return

        if self.is_playing and pygame.mixer.music.get_busy():
            # Get current position
            pos = pygame.mixer.music.get_pos() / 1000.0  # Convert to seconds

            # Use cached track duration instead of reloading audio file
            if self.current_playing_track and self.current_track_duration > 0:
                # Update progress bar
                progress = pos / self.current_track_duration
                self.progress_bar.set(min(progress, 1.0))

                # Update time labels
                self.time_elapsed_label.configure(text=self.format_time(pos))
                self.time_total_label.configure(text=self.format_time(self.current_track_duration))
            elif self.current_playing_track:
                # Fallback: just show elapsed time
                self.time_elapsed_label.configure(text=self.format_time(pos))

        # Schedule next update
        self.after(1000, self.update_progress)

    def format_time(self, seconds):
        """Format seconds to MM:SS"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"

    # Malkavian Whisper handlers
    def edit_whisper_subtitle(self, whisper):
        """Open dialog to edit whisper subtitle text"""
        dialog = WhisperSubtitleDialog(self, whisper, colors=self.colors)
        new_text = dialog.get_result()

        if new_text is not None and new_text.strip():
            success = self.whisper_manager.edit_whisper_subtitle(whisper, new_text.strip())
            if success:
                messagebox.showinfo("Success", f"Updated subtitle for '{whisper.display_name}'")
                self.refresh_tracks()  # Refresh to show updated text
            else:
                messagebox.showerror("Error", "Failed to update whisper subtitle")

    def add_whisper_audio(self, whisper):
        """Browse and add audio file for whisper"""
        from tkinter import filedialog

        audio_path = filedialog.askopenfilename(
            title=f"Select Audio for '{whisper.display_name}'",
            filetypes=[
                ("WAV Audio", "*.wav"),
                ("All Files", "*.*")
            ],
            parent=self
        )

        if audio_path:
            success = self.whisper_manager.add_whisper_audio(whisper, audio_path)
            if success:
                messagebox.showinfo("Success",
                    f"Added audio for '{whisper.display_name}'\n\n"
                    f"The custom whisper will now play in-game during Malkavian playthroughs!")
                self.refresh_tracks()  # Refresh to show audio status
            else:
                messagebox.showerror("Error",
                    "Failed to add whisper audio.\n"
                    "Make sure the file is a valid .wav audio file.")

    def play_whisper_audio(self, whisper):
        """Play whisper audio file"""
        self._init_audio_mixer()
        if not pygame.mixer.get_init():
            return

        try:
            if self.current_playing_track == whisper.audio_path:
                # Stop current whisper
                pygame.mixer.music.stop()
                self.current_playing_track = None
                self.is_playing = False
                self.play_pause_btn.configure(text="▶")
                self.current_track_label.configure(text="No track playing")
            else:
                # Play whisper
                pygame.mixer.music.load(whisper.audio_path)
                pygame.mixer.music.play()
                self.current_playing_track = whisper.audio_path
                self.is_playing = True
                self.play_pause_btn.configure(text="⏸")

                # Cache duration
                if whisper.audio_path not in self.track_duration_cache:
                    try:
                        sound = pygame.mixer.Sound(whisper.audio_path)
                        self.track_duration_cache[whisper.audio_path] = sound.get_length()
                    except:
                        self.track_duration_cache[whisper.audio_path] = 0.0
                self.current_track_duration = self.track_duration_cache.get(whisper.audio_path, 0.0)

                # Update track label
                self.current_track_label.configure(text=f"🗣️ {whisper.display_name}")

        except Exception as e:
            messagebox.showerror("Playback Error",
                               f"Could not play whisper audio:\n{str(e)}")

    def remove_whisper_audio(self, whisper):
        """Remove custom audio from whisper slot"""
        confirm = messagebox.askyesno(
            "Remove Whisper Audio",
            f"Remove custom audio for '{whisper.display_name}'?\n\n"
            f"This will delete the .wav file and the whisper will return to being silent.",
            parent=self
        )

        if confirm:
            success = self.whisper_manager.remove_whisper_audio(whisper)
            if success:
                messagebox.showinfo("Success", f"Removed audio for '{whisper.display_name}'")
                self.refresh_tracks()  # Refresh to show updated status
            else:
                messagebox.showerror("Error", "Failed to remove whisper audio")

    def find_playlist_for_track(self, track_path):
        """Find if a playlist is assigned to this track"""
        # Normalize the track path for comparison (handles Windows path case-sensitivity and separators)
        normalized_track = os.path.normpath(track_path).lower() if track_path else ""

        for playlist in self.config.playlists:
            if playlist.game_file_path:
                normalized_playlist = os.path.normpath(playlist.game_file_path).lower()
                if normalized_playlist == normalized_track:
                    return playlist
        return None

    def edit_track(self, track):
        """Open editor for a specific track"""
        # Find existing playlist or create new one
        existing_playlist = self.find_playlist_for_track(track['path'])

        if existing_playlist:
            self.edit_playlist(existing_playlist)
        else:
            # Create new playlist for this track
            messagebox.showinfo("Create Playlist",
                              f"Create a new playlist for:\n{track['filename']}")
            self.new_playlist_for_track(track)

    def assign_playlist_to_track(self, track):
        """Show dialog to assign existing playlist to track"""
        if not self.config.playlists:
            messagebox.showinfo("No Playlists",
                              "You don't have any playlists yet.\nCreate one first!")
            return

        # Create selection dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Assign Playlist")
        dialog.geometry("400x300")
        dialog.configure(fg_color=self.colors['bg_medium'])
        apply_app_icon(dialog)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text=f"Assign playlist to:\n{track['filename']}",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(pady=15)

        # List playlists
        listframe = ctk.CTkFrame(dialog)
        listframe.pack(fill="both", expand=True, padx=20, pady=10)

        listbox = tk.Listbox(listframe, bg="#2b2b2b", fg="white")
        scrollbar = ctk.CTkScrollbar(listframe, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)

        for playlist in self.config.playlists:
            listbox.insert(tk.END, f"{playlist.name} ({len(playlist.audio_files)} songs)")

        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def assign():
            selection = listbox.curselection()
            if selection:
                selected_playlist = self.config.playlists[selection[0]]
                selected_playlist.game_file_path = track['path']
                self.save_config()
                self.refresh_tracks()
                dialog.destroy()
                messagebox.showinfo("Success",
                                  f"Assigned '{selected_playlist.name}' to\n{track['filename']}")

        def assign_and_apply():
            selection = listbox.curselection()
            if selection:
                selected_playlist = self.config.playlists[selection[0]]
                selected_playlist.game_file_path = track['path']
                self.save_config()
                dialog.destroy()

                # Apply the playlist immediately
                self.apply_single_playlist(selected_playlist)
                self.refresh_tracks()

        # Button container
        button_container = ctk.CTkFrame(dialog, fg_color="transparent")
        button_container.pack(pady=10)

        ctk.CTkButton(
            button_container,
            text="Assign Only",
            command=assign,
            fg_color=self.colors['accent'],
            hover_color=self.colors['secondary'],
            width=140
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            button_container,
            text="Assign & Apply Now",
            command=assign_and_apply,
            fg_color=self.colors['secondary'],
            hover_color=self.colors['primary'],
            width=160
        ).pack(side="left", padx=5)

        finalize_modal(dialog, min_width=420, min_height=360)

    def new_playlist_for_track(self, track):
        """Create a new playlist for a specific track"""
        # Pre-fill the track info in the playlist editor
        dialog = PlaylistEditorDialog(
            self,
            None,
            self.game_manager,
            colors=self.colors,
            audio_library=self.config.audio_library
        )

        # Pre-fill game file path
        if hasattr(dialog, 'game_file_entry'):
            dialog.game_file_entry.insert(0, track['path'])

        # Pre-fill name from track info
        if track['info']:
            suggested_name = f"{track['info']['description']} Custom"
            dialog.name_entry.insert(0, suggested_name)

        self.wait_window(dialog)

        if dialog.result:
            self.config.playlists.append(dialog.result)
            self.save_config()
            self.refresh_playlists()
            self.refresh_tracks()

    def bulk_assign_playlist(self):
        """Bulk assign a playlist to multiple tracks"""
        if not self.config.playlists:
            messagebox.showinfo("No Playlists",
                              "Create at least one playlist first!")
            return

        if not self.game_tracks:
            messagebox.showinfo("No Tracks",
                              "Scan game files first to see tracks!")
            return

        # Create dialog for bulk assignment
        dialog = ctk.CTkToplevel(self)
        dialog.title("Bulk Assign Playlist")
        dialog.geometry("600x500")
        dialog.configure(fg_color=self.colors['bg_medium'])
        apply_app_icon(dialog)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="🎵 Bulk Assign Playlist to Multiple Tracks",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=15)

        # Playlist selection
        playlist_frame = ctk.CTkFrame(dialog)
        playlist_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            playlist_frame,
            text="Select Playlist:",
            font=ctk.CTkFont(weight="bold")
        ).pack(side="left", padx=5)

        playlist_var = ctk.StringVar()
        playlist_names = [p.name for p in self.config.playlists]
        playlist_combo = ctk.CTkComboBox(
            playlist_frame,
            values=playlist_names,
            variable=playlist_var,
            width=250
        )
        playlist_combo.pack(side="left", padx=10)
        if playlist_names:
            playlist_combo.set(playlist_names[0])

        # Track selection with checkboxes
        ctk.CTkLabel(
            dialog,
            text="Select tracks to assign:",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=20, pady=(10, 5))

        tracks_frame = ctk.CTkScrollableFrame(dialog, height=250)
        tracks_frame.pack(fill="both", expand=True, padx=20, pady=5)

        track_vars = []
        for track in self.game_tracks:
            var = ctk.BooleanVar()
            track_vars.append((var, track))

            frame = ctk.CTkFrame(tracks_frame)
            frame.pack(fill="x", pady=2)

            check = ctk.CTkCheckBox(
                frame,
                text="",
                variable=var,
                width=30
            )
            check.pack(side="left", padx=5)

            desc = track['info']['description'] if track['info'] else track['filename']
            label = ctk.CTkLabel(
                frame,
                text=f"{track['filename']} - {desc}",
                anchor="w",
                wraplength=500,
                justify="left",
                text_color=self.colors['text']
            )
            label.pack(side="left", fill="x", expand=True, padx=5)

        # Buttons
        button_frame = ctk.CTkFrame(dialog)
        button_frame.pack(fill="x", padx=20, pady=15)

        def do_assign():
            selected_playlist_name = playlist_var.get()
            selected_playlist = next((p for p in self.config.playlists if p.name == selected_playlist_name), None)

            if not selected_playlist:
                messagebox.showerror("Error", "Please select a playlist")
                return

            selected_tracks = [track for var, track in track_vars if var.get()]

            if not selected_tracks:
                messagebox.showwarning("No Selection", "Please select at least one track")
                return

            # Assign playlist to all selected tracks by creating copies
            import copy
            for track in selected_tracks:
                # Create a copy of the playlist for each track
                playlist_copy = copy.deepcopy(selected_playlist)
                playlist_copy.game_file_path = track['path']

                # Check if a playlist already exists for this track
                existing = self.find_playlist_for_track(track['path'])
                if existing:
                    # Update existing playlist instead of creating duplicate
                    existing.audio_files = playlist_copy.audio_files
                    existing.playback_mode = playlist_copy.playback_mode
                else:
                    self.config.playlists.append(playlist_copy)

            self.save_config()
            self.refresh_playlists()
            self.refresh_tracks()
            dialog.destroy()

            messagebox.showinfo("Success",
                              f"Assigned '{selected_playlist.name}' to {len(selected_tracks)} tracks!")

        ctk.CTkButton(
            button_frame,
            text="Assign to Selected",
            command=do_assign,
            fg_color=self.colors['secondary'],
            hover_color=self.colors['accent']
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            fg_color="gray"
        ).pack(side="right")

        finalize_modal(dialog, min_width=640, min_height=520)

    def bulk_assign_by_type(self, track_type):
        """Bulk assign playlist to all tracks of a specific type"""
        if not self.config.playlists:
            messagebox.showinfo("No Playlists",
                              "Create at least one playlist first!")
            return

        if not self.game_tracks:
            messagebox.showinfo("No Tracks",
                              "Scan game files first!")
            return

        # Filter tracks by type
        matching_tracks = [
            t for t in self.game_tracks
            if t['info'] and t['info'].get('type') == track_type
        ]

        if not matching_tracks:
            messagebox.showinfo("No Tracks",
                              f"No {track_type} tracks found in the game.")
            return

        # Ask which playlist to use
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Assign to All {track_type.capitalize()} Tracks")
        dialog.geometry("450x350")
        dialog.configure(fg_color=self.colors['bg_medium'])
        apply_app_icon(dialog)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text=f"Assign to {len(matching_tracks)} {track_type} tracks:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(pady=15)

        # Show matching tracks
        tracks_info = ctk.CTkScrollableFrame(dialog, height=150)
        tracks_info.pack(fill="both", padx=20, pady=10)

        for track in matching_tracks:
            desc = track['info']['description'] if track['info'] else track['filename']
            ctk.CTkLabel(
                tracks_info,
                text=f"🎵 {desc}",
                anchor="w",
                wraplength=420,
                justify="left",
                text_color=self.colors['text']
            ).pack(anchor="w", padx=5, pady=2)

        # Playlist selection
        ctk.CTkLabel(
            dialog,
            text="Select playlist to assign:",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=20, pady=(10, 5))

        listframe = ctk.CTkFrame(dialog)
        listframe.pack(fill="x", padx=20, pady=5)

        listbox = tk.Listbox(listframe, bg="#2b2b2b", fg="white", height=4)
        for playlist in self.config.playlists:
            listbox.insert(tk.END, f"{playlist.name} ({len(playlist.audio_files)} songs)")
        listbox.pack(fill="x")

        def do_assign():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a playlist")
                return

            selected_playlist = self.config.playlists[selection[0]]

            # Assign to all matching tracks
            for track in matching_tracks:
                # Create copies of the playlist for each track
                import copy
                playlist_copy = copy.deepcopy(selected_playlist)
                playlist_copy.game_file_path = track['path']

                # Check if a playlist already exists for this track
                existing = self.find_playlist_for_track(track['path'])
                if existing:
                    # Update existing playlist instead of creating duplicate
                    existing.audio_files = playlist_copy.audio_files
                    existing.playback_mode = playlist_copy.playback_mode
                else:
                    self.config.playlists.append(playlist_copy)

            self.save_config()
            self.refresh_playlists()
            self.refresh_tracks()
            dialog.destroy()

            messagebox.showinfo("Success",
                              f"Applied '{selected_playlist.name}' to {len(matching_tracks)} {track_type} tracks!")

        ctk.CTkButton(
            dialog,
            text=f"Apply to All {track_type.capitalize()}",
            command=do_assign,
            fg_color=self.colors['secondary'],
            hover_color=self.colors['accent']
        ).pack(pady=15)

        finalize_modal(dialog, min_width=480, min_height=380)

    def refresh_library(self):
        """Refresh the audio library display"""
        # Clear existing
        for widget in self.library_container.winfo_children():
            widget.destroy()

        # Update count
        self.library_count_label.configure(text=f"({len(self.config.audio_library)} files)")

        if not self.config.audio_library:
            no_library = ctk.CTkLabel(
                self.library_container,
                text="No audio files yet.\nClick 📁 to import!",
                text_color=self.colors['text_dim'],
                font=ctk.CTkFont(size=10)
            )
            no_library.pack(pady=15)
        else:
            for audio_file in self.config.audio_library:
                file_frame = ctk.CTkFrame(
                    self.library_container,
                    fg_color=self.colors['bg_medium'],
                    corner_radius=4
                )
                file_frame.pack(fill="x", pady=2, padx=3)

                ctk.CTkLabel(
                    file_frame,
                    text=f"🎵 {audio_file.filename}",
                    font=ctk.CTkFont(size=10),
                    text_color=self.colors['text'],
                    anchor="w"
                ).pack(side="left", padx=8, pady=4, fill="x", expand=True)

    def import_to_library(self):
        """Import audio files to the library"""
        filetypes = [
            ("Audio Files", "*.mp3 *.wav *.ogg *.flac *.m4a *.aac"),
            ("All Files", "*.*")
        ]

        filenames = filedialog.askopenfilenames(
            title="Import Audio Files to Library",
            filetypes=filetypes
        )

        if not filenames:
            return

        added_count = 0
        for filename in filenames:
            # Check if already in library
            if any(af.path == filename for af in self.config.audio_library):
                continue

            # Validate file
            is_valid, error = self.audio_processor.validate_audio_file(filename)
            if is_valid:
                audio_file = AudioFile(
                    path=filename,
                    filename=os.path.basename(filename)
                )
                self.config.audio_library.append(audio_file)
                added_count += 1
            else:
                messagebox.showwarning(
                    "Invalid File",
                    f"Could not add {os.path.basename(filename)}:\n{error}"
                )

        if added_count > 0:
            self.save_config()
            self.refresh_library()
            messagebox.showinfo(
                "Success",
                f"Added {added_count} file(s) to your Audio Library!"
            )

    def clear_library(self):
        """Clear all files from the audio library"""
        if not self.config.audio_library:
            messagebox.showinfo("Empty", "Audio library is already empty.")
            return

        if messagebox.askyesno(
            "Confirm Clear",
            f"Remove all {len(self.config.audio_library)} files from your Audio Library?\n\n"
            "This won't delete the actual files, just removes them from the library."
        ):
            self.config.audio_library.clear()
            self.save_config()
            self.refresh_library()
            messagebox.showinfo("Cleared", "Audio library has been cleared.")

    def refresh_playlists(self):
        """Refresh the playlists display"""
        # Clear existing
        for widget in self.playlists_container.winfo_children():
            widget.destroy()

        # Add playlists
        if not self.config.playlists:
            no_playlists = ctk.CTkLabel(
                self.playlists_container,
                text="No playlists yet.\nClick '+' to create one!",
                text_color=self.colors['text_dim'],
                font=ctk.CTkFont(size=11)
            )
            no_playlists.pack(pady=20)
        else:
            for playlist in self.config.playlists:
                frame = PlaylistFrame(
                    self.playlists_container,
                    playlist,
                    self.delete_playlist,
                    self.edit_playlist,
                    self.save_config,
                    colors=self.colors,
                    fg_color=self.colors['bg_dark'],
                    corner_radius=10,
                    border_width=2,
                    border_color=self.colors['accent']
                )
                frame.pack(fill="x", pady=6, padx=8)

    def new_playlist(self):
        """Create a new playlist"""
        dialog = PlaylistEditorDialog(
            self,
            game_manager=self.game_manager,
            colors=self.colors,
            audio_library=self.config.audio_library
        )
        self.wait_window(dialog)

        if dialog.result:
            self.config.playlists.append(dialog.result)
            self.save_config()
            self.refresh_playlists()

    def edit_playlist(self, playlist: Playlist):
        """Edit an existing playlist"""
        dialog = PlaylistEditorDialog(
            self,
            playlist,
            self.game_manager,
            colors=self.colors,
            audio_library=self.config.audio_library
        )
        self.wait_window(dialog)

        if dialog.result:
            # Find and update the playlist frame
            for widget in self.playlists_container.winfo_children():
                if isinstance(widget, PlaylistFrame) and widget.playlist == playlist:
                    widget.update_display()
                    break
            self.save_config()

    def delete_playlist(self, playlist: Playlist):
        """Delete a playlist"""
        self.config.playlists.remove(playlist)
        self.save_config()
        self.refresh_playlists()

    def auto_detect_game_directory(self):
        """Auto-detect VTMB installation on first launch"""
        detected = find_vtmb_installation()

        if detected:
            path = detected['path']
            source = detected.get('source', 'Unknown')
            patch_version = detected.get('patch_version', 'Not detected')

            message = f"Found VTMB installation!\n\n"
            message += f"Location: {path}\n"
            message += f"Source: {source}\n"
            message += f"Version: {patch_version}\n\n"

            if 'Unofficial_Patch' in patch_version:
                message += "✓ Unofficial Patch detected - you're all set!\n\n"
            else:
                message += "⚠️ Warning: Unofficial Patch not detected.\n"
                message += "Most VTMB players use the Unofficial Patch.\n"
                message += "Consider installing it for the best experience.\n\n"

            message += "Use this directory?"

            if messagebox.askyesno("Game Directory Detected", message):
                self.config.game_directory = path
                self.game_manager.game_directory = path
                self.radio_segment_manager.set_game_directory(path)
                self.whisper_manager.set_game_directory(path)
                self.save_config()
                messagebox.showinfo("Success",
                                  "Game directory configured!\n\n"
                                  "Next step: Create a backup before making any changes.")
        else:
            message = "Could not auto-detect VTMB installation.\n\n"
            message += "Please manually set the game directory in Settings.\n\n"
            message += "Common locations:\n"
            message += "• Steam: C:\\Program Files (x86)\\Steam\\steamapps\\common\\Vampire The Masquerade - Bloodlines\n"
            message += "• GOG: C:\\GOG Games\\Vampire The Masquerade - Bloodlines\n\n"
            message += "Note: The Unofficial Patch is recommended for best results."

            messagebox.showinfo("Manual Setup Required", message)
            self.open_settings()

    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self, self.config, self.game_manager, colors=self.colors)
        self.wait_window(dialog)

        if dialog.result:
            self.config = dialog.result
            self.game_manager.game_directory = self.config.game_directory
            self.game_manager.backup_directory = self.config.backup_directory
            self.radio_segment_manager.set_game_directory(self.config.game_directory)
            self.whisper_manager.set_game_directory(self.config.game_directory)
            self.save_config()

    def backup_game_files(self):
        """Backup all game audio files"""
        if not self.config.game_directory:
            messagebox.showerror("Error", "Please set the game directory in Settings first")
            return

        if messagebox.askyesno("Confirm Backup", "This will backup all audio files in the game directory. Continue?"):
            success, message = self.game_manager.backup_all_audio_files()
            if success:
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", message)

    def restore_backup(self):
        """Restore from a backup"""
        backups = self.game_manager.list_backups()
        if not backups:
            messagebox.showinfo("No Backups", "No backups found")
            return

        # Create backup selection dialog
        dialog = BackupSelectionDialog(self, backups, self.game_manager, colors=self.colors)
        self.wait_window(dialog)

    def apply_single_playlist(self, playlist: Playlist):
        """Apply a single playlist immediately"""
        if not self.config.game_directory:
            messagebox.showerror("Error", "Please set the game directory in Settings first")
            return False

        if not playlist.game_file_path or not playlist.game_file_path.strip():
            messagebox.showerror("Error", "This playlist has no game file assigned")
            return False

        if not playlist.audio_files:
            messagebox.showerror("Error", "This playlist has no audio files")
            return False

        # Stop audio playback to release file locks
        try:
            self.stop_playback()
            if pygame.mixer.get_init():
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass
                pygame.mixer.quit()
        except Exception as e:
            print(f"Warning: Could not stop audio playback: {e}")

        # Small delay to ensure file handles are released
        import time
        time.sleep(0.2)

        # Progress dialog for single playlist
        progress = ProgressDialog(
            self,
            "Applying Playlist",
            [playlist],
            self.audio_processor,
            self.game_manager,
            self.radio_segment_manager,
            colors=self.colors
        )
        self.wait_window(progress)
        self._init_audio_mixer()
        return True

    def apply_playlists(self):
        """Apply all enabled playlists"""
        if not self.config.game_directory:
            messagebox.showerror("Error", "Please set the game directory in Settings first")
            return

        enabled_playlists = [p for p in self.config.playlists if p.enabled]
        if not enabled_playlists:
            messagebox.showwarning("No Playlists", "No enabled playlists to apply")
            return

        # Filter out playlists without game file assignments
        playlists_to_apply = [p for p in enabled_playlists if p.game_file_path and p.game_file_path.strip()]
        unassigned_playlists = [p for p in enabled_playlists if not p.game_file_path or not p.game_file_path.strip()]

        if unassigned_playlists:
            unassigned_names = "\n".join([f"  • {p.name}" for p in unassigned_playlists])
            if playlists_to_apply:
                messagebox.showinfo("Unassigned Playlists",
                    f"The following playlists have no game file assigned and will be skipped:\n\n{unassigned_names}\n\n"
                    f"Use the 'Assign' button on game tracks to assign playlists.")
            else:
                messagebox.showwarning("No Assigned Playlists",
                    f"All enabled playlists are missing game file assignments:\n\n{unassigned_names}\n\n"
                    f"Use the 'Assign' button on game tracks to assign playlists to specific music files.")
                return

        if not playlists_to_apply:
            return

        if not messagebox.askyesno("Confirm", f"This will replace {len(playlists_to_apply)} game audio files. Continue?"):
            return

        # Stop audio playback to release file locks
        try:
            self.stop_playback()
            if pygame.mixer.get_init():
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass
                pygame.mixer.quit()
        except Exception as e:
            print(f"Warning: Could not stop audio playback: {e}")

        # Small delay to ensure file handles are released
        import time
        time.sleep(0.2)

        # Progress dialog
        progress = ProgressDialog(
            self,
            "Applying Playlists",
            playlists_to_apply,
            self.audio_processor,
            self.game_manager,
            self.radio_segment_manager,
            colors=self.colors
        )
        self.wait_window(progress)
        self._init_audio_mixer()

    def save_config(self):
        """Save configuration"""
        self.config.save()

    def on_closing(self):
        """Handle window closing"""
        self.save_config()
        self.destroy()


class SettingsDialog(ctk.CTkToplevel):
    """Settings dialog"""

    def __init__(self, master, config: AppConfig, game_manager: GameFileManager, colors: dict = None):
        super().__init__(master)

        self.config = config
        self.game_manager = game_manager
        self.result = None
        self.colors = colors or {
            'primary': '#8B0000',
            'primary_hover': '#A50000',
            'secondary': '#DC143C',
            'accent': '#B22222',
            'bg_dark': '#1a0000',
            'bg_medium': '#2d0a0a',
            'text': '#FFE4E4',
            'text_dim': '#B88888',
        }

        self.title("Settings")
        self.geometry("600x400")
        self.configure(fg_color=self.colors['bg_medium'])
        apply_app_icon(self)
        self.transient(master)
        self.grab_set()

        self.setup_ui()

    def setup_ui(self):
        main_frame = ctk.CTkFrame(self, fg_color=self.colors['bg_dark'])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Game directory
        ctk.CTkLabel(
            main_frame,
            text="Game Directory:",
            font=ctk.CTkFont(weight="bold"),
            text_color=self.colors['text']
        ).pack(anchor="w", pady=(0, 5))
        game_dir_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        game_dir_frame.pack(fill="x", pady=(0, 15))

        self.game_dir_entry = ctk.CTkEntry(
            game_dir_frame,
            placeholder_text="Path to VTMB installation",
            fg_color=self.colors['bg_medium'],
            border_color=self.colors['accent'],
            text_color=self.colors['text']
        )
        self.game_dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        if self.config.game_directory:
            self.game_dir_entry.insert(0, self.config.game_directory)

        ctk.CTkButton(
            game_dir_frame,
            text="Browse",
            width=100,
            command=self.browse_game_dir,
            fg_color=self.colors['accent'],
            hover_color=self.colors['secondary'],
            text_color=self.colors['text']
        ).pack(side="left")

        # Backup directory
        ctk.CTkLabel(
            main_frame,
            text="Backup Directory:",
            font=ctk.CTkFont(weight="bold"),
            text_color=self.colors['text']
        ).pack(anchor="w", pady=(0, 5))
        backup_dir_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        backup_dir_frame.pack(fill="x", pady=(0, 15))

        self.backup_dir_entry = ctk.CTkEntry(
            backup_dir_frame,
            placeholder_text="Path for backups",
            fg_color=self.colors['bg_medium'],
            border_color=self.colors['accent'],
            text_color=self.colors['text']
        )
        self.backup_dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        if self.config.backup_directory:
            self.backup_dir_entry.insert(0, self.config.backup_directory)

        ctk.CTkButton(
            backup_dir_frame,
            text="Browse",
            width=100,
            command=self.browse_backup_dir,
            fg_color=self.colors['accent'],
            hover_color=self.colors['secondary'],
            text_color=self.colors['text']
        ).pack(side="left")

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", pady=(20, 0))

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.cancel,
            fg_color=self.colors['bg_medium'],
            hover_color=self.colors['accent'],
            text_color=self.colors['text'],
            width=100
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="💾 Save",
            command=self.save,
            fg_color=self.colors['secondary'],
            hover_color=self.colors['accent'],
            text_color=self.colors['text'],
            width=100,
            font=ctk.CTkFont(weight="bold")
        ).pack(side="right", padx=5)

    def browse_game_dir(self):
        directory = filedialog.askdirectory(title="Select VTMB Installation Directory")
        if directory:
            is_valid, message = self.game_manager.validate_game_directory(directory)
            if is_valid:
                self.game_dir_entry.delete(0, tk.END)
                self.game_dir_entry.insert(0, directory)
                messagebox.showinfo("Valid Directory", message)
            else:
                messagebox.showerror("Invalid Directory", message)

    def browse_backup_dir(self):
        directory = filedialog.askdirectory(title="Select Backup Directory")
        if directory:
            self.backup_dir_entry.delete(0, tk.END)
            self.backup_dir_entry.insert(0, directory)

    def save(self):
        game_dir = self.game_dir_entry.get().strip()
        backup_dir = self.backup_dir_entry.get().strip()

        if not game_dir:
            messagebox.showerror("Error", "Please specify the game directory")
            return

        if not backup_dir:
            messagebox.showerror("Error", "Please specify the backup directory")
            return

        self.config.game_directory = game_dir
        self.config.backup_directory = backup_dir
        self.result = self.config
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


class BackupSelectionDialog(ctk.CTkToplevel):
    """Dialog for selecting and restoring backups"""

    def __init__(self, master, backups: List[dict], game_manager: GameFileManager, colors: dict = None):
        super().__init__(master)

        self.backups = backups
        self.game_manager = game_manager
        self.colors = colors or {
            'primary': '#8B0000',
            'primary_hover': '#A50000',
            'secondary': '#DC143C',
            'accent': '#B22222',
            'bg_dark': '#1a0000',
            'bg_medium': '#2d0a0a',
            'text': '#FFE4E4',
            'text_dim': '#B88888',
        }

        self.title("Restore Backup")
        self.geometry("600x400")
        self.configure(fg_color=self.colors['bg_medium'])
        apply_app_icon(self)
        self.transient(master)
        self.grab_set()

        self.setup_ui()

    def setup_ui(self):
        main_frame = ctk.CTkFrame(self, fg_color=self.colors['bg_dark'])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            main_frame,
            text="Select a backup to restore:",
            font=ctk.CTkFont(weight="bold"),
            text_color=self.colors['text']
        ).pack(pady=10)

        # Backup list
        list_frame = ctk.CTkFrame(main_frame, fg_color=self.colors['bg_medium'])
        list_frame.pack(fill="both", expand=True, pady=10)

        self.backup_listbox = tk.Listbox(
            list_frame,
            bg=self.colors['bg_medium'],
            fg=self.colors['text'],
            selectbackground=self.colors['accent'],
            selectforeground=self.colors['text']
        )
        scrollbar = ctk.CTkScrollbar(list_frame, command=self.backup_listbox.yview)
        self.backup_listbox.configure(yscrollcommand=scrollbar.set)

        for backup in self.backups:
            size_mb = backup['size'] / (1024 * 1024)
            display = f"{backup['name']} - {backup['created'].strftime('%Y-%m-%d %H:%M:%S')} ({size_mb:.1f} MB)"
            self.backup_listbox.insert(tk.END, display)

        self.backup_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.destroy,
            fg_color=self.colors['bg_medium'],
            hover_color=self.colors['accent'],
            text_color=self.colors['text']
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="🔄 Restore",
            command=self.restore,
            fg_color=self.colors['secondary'],
            hover_color=self.colors['accent'],
            text_color=self.colors['text'],
            font=ctk.CTkFont(weight="bold")
        ).pack(side="right", padx=5)

    def restore(self):
        selection = self.backup_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a backup to restore")
            return

        backup = self.backups[selection[0]]

        if messagebox.askyesno("Confirm Restore", f"Restore backup from {backup['created'].strftime('%Y-%m-%d %H:%M:%S')}?\nThis will overwrite current game files."):
            success, message = self.game_manager.restore_from_backup(backup['path'])
            if success:
                messagebox.showinfo("Success", message)
                self.destroy()
            else:
                messagebox.showerror("Error", message)


class ScanProgressDialog(ctk.CTkToplevel):
    """Simple modal dialog displayed while scanning game files"""

    def __init__(self, master, colors: dict = None):
        super().__init__(master)

        self.colors = colors or {
            'primary': '#8B0000',
            'primary_hover': '#A50000',
            'secondary': '#DC143C',
            'accent': '#B22222',
            'bg_dark': '#1a0000',
            'bg_medium': '#2d0a0a',
            'text': '#FFE4E4',
            'text_dim': '#B88888',
        }

        self.title("Scanning Game Files - Please wait until it's finished")
        self.geometry("360x140")
        self.configure(fg_color=self.colors['bg_medium'])
        apply_app_icon(self)
        self.transient(master)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # Disable manual close

        main_frame = ctk.CTkFrame(
            self,
            fg_color=self.colors['bg_dark'],
            corner_radius=10,
            border_width=2,
            border_color=self.colors['accent']
        )
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        title_label = ctk.CTkLabel(
            main_frame,
            text="Scanning your VTMB installation...",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.colors['text']
        )
        title_label.pack(pady=(15, 10))

        self.status_label = ctk.CTkLabel(
            main_frame,
            text="Preparing scan...",
            font=ctk.CTkFont(size=12),
            text_color=self.colors['text_dim'],
            wraplength=280,
            justify="center"
        )
        self.status_label.pack(pady=(0, 15))

        self.progress_bar = ctk.CTkProgressBar(
            main_frame,
            mode="indeterminate",
            progress_color=self.colors['secondary'],
            fg_color=self.colors['bg_medium'],
            border_color=self.colors['accent'],
            border_width=2,
            height=14
        )
        self.progress_bar.pack(fill="x", padx=30, pady=(0, 15))
        self.progress_bar.start()

        finalize_modal(self, min_width=360, min_height=140)
        self.update_idletasks()

    def update_status(self, text: str):
        """Thread-safe status message update"""
        def _update():
            if not self.winfo_exists():
                return
            self.status_label.configure(text=text)
            self.update_idletasks()
        self.after(0, _update)

    def close(self):
        """Thread-safe dialog termination"""
        def _close():
            if not self.winfo_exists():
                return
            try:
                self.progress_bar.stop()
            except Exception:
                pass
            self.destroy()
        self.after(0, _close)


class WhisperSubtitleDialog(ctk.CTkToplevel):
    """Styled dialog for editing whisper subtitles"""

    def __init__(self, master, whisper, colors: dict = None):
        super().__init__(master)

        self.whisper = whisper
        self.result = None
        self.colors = colors or {
            'primary': '#8B0000',
            'primary_hover': '#A50000',
            'secondary': '#DC143C',
            'accent': '#B22222',
            'bg_dark': '#1a0000',
            'bg_medium': '#2d0a0a',
            'text': '#FFE4E4',
            'text_dim': '#B88888',
        }

        self.title("Edit Whisper Subtitle")
        self.geometry("500x300")
        self.configure(fg_color=self.colors['bg_medium'])
        apply_app_icon(self)
        self.transient(master)
        self.grab_set()

        self.setup_ui()
        finalize_modal(self, min_width=520, min_height=320)

    def setup_ui(self):
        main_frame = ctk.CTkFrame(
            self,
            fg_color=self.colors['bg_dark'],
            corner_radius=12,
            border_width=2,
            border_color='#9370DB'  # Purple border for whispers
        )
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        ctk.CTkLabel(
            main_frame,
            text=f"🗣️ Edit Subtitle: {self.whisper.display_name}",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color='#9370DB'
        ).pack(pady=(15, 5))

        ctk.CTkLabel(
            main_frame,
            text=f"Category: {self.whisper.category.upper()}",
            font=ctk.CTkFont(size=10),
            text_color=self.colors['text_dim']
        ).pack(pady=(0, 15))

        # Current text display
        ctk.CTkLabel(
            main_frame,
            text="Current subtitle:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.colors['text'],
            anchor="w"
        ).pack(anchor="w", padx=15, pady=(0, 5))

        current_frame = ctk.CTkFrame(main_frame, fg_color=self.colors['bg_medium'], corner_radius=6)
        current_frame.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkLabel(
            current_frame,
            text=f'"{self.whisper.text}"',
            font=ctk.CTkFont(size=10),
            text_color=self.colors['text_dim'],
            anchor="w",
            wraplength=420,
            justify="left"
        ).pack(padx=10, pady=8, anchor="w")

        # New text input
        ctk.CTkLabel(
            main_frame,
            text="New subtitle text:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.colors['text'],
            anchor="w"
        ).pack(anchor="w", padx=15, pady=(0, 5))

        self.text_entry = ctk.CTkTextbox(
            main_frame,
            height=60,
            fg_color=self.colors['bg_medium'],
            text_color=self.colors['text'],
            border_width=1,
            border_color='#9370DB'
        )
        self.text_entry.pack(fill="x", padx=15, pady=(0, 15))
        self.text_entry.insert("1.0", self.whisper.text)
        self.text_entry.focus()

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.cancel,
            fg_color=self.colors['bg_medium'],
            hover_color=self.colors['accent'],
            text_color=self.colors['text'],
            width=100
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="💾 Save",
            command=self.save,
            fg_color='#9370DB',  # Purple for whisper theme
            hover_color='#7B68EE',
            text_color=self.colors['text'],
            font=ctk.CTkFont(weight="bold"),
            width=100
        ).pack(side="right", padx=5)

    def save(self):
        self.result = self.text_entry.get("1.0", "end-1c").strip()
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()

    def get_result(self):
        self.wait_window()
        return self.result


class ProgressDialog(ctk.CTkToplevel):
    """Progress dialog for applying playlists"""

    def __init__(self, master, title: str, playlists: List[Playlist],
                 audio_processor: AudioProcessor, game_manager: GameFileManager,
                 radio_segment_manager: RadioSegmentManager, colors: dict = None):
        super().__init__(master)

        self.playlists = playlists
        self.audio_processor = audio_processor
        self.game_manager = game_manager
        self.radio_segment_manager = radio_segment_manager
        self.colors = colors or {
            'primary': '#8B0000',
            'primary_hover': '#A50000',
            'secondary': '#DC143C',
            'accent': '#B22222',
            'danger': '#8B0000',
            'danger_hover': '#A50000',
            'bg_dark': '#1a0000',
            'bg_medium': '#2d0a0a',
            'text': '#FFE4E4',
            'text_dim': '#B88888',
        }

        self.title(title)
        self.geometry("600x400")
        self.configure(fg_color=self.colors['bg_medium'])
        apply_app_icon(self)
        self.transient(master)
        self.grab_set()

        self.setup_ui()
        finalize_modal(self, min_width=620, min_height=420)
        self.after(100, self.process_playlists)

    def setup_ui(self):
        main_frame = ctk.CTkFrame(
            self,
            fg_color=self.colors['bg_dark'],
            corner_radius=12,
            border_width=2,
            border_color=self.colors['accent']
        )
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        self.status_label = ctk.CTkLabel(
            main_frame,
            text="Processing...",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.colors['text']
        )
        self.status_label.pack(pady=20)

        self.progress_bar = ctk.CTkProgressBar(
            main_frame,
            progress_color=self.colors['secondary'],
            fg_color=self.colors['bg_medium'],
            border_color=self.colors['accent'],
            border_width=2
        )
        self.progress_bar.pack(fill="x", pady=10)
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)

        self.log_text = ctk.CTkTextbox(
            main_frame,
            height=150,
            fg_color=self.colors['bg_medium'],
            text_color=self.colors['text'],
            corner_radius=8,
            border_width=1,
            border_color=self.colors['accent']
        )
        self.log_text.pack(fill="both", expand=True, pady=10)

        self.close_btn = ctk.CTkButton(
            main_frame,
            text="Close",
            command=self.destroy,
            state="disabled",
            fg_color=self.colors['accent'],
            hover_color=self.colors['secondary'],
            text_color=self.colors['text']
        )
        self.close_btn.pack(pady=10)

    def log(self, message: str):
        """Thread-safe logging to the text box"""
        def _update():
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
        # Schedule GUI update on main thread
        self.after(0, _update)

    def update_status(self, text: str):
        """Thread-safe status label update"""
        self.after(0, lambda: self.status_label.configure(text=text))

    def update_progress(self, value: float):
        """Thread-safe progress bar update"""
        self.after(0, lambda: self.progress_bar.set(value))

    def process_playlists(self):
        """Start playlist processing in background thread"""
        # Run in a background thread to keep UI responsive
        thread = threading.Thread(target=self._process_playlists_thread, daemon=True)
        thread.start()

    def _process_playlists_thread(self):
        """Background thread for processing playlists"""
        total = len(self.playlists)
        success_count = 0
        failed_count = 0

        for i, playlist in enumerate(self.playlists):
            progress = (i + 1) / total
            self.update_progress(progress)
            self.update_status(f"Processing {i+1}/{total}: {playlist.name}")

            self.log(f"\n--- Processing: {playlist.name} ---")

            # Check if this is a radio segment assignment
            is_radio_segment = ".virtual" in playlist.game_file_path

            if is_radio_segment:
                # Handle radio segment replacement
                success = self._process_radio_segment_playlist(playlist)
                if success:
                    success_count += 1
                else:
                    failed_count += 1
            else:
                # Standard playlist processing
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                    temp_file = tmp.name

                try:
                    # Get original game file path to match audio properties
                    original_file_path = None
                    if self.game_manager.game_directory and playlist.game_file_path:
                        original_file_path = os.path.join(
                            self.game_manager.game_directory,
                            playlist.game_file_path
                        )

                    success, error_msg = self.audio_processor.create_playlist_audio(
                        playlist,
                        temp_file,
                        original_file_path=original_file_path
                    )

                    if success:
                        # Replace game file
                        replace_success, msg = self.game_manager.replace_game_file(
                            playlist.game_file_path,
                            temp_file,
                            create_backup=True
                        )

                        if replace_success:
                            self.log(f"✓ Success: {msg}")
                            success_count += 1
                        else:
                            self.log(f"✗ Failed: {msg}")
                            failed_count += 1
                    else:
                        self.log(f"✗ Failed to generate audio for {playlist.name}")
                        if error_msg:
                            self.log(f"  Error: {error_msg}")
                        failed_count += 1
                finally:
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass

        self.update_status("Complete!")
        self.log(f"\n=== Summary ===")
        self.log(f"Successfully applied: {success_count}")
        self.log(f"Failed: {failed_count}")

        # Enable close button on main thread
        self.after(0, lambda: self.close_btn.configure(state="normal"))

    def _process_radio_segment_playlist(self, playlist: Playlist) -> bool:
        """
        Process a playlist assigned to a radio loop segment

        Returns:
            True if successful, False otherwise
        """
        try:
            # Parse segment info from virtual path
            # Format: "Vampire\\sound\\radio\\radio_loop_1\\segment_05.virtual"
            virtual_path = (playlist.game_file_path or "").replace('\\', os.sep).replace('/', os.sep)
            path_parts = virtual_path.split(os.sep)
            if len(path_parts) < 2:
                self.log(f"  ✗ Invalid virtual path for playlist: {playlist.game_file_path}")
                return False
            loop_name = path_parts[-2]  # e.g., "radio_loop_1"
            segment_filename = path_parts[-1]  # e.g., "segment_05.virtual"
            segment_index = int(segment_filename.split('_')[1].split('.')[0])  # Extract "05" -> 5

            self.log(f"  Processing radio segment: {loop_name} segment {segment_index}")

            # Get all segments for this loop
            all_segments = self.radio_segment_manager.get_loop_segments(loop_name)
            if not all_segments:
                self.log(f"  ✗ No segments found for {loop_name}")
                return False

            target_segment = all_segments[segment_index]
            self.log(f"  Target: {target_segment.label} ({target_segment.duration_sec:.1f}s)")

            # IMPORTANT: Find ALL other playlists assigned to segments in this loop
            # so we preserve previous edits to other segments
            parent_app = self.master if hasattr(self, "master") else None
            candidate_playlists = list(self.playlists)
            if parent_app and hasattr(parent_app, "config") and parent_app.config:
                candidate_playlists.extend(parent_app.config.playlists)

            other_segment_playlists = []
            seen_playlist_ids = set()
            for other_playlist in candidate_playlists:
                if other_playlist is None or other_playlist is playlist:
                    continue  # Skip the current one

                playlist_id = id(other_playlist)
                if playlist_id in seen_playlist_ids:
                    continue

                other_path_raw = (getattr(other_playlist, "game_file_path", "") or "")
                if ".virtual" not in other_path_raw.lower():
                    continue

                normalized_path = other_path_raw.replace('\\', os.sep).replace('/', os.sep)
                other_parts = normalized_path.split(os.sep)
                if len(other_parts) < 2:
                    continue

                other_loop_name = other_parts[-2]
                if other_loop_name != loop_name:
                    continue

                other_segment_playlists.append(other_playlist)
                seen_playlist_ids.add(playlist_id)

            if other_segment_playlists:
                self.log(f"  Found {len(other_segment_playlists)} other segment(s) in this loop with playlists")

            # Create playlist audio for this segment
            import tempfile
            from pydub import AudioSegment as PyDubSegment

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                temp_segment_file = tmp.name

            try:
                # Get original loop path from game directory (for properties)
                game_loop_path = self.radio_segment_manager.get_original_loop_path(loop_name)

                # CRITICAL: Find the OLDEST backup to extract original segments from
                # We need the truly original file, not a backup that already has edits!
                backup_loop_path = None
                loop_filename = f"{loop_name}.mp3"

                if os.path.exists("./backups"):
                    import glob
                    # Sort backups oldest first (NOT reverse) to get the original file
                    backup_dirs = sorted(glob.glob("./backups/*"), reverse=False)

                    # Prioritize "full_backup_*" as these are user-initiated full backups (original files)
                    full_backup_dirs = [d for d in backup_dirs if "full_backup_" in os.path.basename(d)]
                    if full_backup_dirs:
                        backup_dirs = full_backup_dirs + [d for d in backup_dirs if d not in full_backup_dirs]

                    for backup_dir in backup_dirs:
                        # Look for the radio loop file in backup
                        for root, dirs, files in os.walk(backup_dir):
                            if loop_filename.lower() in [f.lower() for f in files]:
                                # Found it - construct full path
                                backup_loop_path = os.path.join(root, loop_filename)
                                self.log(f"  Using ORIGINAL backup from: {os.path.basename(backup_dir)}")
                                break
                        if backup_loop_path:
                            break

                # If no backup found, use game file (first edit scenario)
                if not backup_loop_path:
                    backup_loop_path = game_loop_path
                    self.log(f"  WARNING: No backup found - using current game file (may already be modified)")

                success, error_msg = self.audio_processor.create_playlist_audio(
                    playlist,
                    temp_segment_file,
                    original_file_path=backup_loop_path
                )

                if not success:
                    self.log(f"  ✗ Failed to create segment audio")
                    if error_msg:
                        self.log(f"    Error: {error_msg}")
                    return False

                # Load the replacement segment
                replacement_audio = PyDubSegment.from_file(temp_segment_file)
                self.log(f"  Replacement audio: {len(replacement_audio)/1000:.1f}s")

                # Create replacements dict with current segment
                replacements = {
                    target_segment.unique_id: replacement_audio
                }

                # Process other segment playlists to preserve previous edits
                for other_pl in other_segment_playlists:
                    try:
                        # Parse the segment index from the virtual path
                        normalized_other_path = other_pl.game_file_path.replace('\\', os.sep).replace('/', os.sep)
                        other_parts = normalized_other_path.split(os.sep)
                        other_seg_filename = other_parts[-1]
                        other_seg_index = int(other_seg_filename.split('_')[1].split('.')[0])
                        other_segment = all_segments[other_seg_index]

                        self.log(f"  Processing other segment: {other_segment.label}")

                        # Generate audio for this segment
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as other_tmp:
                            other_temp_file = other_tmp.name

                        try:
                            other_success, other_error_msg = self.audio_processor.create_playlist_audio(
                                other_pl,
                                other_temp_file,
                                original_file_path=backup_loop_path
                            )

                            if other_success:
                                other_replacement = PyDubSegment.from_file(other_temp_file)
                                replacements[other_segment.unique_id] = other_replacement
                                self.log(f"    Added to replacements: {len(other_replacement)/1000:.1f}s")
                            else:
                                self.log(f"    Warning: Could not generate audio for other segment")
                                if other_error_msg:
                                    self.log(f"      Error: {other_error_msg}")
                        finally:
                            try:
                                os.remove(other_temp_file)
                            except:
                                pass

                    except Exception as e:
                        self.log(f"    Warning: Could not process other segment: {e}")

                # Reassemble the full loop using BACKUP file for original segments
                self.log(f"  Reassembling {loop_name} with {len(replacements)} replacement(s) (using backup for originals)...")
                reassembled_loop = self.radio_segment_manager.segmenter.reassemble_radio_loop(
                    backup_loop_path,  # Use backup, not game file!
                    all_segments,
                    replacements
                )

                self.log(f"  Reassembly complete, preparing to export...")

                # Save the reassembled loop
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                    temp_loop_file = tmp.name

                self.log(f"  Created temp file: {temp_loop_file}")

                # Export at correct sample rate (use backup file for properties)
                self.log(f"  Reading backup file properties from: {backup_loop_path}")
                original_audio = PyDubSegment.from_file(backup_loop_path)
                target_sample_rate = original_audio.frame_rate
                self.log(f"  Target sample rate: {target_sample_rate} Hz")

                # Normalize reassembled loop to match game volume
                self.log(f"  Normalizing reassembled loop...")
                original_dBFS = reassembled_loop.dBFS
                target_dBFS = -8.0  # Conservative level to prevent clipping
                change_in_dBFS = target_dBFS - original_dBFS
                reassembled_loop = reassembled_loop.apply_gain(change_in_dBFS)
                self.log(f"  Normalized loop: {original_dBFS:.2f} dBFS -> {reassembled_loop.dBFS:.2f} dBFS ({change_in_dBFS:+.2f} dB)")

                self.log(f"  Exporting reassembled loop at {target_sample_rate} Hz...")
                reassembled_loop.export(
                    temp_loop_file,
                    format='mp3',
                    bitrate='128k',
                    parameters=["-ar", str(target_sample_rate)]
                )

                # Replace the original loop file in the correct location
                # Use the same path structure as where we found the backup
                loop_filename = f"{loop_name}.mp3"

                # Determine the correct relative path based on where the game reads from
                # Check if Unofficial_Patch version exists (takes priority)
                unofficial_path = os.path.join(self.game_manager.game_directory, "Unofficial_Patch", "sound", "radio", loop_filename)
                if os.path.exists(unofficial_path):
                    loop_rel_path = os.path.join("Unofficial_Patch", "sound", "radio", loop_filename)
                    self.log(f"  Replacing in Unofficial_Patch/sound/radio/")
                else:
                    loop_rel_path = os.path.join("Vampire", "sound", "radio", loop_filename)
                    self.log(f"  Replacing in Vampire/sound/radio/")

                replace_success, msg = self.game_manager.replace_game_file(
                    loop_rel_path,
                    temp_loop_file,
                    create_backup=True
                )

                if replace_success:
                    self.log(f"  ✓ Success: Replaced {loop_filename} with modified loop")

                    # CRITICAL: Regenerate cached segments from the NEW modified loop
                    # The old cache was based on original timings and is now invalid
                    self.log(f"  Regenerating segment cache for {loop_name}...")
                    try:
                        # Get the path to the newly modified loop file
                        modified_loop_path = os.path.join(self.game_manager.game_directory, loop_rel_path)

                        # Clear old cache for this loop
                        import glob
                        cache_pattern = os.path.join("./cache/radio_segments", f"{loop_name}_segment_*.mp3")
                        for cached_file in glob.glob(cache_pattern):
                            try:
                                os.remove(cached_file)
                                self.log(f"    Cleared old cache: {os.path.basename(cached_file)}")
                            except:
                                pass

                        # Calculate NEW segment timings based on the reassembly
                        # This is critical because segment positions change when we replace segments with different lengths
                        self.log(f"    Calculating new segment timings...")
                        new_timings = self.radio_segment_manager.segmenter.calculate_new_segment_timings(
                            all_segments,
                            replacements,
                            backup_loop_path
                        )

                        parent_app = self.master
                        # Update in-memory segment metadata so future operations use the new timings
                        for seg, new_timing in zip(all_segments, new_timings):
                            seg.start_ms = new_timing['start_ms']
                            seg.end_ms = new_timing['end_ms']
                            seg.start_sec = new_timing['start_ms'] / 1000
                            seg.end_sec = new_timing['end_ms'] / 1000
                            seg.duration_sec = new_timing['duration_ms'] / 1000

                        # Persist updated segment metadata to the JSON cache for this loop
                        cache_json_path = self.radio_segment_manager.segmenter.get_cache_path(f"{loop_name}.mp3")
                        self.radio_segment_manager.segmenter.save_segments_to_cache(all_segments, cache_json_path)

                        # Extract and cache segments from the NEW modified loop using NEW timings
                        from pydub import AudioSegment as PyDubSegment
                        import time
                        modified_loop_audio = PyDubSegment.from_file(modified_loop_path)

                        cached_count = 0
                        for seg, new_timing in zip(all_segments, new_timings):
                            # Use NEW timings, not original!
                            seg_audio = modified_loop_audio[new_timing['start_ms']:new_timing['end_ms']]
                            cache_filename = f"{loop_name}_segment_{seg.index:02d}.mp3"
                            cache_path = os.path.join("./cache/radio_segments", cache_filename)

                            self.log(f"    Segment {seg.index} ({seg.label}): {new_timing['start_ms']/1000:.1f}s - {new_timing['end_ms']/1000:.1f}s")

                            # Try to export with retry logic for file locks
                            max_retries = 3
                            for attempt in range(max_retries):
                                try:
                                    seg_audio.export(cache_path, format="mp3")
                                    seg.cached_audio_path = cache_path

                                    # Update the segment in the manager's maps so preview player sees new cache
                                    if seg.unique_id in self.radio_segment_manager.segment_map:
                                        self.radio_segment_manager.segment_map[seg.unique_id].cached_audio_path = cache_path

                                    # Keep game track entries pointing at the latest cache
                                    if parent_app is not None:
                                        for track in getattr(parent_app, "game_tracks", []):
                                            if track.get('is_radio_segment') and track.get('radio_segment') is seg:
                                                track['full_path'] = cache_path

                                    cached_count += 1
                                    break
                                except PermissionError:
                                    if attempt < max_retries - 1:
                                        time.sleep(0.5)
                                    else:
                                        self.log(f"    Warning: Could not cache segment {seg.index} (file locked)")
                                        seg.cached_audio_path = None
                                        # Update manager's map even if cache failed
                                        if seg.unique_id in self.radio_segment_manager.segment_map:
                                            self.radio_segment_manager.segment_map[seg.unique_id].cached_audio_path = None

                        self.log(f"    ✓ Regenerated {cached_count}/{len(all_segments)} segment caches")

                        # Refresh the track display to show updated segments
                        def refresh_location():
                            parent = self.master
                            handler = getattr(parent, "on_location_change", None)
                            if callable(handler):
                                handler(None)
                            else:
                                fallback = getattr(parent, "refresh_tracks", None)
                                if callable(fallback):
                                    fallback()
                        self.after(100, refresh_location)

                    except Exception as cache_error:
                        self.log(f"    Warning: Could not regenerate cache: {cache_error}")
                        # Don't fail the whole operation if cache regeneration fails

                    return True
                else:
                    self.log(f"  ✗ Failed: {msg}")
                    return False

            finally:
                # Clean up temp files
                try:
                    os.remove(temp_segment_file)
                except:
                    pass
                try:
                    os.remove(temp_loop_file)
                except:
                    pass

        except Exception as e:
            self.log(f"  ✗ Error processing radio segment: {e}")
            import traceback
            traceback.print_exc()
            return False


def run():
    """Run the application"""
    app = VTMBPlaylistMakerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
