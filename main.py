#!/usr/bin/env python3
"""
VTMB Playlist Maker - Main Entry Point

A tool for creating custom music playlists for Vampire: The Masquerade - Bloodlines
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.gui import run

if __name__ == "__main__":
    run()
