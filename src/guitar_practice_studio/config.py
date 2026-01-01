"""
Configuration for Guitar Practice Studio
"""
import os
from pathlib import Path

# Base paths - use user's home directory for data persistence
DATA_DIR = Path.home() / ".guitar-practice-studio"
RECORDINGS_DIR = DATA_DIR / "recordings"
DATABASE_PATH = DATA_DIR / "practice.db"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# Audio settings
AUDIO_SAMPLE_RATE = 44100  # Standard CD quality
AUDIO_CHANNELS = 2         # Stereo for better guitar sound
AUDIO_FORMAT = "wav"

# Video settings
VIDEO_FPS = 30
VIDEO_CODEC = "mp4v"
VIDEO_FORMAT = "mp4"
VIDEO_RESOLUTION = (1280, 720)  # 720p default, adjust for your camera

# Recording settings
DEFAULT_CAMERA_INDEX = 0  # Usually 0 for primary USB camera

# Practice categories (Sandercoe-inspired structure)
PRACTICE_CATEGORIES = [
    "Technique",
    "Knowledge",
    "Songs",
    "Ear Training",
    "Time/Rythm",
    "Improvisation",
]

# Dash app settings
DEBUG = os.environ.get("GPS_DEBUG", "false").lower() == "true"
HOST = os.environ.get("GPS_HOST", "127.0.0.1")
PORT = int(os.environ.get("GPS_PORT", "8050"))
