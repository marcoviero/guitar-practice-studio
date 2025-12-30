"""
Audio utilities for Guitar Practice Studio
Handles waveform generation and audio analysis
"""
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import subprocess
import tempfile
import os

try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False


def extract_audio_from_video(video_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Extract audio track from video file using ffmpeg.
    Returns path to extracted WAV file.
    """
    if output_path is None:
        output_path = str(Path(video_path).with_suffix('.extracted.wav'))
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",  # No video
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        "-ac", "1",  # Mono
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and os.path.exists(output_path):
            return output_path
        else:
            print(f"ffmpeg error: {result.stderr}")
            return None
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Audio extraction failed: {e}")
        return None


def load_audio(filepath: str) -> Tuple[Optional[np.ndarray], Optional[int]]:
    """
    Load audio from file. Handles audio and video files.
    Returns (audio_data, sample_rate) or (None, None) on failure.
    """
    if not SOUNDFILE_AVAILABLE:
        return None, None
    
    filepath = str(filepath)
    
    # Try loading directly first (works for wav, flac, ogg)
    try:
        data, sr = sf.read(filepath)
        return data, sr
    except Exception:
        pass
    
    # For mp4, m4a, avi - extract audio with ffmpeg
    if filepath.endswith(('.mp4', '.m4a', '.avi', '.mov', '.mkv')):
        temp_audio = extract_audio_from_video(filepath)
        if temp_audio:
            try:
                data, sr = sf.read(temp_audio)
                # Clean up temp file
                os.remove(temp_audio)
                return data, sr
            except Exception as e:
                print(f"Failed to load extracted audio: {e}")
    
    return None, None


def generate_waveform_data(
    audio_data: np.ndarray, 
    sample_rate: int, 
    num_points: int = 1000
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate downsampled waveform data for visualization.
    
    Returns:
        times: Array of time values in seconds
        waveform_min: Minimum amplitude at each point
        waveform_max: Maximum amplitude at each point
    """
    # Handle stereo by converting to mono
    if len(audio_data.shape) > 1:
        audio_data = np.mean(audio_data, axis=1)
    
    total_samples = len(audio_data)
    duration = total_samples / sample_rate
    
    # Calculate samples per point
    samples_per_point = max(1, total_samples // num_points)
    actual_points = total_samples // samples_per_point
    
    # Reshape and compute min/max for each segment
    truncated = audio_data[:actual_points * samples_per_point]
    reshaped = truncated.reshape(actual_points, samples_per_point)
    
    waveform_min = np.min(reshaped, axis=1)
    waveform_max = np.max(reshaped, axis=1)
    
    # Generate time values
    times = np.linspace(0, duration, actual_points)
    
    return times, waveform_min, waveform_max


def get_audio_duration(filepath: str) -> float:
    """Get duration of audio/video file in seconds."""
    if not SOUNDFILE_AVAILABLE:
        return 0.0
    
    try:
        info = sf.info(filepath)
        return info.duration
    except Exception:
        # Try loading and computing duration
        data, sr = load_audio(filepath)
        if data is not None and sr is not None:
            if len(data.shape) > 1:
                return len(data) / sr
            return len(data) / sr
        return 0.0
