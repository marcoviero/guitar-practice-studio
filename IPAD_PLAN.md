# iPad Compatibility Plan

Goal: use Guitar Practice Studio on an iPad. Two very different paths were evaluated.
This branch (`ipad-compatible-app-1`) implements **Path A** — the one that is actually
feasible and reuses the existing Python/Dash codebase. Path B (native TestFlight app) is
documented for the record but is **not** a port of this app.

---

## Background: why Sidecar can't reach `127.0.0.1:8050`

Sidecar mirrors/extends the Mac **display** to the iPad. It is not a network bridge.
Safari on the iPad resolves `127.0.0.1`/`localhost` to the **iPad itself**, where nothing
is running. The Mac's Dash server also currently binds to `127.0.0.1` (loopback), so it is
only reachable from the Mac.

Quick workaround with no code: run the app window on the Mac and drag it onto the iPad's
Sidecar display. To use the iPad's own Safari over Wi-Fi, we need Path A below.

---

## Path A — Serve over the LAN + PWA polish (this branch)

The Mac keeps hosting the app and doing all recording with the Acer USB camera. The iPad
becomes a remote screen / controller over Wi-Fi. This is the realistic "iPad-compatible"
outcome.

### A1. Bind the server to the LAN (core change)
- Default `HOST` is `127.0.0.1` in `src/guitar_practice_studio/config.py`. It is already
  overridable via `GPS_HOST`. Verify `desktop.py run_server()` and `app.py` `app.run()`
  both honor `HOST`.
- Provide a first-class "share to network" toggle instead of requiring the env var:
  - Add a launch flag / setting that sets `HOST=0.0.0.0`.
  - On startup, print the reachable URL(s): detect the Mac's LAN IP (e.g. `192.168.0.5`)
    and log `http://<ip>:8050`.
- Acceptance: on the same Wi-Fi, iPad Safari at `http://<mac-ip>:8050` loads the full app;
  recording (Acer camera on the Mac) still works and files land in `~/.guitar-practice-studio/recordings`.

### A2. Security / UX guardrails for network mode
- Binding to `0.0.0.0` exposes the app to the local network. Add:
  - A clear on-screen banner when in network mode.
  - Optional: a simple access token in the URL/query, or bind only when the user opts in.
- Confirm CORS / Dash assets load correctly from a non-localhost origin (usually fine, but
  verify the YouTube player, drum machine WebAudio, and any absolute-localhost URLs in
  `app.py`).

### A3. iPad browser compatibility pass
- Test on iPad Safari specifically:
  - Layout / responsive behavior of the Dash Bootstrap UI at iPad viewport sizes.
  - WebAudio drum machine (Safari has autoplay + AudioContext-resume quirks — needs a user
    gesture to start).
  - YouTube backing-track embed behavior on iPadOS.
  - Timer / auto-advance callbacks over the network (latency, websocket vs long-poll).
- Fix the highest-impact layout issues; note the rest.

### A4. Add-to-Home-Screen PWA polish (optional but nice)
- Add a web manifest + apple-touch-icon and `apple-mobile-web-app-capable` meta so the iPad
  can "Add to Home Screen" and launch it fullscreen like an app. No App Store needed.
- Serve these as Dash assets.

### A5. Docs
- README section: "Use on iPad over Wi-Fi" with the exact steps and the security note.

**Estimated effort:** A1–A2 small (hours). A3 is the real work (Safari testing/fixes). A4
small. This is the recommended deliverable.

---

## Path B — Native iPad app via TestFlight (NOT a port; documented only)

Reality check before anyone starts this:

- The current app is **Python** (Dash web server, OpenCV, `sounddevice`, `ffmpeg`). None of
  it runs on iPadOS, and Apple does not allow shipping a Python web-server app. **Zero code
  reuse** — it is a ground-up rewrite in Swift/SwiftUI + AVFoundation + AVAudioEngine.
- **Acer USB camera on iPad:** external UVC webcams are only supported on **USB-C iPads
  running iPadOS 17+**, and support is limited/finicky. On Lightning iPads it does not work.
  Most iPad apps just use the built-in cameras. This is the weakest part of the idea.
- Requires the **Apple Developer Program ($99/yr)**, an Xcode project, and App Store Connect
  for TestFlight distribution.

If pursued, it is a separate project: rebuild planner/journal/recording UI natively, use
AVFoundation for capture (built-in cameras reliably; external UVC only on supported
hardware), and reimplement the SQLite data model. Recommend deferring in favor of Path A.

---

## Decision

Proceed with **Path A** on this branch. Revisit Path B only if a native, offline,
built-in-camera iPad experience becomes a hard requirement — and accept that the Acer USB
camera may not be usable on the iPad at all.
