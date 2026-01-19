# 🎸 Guitar Practice Studio

A practice planning, recording, and review tool inspired by the teaching philosophies of **Justin Sandercoe** (structured practice routines) and **Molly Gebrian** (*Learn Faster, Perform Better* — the importance of recording yourself).

## Core Philosophy

> "You cannot hear yourself accurately while you're playing. Your brain is too busy executing motor commands to objectively evaluate the sound." — Molly Gebrian

This app helps you:
1. **Plan** your weekly practice with a structured routine
2. **Track** your repertoire (songs, etudes, suites)
3. **Record** practice sessions (audio + video)
4. **Review** recordings with time-stamped annotations
5. **Journal** and reflect on progress

## Installation

### Step 1: Install uv (Package Manager)

**uv** is a fast Python package manager that makes installation simple.

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, restart your terminal (or open a new one).

To verify it worked, type:
```bash
uv --version
```
You should see something like `uv 0.5.x`.

### Step 2: Install Guitar Practice Studio

```bash
# Unzip the project and navigate into it
cd guitar-practice-studio

# Install dependencies (this may take a minute the first time)
uv sync

# Run the app (browser mode)
uv run guitar-practice
```

Then open **http://127.0.0.1:8050** in your browser.

### Step 2b (Alternative): Run as Desktop App

For a native desktop window (no browser needed):

```bash
uv run guitar-practice-desktop
```

This opens a standalone window with the app. Benefits:
- No browser URL bar
- Dedicated window in your dock/taskbar
- Cleaner look and feel

### Step 3 (Optional): Install ffmpeg for Video Recording

ffmpeg is needed for video recording (combining audio + video). Audio-only recording works without it.

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg
```

**Windows:** Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

## Features

### 📅 Planner Tab
- **Guitar type filter** — Switch between Classical, Electric, and Steel String guitars
- **Weekly grid** — Schedule exercises for each day of the week
- **Week navigation** — Browse previous and future weeks
- **Six practice categories** (customizable in `exercises.toml`):
  - Technique, Knowledge, Songs, Ear Training, Time/Rhythm, Improvisation
- **Time targets** — Each category shows progress toward daily targets
- **Visual feedback** — Columns highlight when you've practiced that day
- **Today's checklist** — Reorderable list of what to practice today

### 🎵 Repertoire Tab
- **Track your pieces** — Songs, etudes, suites, riffs
- **Status workflow**: Want to Learn → Learning → Review → Mastered
- **Metadata** — Artist, genre, difficulty (1-5 stars), notes, links
- **Quick actions** — Advance status, edit, delete

### 🎤 Practice Tab
- **Countdown timer** — Set your practice duration and stay focused
- **☕ Keep Awake** — Prevent laptop from sleeping during practice
- **Recording** with device selection (camera + microphone)
- **Recording types** — Label as Performance, Exercise, or Riff
- **🥁 Drum Machine** — Built-in patterns for practicing with rhythm:
  - Rock, Pop, Blues Shuffle, Funk, Jazz Swing, Bossa Nova, Metronome
  - Adjustable BPM (40-200) and volume
  - Visual beat indicator
- **▶ YouTube Backing Tracks** — Paste any YouTube URL to play along:
  - **Save tracks** — Build a library of your favorite backing tracks
  - Speed control (0.25x - 2x) for learning parts slowly
  - Loop toggle for continuous practice
  - Audio-only mode (hides video)
  - Sync with drum machine
- **Today's Practice sidebar** — Quick checklist from your plan

### 📔 Journal Tab
- **Week-at-a-glance** — Navigate weeks with visual daily summaries
- **Daily details** — All recordings and notes for the selected day
- **Editable notes** — Add reflections for any day

### 🔍 Review Tab
- **Playback recordings** with waveform visualization
- **Loop sections** for focused review
- **Filter by type** — Performance, Exercise, Riff
- **Speed control** (0.5x - 2x)

## Configuration

### exercises.toml

All exercises and category targets are defined in `exercises.toml`. **Changes sync automatically on restart** — no need to delete the database.

```toml
[categories.technique]
name = "Technique"
target_minutes = 15

[[exercises]]
name = "Spider Exercise"
category = "Technique"
duration = 5
description = "Chromatic finger independence exercise"

# Exercises can be limited to specific guitar types
[[exercises]]
name = "Bend in Tune"
category = "Technique"
duration = 5
guitars = ["electric", "steel"]  # Won't show for classical

[[exercises]]
name = "Rest Stroke Practice"
category = "Technique"
duration = 5
guitars = ["classical"]  # Only shows for classical
```

Edit this file to:
- Add/remove/rename exercises
- Change default durations
- Adjust target minutes per category
- Assign exercises to specific guitar types: `classical`, `electric`, `steel`, or `all` (default)

### Environment Variables

- `GPS_DEBUG` — Enable debug mode (`true`/`false`, default: `false`)
- `GPS_HOST` — Server host (default: `127.0.0.1`)
- `GPS_PORT` — Server port (default: `8050`)

## Data Storage

All user data is stored in `~/.guitar-practice-studio/`:
- `practice.db` — SQLite database (sessions, plans, repertoire)
- `recordings/` — Audio and video files

## Troubleshooting

### No cameras/microphones detected

**macOS:** Grant permissions in System Settings > Privacy & Security > Camera/Microphone

List available devices:
```bash
ffmpeg -f avfoundation -list_devices true -i ""
```

### Recording fails

1. Check terminal output for errors
2. Try audio-only recording first (uncheck camera)
3. Ensure no other app is using the camera
4. Click "Refresh" in the Recording Devices section

### Database reset

To completely reset (clears all data):
```bash
rm ~/.guitar-practice-studio/practice.db
```

### uv not found after installation

- **macOS/Linux:** Run `source ~/.bashrc` or `source ~/.zshrc`, or restart terminal
- **Windows:** Close and reopen PowerShell

## Tips for Effective Practice

1. **Plan your week** — Use the Planner to schedule balanced practice
2. **Use the drum machine** — Practicing with rhythm improves timing
3. **Record yourself** — Even audio-only reveals things you miss while playing
4. **Slow it down** — Use YouTube speed control to learn difficult parts
5. **Review with purpose** — Use annotations to mark specific issues
6. **Be consistent** — Short daily sessions beat long sporadic ones

## Project Structure

```
guitar-practice-studio/
├── pyproject.toml          # Dependencies & project config
├── exercises.toml          # Exercise definitions & category targets
├── README.md
└── src/
    └── guitar_practice_studio/
        ├── app.py          # Main Dash application & UI
        ├── config.py       # Settings (audio/video params)
        ├── database.py     # SQLite models & queries
        ├── recorder.py     # Audio/video capture
        └── audio_utils.py  # Waveform generation
```

## License

MIT — Use freely, practice often! 🎶
