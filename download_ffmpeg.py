"""
Download and set up FFmpeg binaries for bundling with the VTMB Playlist Maker executable.
Usage: python download_ffmpeg.py

Windows: Downloads a release build from https://github.com/GyanD/codexffmpeg/releases
macOS/Linux: Copies ffmpeg/ffprobe from your system PATH into ffmpeg_binaries/.
"""
import io
import os
import platform
import shutil
import sys
import zipfile

# Where to place the binaries
OUTPUT_DIR = "ffmpeg_binaries"
BIN_DIR = os.path.join(OUTPUT_DIR, "bin")

# Windows: URL for the essentials build (smaller, ~30 MB zip)
FFMPEG_WIN_URL = (
    "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip"
)


def _download_windows():
    """Download and extract FFmpeg for Windows."""
    try:
        import urllib.request
    except ImportError:
        print("ERROR: urllib.request not available.")
        sys.exit(1)

    os.makedirs(BIN_DIR, exist_ok=True)

    print(f"Downloading FFmpeg from:\n  {FFMPEG_WIN_URL}")
    print("This may take a minute...")

    req = urllib.request.Request(FFMPEG_WIN_URL, headers={"User-Agent": "vtmb-playlist-maker"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()

    print(f"Downloaded {len(data) / (1024*1024):.1f} MB — extracting...")

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        needed = {"ffmpeg.exe", "ffprobe.exe"}
        found = set()
        for entry in zf.namelist():
            basename = os.path.basename(entry)
            if basename in needed:
                target = os.path.join(BIN_DIR, basename)
                with zf.open(entry) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                found.add(basename)
                print(f"  Extracted: {basename}")
        missing = needed - found
        if missing:
            print(f"WARNING: Could not find {missing} inside the zip.")
            return False
    return True


def _copy_system_unix():
    """Copy ffmpeg/ffprobe from system PATH (macOS/Linux)."""
    os.makedirs(BIN_DIR, exist_ok=True)
    success = True
    for name in ("ffmpeg", "ffprobe"):
        src = shutil.which(name)
        if src:
            dst = os.path.join(BIN_DIR, name)
            shutil.copy2(src, dst)
            print(f"  Copied {src} -> {dst}")
        else:
            print(f"WARNING: '{name}' not found on PATH.")
            print(f"  Install it via your package manager (e.g. brew install ffmpeg)")
            success = False
    return success


def main():
    if os.path.exists(BIN_DIR):
        binaries = os.listdir(BIN_DIR)
        if binaries:
            print(f"FFmpeg binaries already present in {BIN_DIR}/:")
            for b in binaries:
                print(f"  {b}")
            answer = input("Re-download / overwrite? [y/N] ").strip().lower()
            if answer != "y":
                print("Skipped.")
                return

    system = platform.system()
    if system == "Windows":
        ok = _download_windows()
    else:
        ok = _copy_system_unix()

    if ok:
        print(f"\nFFmpeg binaries are ready in {BIN_DIR}/")
        print("You can now run: python build.py")
    else:
        print("\nSetup incomplete — see warnings above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
