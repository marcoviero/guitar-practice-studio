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

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone or unzip the project
cd guitar-practice-studio

# Install dependencies
uv sync

# Run the app
uv run guitar-practice
```

Then open http://127.0.0.1:8050 in your browser.

### Optional: ffmpeg (for video recording)

ffmpeg is needed for video recording (muxing audio + video). Audio-only recording works without it.

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows: Download from ffmpeg.org and add to PATH
```

## Features

### 📅 Planner Tab
- **Weekly grid** — Schedule exercises for each day of the week
- **Six practice categories** (Justin Guitar inspired):
  - Technique (finger gym, scales, picking)
  - Chord Perfect (chord changes, transitions)
  - Songs (repertoire practice)
  - Ear Training (intervals, chord recognition)
  - Theory (fretboard knowledge, chord construction)
  - Transcribing (learning by ear)
- **Time targets** — Each category shows progress toward daily targets
- **Visual feedback** — Categories turn green when targets are met
- **Today's checklist** — Quick view of what to practice today

### 🎵 Repertoire Tab
- **Track your pieces** — Songs, etudes, suites, riffs
- **Status workflow**: Want to Learn → Learning → Review → Mastered
- **Metadata** — Artist, genre, difficulty (1-5 stars), notes, links
- **Quick actions** — Advance status, edit, delete

### 📹 Practice Tab (Recording)
- Audio/video recording with device selection
- Real-time duration timer
- Post-session notes and self-rating
- Automatic file organization

### 📔 Journal Tab
- View all practice sessions
- Filter by date and category
- Add manual (non-recorded) entries

### 🔍 Review Tab
- Playback recordings with waveform visualization
- Loop sections for focused review
- Add time-stamped annotations
- Speed control (0.5x - 2x)

### 📊 Stats Tab
- Practice time by category (pie chart)
- Daily practice timeline
- Summary statistics

## Configuration

### exercises.toml

All exercises and category targets are defined in `exercises.toml`:

```toml
[categories.technique]
name = "Technique"
target_minutes = 15

[[exercises]]
name = "Spider Exercise"
category = "Technique"
duration = 5
description = "Chromatic finger independence exercise"
```

Edit this file to:
- Add/remove exercises
- Change default durations
- Adjust target minutes per category

**To reload exercises:** Delete `~/.guitar-practice-studio/practice.db` and restart the app.

### Environment Variables

- `GPS_DEBUG` — Enable debug mode (`true`/`false`, default: `false`)
- `GPS_HOST` — Server host (default: `127.0.0.1`)
- `GPS_PORT` — Server port (default: `8050`)

## Data Storage

All user data is stored in `~/.guitar-practice-studio/`:
- `practice.db` — SQLite database (sessions, plans, repertoire, goals)
- `recordings/` — Audio and video files

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

## Troubleshooting

### No cameras/microphones detected

**macOS:** Grant permissions in System Settings > Privacy & Security > Camera/Microphone

List available devices:
```bash
ffmpeg -f avfoundation -list_devices true -i ""
```

### Recording fails

1. Check terminal output for errors
2. Try audio-only recording first
3. Ensure no other app is using the camera
4. Test ffmpeg directly:
   ```bash
   ffmpeg -f avfoundation -framerate 30 -i "0:0" -t 3 test.mp4
   ```

### Database issues

To reset the database (clears all data):
```bash
rm ~/.guitar-practice-studio/practice.db
```

## Tips for Effective Practice

1. **Plan your week** — Use the Planner to schedule balanced practice
2. **Track your repertoire** — Keep pieces moving through the status workflow
3. **Record yourself** — Even audio-only reveals things you miss while playing
4. **Review with purpose** — Use annotations to mark specific issues
5. **Be consistent** — Short daily sessions beat long sporadic ones

## License

MIT — Use freely, practice often! 🎶
