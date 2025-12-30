"""
Guitar Practice Studio - Main Dash Application

A tool for recording, journaling, and reviewing guitar practice sessions.
Inspired by the teaching methods of Molly Gebrian and Justin Sandercoe.
"""
import os
import mimetypes
from datetime import datetime, date, timedelta
from pathlib import Path

import dash
from dash import html, dcc, callback, Input, Output, State, ctx, ALL, MATCH
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from flask import send_from_directory
import numpy as np

from .config import PRACTICE_CATEGORIES, RECORDINGS_DIR, DEBUG, HOST, PORT
from .database import (
    init_db, get_session, PracticeSession, Goal, Annotation,
    create_practice_session, get_recent_sessions, add_annotation,
    get_active_goals, get_practice_stats, get_sessions_by_date_range
)
from .recorder import Recorder, PlaybackController, AUDIO_AVAILABLE, VIDEO_AVAILABLE
from .audio_utils import load_audio, generate_waveform_data, get_audio_duration

# Initialize
init_db()
recorder = Recorder()
playback = PlaybackController()

# Create Dash app with Bootstrap theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True
)
app.title = "Guitar Practice Studio"

# ============================================================================
# LAYOUT COMPONENTS
# ============================================================================

def create_navbar():
    return dbc.Navbar(
        dbc.Container([
            dbc.NavbarBrand("🎸 Guitar Practice Studio", className="ms-2 fs-4"),
            dbc.Nav([
                dbc.NavItem(dbc.NavLink("Record", href="/", active="exact")),
                dbc.NavItem(dbc.NavLink("Journal", href="/journal", active="exact")),
                dbc.NavItem(dbc.NavLink("Review", href="/review", active="exact")),
                dbc.NavItem(dbc.NavLink("Goals", href="/goals", active="exact")),
                dbc.NavItem(dbc.NavLink("Stats", href="/stats", active="exact")),
            ], navbar=True),
        ]),
        color="primary",
        dark=True,
        className="mb-4"
    )


def create_record_page():
    """Recording page with video preview and controls"""
    # Get available devices
    available_cameras = recorder.get_available_cameras()
    available_audio = recorder.get_available_audio_devices()
    
    camera_options = [{"label": f"Camera {c['index']}: {c.get('name', 'Unknown')}", "value": c['index']} 
                      for c in available_cameras]
    if not camera_options:
        camera_options = [{"label": "No cameras found", "value": -1}]
    
    audio_options = [{"label": f"{a['name']}", "value": a['index']} 
                     for a in available_audio]
    if not audio_options:
        audio_options = [{"label": "No audio inputs found", "value": -1}]
    
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H3("Record Practice Session", className="mb-4"),
                
                # Session info form
                dbc.Card([
                    dbc.CardHeader("Session Details"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Title"),
                                dbc.Input(id="record-title", placeholder="What are you working on?"),
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Category"),
                                dcc.Dropdown(
                                    id="record-category",
                                    options=[{"label": c, "value": c} for c in PRACTICE_CATEGORIES],
                                    value=PRACTICE_CATEGORIES[0]
                                ),
                            ], md=6),
                        ], className="mb-3"),
                        dbc.Label("Description (optional)"),
                        dbc.Textarea(id="record-description", placeholder="Notes about what you're practicing..."),
                    ])
                ], className="mb-4"),
                
                # Device selection
                dbc.Card([
                    dbc.CardHeader("Devices"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Camera"),
                                dcc.Dropdown(
                                    id="camera-select",
                                    options=camera_options,
                                    value=camera_options[0]["value"] if camera_options else None,
                                    clearable=False
                                ),
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Audio Input"),
                                dcc.Dropdown(
                                    id="audio-select",
                                    options=audio_options,
                                    value=audio_options[0]["value"] if audio_options else None,
                                    clearable=False
                                ),
                            ], md=6),
                        ]),
                        dbc.Button("🔄 Refresh Devices", id="btn-refresh-devices", 
                                   color="link", size="sm", className="mt-2"),
                    ])
                ], className="mb-4"),
                
                # Recording controls
                dbc.Card([
                    dbc.CardHeader("Recording"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Checklist(
                                    id="record-options",
                                    options=[
                                        {"label": " Include Video", "value": "video", "disabled": not VIDEO_AVAILABLE},
                                        {"label": " Include Audio", "value": "audio", "disabled": not AUDIO_AVAILABLE},
                                    ],
                                    value=["audio"] + (["video"] if VIDEO_AVAILABLE else []),
                                    inline=True
                                ),
                            ], md=8),
                            dbc.Col([
                                html.Div(id="record-timer", className="fs-3 text-center font-monospace"),
                            ], md=4),
                        ], className="mb-3"),
                        
                        dbc.ButtonGroup([
                            dbc.Button("▶ Start Recording", id="btn-start-record", color="success", size="lg"),
                            dbc.Button("⏹ Stop & Save", id="btn-stop-record", color="danger", size="lg", disabled=True),
                        ], className="w-100"),
                        
                        # Status message
                        html.Div(id="record-status", className="mt-3 text-center"),
                    ])
                ], className="mb-4"),
                
                # Post-recording form (appears after stopping)
                html.Div(id="post-record-form", style={"display": "none"}, children=[
                    dbc.Card([
                        dbc.CardHeader("Review Recording"),
                        dbc.CardBody([
                            # Preview playback
                            html.Div(id="recording-preview", className="mb-3"),
                            
                            html.Hr(),
                            
                            dbc.Label("How did it go?"),
                            dbc.RadioItems(
                                id="record-rating",
                                options=[
                                    {"label": "⭐", "value": 1},
                                    {"label": "⭐⭐", "value": 2},
                                    {"label": "⭐⭐⭐", "value": 3},
                                    {"label": "⭐⭐⭐⭐", "value": 4},
                                    {"label": "⭐⭐⭐⭐⭐", "value": 5},
                                ],
                                inline=True,
                                className="mb-3"
                            ),
                            dbc.Label("Reflection"),
                            dbc.Textarea(id="record-notes", placeholder="What did you learn? What needs work?"),
                            
                            html.Div([
                                dbc.Button("💾 Save", id="btn-save-session", color="success", className="me-2"),
                                dbc.Button("🔄 Discard & Retry", id="btn-discard-retry", color="warning", className="me-2"),
                                dbc.Button("🗑 Discard", id="btn-discard", color="danger", outline=True),
                            ], className="mt-3"),
                        ])
                    ])
                ]),
            ], lg=8),
            
            dbc.Col([
                # Quick stats sidebar
                dbc.Card([
                    dbc.CardHeader("Today's Practice"),
                    dbc.CardBody(id="today-stats"),
                ], className="mb-4"),
                
                dbc.Card([
                    dbc.CardHeader("Active Goals"),
                    dbc.CardBody(id="sidebar-goals"),
                ]),
            ], lg=4),
        ]),
        
        # Interval for timer updates
        dcc.Interval(id="timer-interval", interval=1000, disabled=True),
        
        # Store for recording state
        dcc.Store(id="recording-state", data={"is_recording": False, "start_time": None, "result": None}),
        
        # Store for device selections
        dcc.Store(id="device-state", data={"camera": 0, "audio": None}),
    ])


def create_journal_page():
    """Practice journal with session history"""
    return dbc.Container([
        html.H3("Practice Journal", className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                # Filters
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Date Range"),
                                dcc.DatePickerRange(
                                    id="journal-date-range",
                                    start_date=(date.today() - timedelta(days=30)),
                                    end_date=date.today(),
                                    display_format="MMM D, YYYY"
                                ),
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Category"),
                                dcc.Dropdown(
                                    id="journal-category-filter",
                                    options=[{"label": "All", "value": "all"}] + 
                                            [{"label": c, "value": c} for c in PRACTICE_CATEGORIES],
                                    value="all"
                                ),
                            ], md=4),
                            dbc.Col([
                                dbc.Label(" "),
                                dbc.Button("🔄 Refresh", id="btn-refresh-journal", className="d-block"),
                            ], md=2),
                        ]),
                    ])
                ], className="mb-4"),
                
                # Sessions list
                html.Div(id="journal-sessions-list"),
            ], lg=8),
            
            dbc.Col([
                # Add manual entry
                dbc.Card([
                    dbc.CardHeader("Log Practice (No Recording)"),
                    dbc.CardBody([
                        dbc.Label("Title"),
                        dbc.Input(id="manual-title", placeholder="What did you practice?", className="mb-2"),
                        dbc.Label("Category"),
                        dcc.Dropdown(
                            id="manual-category",
                            options=[{"label": c, "value": c} for c in PRACTICE_CATEGORIES],
                            className="mb-2"
                        ),
                        dbc.Label("Duration (minutes)"),
                        dbc.Input(id="manual-duration", type="number", min=1, className="mb-2"),
                        dbc.Label("Notes"),
                        dbc.Textarea(id="manual-notes", className="mb-2"),
                        dbc.Button("Add Entry", id="btn-add-manual", color="primary"),
                        html.Div(id="manual-status", className="mt-2"),
                    ])
                ])
            ], lg=4),
        ])
    ])


def create_review_page():
    """Review recordings with playback, waveform visualization, and annotations"""
    return dbc.Container([
        html.H3("Review Recordings", className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                # Session table
                dbc.Card([
                    dbc.CardHeader([
                        "Recordings",
                        dbc.Button("🔄 Refresh", id="btn-refresh-recordings", size="sm", 
                                   color="link", className="float-end p-0")
                    ]),
                    dbc.CardBody([
                        html.Div(id="recordings-table-container"),
                    ])
                ], className="mb-4"),
                
                # Playback area (shown when a session is selected)
                html.Div(id="review-playback-area"),
                
                # Waveform and controls
                html.Div(id="review-waveform-area", className="mt-3"),
                
                # Playback controls
                html.Div(id="review-controls-area", className="mt-3"),
                
                # Annotations list
                html.Div(id="review-annotations-list", className="mt-4"),
            ], lg=8),
            
            dbc.Col([
                # Add annotation
                dbc.Card([
                    dbc.CardHeader("Add Annotation"),
                    dbc.CardBody([
                        dbc.Label("Timestamp (seconds)"),
                        dbc.Input(id="annotation-timestamp", type="number", min=0, step=0.1, className="mb-2"),
                        dbc.Button("⏱ Use Current Time", id="btn-get-current-time", size="sm", color="secondary", className="mb-2"),
                        dbc.Label("Type"),
                        dcc.Dropdown(
                            id="annotation-type",
                            options=[
                                {"label": "🔴 Issue", "value": "issue"},
                                {"label": "🟢 Good", "value": "good"},
                                {"label": "❓ Question", "value": "question"},
                                {"label": "📝 Note", "value": "note"},
                            ],
                            value="note",
                            className="mb-2"
                        ),
                        dbc.Label("Note"),
                        dbc.Textarea(id="annotation-text", placeholder="What did you notice?", className="mb-2"),
                        dbc.Button("Add Annotation", id="btn-add-annotation", color="primary"),
                        html.Div(id="annotation-status", className="mt-2"),
                    ])
                ]),
                
                # Session details
                html.Div(id="review-session-details", className="mt-4"),
            ], lg=4),
        ]),
        
        # Hidden stores for state
        dcc.Store(id="review-session-select", data=None),
        dcc.Store(id="review-audio-data", data=None),
        dcc.Store(id="review-loop-range", data={"start": None, "end": None}),
        dcc.Store(id="review-current-time", data=0),
        dcc.Store(id="table-refresh-trigger", data=0),
        
        # Hidden divs for clientside callback outputs
        html.Div(id="playback-speed-output", style={"display": "none"}),
        html.Div(id="waveform-click-output", style={"display": "none"}),
        html.Div(id="loop-handler-output", style={"display": "none"}),
        html.Div(id="loop-controls-output", style={"display": "none"}),
        html.Div(id="skip-controls-output", style={"display": "none"}),
        html.Div(id="annotation-seek-output", style={"display": "none"}),
        
        # Interval for updating current time display (disabled until we need it)
        dcc.Interval(id="review-time-interval", interval=500, disabled=True, n_intervals=0),
    ])


def create_goals_page():
    """Goals management"""
    return dbc.Container([
        html.H3("Practice Goals", className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                # Active goals
                html.H5("Active Goals"),
                html.Div(id="goals-active-list"),
            ], lg=8),
            
            dbc.Col([
                # Add new goal
                dbc.Card([
                    dbc.CardHeader("New Goal"),
                    dbc.CardBody([
                        dbc.Label("Goal"),
                        dbc.Input(id="goal-title", placeholder="e.g., Learn Clair de Lune", className="mb-2"),
                        dbc.Label("Category"),
                        dcc.Dropdown(
                            id="goal-category",
                            options=[{"label": c, "value": c} for c in PRACTICE_CATEGORIES],
                            className="mb-2"
                        ),
                        dbc.Label("Type"),
                        dcc.Dropdown(
                            id="goal-type",
                            options=[
                                {"label": "Weekly", "value": "weekly"},
                                {"label": "Monthly", "value": "monthly"},
                                {"label": "Ongoing", "value": "ongoing"},
                            ],
                            value="weekly",
                            className="mb-2"
                        ),
                        dbc.Label("Target Minutes (optional)"),
                        dbc.Input(id="goal-target-minutes", type="number", min=0, className="mb-2"),
                        dbc.Label("Description"),
                        dbc.Textarea(id="goal-description", className="mb-2"),
                        dbc.Button("Add Goal", id="btn-add-goal", color="primary"),
                        html.Div(id="goal-status", className="mt-2"),
                    ])
                ])
            ], lg=4),
        ])
    ])


def create_stats_page():
    """Practice statistics and visualizations"""
    return dbc.Container([
        html.H3("Practice Statistics", className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.DatePickerRange(
                            id="stats-date-range",
                            start_date=(date.today() - timedelta(days=30)),
                            end_date=date.today(),
                            display_format="MMM D, YYYY"
                        ),
                        dbc.Button("Update", id="btn-update-stats", color="primary", className="ms-3"),
                    ])
                ], className="mb-4"),
            ])
        ]),
        
        # Summary cards
        dbc.Row(id="stats-summary-cards", className="mb-4"),
        
        # Charts
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Practice by Category"),
                    dbc.CardBody([dcc.Graph(id="stats-category-chart")])
                ])
            ], md=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Practice Over Time"),
                    dbc.CardBody([dcc.Graph(id="stats-timeline-chart")])
                ])
            ], md=6),
        ])
    ])


# ============================================================================
# MAIN LAYOUT
# ============================================================================

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    create_navbar(),
    html.Div(id="page-content", className="container-fluid"),
])


# ============================================================================
# CALLBACKS
# ============================================================================

@callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    if pathname == "/journal":
        return create_journal_page()
    elif pathname == "/review":
        return create_review_page()
    elif pathname == "/goals":
        return create_goals_page()
    elif pathname == "/stats":
        return create_stats_page()
    else:
        return create_record_page()


# --- Recording callbacks ---

@callback(
    Output("recording-state", "data"),
    Output("btn-start-record", "disabled"),
    Output("btn-stop-record", "disabled"),
    Output("record-status", "children"),
    Output("post-record-form", "style"),
    Output("recording-preview", "children"),
    Input("btn-start-record", "n_clicks"),
    Input("btn-stop-record", "n_clicks"),
    Input("btn-discard-retry", "n_clicks"),
    Input("btn-discard", "n_clicks"),
    State("record-options", "value"),
    State("recording-state", "data"),
    State("camera-select", "value"),
    State("audio-select", "value"),
    prevent_initial_call=True
)
def handle_recording(start_clicks, stop_clicks, retry_clicks, discard_clicks, 
                     options, state, camera_idx, audio_idx):
    triggered = ctx.triggered_id
    
    if triggered == "btn-start-record":
        include_video = "video" in (options or [])
        include_audio = "audio" in (options or [])
        
        # Update recorder with selected devices
        if camera_idx is not None and camera_idx >= 0:
            recorder.camera_index = camera_idx
        if audio_idx is not None and audio_idx >= 0:
            recorder.audio_device = audio_idx
        
        recorder.start(include_video=include_video, include_audio=include_audio)
        
        return (
            {"is_recording": True, "start_time": datetime.now().isoformat(), "result": None},
            True,  # disable start
            False,  # enable stop
            dbc.Alert("🔴 Recording...", color="danger"),
            {"display": "none"},
            None
        )
    
    elif triggered == "btn-stop-record":
        result = recorder.stop()
        
        # Create preview element
        preview = None
        if result and result.get("final_path"):
            final_path = Path(result["final_path"])
            if final_path.exists():
                filename = final_path.name
                file_size = final_path.stat().st_size
                
                if file_size < 1000:
                    preview = dbc.Alert(
                        f"Recording file is too small ({file_size} bytes). Recording may have failed. Check terminal for errors.",
                        color="warning"
                    )
                elif result.get("has_video") or str(final_path).endswith((".mp4", ".avi")):
                    preview = html.Div([
                        html.Video(
                            id="preview-player",
                            src=f"/recordings/{filename}",
                            controls=True,
                            style={"width": "100%", "maxHeight": "300px"},
                            autoPlay=False,
                        ),
                        html.Small(f"File: {filename} ({file_size // 1024} KB)", className="text-muted d-block mt-1"),
                    ])
                else:
                    preview = html.Div([
                        html.Audio(
                            id="preview-player",
                            src=f"/recordings/{filename}",
                            controls=True,
                            style={"width": "100%"},
                            autoPlay=False,
                        ),
                        html.Small(f"File: {filename} ({file_size // 1024} KB)", className="text-muted d-block mt-1"),
                    ])
            else:
                preview = dbc.Alert("Recording file not found. Check terminal for errors.", color="danger")
        else:
            preview = dbc.Alert("Recording failed. Check terminal for errors.", color="danger")
        
        return (
            {"is_recording": False, "start_time": None, "result": result},
            False,  # enable start
            True,  # disable stop
            dbc.Alert(f"Recording complete: {result['duration_seconds']:.1f}s — Review below", color="success") if result else dbc.Alert("Recording failed", color="danger"),
            {"display": "block"},
            preview
        )
    
    elif triggered == "btn-discard-retry":
        # Delete the recording and start fresh
        result = state.get("result", {})
        _delete_recording_files(result)
        
        include_video = "video" in (options or [])
        include_audio = "audio" in (options or [])
        
        if camera_idx is not None and camera_idx >= 0:
            recorder.camera_index = camera_idx
        if audio_idx is not None and audio_idx >= 0:
            recorder.audio_device = audio_idx
        
        recorder.start(include_video=include_video, include_audio=include_audio)
        
        return (
            {"is_recording": True, "start_time": datetime.now().isoformat(), "result": None},
            True,
            False,
            dbc.Alert("🔴 Recording... (previous take discarded)", color="danger"),
            {"display": "none"},
            None
        )
    
    elif triggered == "btn-discard":
        # Delete the recording and reset
        result = state.get("result", {})
        _delete_recording_files(result)
        
        return (
            {"is_recording": False, "start_time": None, "result": None},
            False,
            True,
            dbc.Alert("Recording discarded", color="secondary"),
            {"display": "none"},
            None
        )
    
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update


def _delete_recording_files(result):
    """Helper to delete recording files from a result dict"""
    if not result:
        return
    
    filename = result.get("filename")
    if not filename:
        return
    
    # Handle both old and new file patterns
    for ext in ["_final.mp4", "_video.mp4", "_video.avi", "_audio.wav", "_audio.m4a"]:
        filepath = RECORDINGS_DIR / f"{filename}{ext}"
        if filepath.exists():
            try:
                filepath.unlink()
                print(f"Deleted: {filepath}")
            except Exception as e:
                print(f"Failed to delete {filepath}: {e}")


@callback(
    Output("camera-select", "options"),
    Output("audio-select", "options"),
    Output("camera-select", "value"),
    Output("audio-select", "value"),
    Input("btn-refresh-devices", "n_clicks"),
    State("camera-select", "value"),
    State("audio-select", "value"),
    prevent_initial_call=True
)
def refresh_devices(n, current_camera, current_audio):
    """Rescan for available devices"""
    import cv2
    import sounddevice as sd
    
    # Force rescan cameras by actually trying to open them
    cameras = []
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            backend = cap.getBackendName()
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cameras.append({
                "index": i,
                "name": f"{backend} ({width}x{height})",
            })
            cap.release()
    
    # Force rescan audio devices
    sd._terminate()
    sd._initialize()
    devices = sd.query_devices()
    audio_devs = []
    for i, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            audio_devs.append({
                "index": i,
                "name": d['name'],
            })
    
    camera_options = [{"label": f"Camera {c['index']}: {c['name']}", "value": c['index']} 
                      for c in cameras]
    if not camera_options:
        camera_options = [{"label": "No cameras found", "value": -1}]
    
    audio_options = [{"label": a['name'], "value": a['index']} 
                     for a in audio_devs]
    if not audio_options:
        audio_options = [{"label": "No audio inputs found", "value": -1}]
    
    # Keep current selection if still valid, otherwise pick first
    valid_camera_indices = [c['index'] for c in cameras]
    new_camera = current_camera if current_camera in valid_camera_indices else (camera_options[0]["value"] if camera_options else -1)
    
    valid_audio_indices = [a['index'] for a in audio_devs]
    new_audio = current_audio if current_audio in valid_audio_indices else (audio_options[0]["value"] if audio_options else -1)
    
    return camera_options, audio_options, new_camera, new_audio


@callback(
    Output("timer-interval", "disabled"),
    Input("recording-state", "data")
)
def toggle_timer(state):
    return not state.get("is_recording", False)


@callback(
    Output("record-timer", "children"),
    Input("timer-interval", "n_intervals"),
    State("recording-state", "data")
)
def update_timer(n, state):
    if state.get("is_recording") and state.get("start_time"):
        start = datetime.fromisoformat(state["start_time"])
        elapsed = (datetime.now() - start).total_seconds()
        mins, secs = divmod(int(elapsed), 60)
        return f"{mins:02d}:{secs:02d}"
    return "00:00"


@callback(
    Output("record-status", "children", allow_duplicate=True),
    Output("post-record-form", "style", allow_duplicate=True),
    Output("recording-state", "data", allow_duplicate=True),
    Input("btn-save-session", "n_clicks"),
    State("record-title", "value"),
    State("record-category", "value"),
    State("record-description", "value"),
    State("record-notes", "value"),
    State("record-rating", "value"),
    State("recording-state", "data"),
    prevent_initial_call=True
)
def save_session(n_clicks, title, category, description, notes, rating, state):
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update
    
    result = state.get("result", {})
    duration_mins = int(result.get("duration_seconds", 0) / 60)
    
    session = create_practice_session(
        title=title or "Practice Session",
        category=category,
        duration_minutes=max(1, duration_mins),
        description=description or "",
        notes=notes or "",
        rating=rating,
        recording_filename=result.get("filename"),
        has_video=result.get("has_video", False)
    )
    
    return (
        dbc.Alert(f"✅ Session #{session.id} saved!", color="success"),
        {"display": "none"},
        {"is_recording": False, "start_time": None, "result": None}
    )


@callback(
    Output("today-stats", "children"),
    Input("url", "pathname"),
    Input("btn-save-session", "n_clicks")
)
def update_today_stats(pathname, n):
    today = date.today()
    stats = get_practice_stats(today, today)
    
    return html.Div([
        html.P(f"Sessions: {stats['total_sessions']}", className="mb-1"),
        html.P(f"Total time: {stats['total_minutes']} min", className="mb-1"),
    ])


@callback(
    Output("sidebar-goals", "children"),
    Input("url", "pathname")
)
def update_sidebar_goals(pathname):
    goals = get_active_goals()
    if not goals:
        return html.P("No active goals", className="text-muted")
    
    return html.Ul([
        html.Li(g.title, className="mb-1") for g in goals[:5]
    ], className="mb-0 ps-3")


# --- Journal callbacks ---

@callback(
    Output("journal-sessions-list", "children"),
    Input("btn-refresh-journal", "n_clicks"),
    Input("journal-date-range", "start_date"),
    Input("journal-date-range", "end_date"),
    Input("journal-category-filter", "value")
)
def update_journal_list(n, start_date, end_date, category):
    sessions = get_recent_sessions(limit=50)
    
    if not sessions:
        return dbc.Alert("No practice sessions yet. Start recording!", color="info")
    
    # Filter
    if category and category != "all":
        sessions = [s for s in sessions if s.category == category]
    
    cards = []
    for s in sessions:
        rating_str = "⭐" * (s.rating or 0) if s.rating else ""
        recording_badge = dbc.Badge("🎬 Video", color="info", className="me-1") if s.has_video else ""
        recording_badge2 = dbc.Badge("🎵 Audio", color="secondary", className="me-1") if s.has_recording and not s.has_video else ""
        
        cards.append(
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.H5(s.title or "Untitled", className="d-inline me-2"),
                        dbc.Badge(s.category, color="primary"),
                        recording_badge,
                        recording_badge2,
                    ]),
                    html.Small(f"{s.date} • {s.duration_minutes} min {rating_str}", className="text-muted"),
                    html.P(s.notes, className="mt-2 mb-0") if s.notes else None,
                ])
            ], className="mb-2")
        )
    
    return cards


@callback(
    Output("manual-status", "children"),
    Input("btn-add-manual", "n_clicks"),
    State("manual-title", "value"),
    State("manual-category", "value"),
    State("manual-duration", "value"),
    State("manual-notes", "value"),
    prevent_initial_call=True
)
def add_manual_entry(n, title, category, duration, notes):
    if not all([title, category, duration]):
        return dbc.Alert("Please fill in title, category, and duration", color="warning")
    
    session = create_practice_session(
        title=title,
        category=category,
        duration_minutes=int(duration),
        notes=notes or ""
    )
    
    return dbc.Alert(f"✅ Added: {title}", color="success")


# --- Review callbacks ---

@callback(
    Output("recordings-table-container", "children"),
    Input("url", "pathname"),
    Input("btn-refresh-recordings", "n_clicks"),
    Input("table-refresh-trigger", "data"),
)
def populate_recordings_table(pathname, refresh_clicks, refresh_trigger):
    """Generate the recordings table with inline-editable titles"""
    sessions = get_recent_sessions(limit=100)
    sessions_with_recordings = [s for s in sessions if s.has_recording]
    
    if not sessions_with_recordings:
        return dbc.Alert("No recordings yet. Go to Record tab to create one!", color="info")
    
    # Build table rows
    rows = []
    for s in sessions_with_recordings:
        # Check if file exists
        file_exists = False
        for ext in ["_final.mp4", "_video.mp4", "_video.avi", "_audio.m4a", "_audio.wav"]:
            if (RECORDINGS_DIR / f"{s.recording_filename}{ext}").exists():
                file_exists = True
                break
        
        # Format duration
        duration_str = f"{s.duration_minutes} min" if s.duration_minutes else "—"
        
        # Rating stars
        rating_str = "⭐" * (s.rating or 0) if s.rating else "—"
        
        # Media type badge
        if not file_exists:
            media_badge = dbc.Badge("Missing", color="danger", className="ms-2")
        elif s.has_video:
            media_badge = dbc.Badge("Video", color="info", className="ms-2")
        else:
            media_badge = dbc.Badge("Audio", color="secondary", className="ms-2")
        
        # Editable title input - saves on blur (like Finder)
        title_input = dbc.Input(
            id={"type": "title-input", "index": s.id},
            value=s.title or "Untitled",
            size="sm",
            className="border-0 bg-transparent p-0",
            style={"width": "200px"},
            debounce=True,  # Only fires callback after user stops typing
        )
        
        row = html.Tr([
            html.Td(str(s.date)),
            html.Td([title_input, media_badge]),
            html.Td(s.category or "—"),
            html.Td(duration_str),
            html.Td(rating_str),
            html.Td([
                dbc.Button("▶", id={"type": "btn-play", "index": s.id}, 
                           size="sm", color="primary", className="me-1", title="Play"),
                dbc.Button("🗑", id={"type": "btn-delete", "index": s.id}, 
                           size="sm", color="danger", outline=True, title="Delete"),
            ]),
        ])
        rows.append(row)
    
    table = dbc.Table([
        html.Thead(html.Tr([
            html.Th("Date", style={"width": "100px"}),
            html.Th("Title"),
            html.Th("Category", style={"width": "120px"}),
            html.Th("Duration", style={"width": "80px"}),
            html.Th("Rating", style={"width": "80px"}),
            html.Th("Actions", style={"width": "100px"}),
        ])),
        html.Tbody(rows)
    ], bordered=True, hover=True, responsive=True, size="sm")
    
    return table


# Handle play button clicks
@callback(
    Output("review-session-select", "data"),
    Input({"type": "btn-play", "index": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def handle_play_click(n_clicks):
    if not any(n_clicks):
        return dash.no_update
    
    triggered = ctx.triggered_id
    if triggered and isinstance(triggered, dict):
        return triggered["index"]
    return dash.no_update


# Handle inline title editing - saves on blur/enter
@callback(
    Output({"type": "title-input", "index": MATCH}, "className"),
    Input({"type": "title-input", "index": MATCH}, "value"),
    State({"type": "title-input", "index": MATCH}, "id"),
    prevent_initial_call=True
)
def save_title(new_title, input_id):
    if new_title is None:
        return dash.no_update
    
    session_id = input_id["index"]
    db = get_session()
    session = db.query(PracticeSession).get(session_id)
    if session:
        session.title = new_title.strip() or "Untitled"
        db.commit()
    
    # Return same class (just to have an output)
    return "border-0 bg-transparent p-0"


# Handle delete button - direct delete, no confirmation
@callback(
    Output("table-refresh-trigger", "data"),
    Output("review-session-select", "data", allow_duplicate=True),
    Input({"type": "btn-delete", "index": ALL}, "n_clicks"),
    State("review-session-select", "data"),
    State("table-refresh-trigger", "data"),
    prevent_initial_call=True
)
def handle_delete(delete_clicks, current_session, refresh_count):
    if not any(delete_clicks):
        return dash.no_update, dash.no_update
    
    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict):
        return dash.no_update, dash.no_update
    
    session_id = triggered["index"]
    
    db = get_session()
    session = db.query(PracticeSession).get(session_id)
    if session:
        # Delete recording files
        if session.recording_filename:
            for ext in ["_final.mp4", "_video.mp4", "_video.avi", "_audio.wav", 
                        "_audio.m4a", "_audio.extracted.wav"]:
                filepath = RECORDINGS_DIR / f"{session.recording_filename}{ext}"
                if filepath.exists():
                    try:
                        filepath.unlink()
                    except Exception as e:
                        print(f"Failed to delete {filepath}: {e}")
        
        # Delete database entry (cascades to annotations)
        db.delete(session)
        db.commit()
    
    # Clear selection if we deleted the currently playing session
    new_selection = None if current_session == session_id else current_session
    
    # Increment refresh trigger to force table rebuild
    return (refresh_count or 0) + 1, new_selection


@callback(
    Output("review-playback-area", "children"),
    Output("review-waveform-area", "children"),
    Output("review-controls-area", "children"),
    Output("review-session-details", "children"),
    Output("review-annotations-list", "children"),
    Output("review-audio-data", "data"),
    Output("review-time-interval", "disabled"),
    Input("review-session-select", "data")
)
def load_review_session(session_id):
    empty_return = (
        dbc.Alert("Click ▶ on a recording above to review it", color="info"),
        None, None, None, None, None, True
    )
    
    if not session_id:
        return empty_return
    
    db = get_session()
    session = db.query(PracticeSession).get(session_id)
    
    if not session or not session.recording_filename:
        return (
            dbc.Alert("Recording not found", color="warning"),
            None, None, None, None, None, True
        )
    
    # Find the recording file
    recording_path = None
    for ext in ["_final.mp4", "_video.mp4", "_video.avi", "_audio.m4a", "_audio.wav"]:
        potential_path = RECORDINGS_DIR / f"{session.recording_filename}{ext}"
        if potential_path.exists():
            recording_path = potential_path
            break
    
    if not recording_path:
        return (
            dbc.Alert("Recording file not found on disk", color="warning"),
            None, None, None, None, None, True
        )
    
    # Create media element with ID for JavaScript control
    is_video = session.has_video or str(recording_path).endswith((".mp4", ".avi"))
    is_audio_only = str(recording_path).endswith((".m4a", ".wav"))
    media_id = "review-media-player"
    
    if is_video and not is_audio_only:
        playback_element = html.Video(
            id=media_id,
            src=f"/recordings/{recording_path.name}",
            controls=True,
            preload="metadata",
            style={"width": "100%", "maxHeight": "400px", "backgroundColor": "#000"}
        )
    else:
        playback_element = html.Audio(
            id=media_id,
            src=f"/recordings/{recording_path.name}",
            controls=True,
            preload="metadata",
            style={"width": "100%"}
        )
    
    playback_area = dbc.Card([
        dbc.CardHeader(f"{'📹' if is_video else '🎵'} {session.title}"),
        dbc.CardBody([playback_element])
    ])
    
    # Generate waveform
    waveform_area = None
    audio_data_store = None
    
    audio_data, sr = load_audio(str(recording_path))
    if audio_data is not None:
        times, wf_min, wf_max = generate_waveform_data(audio_data, sr, num_points=800)
        duration = len(audio_data) / sr if len(audio_data.shape) == 1 else len(audio_data) / sr
        
        # Create waveform figure
        fig = go.Figure()
        
        # Add waveform as filled area
        fig.add_trace(go.Scatter(
            x=list(times) + list(times)[::-1],
            y=list(wf_max) + list(wf_min)[::-1],
            fill='toself',
            fillcolor='rgba(52, 152, 219, 0.5)',
            line=dict(color='rgba(52, 152, 219, 0.8)', width=1),
            hoverinfo='x',
            name='Waveform'
        ))
        
        # Add playhead line (will be updated by JS)
        fig.add_vline(x=0, line_width=2, line_color="red", annotation_text="", name="playhead")
        
        fig.update_layout(
            height=120,
            margin=dict(l=40, r=20, t=10, b=30),
            xaxis=dict(
                title="Time (s)",
                range=[0, duration],
                showgrid=True,
                gridcolor='rgba(128,128,128,0.2)'
            ),
            yaxis=dict(
                title="",
                showticklabels=False,
                range=[-1, 1],
                fixedrange=True
            ),
            showlegend=False,
            dragmode='select',  # Enable range selection
            selectdirection='h',  # Horizontal selection only
        )
        
        waveform_area = dbc.Card([
            dbc.CardHeader([
                "Waveform ",
                html.Small("(click to seek • drag to select section)", className="text-muted")
            ]),
            dbc.CardBody([
                dcc.Graph(
                    id="waveform-graph",
                    figure=fig,
                    config={
                        'displayModeBar': True,
                        'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d'],
                        'displaylogo': False
                    },
                    style={"height": "120px"}
                ),
                html.Div([
                    html.Span("Current: ", className="text-muted"),
                    html.Span(id="current-time-display", children="0:00.0"),
                    html.Span(" / ", className="text-muted"),
                    html.Span(f"{int(duration//60)}:{duration%60:04.1f}"),
                ], className="mt-2 font-monospace")
            ])
        ])
        
        audio_data_store = {"duration": duration, "sample_rate": sr}
    
    # Playback controls
    controls_area = dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Playback Speed"),
                    dcc.Slider(
                        id="playback-speed-slider",
                        min=0.25, max=2.0, step=0.25, value=1.0,
                        marks={0.25: "0.25x", 0.5: "0.5x", 0.75: "0.75x", 1.0: "1x", 1.5: "1.5x", 2.0: "2x"},
                        tooltip={"placement": "bottom", "always_visible": False}
                    ),
                ], md=6),
                dbc.Col([
                    dbc.Label("Navigation"),
                    html.Div([
                        dbc.Button("⏮ -5s", id="btn-back-5", size="sm", color="secondary", className="me-1"),
                        dbc.Button("+5s ⏭", id="btn-forward-5", size="sm", color="secondary"),
                    ]),
                ], md=6),
            ], className="mb-3"),
            
            # Loop section controls - shown when range is selected
            html.Hr(),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Selection Controls"),
                    html.Div(id="loop-range-display", className="small text-muted mb-2"),
                    dbc.ButtonGroup([
                        dbc.Button("⏮", id="btn-loop-start", size="sm", color="primary", 
                                   title="Back to start of selection"),
                        dbc.Button("▶", id="btn-loop-play", size="sm", color="success",
                                   title="Play"),
                        dbc.Button("⏸", id="btn-loop-pause", size="sm", color="warning",
                                   title="Pause"),
                    ], className="me-3"),
                    dbc.Checklist(
                        id="loop-enabled",
                        options=[{"label": " Loop", "value": "loop"}],
                        value=[],
                        inline=True,
                        className="d-inline-block align-middle"
                    ),
                ], md=12),
            ]),
        ])
    ])
    
    # Session details
    details = dbc.Card([
        dbc.CardHeader("Session Info"),
        dbc.CardBody([
            html.P([html.Strong("Category: "), session.category]),
            html.P([html.Strong("Duration: "), f"{session.duration_minutes} min"]),
            html.P([html.Strong("Rating: "), "⭐" * (session.rating or 0) or "Not rated"]),
            html.P([html.Strong("Notes: "), session.notes or "None"]),
        ])
    ])
    
    # Annotations
    annotations = db.query(Annotation).filter(Annotation.session_id == session_id).order_by(Annotation.timestamp_seconds).all()
    
    if annotations:
        ann_items = [
            html.Li([
                dbc.Button(
                    f"[{a.timestamp_seconds:.1f}s]",
                    id={"type": "annotation-seek", "index": a.id},
                    color="link",
                    size="sm",
                    className="p-0 me-2 font-monospace"
                ),
                html.Span({"issue": "🔴", "good": "🟢", "question": "❓", "note": "📝"}.get(a.annotation_type, "📝")),
                html.Span(f" {a.text}")
            ], className="mb-2")
            for a in annotations
        ]
        ann_list = dbc.Card([
            dbc.CardHeader(f"Annotations ({len(annotations)})"),
            dbc.CardBody(html.Ul(ann_items, className="ps-3 mb-0"))
        ])
    else:
        ann_list = dbc.Card([
            dbc.CardHeader("Annotations"),
            dbc.CardBody("No annotations yet. Add one while reviewing!")
        ])
    
    return playback_area, waveform_area, controls_area, details, ann_list, audio_data_store, False


@callback(
    Output("annotation-status", "children"),
    Input("btn-add-annotation", "n_clicks"),
    State("review-session-select", "data"),
    State("annotation-timestamp", "value"),
    State("annotation-type", "value"),
    State("annotation-text", "value"),
    prevent_initial_call=True
)
def save_annotation(n, session_id, timestamp, ann_type, text):
    if not all([session_id, timestamp is not None, text]):
        return dbc.Alert("Please fill in timestamp and note", color="warning")
    
    add_annotation(session_id, float(timestamp), text, ann_type)
    return dbc.Alert("✅ Annotation added!", color="success")


# --- Goals callbacks ---

@callback(
    Output("goals-active-list", "children"),
    Input("url", "pathname"),
    Input("btn-add-goal", "n_clicks")
)
def update_goals_list(pathname, n):
    goals = get_active_goals()
    
    if not goals:
        return dbc.Alert("No active goals. Add one to get started!", color="info")
    
    cards = []
    for g in goals:
        cards.append(
            dbc.Card([
                dbc.CardBody([
                    html.H5(g.title),
                    dbc.Badge(g.category, color="primary", className="me-2"),
                    dbc.Badge(g.goal_type, color="secondary"),
                    html.P(g.description, className="mt-2 mb-0 text-muted") if g.description else None,
                    html.Small(f"Target: {g.target_minutes} min" if g.target_minutes else ""),
                ])
            ], className="mb-2")
        )
    
    return cards


@callback(
    Output("goal-status", "children"),
    Input("btn-add-goal", "n_clicks"),
    State("goal-title", "value"),
    State("goal-category", "value"),
    State("goal-type", "value"),
    State("goal-target-minutes", "value"),
    State("goal-description", "value"),
    prevent_initial_call=True
)
def add_goal(n, title, category, goal_type, target_mins, description):
    if not title:
        return dbc.Alert("Please enter a goal title", color="warning")
    
    db = get_session()
    goal = Goal(
        title=title,
        category=category,
        goal_type=goal_type,
        target_minutes=int(target_mins) if target_mins else None,
        description=description,
        start_date=date.today()
    )
    db.add(goal)
    db.commit()
    
    return dbc.Alert(f"✅ Goal added: {title}", color="success")


# --- Stats callbacks ---

@callback(
    Output("stats-summary-cards", "children"),
    Output("stats-category-chart", "figure"),
    Output("stats-timeline-chart", "figure"),
    Input("btn-update-stats", "n_clicks"),
    State("stats-date-range", "start_date"),
    State("stats-date-range", "end_date")
)
def update_stats(n, start_date, end_date):
    start = datetime.fromisoformat(start_date).date() if start_date else date.today() - timedelta(days=30)
    end = datetime.fromisoformat(end_date).date() if end_date else date.today()
    
    stats = get_practice_stats(start, end)
    sessions = get_sessions_by_date_range(start, end)
    
    # Summary cards
    summary = dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(stats["total_sessions"], className="text-primary"),
                html.P("Sessions", className="mb-0")
            ])
        ]), md=3),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(f"{stats['total_minutes']} min", className="text-success"),
                html.P("Total Practice", className="mb-0")
            ])
        ]), md=3),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(f"{stats['total_minutes'] // max(1, (end - start).days)} min", className="text-info"),
                html.P("Daily Average", className="mb-0")
            ])
        ]), md=3),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(f"{stats['avg_rating']:.1f}" if stats['avg_rating'] else "N/A", className="text-warning"),
                html.P("Avg Rating", className="mb-0")
            ])
        ]), md=3),
    ])
    
    # Category pie chart
    if stats["by_category"]:
        cat_fig = px.pie(
            names=list(stats["by_category"].keys()),
            values=list(stats["by_category"].values()),
            title=""
        )
    else:
        cat_fig = go.Figure()
        cat_fig.add_annotation(text="No data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
    
    # Timeline chart
    if sessions:
        daily_data = {}
        for s in sessions:
            d = s.date.isoformat()
            daily_data[d] = daily_data.get(d, 0) + (s.duration_minutes or 0)
        
        timeline_fig = px.bar(
            x=list(daily_data.keys()),
            y=list(daily_data.values()),
            labels={"x": "Date", "y": "Minutes"},
            title=""
        )
    else:
        timeline_fig = go.Figure()
        timeline_fig.add_annotation(text="No data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
    
    return summary, cat_fig, timeline_fig


# Serve static files (recordings)
@app.server.route('/recordings/<path:filename>')
def serve_recording(filename):
    """Serve recording files with proper MIME types for browser playback"""
    filepath = RECORDINGS_DIR / filename
    if not filepath.exists():
        print(f"Recording file not found: {filepath}")
        return "File not found", 404
    
    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(str(filepath))
    if mime_type is None:
        if filename.endswith('.mp4'):
            mime_type = 'video/mp4'
        elif filename.endswith('.m4a'):
            mime_type = 'audio/mp4'
        elif filename.endswith('.wav'):
            mime_type = 'audio/wav'
        else:
            mime_type = 'application/octet-stream'
    
    # Send file with cache disabled for fresh recordings
    response = send_from_directory(
        RECORDINGS_DIR, 
        filename,
        mimetype=mime_type
    )
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# ============================================================================
# CLIENTSIDE CALLBACKS FOR MEDIA CONTROL
# ============================================================================

# Playback speed control
app.clientside_callback(
    """
    function(speed) {
        const media = document.getElementById('review-media-player');
        if (media) {
            media.playbackRate = speed;
        }
        return '';
    }
    """,
    Output("playback-speed-output", "children"),
    Input("playback-speed-slider", "value"),
    prevent_initial_call=True
)

# Click on waveform to seek
app.clientside_callback(
    """
    function(clickData) {
        if (clickData && clickData.points && clickData.points.length > 0) {
            const time = clickData.points[0].x;
            const media = document.getElementById('review-media-player');
            if (media) {
                media.currentTime = time;
            }
        }
        return '';
    }
    """,
    Output("waveform-click-output", "children"),
    Input("waveform-graph", "clickData"),
    prevent_initial_call=True
)

# Handle range selection on waveform for loop
app.clientside_callback(
    """
    function(selectedData, loopEnabled) {
        if (selectedData && selectedData.range && selectedData.range.x) {
            const start = selectedData.range.x[0];
            const end = selectedData.range.x[1];
            return {start: start, end: end};
        }
        return {start: null, end: null};
    }
    """,
    Output("review-loop-range", "data"),
    Input("waveform-graph", "selectedData"),
    State("loop-enabled", "value"),
    prevent_initial_call=True
)

# Display loop range
@callback(
    Output("loop-range-display", "children"),
    Input("review-loop-range", "data")
)
def display_loop_range(loop_range):
    if loop_range and loop_range.get("start") is not None:
        start = loop_range["start"]
        end = loop_range["end"]
        duration = end - start
        return f"Selected: {start:.1f}s → {end:.1f}s ({duration:.1f}s)"
    return "Drag on waveform to select a section"

# Loop playback logic - updated to handle loop vs non-loop
app.clientside_callback(
    """
    function(loopEnabled, loopRange) {
        const media = document.getElementById('review-media-player');
        if (!media) return '';
        
        // Remove existing listener if any
        if (window.loopHandler) {
            media.removeEventListener('timeupdate', window.loopHandler);
            window.loopHandler = null;
        }
        
        if (loopRange && loopRange.start !== null && loopRange.end !== null) {
            const isLooping = loopEnabled && loopEnabled.includes('loop');
            
            window.loopHandler = function() {
                if (media.currentTime >= loopRange.end) {
                    if (isLooping) {
                        // Loop back to start
                        media.currentTime = loopRange.start;
                    } else {
                        // Just pause at the end
                        media.pause();
                        media.currentTime = loopRange.start;
                    }
                }
            };
            media.addEventListener('timeupdate', window.loopHandler);
        }
        
        return '';
    }
    """,
    Output("loop-handler-output", "children"),
    Input("loop-enabled", "value"),
    Input("review-loop-range", "data"),
    prevent_initial_call=True
)

# Selection control buttons: start, play, pause
app.clientside_callback(
    """
    function(nStart, nPlay, nPause, loopRange) {
        const media = document.getElementById('review-media-player');
        if (!media) return '';
        
        const triggered = window.dash_clientside.callback_context.triggered;
        if (!triggered || triggered.length === 0) return '';
        
        const triggerId = triggered[0].prop_id.split('.')[0];
        
        if (triggerId === 'btn-loop-start') {
            // Jump to start of selection (or beginning if no selection)
            if (loopRange && loopRange.start !== null) {
                media.currentTime = loopRange.start;
            } else {
                media.currentTime = 0;
            }
        } else if (triggerId === 'btn-loop-play') {
            // If we have a selection and we're outside it, jump to start first
            if (loopRange && loopRange.start !== null) {
                if (media.currentTime < loopRange.start || media.currentTime >= loopRange.end) {
                    media.currentTime = loopRange.start;
                }
            }
            media.play();
        } else if (triggerId === 'btn-loop-pause') {
            media.pause();
        }
        
        return '';
    }
    """,
    Output("loop-controls-output", "children"),
    Input("btn-loop-start", "n_clicks"),
    Input("btn-loop-play", "n_clicks"),
    Input("btn-loop-pause", "n_clicks"),
    State("review-loop-range", "data"),
    prevent_initial_call=True
)

# Skip back/forward buttons
app.clientside_callback(
    """
    function(nBack, nForward) {
        const media = document.getElementById('review-media-player');
        if (!media) return '';
        
        const triggered = window.dash_clientside.callback_context.triggered;
        if (triggered && triggered.length > 0) {
            const triggerId = triggered[0].prop_id.split('.')[0];
            if (triggerId === 'btn-back-5') {
                media.currentTime = Math.max(0, media.currentTime - 5);
            } else if (triggerId === 'btn-forward-5') {
                media.currentTime = Math.min(media.duration, media.currentTime + 5);
            }
        }
        return '';
    }
    """,
    Output("skip-controls-output", "children"),
    Input("btn-back-5", "n_clicks"),
    Input("btn-forward-5", "n_clicks"),
    prevent_initial_call=True
)

# Update current time display
app.clientside_callback(
    """
    function(n) {
        const media = document.getElementById('review-media-player');
        if (!media) return '0:00.0';
        
        const time = media.currentTime;
        const mins = Math.floor(time / 60);
        const secs = (time % 60).toFixed(1);
        return mins + ':' + secs.padStart(4, '0');
    }
    """,
    Output("current-time-display", "children"),
    Input("review-time-interval", "n_intervals"),
)

# Get current time for annotation
app.clientside_callback(
    """
    function(n) {
        const media = document.getElementById('review-media-player');
        if (media) {
            return media.currentTime.toFixed(1);
        }
        return 0;
    }
    """,
    Output("annotation-timestamp", "value"),
    Input("btn-get-current-time", "n_clicks"),
    prevent_initial_call=True
)

# Click annotation timestamp to seek
app.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return '';
        
        const triggered = window.dash_clientside.callback_context.triggered;
        if (triggered && triggered.length > 0) {
            // Extract the annotation ID and find the timestamp from the button text
            const button = document.activeElement;
            if (button && button.textContent) {
                const match = button.textContent.match(/\\[([\\d.]+)s\\]/);
                if (match) {
                    const time = parseFloat(match[1]);
                    const media = document.getElementById('review-media-player');
                    if (media) {
                        media.currentTime = time;
                        media.play();
                    }
                }
            }
        }
        return '';
    }
    """,
    Output("annotation-seek-output", "children"),
    Input({"type": "annotation-seek", "index": ALL}, "n_clicks"),
    prevent_initial_call=True
)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point for the application"""
    print("🎸 Guitar Practice Studio")
    print(f"   Audio available: {AUDIO_AVAILABLE}")
    print(f"   Video available: {VIDEO_AVAILABLE}")
    print(f"   Data directory: {RECORDINGS_DIR.parent}")
    print(f"   Starting server at http://{HOST}:{PORT}")
    
    app.run(debug=DEBUG, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
