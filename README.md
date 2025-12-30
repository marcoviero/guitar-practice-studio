# 🎸 Guitar Practice Studio

A practice recording, journaling, and review tool inspired by the teaching philosophies of **Molly Gebrian** (*Learn Faster, Perform Better*) and **Justin Sandercoe**.

## Core Philosophy

> "You cannot hear yourself accurately while you're playing. Your brain is too busy executing motor commands to objectively evaluate the sound." — Molly Gebrian

This app helps you:
1. **Record** your practice sessions (audio + video)
2. **Review** recordings with time-stamped annotations
3. **Journal** what you practiced and reflect on progress
4. **Track goals** with structured categories

## Installation

Requires Python 3.10+, [uv](https://docs.astral.sh/uv/), and **ffmpeg**.

```bash
# Install ffmpeg first (required for recording)
# macOS:
brew install ffmpeg

# Ubuntu:
sudo apt install ffmpeg

# Windows: Download from ffmpeg.org and add to PATH

# Clone the repo
git clone https://github.com/YOUR_USERNAME/guitar-practice-studio.git
cd guitar-practice-studio

# Install dependencies with uv
uv sync

# Optional: Install audio effects (pitch-corrected slow playback)
uv sync --extra audio-effects
```

## Quick Start

```bash
# Run the app
uv run guitar-practice

# Or run directly
uv run python -m guitar_practice_studio.app
```

Then open http://127.0.0.1:8050 in your browser.

## Features

### 📹 Record Tab
- One-click audio/video recording
- Real-time duration timer
- Post-session notes and self-rating
- Automatic file organization

### 📔 Journal Tab
- View all practice sessions
- Filter by date and category
- Add manual (non-recorded) practice entries

### 🔍 Review Tab
- Playback recordings with speed control
- Add time-stamped annotations
- Mark issues, good moments, questions

### 🎯 Goals Tab
- Set weekly/monthly goals
- Track by practice category
- Optional time targets

### 📊 Stats Tab
- Practice time by category (pie chart)
- Daily practice timeline
- Summary statistics

## Practice Categories (Sandercoe-inspired)

- Technique
- Repertoire
- Ear Training
- Theory
- Sight Reading
- Improvisation
- Song Learning
- Maintenance/Review

## Project Structure

```
guitar-practice-studio/
├── pyproject.toml                      # Project config & dependencies
├── README.md
├── .gitignore
└── src/
    └── guitar_practice_studio/
        ├── __init__.py
        ├── app.py                      # Main Dash application
        ├── config.py                   # Settings (audio/video params, categories)
        ├── database.py                 # SQLite models and queries
        └── recorder.py                 # Audio/video capture module
```

## Data Storage

All user data is stored in `~/.guitar-practice-studio/`:
- `practice.db` — SQLite database (sessions, goals, annotations)
- `recordings/` — Audio and video files

## Configuration

Environment variables:
- `GPS_DEBUG` — Enable debug mode (`true`/`false`, default: `false`)
- `GPS_HOST` — Server host (default: `127.0.0.1`)
- `GPS_PORT` — Server port (default: `8050`)

Edit `src/guitar_practice_studio/config.py` to adjust:
- Video resolution (default: 720p)
- Audio sample rate (default: 44100 Hz)
- Camera index (default: 0)
- Practice categories

## Development

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Lint
uv run ruff check src/
```

## Tips for Effective Practice Review

1. **Don't watch immediately** — Let some time pass before reviewing
2. **Use annotations liberally** — Mark both problems AND successes
3. **Slow down playback** — Use 0.5x-0.75x to catch details in fast passages
4. **Review with a purpose** — Focus on specific elements (tone, timing, dynamics)
5. **Be kind but honest** — Note what needs work without self-criticism

## Troubleshooting

**Test recording from command line:**
```bash
# Run the built-in test
uv run python -m guitar_practice_studio.test_recording

# Or test ffmpeg directly (macOS)
ffmpeg -f avfoundation -framerate 30 -i "0:0" -t 3 -c:v libx264 -c:a aac test.mp4
```

**ffmpeg not found:**
- Ensure ffmpeg is installed and in your PATH
- Test with: `ffmpeg -version`

**No cameras detected:**
- On macOS: Grant Terminal/your IDE camera permissions in System Preferences > Privacy & Security
- List devices: `ffmpeg -f avfoundation -list_devices true -i ""`
- Try different camera indices in the dropdown
- Ensure no other app is using the camera

**No audio input detected:**
- On macOS: Grant microphone permissions in System Preferences > Privacy & Security
- Check that your audio interface/microphone is connected and set as default input

**Recording fails to start:**
- Check terminal output for ffmpeg errors
- On macOS, you may need to allow access the first time: a system dialog should appear
- Try audio-only recording first to isolate the issue

**Playback doesn't work:**
- Check file size in the preview - if it's very small (< 1KB), recording failed
- Check terminal for ffmpeg errors
- Try playing the file directly: `open ~/.guitar-practice-studio/recordings/filename.mp4`

## License

MIT — Use freely, practice often! 🎶
