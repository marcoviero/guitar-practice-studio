"""
Desktop wrapper for Guitar Practice Studio using pywebview.
Runs the Dash app in a native window instead of a browser.
"""

import os
import sys
import threading
import time

# Handle PyInstaller bundled app
def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Set exercises.toml path before importing app
if hasattr(sys, '_MEIPASS'):
    os.environ['GPS_EXERCISES_PATH'] = get_resource_path('exercises.toml')

# Handle imports for both module and PyInstaller contexts
try:
    # When running as a module (uv run guitar-practice-desktop)
    from .app import app, init_db, init_default_exercises, recorder
    from .config import HOST, PORT, DEBUG, RECORDINGS_DIR
except ImportError:
    # When running as PyInstaller bundle
    from guitar_practice_studio.app import app, init_db, init_default_exercises, recorder
    from guitar_practice_studio.config import HOST, PORT, DEBUG, RECORDINGS_DIR

import webview

# Flag to track if server is ready
server_ready = threading.Event()


def run_server():
    """Run the Dash server in a background thread"""
    # Disable Dash's dev tools reloader when running in desktop mode
    app.run(
        debug=False,  # Disable debug mode for desktop
        host=HOST,
        port=PORT,
        use_reloader=False,  # Important: disable reloader for threading
        threaded=True
    )


def on_loaded():
    """Called when webview window is loaded"""
    pass


def on_closing():
    """Called when window is closing"""
    # Could add cleanup here if needed
    return True


def main():
    """Main entry point for desktop app"""
    print("🎸 Guitar Practice Studio (Desktop)")
    print(f"   Data directory: {RECORDINGS_DIR.parent}")
    
    if hasattr(sys, '_MEIPASS'):
        print(f"   Running from bundle: {sys._MEIPASS}")
    
    # Initialize database
    init_db()
    init_default_exercises()
    
    # Detect devices
    print("   Detecting devices...")
    cameras = recorder.get_available_cameras()
    audio_devs = recorder.get_available_audio_devices()
    print(f"   Cameras: {len(cameras)}")
    for c in cameras:
        print(f"      [{c['index']}] {c['name']}")
    print(f"   Audio inputs: {len(audio_devs)}")
    for a in audio_devs:
        print(f"      [{a['index']}] {a['name']}")
    
    # Start the Dash server in a background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Give server a moment to start
    time.sleep(1)
    
    print(f"   Server running at http://{HOST}:{PORT}")
    print("   Opening desktop window...")
    
    # Create the native window
    window = webview.create_window(
        title="🎸 Guitar Practice Studio",
        url=f"http://{HOST}:{PORT}",
        width=1400,
        height=900,
        min_size=(1024, 768),
        resizable=True,
        confirm_close=False,
        text_select=True,
    )
    
    # Start webview (this blocks until window is closed)
    webview.start(
        debug=DEBUG,
        http_server=False,  # We're running our own server
    )
    
    print("   Window closed. Goodbye!")


if __name__ == "__main__":
    main()
