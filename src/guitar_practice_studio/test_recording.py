#!/usr/bin/env python3
"""
Test script for Guitar Practice Studio recording.
Run this to debug recording issues.

Usage:
    uv run python -m guitar_practice_studio.test_recording
"""
import subprocess
import sys
import time
from pathlib import Path

def check_ffmpeg():
    """Check if ffmpeg is available and working"""
    print("Checking ffmpeg...")
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"  ✓ ffmpeg found: {version}")
            return True
        else:
            print(f"  ✗ ffmpeg error: {result.stderr}")
            return False
    except FileNotFoundError:
        print("  ✗ ffmpeg not found in PATH")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def list_devices():
    """List available audio/video devices"""
    import platform
    system = platform.system()
    
    print(f"\nListing devices on {system}...")
    
    if system == "Darwin":
        try:
            result = subprocess.run(
                ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                capture_output=True, text=True, timeout=10
            )
            # The device list is in stderr
            print(result.stderr)
        except Exception as e:
            print(f"  Error: {e}")
    elif system == "Linux":
        print("  Video devices:")
        for i in range(5):
            if Path(f"/dev/video{i}").exists():
                print(f"    /dev/video{i}")
        print("  Audio: Use 'pactl list sources' for PulseAudio devices")
    else:
        print("  Use 'ffmpeg -list_devices true -f dshow -i dummy' for Windows devices")


def test_recording(duration=3, video=True, audio=True):
    """Test a short recording"""
    import platform
    from .config import RECORDINGS_DIR, VIDEO_FPS, VIDEO_RESOLUTION
    
    system = platform.system()
    output_path = RECORDINGS_DIR / "test_recording.mp4"
    
    print(f"\nTesting {duration}s recording (video={video}, audio={audio})...")
    print(f"Output: {output_path}")
    
    cmd = ["ffmpeg", "-y"]
    
    if system == "Darwin":
        if video and audio:
            cmd.extend(["-f", "avfoundation", "-framerate", str(VIDEO_FPS), "-i", "0:0"])
        elif video:
            cmd.extend(["-f", "avfoundation", "-framerate", str(VIDEO_FPS), "-i", "0:"])
        elif audio:
            cmd.extend(["-f", "avfoundation", "-i", ":0"])
    else:
        print(f"  Platform {system} - adjust device indices as needed")
        return
    
    cmd.extend([
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(output_path)
    ])
    
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 30)
        
        if result.returncode == 0:
            if output_path.exists():
                size = output_path.stat().st_size
                print(f"  ✓ Recording successful! File size: {size} bytes")
                if size < 1000:
                    print(f"  ⚠ Warning: File is very small, might be empty")
            else:
                print(f"  ✗ Recording failed - no output file")
        else:
            print(f"  ✗ Recording failed:")
            print(result.stderr[-1000:])
    except subprocess.TimeoutExpired:
        print(f"  ✗ Recording timed out")
    except Exception as e:
        print(f"  ✗ Error: {e}")


def main():
    print("=" * 50)
    print("Guitar Practice Studio - Recording Test")
    print("=" * 50)
    
    if not check_ffmpeg():
        print("\nPlease install ffmpeg first:")
        print("  macOS: brew install ffmpeg")
        print("  Linux: sudo apt install ffmpeg")
        sys.exit(1)
    
    list_devices()
    
    print("\nTesting audio-only recording...")
    test_recording(duration=2, video=False, audio=True)
    
    print("\nTesting video+audio recording...")
    test_recording(duration=3, video=True, audio=True)
    
    print("\n" + "=" * 50)
    print("Test complete. Check the output above for errors.")
    print("=" * 50)


if __name__ == "__main__":
    main()
