"""
Recording module for Guitar Practice Studio
Uses sounddevice for audio (clean quality) and OpenCV for video,
then muxes with ffmpeg using timestamp alignment for sync.
"""
import os
import re
import time
import threading
import subprocess
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
import shutil

import numpy as np

try:
    import sounddevice as sd
    import soundfile as sf
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("Warning: sounddevice/soundfile not available. Audio recording disabled.")

try:
    import cv2
    VIDEO_AVAILABLE = True
except ImportError:
    VIDEO_AVAILABLE = False
    print("Warning: OpenCV not available. Video recording disabled.")

from .config import (
    RECORDINGS_DIR, AUDIO_SAMPLE_RATE, AUDIO_CHANNELS,
    VIDEO_FPS, VIDEO_RESOLUTION, DEFAULT_CAMERA_INDEX
)

def _find_ffmpeg():
    """Find ffmpeg, checking common macOS paths"""
    # First check PATH
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    
    # Check common macOS install locations
    common_paths = [
        "/opt/homebrew/bin/ffmpeg",  # Apple Silicon Homebrew
        "/usr/local/bin/ffmpeg",      # Intel Homebrew
        "/usr/bin/ffmpeg",            # System
    ]
    for path in common_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    
    return None

FFMPEG_PATH = _find_ffmpeg()
FFMPEG_AVAILABLE = FFMPEG_PATH is not None


class Recorder:
    """
    Records audio via sounddevice and video via OpenCV,
    then muxes them with ffmpeg for proper sync.
    """
    
    def __init__(self, camera_index: int = DEFAULT_CAMERA_INDEX):
        self.camera_index = camera_index
        self.audio_device = None
        self.is_recording = False
        self.start_time = None
        
        # File paths
        self.base_filename = None
        self.audio_path = None
        self.video_path = None
        
        # Threads
        self._audio_thread = None
        self._video_thread = None
        self._stop_event = threading.Event()
        
        # Sync: record when each actually starts
        self._audio_start_time = None
        self._video_start_time = None
        
        # Audio buffer
        self._audio_data = []
        
        self.on_duration_update: Optional[Callable[[float], None]] = None
    
    def _generate_filename(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def get_available_cameras(self) -> list:
        """List cameras - use ffmpeg on macOS for proper names"""
        cameras = []
        
        # On macOS, use ffmpeg to get proper device names
        if platform.system() == "Darwin" and FFMPEG_AVAILABLE:
            try:
                result = subprocess.run(
                    [FFMPEG_PATH, "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                    capture_output=True, text=True, timeout=5
                )
                lines = result.stderr.split('\n')
                in_video = False
                for line in lines:
                    if "AVFoundation video devices:" in line:
                        in_video = True
                        continue
                    if "AVFoundation audio devices:" in line:
                        break
                    # Look for lines containing device indices like [0], [1], etc
                    if in_video:
                        # Match pattern: [AVFoundation ...] [0] Device Name
                        match = re.search(r'\]\s*\[(\d+)\]\s*(.+)$', line)
                        if match:
                            idx = int(match.group(1))
                            name = match.group(2).strip()
                            cameras.append({"index": idx, "name": name})
                            print(f"  Found camera [{idx}]: {name}")
            except Exception as e:
                print(f"Error listing cameras: {e}")
        
        # Fallback to OpenCV (less descriptive names)
        if not cameras and VIDEO_AVAILABLE:
            print("  Using OpenCV fallback for camera detection")
            consecutive_failures = 0
            for i in range(10):
                if consecutive_failures >= 3:
                    break
                try:
                    cap = cv2.VideoCapture(i)
                    if cap.isOpened():
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        cameras.append({"index": i, "name": f"Camera {i} ({w}x{h})"})
                        cap.release()
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        cap.release()
                except Exception:
                    consecutive_failures += 1
        
        return cameras
    
    def get_available_audio_devices(self) -> list:
        """List audio inputs using sounddevice (matches what we record with)"""
        devices = []
        
        if AUDIO_AVAILABLE:
            try:
                for i, d in enumerate(sd.query_devices()):
                    if d['max_input_channels'] > 0:
                        devices.append({"index": i, "name": d['name']})
            except Exception as e:
                print(f"Error listing audio devices: {e}")
        
        return devices
    
    def _record_audio(self):
        """Record audio using sounddevice"""
        self._audio_data = []
        first_callback = [True]  # Use list to allow mutation in nested function
        
        def callback(indata, frames, time_info, status):
            if status:
                print(f"Audio: {status}")
            if first_callback[0]:
                self._audio_start_time = time.perf_counter()
                first_callback[0] = False
            self._audio_data.append(indata.copy())
        
        # Determine channels - use device's max or config, whichever is lower
        channels = AUDIO_CHANNELS
        if self.audio_device is not None and AUDIO_AVAILABLE:
            try:
                device_info = sd.query_devices(self.audio_device)
                max_channels = device_info.get('max_input_channels', 1)
                channels = min(channels, max_channels)
            except:
                pass
        
        try:
            with sd.InputStream(
                device=self.audio_device,
                samplerate=AUDIO_SAMPLE_RATE,
                channels=channels,
                callback=callback
            ):
                while not self._stop_event.is_set():
                    time.sleep(0.02)
        except Exception as e:
            print(f"Audio error: {e}")
            return
        
        if self._audio_data:
            audio = np.concatenate(self._audio_data, axis=0)
            sf.write(str(self.audio_path), audio, AUDIO_SAMPLE_RATE)
            print(f"Audio: {self.audio_path} ({len(audio)/AUDIO_SAMPLE_RATE:.1f}s, {channels}ch)")
    
    def _record_video(self):
        """Record video using OpenCV"""
        # On macOS, explicitly use AVFoundation backend for consistent indexing with ffmpeg
        if platform.system() == "Darwin":
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_AVFOUNDATION)
        else:
            cap = cv2.VideoCapture(self.camera_index)
        
        if not cap.isOpened():
            print(f"Cannot open camera {self.camera_index}")
            return
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, VIDEO_RESOLUTION[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, VIDEO_RESOLUTION[1])
        cap.set(cv2.CAP_PROP_FPS, VIDEO_FPS)
        
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Try codecs
        out = None
        for codec, ext in [('avc1', '.mp4'), ('mp4v', '.mp4'), ('XVID', '.avi')]:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            path = RECORDINGS_DIR / f"{self.base_filename}_video{ext}"
            out = cv2.VideoWriter(str(path), fourcc, VIDEO_FPS, (w, h))
            if out.isOpened():
                self.video_path = path
                break
            out.release()
            out = None
        
        if not out:
            print("Cannot create video writer")
            cap.release()
            return
        
        # Capture first frame and mark start time
        frames = 0
        while not self._stop_event.is_set():
            ret, frame = cap.read()
            if ret:
                if frames == 0:
                    # Mark time when first frame is actually captured
                    self._video_start_time = time.perf_counter()
                out.write(frame)
                frames += 1
            else:
                time.sleep(0.001)
        
        cap.release()
        out.release()
        print(f"Video: {self.video_path} ({frames} frames)")
    
    def _mux(self) -> str:
        """Mux audio+video with sync correction"""
        output = RECORDINGS_DIR / f"{self.base_filename}_final.mp4"
        
        # Calculate which started first and by how much
        audio_delay = 0
        video_delay = 0
        
        if self._audio_start_time and self._video_start_time:
            diff = self._audio_start_time - self._video_start_time
            if diff > 0:
                # Audio started AFTER video - delay audio
                audio_delay = diff
                print(f"Sync: audio started {diff*1000:.0f}ms late, delaying audio")
            else:
                # Video started AFTER audio - delay video
                video_delay = -diff
                print(f"Sync: video started {-diff*1000:.0f}ms late, delaying video")
        
        cmd = [FFMPEG_PATH, "-y"]
        
        # Video input (with delay if needed)
        if video_delay > 0:
            cmd.extend(["-itsoffset", f"{video_delay:.3f}"])
        cmd.extend(["-i", str(self.video_path)])
        
        # Audio input (with delay if needed)
        if audio_delay > 0:
            cmd.extend(["-itsoffset", f"{audio_delay:.3f}"])
        cmd.extend(["-i", str(self.audio_path)])
        
        cmd.extend([
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "256k",
            "-movflags", "+faststart",
            "-shortest",
            str(output)
        ])
        
        try:
            print(f"Mux command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0 and output.exists():
                self.audio_path.unlink(missing_ok=True)
                self.video_path.unlink(missing_ok=True)
                return str(output)
            else:
                print(f"Mux failed: {result.stderr[-500:]}")
        except Exception as e:
            print(f"Mux error: {e}")
        
        return str(self.video_path) if self.video_path.exists() else str(self.audio_path)
    
    def start(self, include_video: bool = True, include_audio: bool = True):
        """Start recording"""
        if self.is_recording:
            return
        
        self.base_filename = self._generate_filename()
        self.audio_path = RECORDINGS_DIR / f"{self.base_filename}_audio.wav"
        self.video_path = RECORDINGS_DIR / f"{self.base_filename}_video.mp4"
        
        self._stop_event.clear()
        self._audio_start_time = None
        self._video_start_time = None
        self._audio_data = []
        
        self.start_time = time.time()
        self.is_recording = True
        
        # Start threads together
        if include_video and VIDEO_AVAILABLE:
            self._video_thread = threading.Thread(target=self._record_video, daemon=True)
            self._video_thread.start()
        
        if include_audio and AUDIO_AVAILABLE:
            self._audio_thread = threading.Thread(target=self._record_audio, daemon=True)
            self._audio_thread.start()
        
        print(f"Recording: {self.base_filename}")
    
    def stop(self) -> dict:
        """Stop recording"""
        if not self.is_recording:
            return None
        
        duration = time.time() - self.start_time
        self._stop_event.set()
        self.is_recording = False
        
        # Wait for threads
        if self._audio_thread:
            self._audio_thread.join(timeout=5)
        if self._video_thread:
            self._video_thread.join(timeout=5)
        
        # Log timing info
        if self._audio_start_time and self._video_start_time:
            diff = (self._audio_start_time - self._video_start_time) * 1000
            print(f"Timing: audio started at {self._audio_start_time:.3f}, video at {self._video_start_time:.3f}")
            print(f"Timing: difference = {diff:.1f}ms")
        
        has_audio = self.audio_path and self.audio_path.exists() and self.audio_path.stat().st_size > 1000
        has_video = self.video_path and self.video_path.exists() and self.video_path.stat().st_size > 1000
        
        if has_audio and has_video and FFMPEG_AVAILABLE:
            final = self._mux()
        elif has_video:
            final = str(self.video_path)
        elif has_audio:
            final = str(self.audio_path)
        else:
            final = None
        
        print(f"Stopped: {duration:.1f}s")
        
        return {
            "filename": self.base_filename,
            "duration_seconds": duration,
            "final_path": final,
            "has_video": has_video,
            "has_audio": has_audio
        }
    
    def get_elapsed_time(self) -> float:
        if self.start_time and self.is_recording:
            return time.time() - self.start_time
        return 0


class PlaybackController:
    def __init__(self):
        self.current_file = None
    
    def load(self, filepath: str):
        self.current_file = filepath
    
    def get_duration(self, filepath: str) -> float:
        try:
            return sf.info(filepath).duration
        except:
            return 0


def test_recording(duration: int = 5):
    """Quick test"""
    r = Recorder()
    print(f"Cameras: {r.get_available_cameras()}")
    print(f"Audio: {r.get_available_audio_devices()}")
    r.start()
    time.sleep(duration)
    return r.stop()
