# 🎸 Guitar Practice Studio

A desktop app for guitarists to plan weekly practice routines and easily record themselves.

**Key features:**
- **Weekly Planner** — Schedule exercises across categories (technique, repertoire, theory, etc.) with time targets
- **Easy Recording** — One-click audio recording with waveform visualization; video recording available with ffmpeg
- **Practice Timer** — Countdown timer that auto-advances through your daily checklist
- **Backing Tracks** — Built-in drum machine and YouTube player with speed control
- **Journal** — Track your progress with a week-at-a-glance view
- **Guitar Filtering** — Separate exercises for classical, electric, and steel string

## Download & Install

1. Download `Guitar Practice Studio.app` (or the .dmg)
2. Drag to your Applications folder
3. Double-click to run

That's it — no Python, no terminal, no dependencies needed.

### Video Recording (Optional)

Video recording requires [ffmpeg](https://ffmpeg.org). Without it, audio recording works fine.

To enable video recording on macOS:
```bash
brew install ffmpeg
```

The app will automatically detect ffmpeg and enable video recording.

## Building from Source

If you want to modify the app or build it yourself:

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager
- macOS with Xcode Command Line Tools

### Run in Development Mode

```bash
# Clone or download the source
cd guitar-practice-studio

# Install dependencies
uv sync

# Run in browser mode
uv run guitar-practice

# Or run in desktop window mode
uv run guitar-practice-desktop
```

Then open http://127.0.0.1:8050 in your browser (for browser mode).

### Build the Standalone App

```bash
# Install dev dependencies
uv sync --extra dev

# Build
./build_app.sh
```

The app will be created at `dist/Guitar Practice Studio.app`.

To create a distributable DMG:
```bash
hdiutil create -volname "Guitar Practice Studio" -srcfolder "dist/Guitar Practice Studio.app" -ov -format UDZO GuitarPracticeStudio.dmg
```

## Data Storage

All your data is stored locally in `~/.guitar-practice-studio/`:
- `practice.db` — Database (plans, recordings, journal entries)
- `recordings/` — Audio and video files

To reset completely, delete this folder.

## Project Structure

```
guitar-practice-studio/
├── pyproject.toml              # Dependencies & project config
├── exercises.toml              # Exercise definitions (editable)
├── guitar_practice_studio.spec # PyInstaller build config
├── build_app.sh                # Build script
└── src/guitar_practice_studio/
    ├── app.py                  # Main UI
    ├── desktop.py              # Desktop window wrapper
    ├── database.py             # Data models
    ├── recorder.py             # Audio/video capture
    ├── config.py               # Settings
    └── audio_utils.py          # Waveform generation
```

## Customizing Exercises

Edit `exercises.toml` to add your own exercises:

```toml
[[exercises]]
name = "My Custom Exercise"
category = "Technique"
default_duration = 10
guitars = ["classical", "electric"]  # or "all"
```

For the standalone app, place your custom `exercises.toml` in `~/.guitar-practice-studio/`.

## License

Free for personal use. Share freely, but please don't sell or repackage.

If you find this useful, donations are appreciated (Venmo @Marco-Viero)! 🎶

See [LICENSE](LICENSE) for full terms.
