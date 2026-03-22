"""
Build script for VTMB Playlist Maker executable.
Usage: python build.py
"""
import subprocess
import sys
import os

SPEC_FILE = "vtmb-playlist-maker.spec"


def main():
    if not os.path.exists(SPEC_FILE):
        print(f"ERROR: {SPEC_FILE} not found. Run from the project root.")
        sys.exit(1)

    # Check FFmpeg binaries — auto-download if missing
    ffmpeg_dir = "ffmpeg_binaries"
    ffmpeg_bin = os.path.join(ffmpeg_dir, "bin", "ffmpeg.exe")
    if not os.path.exists(ffmpeg_bin):
        print("FFmpeg binaries not found — downloading automatically...")
        dl = subprocess.run([sys.executable, "download_ffmpeg.py"])
        if dl.returncode != 0 or not os.path.exists(ffmpeg_bin):
            print("WARNING: FFmpeg download failed. The exe will require FFmpeg on the user's PATH.\n")

    print("Building VTMB Playlist Maker...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", SPEC_FILE, "--clean", "--noconfirm"],
        cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
    )

    if result.returncode == 0:
        dist_exe = os.path.join("dist", "VTMB-Playlist-Maker.exe")
        if os.path.exists(dist_exe):
            size_mb = os.path.getsize(dist_exe) / (1024 * 1024)
            print(f"\nBuild successful!  {dist_exe}  ({size_mb:.1f} MB)")
        else:
            print("\nBuild completed. Check the dist/ folder for your executable.")
    else:
        print(f"\nBuild FAILED (exit code {result.returncode}).")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
