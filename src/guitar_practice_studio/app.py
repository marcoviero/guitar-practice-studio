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

from .config import RECORDINGS_DIR, DEBUG, HOST, PORT
from .database import (
    init_db, get_session, PracticeSession, Goal, Annotation, Exercise, WeeklyPlanEntry, RepertoirePiece,
    create_practice_session, get_recent_sessions, add_annotation,
    get_active_goals, get_practice_stats, get_sessions_by_date_range,
    init_default_exercises, get_or_create_current_week_plan, get_exercises_by_category,
    get_week_plan_entries, set_plan_entry, toggle_entry_completed, get_today_exercises,
    get_category_targets, get_week_category_totals,
    reorder_today_entry, remove_today_entry,
    get_all_repertoire, get_active_repertoire, add_repertoire_piece, update_repertoire_piece, delete_repertoire_piece,
    get_daily_summary, get_week_summary, save_daily_notes,
    add_manual_practice, update_manual_practice, delete_manual_practice,
    PRACTICE_CATEGORIES, PIECE_TYPES, PIECE_STATUSES, RECORDING_TYPES
)
from .recorder import Recorder, PlaybackController, AUDIO_AVAILABLE, VIDEO_AVAILABLE
from .audio_utils import load_audio, generate_waveform_data, get_audio_duration

# Initialize
init_db()
init_default_exercises()  # Create default exercises if needed
recorder = Recorder()
playback = PlaybackController()

# Create Dash app with Bootstrap theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],  # Dark mode
    suppress_callback_exceptions=True
)
app.title = "Guitar Practice Studio"

# Custom CSS for dark mode dropdowns
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* Dark mode dropdown fixes */
            .Select-control, .Select-menu-outer {
                background-color: #303030 !important;
                color: #fff !important;
            }
            .Select-value-label, .Select-input input, .Select-placeholder {
                color: #fff !important;
            }
            .Select-option {
                background-color: #303030 !important;
                color: #fff !important;
            }
            .Select-option:hover, .Select-option.is-focused {
                background-color: #444 !important;
            }
            .Select-option.is-selected {
                background-color: #375a7f !important;
            }
            /* Dash dropdown specific */
            .dash-dropdown .Select-control {
                background-color: #303030 !important;
                border-color: #444 !important;
            }
            .dash-dropdown .Select-menu {
                background-color: #303030 !important;
            }
            .VirtualizedSelectOption {
                background-color: #303030 !important;
                color: #fff !important;
            }
            .VirtualizedSelectFocusedOption {
                background-color: #444 !important;
            }
            /* Input field fixes for dark mode */
            input.form-control, textarea.form-control {
                background-color: #303030 !important;
                color: #fff !important;
                border-color: #444 !important;
            }
            input.form-control::placeholder, textarea.form-control::placeholder {
                color: #888 !important;
            }
            input.form-control:focus, textarea.form-control:focus {
                background-color: #383838 !important;
                color: #fff !important;
                border-color: #375a7f !important;
            }
        </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/tone/14.8.49/Tone.js"></script>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# ============================================================================
# LAYOUT COMPONENTS
# ============================================================================

def create_navbar():
    return dbc.Navbar(
        dbc.Container([
            dbc.NavbarBrand("🎸 Guitar Practice Studio", className="ms-2 fs-4"),
            dbc.Nav([
                dbc.NavItem(dbc.NavLink("Planner", href="/planner", active="exact")),
                dbc.NavItem(dbc.NavLink("Practice", href="/", active="exact")),
                dbc.NavItem(dbc.NavLink("Repertoire", href="/repertoire", active="exact")),
                dbc.NavItem(dbc.NavLink("Journal", href="/journal", active="exact")),
                dbc.NavItem(dbc.NavLink("Review", href="/review", active="exact")),
                dbc.NavItem(dbc.NavLink("Stats", href="/stats", active="exact")),
            ], navbar=True),
        ]),
        color="primary",
        dark=True,
        className="mb-4"
    )


# ============================================================================
# PLANNER PAGE
# ============================================================================

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def _build_today_card(plan_id: int):
    """Build the Today's Practice card - extracted for dynamic updates"""
    today_exercises = get_today_exercises(plan_id)
    today_name = DAY_NAMES[date.today().weekday()]
    total_today = sum(ex["duration"] for ex in today_exercises)
    
    if today_exercises:
        today_items = []
        for i, ex in enumerate(today_exercises):
            controls = html.Div([
                dbc.Button("↑", id={"type": "today-move-up", "entry": ex["entry_id"]},
                    size="sm", color="secondary", outline=True, className="me-1 py-0 px-1",
                    disabled=(i == 0), style={"fontSize": "0.7rem", "lineHeight": "1"}),
                dbc.Button("↓", id={"type": "today-move-down", "entry": ex["entry_id"]},
                    size="sm", color="secondary", outline=True, className="me-2 py-0 px-1",
                    disabled=(i == len(today_exercises) - 1), style={"fontSize": "0.7rem", "lineHeight": "1"}),
            ], className="d-inline-flex me-2")
            
            today_items.append(
                dbc.ListGroupItem([
                    controls,
                    dbc.Checkbox(id={"type": "today-complete", "entry": ex["entry_id"]},
                        value=ex["completed"], className="me-2"),
                    html.Span(ex["name"], 
                        className="text-decoration-line-through flex-grow-1" if ex["completed"] else "flex-grow-1"),
                    dbc.Badge(f"{ex['duration']} min", color="secondary", className="ms-2"),
                    dbc.Badge(ex["category"], color="info", className="ms-1"),
                    dbc.Button("✕", id={"type": "today-remove", "entry": ex["entry_id"], "exercise": ex["exercise_id"]},
                        size="sm", color="danger", outline=True, className="ms-2 py-0 px-1",
                        style={"fontSize": "0.7rem", "lineHeight": "1"}),
                ], className="d-flex align-items-center")
            )
        return dbc.Card([
            dbc.CardHeader([
                html.H5(f"Today's Practice ({today_name})", className="mb-0 d-inline"),
                dbc.Badge(f"{total_today} min total", color="primary", className="ms-2")
            ]),
            dbc.CardBody(dbc.ListGroup(today_items, flush=True))
        ], className="mb-4", color="dark", outline=True)
    else:
        return dbc.Card([
            dbc.CardHeader(html.H5(f"Today's Practice ({today_name})", className="mb-0")),
            dbc.CardBody(html.P("No exercises scheduled for today. Use the grid below to plan your week!",
                               className="text-muted mb-0"))
        ], className="mb-4", color="dark", outline=True)


def _build_category_grids(plan_id: int):
    """Build the category grid cards"""
    exercises_by_cat = get_exercises_by_category()
    entries = get_week_plan_entries(plan_id)
    category_targets = get_category_targets()
    
    scheduled = {(e.exercise_id, e.day_of_week) for e in entries}
    daily_totals = {}
    db = get_session()
    for entry in entries:
        exercise = db.query(Exercise).get(entry.exercise_id)
        if exercise:
            cat = exercise.category
            day = entry.day_of_week
            duration = entry.duration_minutes or exercise.default_duration_minutes
            if cat not in daily_totals:
                daily_totals[cat] = {}
            daily_totals[cat][day] = daily_totals[cat].get(day, 0) + duration
    db.close()
    
    category_cards = []
    for category in PRACTICE_CATEGORIES:
        exercises = exercises_by_cat.get(category, [])
        if not exercises:
            continue
        
        target_mins = category_targets.get(category, 15)
        cat_daily = daily_totals.get(category, {})
        
        header_content = html.Div([
            html.H5(category, className="mb-0 d-inline"),
            dbc.Badge(f"Target: {target_mins} min/day", color="secondary", className="ms-2"),
        ])
        
        day_headers = [html.Th("Exercise", style={"minWidth": "150px"})]
        for day_idx, day_name in enumerate(DAY_NAMES):
            day_total = cat_daily.get(day_idx, 0)
            day_met = day_total >= target_mins
            header_style = {"width": "55px", "backgroundColor": "rgba(40, 167, 69, 0.35)" if day_met else "transparent",
                "textAlign": "center", "verticalAlign": "middle"}
            header_text = html.Div([
                html.Div(day_name[:3], style={"fontWeight": "bold"}),
                html.Small(f"{day_total}m", className="text-success" if day_met else "text-muted", style={"fontSize": "0.75em"})
            ])
            day_headers.append(html.Th(header_text, style=header_style))
        header = html.Thead(html.Tr(day_headers))
        
        rows = []
        for ex in exercises:
            cells = [html.Td([ex.name, html.Small(f" ({ex.default_duration_minutes}m)", className="text-muted")], className="text-nowrap")]
            for day_idx in range(7):
                is_checked = (ex.id, day_idx) in scheduled
                day_total = cat_daily.get(day_idx, 0)
                day_met = day_total >= target_mins
                checkbox = dbc.Checkbox(id={"type": "plan-checkbox", "exercise": ex.id, "day": day_idx}, value=is_checked, className="m-0")
                cell_style = {"textAlign": "center", "backgroundColor": "rgba(40, 167, 69, 0.15)" if day_met else "transparent"}
                cells.append(html.Td(checkbox, style=cell_style))
            rows.append(html.Tr(cells))
        
        body = html.Tbody(rows)
        table = dbc.Table([header, body], bordered=True, hover=True, size="sm", className="mb-0")
        card = dbc.Card([dbc.CardHeader(header_content), dbc.CardBody(table, className="p-2")], className="mb-3")
        category_cards.append(card)
    
    return category_cards


def create_planner_page():
    """Weekly planner page with exercise grid by category"""
    plan_id, week_start = get_or_create_current_week_plan()
    week_end = week_start + timedelta(days=6)
    week_nav = dbc.Row([
        dbc.Col([dbc.Button("← Prev Week", id="btn-prev-week", color="secondary", size="sm")], width="auto"),
        dbc.Col([html.H4(f"Week of {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}", className="text-center mb-0")]),
        dbc.Col([dbc.Button("Next Week →", id="btn-next-week", color="secondary", size="sm")], width="auto"),
    ], className="mb-4 align-items-center")
    
    return dbc.Container([
        html.H2("Weekly Planner", className="mb-3"),
        dcc.Store(id="current-plan-id", data=plan_id),
        html.Div(_build_today_card(plan_id), id="today-card-container"),
        week_nav,
        html.Div(_build_category_grids(plan_id), id="planner-grids"),
    ], fluid=True, className="py-3")


# ============================================================================
# REPERTOIRE PAGE
# ============================================================================

def create_repertoire_page():
    """Repertoire management page for songs, etudes, and suites"""
    pieces = get_all_repertoire()
    by_status = {}
    for piece in pieces:
        status = piece.status or "Learning"
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(piece)
    
    status_tables = []
    for status in ["Learning", "Review", "Mastered", "Want to Learn"]:
        status_pieces = by_status.get(status, [])
        if not status_pieces and status not in ["Learning", "Want to Learn"]:
            continue
        
        rows = []
        for piece in status_pieces:
            difficulty_stars = "★" * (piece.difficulty or 0) + "☆" * (5 - (piece.difficulty or 0)) if piece.difficulty else "—"
            row = html.Tr([
                html.Td(piece.title),
                html.Td(piece.artist or "—"),
                html.Td(dbc.Badge(piece.piece_type or "Song", color="info")),
                html.Td(difficulty_stars, style={"color": "#ffc107"}),
                html.Td(piece.genre or "—"),
                html.Td([
                    dbc.Button("Edit", id={"type": "edit-piece", "id": piece.id}, size="sm", color="secondary", className="me-1"),
                    dbc.Button("✓", id={"type": "advance-piece", "id": piece.id}, size="sm", color="success", className="me-1", title="Advance to next status"),
                    dbc.Button("🗑", id={"type": "delete-piece", "id": piece.id}, size="sm", color="danger", outline=True),
                ])
            ])
            rows.append(row)
        
        table = dbc.Table([
            html.Thead(html.Tr([html.Th("Title"), html.Th("Artist/Composer"), html.Th("Type"), html.Th("Difficulty"), html.Th("Genre"), html.Th("Actions", style={"width": "150px"})])),
            html.Tbody(rows) if rows else html.Tbody([html.Tr([html.Td("No pieces in this category", colSpan=6, className="text-muted text-center")])])
        ], bordered=True, hover=True, size="sm")
        
        status_colors = {"Learning": "warning", "Review": "info", "Mastered": "success", "Want to Learn": "secondary"}
        card = dbc.Card([
            dbc.CardHeader([html.H5(status, className="mb-0 d-inline"), dbc.Badge(str(len(status_pieces)), color=status_colors.get(status, "secondary"), className="ms-2")]),
            dbc.CardBody(table, className="p-2")
        ], className="mb-3")
        status_tables.append(card)
    
    add_form = dbc.Card([
        dbc.CardHeader(html.H5("Add New Piece", className="mb-0")),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([dbc.Label("Title *"), dbc.Input(id="new-piece-title", placeholder="Song/Etude title")], md=4),
                dbc.Col([dbc.Label("Artist/Composer"), dbc.Input(id="new-piece-artist", placeholder="Artist or composer")], md=4),
                dbc.Col([dbc.Label("Type"), dcc.Dropdown(id="new-piece-type", options=[{"label": t, "value": t} for t in PIECE_TYPES], value="Song", clearable=False)], md=4),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col([dbc.Label("Genre"), dbc.Input(id="new-piece-genre", placeholder="e.g., Rock, Classical, Blues")], md=3),
                dbc.Col([dbc.Label("Difficulty (1-5)"), dcc.Slider(id="new-piece-difficulty", min=1, max=5, step=1, value=3, marks={i: str(i) for i in range(1, 6)})], md=3),
                dbc.Col([dbc.Label("Status"), dcc.Dropdown(id="new-piece-status", options=[{"label": s, "value": s} for s in PIECE_STATUSES if s != "Archived"], value="Learning", clearable=False)], md=3),
                dbc.Col([dbc.Label("Link (optional)"), dbc.Input(id="new-piece-link", placeholder="YouTube, tab URL, etc.")], md=3),
            ], className="mb-3"),
            dbc.Row([dbc.Col([dbc.Label("Notes"), dbc.Textarea(id="new-piece-notes", placeholder="Any notes about this piece...", rows=2)])], className="mb-3"),
            dbc.Button("Add to Repertoire", id="btn-add-piece", color="primary")
        ])
    ], className="mb-4")
    
    return dbc.Container([
        html.H2("Repertoire", className="mb-3"),
        html.P("Manage your songs, etudes, and suites.", className="text-muted mb-4"),
        add_form,
        html.Div(id="repertoire-status", className="mb-3"),
        html.Div(status_tables, id="repertoire-tables"),
    ], fluid=True, className="py-3")


def create_record_page():
    """Recording page with today's practice checklist and optional timer"""
    available_cameras = recorder.get_available_cameras()
    available_audio = recorder.get_available_audio_devices()
    
    camera_options = [{"label": f"Camera {c['index']}: {c.get('name', 'Unknown')}", "value": c['index']} for c in available_cameras]
    if not camera_options:
        camera_options = [{"label": "No cameras found", "value": -1}]
    
    audio_options = [{"label": f"{a['name']}", "value": a['index']} for a in available_audio]
    if not audio_options:
        audio_options = [{"label": "No audio inputs found", "value": -1}]
    
    plan_id, _ = get_or_create_current_week_plan()
    today_exercises = get_today_exercises(plan_id)
    
    if today_exercises:
        checklist_items = []
        for ex in today_exercises:
            checklist_items.append(
                dbc.ListGroupItem([
                    dbc.Checkbox(id={"type": "practice-complete", "entry": ex["entry_id"]}, value=ex["completed"], className="me-2"),
                    html.Span(ex["name"], className="text-decoration-line-through" if ex["completed"] else "", style={"flex": "1"}),
                    dbc.Badge(f"{ex['duration']}m", color="secondary", className="ms-auto"),
                ], className="d-flex align-items-center py-2")
            )
        total_mins = sum(ex["duration"] for ex in today_exercises)
        completed_mins = sum(ex["duration"] for ex in today_exercises if ex["completed"])
        today_checklist = html.Div([
            dbc.Progress(value=(completed_mins / total_mins * 100) if total_mins > 0 else 0, label=f"{completed_mins}/{total_mins} min", className="mb-3", color="success" if completed_mins >= total_mins else "primary"),
            dbc.ListGroup(checklist_items, flush=True)
        ])
    else:
        today_checklist = html.P("No exercises scheduled. Visit the Planner to set up your practice routine!", className="text-muted")
    
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Session Details"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([dbc.Label("Title"), dbc.Input(id="record-title", placeholder="What are you working on?")], md=4),
                            dbc.Col([dbc.Label("Category"), dcc.Dropdown(id="record-category", options=[{"label": c, "value": c} for c in PRACTICE_CATEGORIES], value=PRACTICE_CATEGORIES[0])], md=4),
                            dbc.Col([dbc.Label("Recording Type"), dcc.Dropdown(id="record-type", options=[{"label": t, "value": t} for t in RECORDING_TYPES], value=RECORDING_TYPES[0], clearable=False)], md=4),
                        ], className="mb-3"),
                    ])
                ], className="mb-4"),

                dbc.Card([
                    dbc.CardHeader("Recording"),
                    dbc.CardBody([
                        dbc.CardHeader(dbc.Button("▼ Recording Devices", id="collapse-devices-btn", color="link", className="p-0 text-decoration-none")),
                        dbc.Collapse(
                            dbc.CardBody([
                                dbc.Row([
                                    dbc.Col([dbc.Label("Camera"), dcc.Dropdown(id="camera-select", options=camera_options, value=camera_options[0]["value"] if camera_options else None, clearable=False)], md=6),
                                    dbc.Col([dbc.Label("Audio Input"), dcc.Dropdown(id="audio-select", options=audio_options, value=audio_options[0]["value"] if audio_options else None, clearable=False)], md=6),
                                ]),
                                dbc.Button("🔄 Refresh Devices", id="btn-refresh-devices", color="link", size="sm", className="mt-2"),
                            ]),
                            id="collapse-devices", is_open=True
                        ),
                        dbc.Row([
                            dbc.Col([dbc.Checklist(id="record-options", options=[{"label": " Include Video", "value": "video", "disabled": not VIDEO_AVAILABLE}, {"label": " Include Audio", "value": "audio", "disabled": not AUDIO_AVAILABLE}], value=["audio"] + (["video"] if VIDEO_AVAILABLE else []), inline=True)], md=8),
                            dbc.Col([html.Div(id="record-timer", className="fs-3 text-center font-monospace")], md=4),
                        ], className="mb-3"),
                        dcc.Loading(id="loading-record", type="default", children=[
                            dbc.ButtonGroup([
                                dbc.Button("⏺ Start Recording", id="btn-start-record", color="danger", size="lg"),
                                dbc.Button("⏹ Stop & Save", id="btn-stop-record", color="primary", size="lg", disabled=True),
                                dbc.Button("🗑 Stop & Discard", id="btn-stop-discard", color="secondary", size="lg", disabled=True),
                            ], className="w-100"),
                            html.Div(id="record-status", className="mt-3 text-center"),
                        ]),
                    ])
                ], className="mb-4"),

                html.Div(id="post-record-form", style={"display": "none"}, children=[
                    dbc.Card([
                        dbc.CardHeader("Review Recording"),
                        dbc.CardBody([
                            html.Div(id="recording-preview", className="mb-3"),
                            html.Hr(),
                            dbc.Label("How did it go?"),
                            dbc.RadioItems(id="record-rating", options=[{"label": "⭐" * i, "value": i} for i in range(1, 6)], inline=True, className="mb-3"),
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
                dbc.Card([
                    dbc.CardHeader(["Today's Practice", dbc.Badge(f"{len([e for e in today_exercises if e['completed']])}/{len(today_exercises)}", color="success" if all(e["completed"] for e in today_exercises) and today_exercises else "primary", className="ms-2") if today_exercises else None]),
                    dbc.CardBody(today_checklist, id="practice-today-checklist"),
                ], className="mb-4"),

                dbc.Card([
                    dbc.CardHeader([html.Span("Practice Timer", className="me-auto"), dbc.Checklist(id="timer-sync-recording", options=[{"label": " Sync with recording", "value": "sync"}], value=[], inline=True, className="ms-2 small")], className="d-flex align-items-center"),
                    dbc.CardBody([
                        dbc.Row([dbc.Col([html.Div([
                            dbc.Button("−", id="btn-timer-minus", color="secondary", outline=True, size="sm", className="me-2"),
                            dbc.Input(id="timer-duration-input", type="number", value=5, min=1, max=120, style={"width": "70px", "display": "inline-block", "textAlign": "center"}),
                            html.Span(" min", className="ms-1 me-2"),
                            dbc.Button("+", id="btn-timer-plus", color="secondary", outline=True, size="sm"),
                        ], className="d-flex align-items-center justify-content-center mb-3")])]),
                        html.Div(id="practice-timer-display", className="display-3 text-center font-monospace mb-3", children="05:00"),
                        dbc.ButtonGroup([
                            dbc.Button("▶ Start", id="btn-timer-start", color="success", outline=True),
                            dbc.Button("⏸ Pause", id="btn-timer-pause", color="warning", outline=True, disabled=True),
                            dbc.Button("⏹ Reset", id="btn-timer-reset", color="secondary", outline=True),
                        ], className="w-100"),
                    ])
                ], className="mb-4"),

                # Drum Machine Card
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("🥁 Drum Machine", className="me-auto"),
                        dbc.Badge(id="drum-bpm-display", children="100 BPM", color="info", className="ms-2"),
                    ], className="d-flex align-items-center"),
                    dbc.CardBody([
                        # Pattern selector
                        dbc.Row([
                            dbc.Col([
                                dcc.Dropdown(
                                    id="drum-pattern-select",
                                    options=[
                                        {"label": "Rock 4/4", "value": "rock"},
                                        {"label": "Pop 4/4", "value": "pop"},
                                        {"label": "Blues Shuffle", "value": "blues_shuffle"},
                                        {"label": "Funk", "value": "funk"},
                                        {"label": "Jazz Swing", "value": "jazz"},
                                        {"label": "Bossa Nova", "value": "bossa"},
                                        {"label": "Metronome", "value": "metronome"},
                                        {"label": "Custom", "value": "custom", "disabled": True},
                                    ],
                                    value="rock",
                                    clearable=False,
                                    className="mb-2"
                                ),
                            ])
                        ]),
                        # BPM control
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Tempo", className="small text-muted mb-1"),
                                html.Div([
                                    dbc.Button("−", id="drum-bpm-minus", size="sm", color="secondary", outline=True, className="me-1"),
                                    dcc.Slider(
                                        id="drum-bpm-slider",
                                        min=40, max=200, step=1, value=100,
                                        marks={40: "40", 80: "80", 120: "120", 160: "160", 200: "200"},
                                        tooltip={"placement": "bottom", "always_visible": False},
                                        className="flex-grow-1 mx-2"
                                    ),
                                    dbc.Button("+", id="drum-bpm-plus", size="sm", color="secondary", outline=True, className="ms-1"),
                                ], className="d-flex align-items-center"),
                            ])
                        ], className="mb-2"),
                        # Volume control
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Volume", className="small text-muted mb-1"),
                                dcc.Slider(
                                    id="drum-volume-slider",
                                    min=0, max=100, step=5, value=70,
                                    marks={0: "🔇", 50: "🔉", 100: "🔊"},
                                ),
                            ])
                        ], className="mb-3"),
                        # Beat indicator
                        html.Div([
                            html.Div([
                                html.Div(id={"type": "beat-indicator", "beat": i}, 
                                    className="beat-dot", 
                                    style={
                                        "width": "20px", "height": "20px", 
                                        "borderRadius": "50%", 
                                        "backgroundColor": "#444",
                                        "display": "inline-block",
                                        "margin": "0 4px",
                                        "transition": "background-color 0.1s"
                                    }
                                ) for i in range(8)
                            ], className="text-center mb-3", id="beat-indicator-container"),
                        ]),
                        # Play/Stop buttons
                        dbc.ButtonGroup([
                            dbc.Button("▶ Play", id="btn-drum-play", color="success", outline=True),
                            dbc.Button("⏹ Stop", id="btn-drum-stop", color="danger", outline=True),
                        ], className="w-100"),
                        # Count-in option
                        dbc.Checklist(
                            id="drum-count-in",
                            options=[{"label": " Count-in (1 bar)", "value": "countin"}],
                            value=[],
                            className="mt-2 small"
                        ),
                    ])
                ], className="mb-4"),
            ], lg=4),
        ]),
        dcc.Interval(id="timer-interval", interval=1000, disabled=True),
        dcc.Interval(id="practice-timer-interval", interval=1000, disabled=True),
        dcc.Store(id="recording-state", data={"is_recording": False, "start_time": None, "result": None}),
        dcc.Store(id="practice-timer-state", data={"running": False, "remaining_seconds": 300, "duration_seconds": 300, "last_tick": None}),
        dcc.Store(id="device-state", data={"camera": 0, "audio": None}),
        dcc.Store(id="practice-plan-id", data=plan_id),
        dcc.Store(id="drum-machine-state", data={"playing": False, "currentBeat": 0}),
        # Drum machine clientside callback outputs
        html.Div(id="drum-machine-output", style={"display": "none"}),
        html.Div(id="drum-bpm-output", style={"display": "none"}),
    ])


def create_journal_page():
    """Practice journal with weekly overview and daily details"""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    
    return dbc.Container([
        html.H3("Practice Journal", className="mb-4"),
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([dbc.Button("← Prev", id="journal-prev-week", size="sm", color="secondary")], width="auto"),
                    dbc.Col([html.H5(id="journal-week-label", className="text-center mb-0")]),
                    dbc.Col([dbc.Button("Next →", id="journal-next-week", size="sm", color="secondary")], width="auto"),
                ], className="mb-3 align-items-center"),
                html.Div(id="journal-week-overview"),
            ])
        ], className="mb-4"),
        html.Div(id="journal-day-details"),
        dcc.Store(id="journal-selected-date", data=today.isoformat()),
        dcc.Store(id="journal-week-start", data=week_start.isoformat()),
    ])


def _build_week_overview(week_start: date, selected_date: date) -> html.Div:
    """Build the week overview row with clickable days"""
    week_summary = get_week_summary(week_start)
    day_buttons = []
    
    for i, day_data in enumerate(week_summary):
        day = day_data["date"]
        mins = day_data["total_minutes"]
        is_selected = day == selected_date
        is_today = day == date.today()
        is_future = day > date.today()
        
        if is_selected:
            color, outline = "primary", False
        elif is_future:
            color, outline = "secondary", True
        elif mins > 0:
            color, outline = "success", True
        else:
            color, outline = "secondary", True
        
        day_btn = dbc.Col([
            dbc.Button(
                html.Div([html.Div(DAY_NAMES[i][:3], style={"fontWeight": "bold"}), html.Div(day.strftime("%d"), style={"fontSize": "1.2em"}), html.Div(f"{mins}m" if mins > 0 else "—", style={"fontSize": "0.8em"}, className="text-muted" if outline else "")]),
                id={"type": "journal-day-btn", "date": day.isoformat()},
                color=color, outline=outline, className="w-100 py-2" + (" border-warning border-2" if is_today else ""), disabled=is_future
            )
        ], className="px-1")
        day_buttons.append(day_btn)
    
    return dbc.Row(day_buttons, className="g-1")


def _build_day_details(target_date: date) -> html.Div:
    """Build the detailed view for a specific day"""
    summary = get_daily_summary(target_date)
    is_today = target_date == date.today()
    is_future = target_date > date.today()
    
    if is_future:
        return dbc.Alert("Select a past or current day to view practice details.", color="info")
    
    exercises_by_cat = {}
    for ex in summary["completed_exercises"]:
        cat = ex["category"]
        if cat not in exercises_by_cat:
            exercises_by_cat[cat] = []
        exercises_by_cat[cat].append(ex)
    
    sections = []
    date_str = target_date.strftime("%A, %B %d, %Y")
    header = dbc.Row([
        dbc.Col([html.H5(date_str, className="mb-0"), html.Small("Today" if is_today else "", className="text-muted")]),
        dbc.Col([dbc.Badge(f"Total: {summary['total_minutes']} min", color="success" if summary['total_minutes'] > 0 else "secondary", className="fs-6")], width="auto"),
    ], className="mb-3 align-items-center")
    sections.append(header)
    
    if exercises_by_cat:
        ex_section = dbc.Card([
            dbc.CardHeader("From Planner", className="py-2"),
            dbc.CardBody([html.Div([html.Div([dbc.Badge(cat, color="info", className="me-2"), html.Span(f"{sum(e['duration'] for e in exs)} min — "), html.Span(", ".join(e["name"] for e in exs), className="text-muted")], className="mb-2") for cat, exs in exercises_by_cat.items()])], className="py-2")
        ], className="mb-3")
        sections.append(ex_section)
    
    if summary["recordings"]:
        rec_items = []
        for rec in summary["recordings"]:
            badges = []
            if rec["has_video"]:
                badges.append(dbc.Badge("🎬 Video", color="info", className="me-1"))
            elif rec["has_recording"]:
                badges.append(dbc.Badge("🎵 Audio", color="secondary", className="me-1"))
            if rec.get("recording_type"):
                badges.append(dbc.Badge(rec["recording_type"], color="warning", className="me-1"))
            if rec["rating"]:
                badges.append(html.Span("⭐" * rec["rating"], className="ms-1"))
            rec_items.append(dbc.ListGroupItem([html.Div([html.Strong(rec["title"] or "Untitled"), *badges, html.Span(f" • {rec['duration'] or 0} min", className="text-muted")]), html.Small(rec["notes"], className="text-muted") if rec["notes"] else None, dbc.Button("Review →", href="/review", size="sm", color="link", className="p-0 float-end")]))
        rec_section = dbc.Card([dbc.CardHeader("Recordings", className="py-2"), dbc.CardBody([dbc.ListGroup(rec_items, flush=True)], className="p-0")], className="mb-3")
        sections.append(rec_section)
    
    manual_items = []
    for m in summary["manual_entries"]:
        manual_items.append(dbc.ListGroupItem([dbc.Row([dbc.Col([dbc.Badge(m["category"] or "Other", color="secondary", className="me-2"), html.Span(f"{m['duration']} min"), html.Span(f" — {m['description']}" if m['description'] else "", className="text-muted")]), dbc.Col([dbc.Button("✎", id={"type": "edit-manual", "id": m["id"]}, size="sm", color="link", className="p-0 me-2"), dbc.Button("🗑", id={"type": "delete-manual", "id": m["id"]}, size="sm", color="link", className="p-0 text-danger")], width="auto")], className="align-items-center")]))
    
    add_form = dbc.Row([
        dbc.Col([dcc.Dropdown(id="manual-category", options=[{"label": c, "value": c} for c in PRACTICE_CATEGORIES], placeholder="Category", className="mb-2 mb-md-0")], md=3),
        dbc.Col([dbc.Input(id="manual-duration", type="number", min=1, placeholder="Min", style={"width": "80px"})], md=2),
        dbc.Col([dbc.Input(id="manual-description", placeholder="What did you practice?")], md=5),
        dbc.Col([dbc.Button("+ Add", id="btn-add-manual", color="success", size="sm")], md=2),
    ], className="g-2 mt-2")
    
    manual_section = dbc.Card([dbc.CardHeader("Additional Practice", className="py-2"), dbc.CardBody([dbc.ListGroup(manual_items, flush=True) if manual_items else html.P("No manual entries", className="text-muted mb-2"), add_form, html.Div(id="manual-status", className="mt-2")])], className="mb-3")
    sections.append(manual_section)
    
    notes_section = dbc.Card([dbc.CardHeader("Daily Notes", className="py-2"), dbc.CardBody([dbc.Textarea(id="journal-notes", value=summary["journal_notes"] or "", placeholder="How did practice go today?", rows=3, className="mb-2"), dbc.Button("Save Notes", id="btn-save-notes", color="primary", size="sm"), html.Span(id="notes-status", className="ms-2 text-muted")])], className="mb-3")
    sections.append(notes_section)
    
    return html.Div(sections)


def create_review_page():
    """Review recordings with playback, waveform visualization, and annotations"""
    return dbc.Container([
        html.H3("Review Recordings", className="mb-4"),
        
        # Type filter tabs
        dbc.Tabs([
            dbc.Tab(label="All", tab_id="all"),
            dbc.Tab(label="🎭 Performances", tab_id="Performance"),
            dbc.Tab(label="🎯 Exercises", tab_id="Exercise"),
            dbc.Tab(label="🎸 Riffs", tab_id="Riff"),
        ], id="review-type-tabs", active_tab="all", className="mb-3"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(["Recordings", dbc.Button("🔄 Refresh", id="btn-refresh-recordings", size="sm", color="link", className="float-end p-0")]),
                    dbc.CardBody([html.Div(id="recordings-table-container")])
                ], className="mb-4"),
                html.Div(id="review-playback-area"),
                html.Div(id="review-waveform-area", className="mt-3"),
                html.Div(id="review-controls-area", className="mt-3"),
                html.Div(id="review-annotations-list", className="mt-4"),
            ], lg=8),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Add Annotation"),
                    dbc.CardBody([
                        dbc.Label("Timestamp (seconds)"),
                        dbc.Input(id="annotation-timestamp", type="number", min=0, step=0.1, className="mb-2"),
                        dbc.Button("⏱ Use Current Time", id="btn-get-current-time", size="sm", color="secondary", className="mb-2"),
                        dbc.Label("Type"),
                        dcc.Dropdown(id="annotation-type", options=[{"label": "🔴 Issue", "value": "issue"}, {"label": "🟢 Good", "value": "good"}, {"label": "❓ Question", "value": "question"}, {"label": "📝 Note", "value": "note"}], value="note", className="mb-2"),
                        dbc.Label("Note"),
                        dbc.Textarea(id="annotation-text", placeholder="What did you notice?", className="mb-2"),
                        dbc.Button("Add Annotation", id="btn-add-annotation", color="primary"),
                        html.Div(id="annotation-status", className="mt-2"),
                    ])
                ]),
                html.Div(id="review-session-details", className="mt-4"),
            ], lg=4),
        ]),
        dcc.Store(id="review-session-select", data=None),
        dcc.Store(id="review-audio-data", data=None),
        dcc.Store(id="review-loop-range", data={"start": None, "end": None}),
        dcc.Store(id="review-current-time", data=0),
        dcc.Store(id="table-refresh-trigger", data=0),
        dcc.Store(id="review-type-filter", data="all"),
        html.Div(id="playback-speed-output", style={"display": "none"}),
        html.Div(id="waveform-click-output", style={"display": "none"}),
        html.Div(id="loop-handler-output", style={"display": "none"}),
        html.Div(id="loop-controls-output", style={"display": "none"}),
        html.Div(id="skip-controls-output", style={"display": "none"}),
        html.Div(id="annotation-seek-output", style={"display": "none"}),
        dcc.Interval(id="review-time-interval", interval=500, disabled=True, n_intervals=0),
    ])


def create_stats_page():
    """Practice statistics and visualizations"""
    return dbc.Container([
        html.H3("Practice Statistics", className="mb-4"),
        dbc.Row([dbc.Col([dbc.Card([dbc.CardBody([dcc.DatePickerRange(id="stats-date-range", start_date=(date.today() - timedelta(days=30)), end_date=date.today(), display_format="MMM D, YYYY"), dbc.Button("Update", id="btn-update-stats", color="primary", className="ms-3")])], className="mb-4")])]),
        dbc.Row(id="stats-summary-cards", className="mb-4"),
        dbc.Row([
            dbc.Col([dbc.Card([dbc.CardHeader("Practice by Category"), dbc.CardBody([dcc.Graph(id="stats-category-chart")])])], md=6),
            dbc.Col([dbc.Card([dbc.CardHeader("Practice Over Time"), dbc.CardBody([dcc.Graph(id="stats-timeline-chart")])])], md=6),
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

@callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    if pathname == "/planner": return create_planner_page()
    elif pathname == "/repertoire": return create_repertoire_page()
    elif pathname == "/journal": return create_journal_page()
    elif pathname == "/review": return create_review_page()
    elif pathname == "/stats": return create_stats_page()
    else: return create_record_page()


# --- Planner callbacks ---

@callback(Output("today-card-container", "children"), Output("planner-grids", "children"),
    Input({"type": "plan-checkbox", "exercise": ALL, "day": ALL}, "value"),
    State({"type": "plan-checkbox", "exercise": ALL, "day": ALL}, "id"),
    State("current-plan-id", "data"), prevent_initial_call=True)
def handle_plan_checkbox(values, ids, plan_id):
    if not ctx.triggered_id or not plan_id: return dash.no_update, dash.no_update
    triggered = ctx.triggered_id
    exercise_id, day = triggered["exercise"], triggered["day"]
    for i, id_dict in enumerate(ids):
        if id_dict["exercise"] == exercise_id and id_dict["day"] == day:
            new_value = values[i]
            break
    else: return dash.no_update, dash.no_update
    set_plan_entry(plan_id, exercise_id, day, new_value)
    return _build_today_card(plan_id), _build_category_grids(plan_id)


@callback(Output({"type": "today-complete", "entry": MATCH}, "value"),
    Input({"type": "today-complete", "entry": MATCH}, "value"),
    State({"type": "today-complete", "entry": MATCH}, "id"), prevent_initial_call=True)
def handle_today_complete(value, id_dict):
    toggle_entry_completed(id_dict["entry"], value)
    return value


@callback(Output("today-card-container", "children", allow_duplicate=True),
    Input({"type": "today-move-up", "entry": ALL}, "n_clicks"),
    State({"type": "today-move-up", "entry": ALL}, "id"),
    State("current-plan-id", "data"), prevent_initial_call=True)
def handle_move_up(n_clicks_list, ids, plan_id):
    if not ctx.triggered_id or not any(n for n in n_clicks_list if n) or not plan_id: return dash.no_update
    reorder_today_entry(ctx.triggered_id["entry"], "up")
    return _build_today_card(plan_id)


@callback(Output("today-card-container", "children", allow_duplicate=True),
    Input({"type": "today-move-down", "entry": ALL}, "n_clicks"),
    State({"type": "today-move-down", "entry": ALL}, "id"),
    State("current-plan-id", "data"), prevent_initial_call=True)
def handle_move_down(n_clicks_list, ids, plan_id):
    if not ctx.triggered_id or not any(n for n in n_clicks_list if n) or not plan_id: return dash.no_update
    reorder_today_entry(ctx.triggered_id["entry"], "down")
    return _build_today_card(plan_id)


@callback(Output("today-card-container", "children", allow_duplicate=True), Output("planner-grids", "children", allow_duplicate=True),
    Input({"type": "today-remove", "entry": ALL, "exercise": ALL}, "n_clicks"),
    State({"type": "today-remove", "entry": ALL, "exercise": ALL}, "id"),
    State("current-plan-id", "data"), prevent_initial_call=True)
def handle_remove_today(n_clicks_list, ids, plan_id):
    if not ctx.triggered_id or not any(n for n in n_clicks_list if n) or not plan_id: return dash.no_update, dash.no_update
    remove_today_entry(plan_id, ctx.triggered_id["exercise"])
    return _build_today_card(plan_id), _build_category_grids(plan_id)


# --- Repertoire callbacks ---

@callback(Output("repertoire-status", "children"), Output("new-piece-title", "value"), Output("new-piece-artist", "value"),
    Output("new-piece-genre", "value"), Output("new-piece-link", "value"), Output("new-piece-notes", "value"),
    Input("btn-add-piece", "n_clicks"),
    State("new-piece-title", "value"), State("new-piece-artist", "value"), State("new-piece-type", "value"),
    State("new-piece-genre", "value"), State("new-piece-difficulty", "value"), State("new-piece-status", "value"),
    State("new-piece-link", "value"), State("new-piece-notes", "value"), prevent_initial_call=True)
def add_piece(n_clicks, title, artist, piece_type, genre, difficulty, status, link, notes):
    if not title: return dbc.Alert("Please enter a title", color="warning"), dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    add_repertoire_piece(title=title, artist=artist, piece_type=piece_type, genre=genre, difficulty=difficulty, status=status, link=link, notes=notes)
    return dbc.Alert(f"Added '{title}' to repertoire!", color="success", duration=3000), "", "", "", "", ""


@callback(Output("url", "pathname", allow_duplicate=True),
    Input({"type": "advance-piece", "id": ALL}, "n_clicks"),
    State({"type": "advance-piece", "id": ALL}, "id"), prevent_initial_call=True)
def advance_piece_status(n_clicks_list, ids):
    if not ctx.triggered_id or not any(n_clicks_list): return dash.no_update
    piece_id = ctx.triggered_id["id"]
    db = get_session()
    piece = db.query(RepertoirePiece).get(piece_id)
    if piece:
        status_order = ["Want to Learn", "Learning", "Review", "Mastered"]
        current_idx = status_order.index(piece.status) if piece.status in status_order else 0
        if current_idx < len(status_order) - 1:
            new_status = status_order[current_idx + 1]
            piece.status = new_status
            if new_status == "Learning" and not piece.date_started: piece.date_started = date.today()
            elif new_status == "Mastered": piece.date_mastered = date.today()
            db.commit()
    db.close()
    return "/repertoire"


@callback(Output("url", "pathname", allow_duplicate=True),
    Input({"type": "delete-piece", "id": ALL}, "n_clicks"),
    State({"type": "delete-piece", "id": ALL}, "id"), prevent_initial_call=True)
def delete_piece(n_clicks_list, ids):
    if not ctx.triggered_id or not any(n_clicks_list): return dash.no_update
    delete_repertoire_piece(ctx.triggered_id["id"])
    return "/repertoire"


# --- Practice Page callbacks ---

@callback(Output("collapse-devices", "is_open"), Output("collapse-devices-btn", "children"),
    Input("collapse-devices-btn", "n_clicks"), State("collapse-devices", "is_open"), prevent_initial_call=True)
def toggle_devices_collapse(n_clicks, is_open):
    new_state = not is_open
    return new_state, f"{'▼' if new_state else '▶'} Recording Devices"


# --- Drum Machine callbacks ---

@callback(Output("drum-bpm-display", "children"), Input("drum-bpm-slider", "value"))
def update_bpm_display(bpm):
    return f"{bpm} BPM"


@callback(Output("drum-bpm-slider", "value"),
    Input("drum-bpm-minus", "n_clicks"), Input("drum-bpm-plus", "n_clicks"),
    State("drum-bpm-slider", "value"), prevent_initial_call=True)
def adjust_drum_bpm(minus_clicks, plus_clicks, current_bpm):
    triggered = ctx.triggered_id
    if triggered == "drum-bpm-minus": return max(40, current_bpm - 5)
    elif triggered == "drum-bpm-plus": return min(200, current_bpm + 5)
    return current_bpm


@callback(Output("timer-duration-input", "value"),
    Input("btn-timer-minus", "n_clicks"), Input("btn-timer-plus", "n_clicks"),
    State("timer-duration-input", "value"), prevent_initial_call=True)
def adjust_timer_duration(minus_clicks, plus_clicks, current_value):
    if current_value is None: current_value = 5
    triggered = ctx.triggered_id
    if triggered == "btn-timer-minus": return max(1, current_value - 1)
    elif triggered == "btn-timer-plus": return min(120, current_value + 1)
    return current_value


@callback(
    Output("practice-timer-display", "children"), Output("practice-timer-display", "style"),
    Output("practice-timer-state", "data"), Output("btn-timer-start", "disabled"),
    Output("btn-timer-pause", "disabled"), Output("btn-timer-start", "children"),
    Output("practice-timer-interval", "disabled"),
    Input("btn-timer-start", "n_clicks"), Input("btn-timer-pause", "n_clicks"),
    Input("btn-timer-reset", "n_clicks"), Input("practice-timer-interval", "n_intervals"),
    Input("timer-duration-input", "value"), Input("btn-start-record", "n_clicks"),
    Input("btn-stop-record", "n_clicks"), Input("btn-stop-discard", "n_clicks"),
    State("practice-timer-state", "data"), State("timer-sync-recording", "value"), prevent_initial_call=True)
def handle_practice_timer(start_clicks, pause_clicks, reset_clicks, n_intervals, duration_input, rec_start, rec_stop, rec_discard, timer_state, sync_options):
    import time
    triggered = ctx.triggered_id
    sync_with_recording = "sync" in (sync_options or [])
    
    if timer_state is None:
        timer_state = {"running": False, "remaining_seconds": (duration_input or 5) * 60, "duration_seconds": (duration_input or 5) * 60, "last_tick": None}
    
    running, remaining = timer_state.get("running", False), timer_state.get("remaining_seconds", 300)
    duration, last_tick = timer_state.get("duration_seconds", 300), timer_state.get("last_tick")
    
    if triggered == "timer-duration-input":
        new_duration = (duration_input or 5) * 60
        return f"{duration_input or 5:02d}:00", {}, {"running": False, "remaining_seconds": new_duration, "duration_seconds": new_duration, "last_tick": None}, False, True, "▶ Start", True
    
    if sync_with_recording:
        if triggered == "btn-start-record": running, last_tick = True, time.time()
        elif triggered in ["btn-stop-record", "btn-stop-discard"]: running, last_tick = False, None
    
    if triggered == "btn-timer-start" and not running and remaining > 0: running, last_tick = True, time.time()
    elif triggered == "btn-timer-pause": running, last_tick = False, None
    elif triggered == "btn-timer-reset": running, remaining, last_tick = False, duration, None
    
    if triggered == "practice-timer-interval" and running and last_tick:
        now = time.time()
        remaining = max(0, remaining - (now - last_tick))
        last_tick = now
        if remaining <= 0: running, remaining, last_tick = False, 0, None
    
    mins, secs = int(remaining // 60), int(remaining % 60)
    display = f"{mins:02d}:{secs:02d}"
    style = {"color": "#dc3545"} if remaining == 0 else {}
    start_disabled = running or remaining == 0
    pause_disabled = not running
    start_text = "✓ Done" if remaining == 0 else ("▶ Resume" if remaining < duration and not running else "▶ Start")
    
    return display, style, {"running": running, "remaining_seconds": remaining, "duration_seconds": duration, "last_tick": last_tick}, start_disabled, pause_disabled, start_text, not running


@callback(Output({"type": "practice-complete", "entry": MATCH}, "value"),
    Input({"type": "practice-complete", "entry": MATCH}, "value"),
    State({"type": "practice-complete", "entry": MATCH}, "id"), prevent_initial_call=True)
def handle_practice_complete(value, id_dict):
    toggle_entry_completed(id_dict["entry"], value)
    return value


# --- Recording callbacks ---

@callback(
    Output("recording-state", "data"), Output("btn-start-record", "disabled"),
    Output("btn-stop-record", "disabled"), Output("btn-stop-discard", "disabled"),
    Output("record-status", "children"), Output("post-record-form", "style"),
    Output("recording-preview", "children"),
    Input("btn-start-record", "n_clicks"), Input("btn-stop-record", "n_clicks"),
    Input("btn-stop-discard", "n_clicks"), Input("btn-discard-retry", "n_clicks"),
    Input("btn-discard", "n_clicks"),
    State("record-options", "value"), State("recording-state", "data"),
    State("camera-select", "value"), State("audio-select", "value"), prevent_initial_call=True)
def handle_recording(start_clicks, stop_clicks, stop_discard_clicks, retry_clicks, discard_clicks, options, state, camera_idx, audio_idx):
    triggered = ctx.triggered_id
    
    if triggered == "btn-start-record":
        include_video = "video" in (options or [])
        include_audio = "audio" in (options or [])
        if camera_idx is not None and camera_idx >= 0: recorder.camera_index = camera_idx
        if audio_idx is not None and audio_idx >= 0: recorder.audio_device = audio_idx
        recorder.start(include_video=include_video, include_audio=include_audio)
        return {"is_recording": True, "start_time": datetime.now().isoformat(), "result": None}, True, False, False, dbc.Alert("🔴 Recording...", color="danger"), {"display": "none"}, None
    
    elif triggered == "btn-stop-record":
        result = recorder.stop()
        preview = None
        if result and result.get("final_path"):
            final_path = Path(result["final_path"])
            if final_path.exists():
                filename, file_size = final_path.name, final_path.stat().st_size
                if file_size < 1000:
                    preview = dbc.Alert(f"Recording file is too small ({file_size} bytes).", color="warning")
                elif result.get("has_video") or str(final_path).endswith((".mp4", ".avi")):
                    preview = html.Div([html.Video(id="preview-player", src=f"/recordings/{filename}", controls=True, style={"width": "100%", "maxHeight": "300px"}, autoPlay=False), html.Small(f"File: {filename} ({file_size // 1024} KB)", className="text-muted d-block mt-1")])
                else:
                    preview = html.Div([html.Audio(id="preview-player", src=f"/recordings/{filename}", controls=True, style={"width": "100%"}, autoPlay=False), html.Small(f"File: {filename} ({file_size // 1024} KB)", className="text-muted d-block mt-1")])
            else: preview = dbc.Alert("Recording file not found.", color="danger")
        else: preview = dbc.Alert("Recording failed.", color="danger")
        return {"is_recording": False, "start_time": None, "result": result}, False, True, True, dbc.Alert(f"Recording complete: {result['duration_seconds']:.1f}s", color="success") if result else dbc.Alert("Recording failed", color="danger"), {"display": "block"}, preview
    
    elif triggered == "btn-stop-discard":
        result = recorder.stop()
        _delete_recording_files(result)
        return {"is_recording": False, "start_time": None, "result": None}, False, True, True, dbc.Alert("Recording discarded", color="secondary"), {"display": "none"}, None
    
    elif triggered == "btn-discard-retry":
        result = state.get("result", {})
        _delete_recording_files(result)
        include_video = "video" in (options or [])
        include_audio = "audio" in (options or [])
        if camera_idx is not None and camera_idx >= 0: recorder.camera_index = camera_idx
        if audio_idx is not None and audio_idx >= 0: recorder.audio_device = audio_idx
        recorder.start(include_video=include_video, include_audio=include_audio)
        return {"is_recording": True, "start_time": datetime.now().isoformat(), "result": None}, True, False, False, dbc.Alert("🔴 Recording... (previous discarded)", color="danger"), {"display": "none"}, None
    
    elif triggered == "btn-discard":
        result = state.get("result", {})
        _delete_recording_files(result)
        return {"is_recording": False, "start_time": None, "result": None}, False, True, True, dbc.Alert("Recording discarded", color="secondary"), {"display": "none"}, None
    
    return (dash.no_update,) * 7


def _delete_recording_files(result):
    if not result: return
    filename = result.get("filename")
    if not filename: return
    for ext in ["_final.mp4", "_video.mp4", "_video.avi", "_audio.wav", "_audio.m4a"]:
        filepath = RECORDINGS_DIR / f"{filename}{ext}"
        if filepath.exists():
            try: filepath.unlink()
            except Exception as e: print(f"Failed to delete {filepath}: {e}")


@callback(Output("camera-select", "options"), Output("audio-select", "options"),
    Output("camera-select", "value"), Output("audio-select", "value"),
    Input("btn-refresh-devices", "n_clicks"),
    State("camera-select", "value"), State("audio-select", "value"), prevent_initial_call=True)
def refresh_devices(n, current_camera, current_audio):
    import cv2
    import sounddevice as sd
    cameras = []
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            cameras.append({"index": i, "name": f"{cap.getBackendName()} ({int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))})"})
            cap.release()
    sd._terminate(); sd._initialize()
    audio_devs = [{"index": i, "name": d['name']} for i, d in enumerate(sd.query_devices()) if d['max_input_channels'] > 0]
    
    camera_options = [{"label": f"Camera {c['index']}: {c['name']}", "value": c['index']} for c in cameras] or [{"label": "No cameras found", "value": -1}]
    audio_options = [{"label": a['name'], "value": a['index']} for a in audio_devs] or [{"label": "No audio inputs found", "value": -1}]
    
    valid_cam = [c['index'] for c in cameras]
    valid_aud = [a['index'] for a in audio_devs]
    new_cam = current_camera if current_camera in valid_cam else (camera_options[0]["value"] if camera_options else -1)
    new_aud = current_audio if current_audio in valid_aud else (audio_options[0]["value"] if audio_options else -1)
    return camera_options, audio_options, new_cam, new_aud


@callback(Output("timer-interval", "disabled"), Input("recording-state", "data"))
def toggle_timer(state):
    return not state.get("is_recording", False)


@callback(Output("record-timer", "children"), Input("timer-interval", "n_intervals"), State("recording-state", "data"))
def update_timer(n, state):
    if state.get("is_recording") and state.get("start_time"):
        start = datetime.fromisoformat(state["start_time"])
        elapsed = (datetime.now() - start).total_seconds()
        mins, secs = divmod(int(elapsed), 60)
        return f"{mins:02d}:{secs:02d}"
    return "00:00"


@callback(Output("record-status", "children", allow_duplicate=True),
    Output("post-record-form", "style", allow_duplicate=True),
    Output("recording-state", "data", allow_duplicate=True),
    Input("btn-save-session", "n_clicks"),
    State("record-title", "value"), State("record-category", "value"),
    State("record-type", "value"), State("record-notes", "value"),
    State("record-rating", "value"), State("recording-state", "data"), prevent_initial_call=True)
def save_session(n_clicks, title, category, recording_type, notes, rating, state):
    if not n_clicks: return dash.no_update, dash.no_update, dash.no_update
    result = state.get("result", {})
    duration_mins = int(result.get("duration_seconds", 0) / 60)
    session = create_practice_session(
        title=title or "Practice Session", category=category, duration_minutes=max(1, duration_mins),
        notes=notes or "", rating=rating, recording_filename=result.get("filename"),
        has_video=result.get("has_video", False), recording_type=recording_type
    )
    return dbc.Alert(f"✅ Session #{session.id} saved!", color="success"), {"display": "none"}, {"is_recording": False, "start_time": None, "result": None}


# --- Journal callbacks ---

@callback(
    Output("journal-week-label", "children"), Output("journal-week-overview", "children"),
    Output("journal-day-details", "children"), Output("journal-selected-date", "data"),
    Output("journal-week-start", "data"),
    Input("journal-prev-week", "n_clicks"), Input("journal-next-week", "n_clicks"),
    Input({"type": "journal-day-btn", "date": ALL}, "n_clicks"), Input("url", "pathname"),
    State("journal-selected-date", "data"), State("journal-week-start", "data"), prevent_initial_call=False)
def update_journal_view(prev_clicks, next_clicks, day_clicks, pathname, selected_date_str, week_start_str):
    if pathname != "/journal": return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    today = date.today()
    selected_date = date.fromisoformat(selected_date_str) if selected_date_str else today
    week_start = date.fromisoformat(week_start_str) if week_start_str else today - timedelta(days=today.weekday())
    triggered = ctx.triggered_id
    
    if triggered == "journal-prev-week":
        week_start = week_start - timedelta(days=7)
        selected_date = week_start
    elif triggered == "journal-next-week":
        new_week_start = week_start + timedelta(days=7)
        if new_week_start <= today:
            week_start = new_week_start
            selected_date = week_start
    elif isinstance(triggered, dict) and triggered.get("type") == "journal-day-btn":
        selected_date = date.fromisoformat(triggered["date"])
    
    week_end = week_start + timedelta(days=6)
    week_label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"
    return week_label, _build_week_overview(week_start, selected_date), _build_day_details(selected_date), selected_date.isoformat(), week_start.isoformat()


@callback(Output("manual-status", "children"), Output("journal-day-details", "children", allow_duplicate=True),
    Input("btn-add-manual", "n_clicks"),
    State("manual-category", "value"), State("manual-duration", "value"),
    State("manual-description", "value"), State("journal-selected-date", "data"), prevent_initial_call=True)
def add_manual_entry(n_clicks, category, duration, description, selected_date_str):
    if not n_clicks: return dash.no_update, dash.no_update
    if not category or not duration: return dbc.Alert("Please select a category and enter duration", color="warning", duration=3000), dash.no_update
    selected_date = date.fromisoformat(selected_date_str) if selected_date_str else date.today()
    add_manual_practice(target_date=selected_date, category=category, duration_minutes=int(duration), description=description or "")
    return dbc.Alert("✓ Added", color="success", duration=2000), _build_day_details(selected_date)


@callback(Output("journal-day-details", "children", allow_duplicate=True),
    Input({"type": "delete-manual", "id": ALL}, "n_clicks"),
    State({"type": "delete-manual", "id": ALL}, "id"),
    State("journal-selected-date", "data"), prevent_initial_call=True)
def delete_manual_entry(n_clicks_list, ids, selected_date_str):
    if not ctx.triggered_id or not any(n for n in n_clicks_list if n): return dash.no_update
    delete_manual_practice(ctx.triggered_id["id"])
    selected_date = date.fromisoformat(selected_date_str) if selected_date_str else date.today()
    return _build_day_details(selected_date)


@callback(Output("notes-status", "children"), Input("btn-save-notes", "n_clicks"),
    State("journal-notes", "value"), State("journal-selected-date", "data"), prevent_initial_call=True)
def save_journal_notes(n_clicks, notes, selected_date_str):
    if not n_clicks: return dash.no_update
    selected_date = date.fromisoformat(selected_date_str) if selected_date_str else date.today()
    save_daily_notes(selected_date, notes or "")
    return "✓ Saved"


# --- Review callbacks ---

@callback(Output("review-type-filter", "data"), Input("review-type-tabs", "active_tab"))
def update_type_filter(active_tab):
    return active_tab


@callback(Output("recordings-table-container", "children"),
    Input("url", "pathname"), Input("btn-refresh-recordings", "n_clicks"),
    Input("table-refresh-trigger", "data"), Input("review-type-filter", "data"))
def populate_recordings_table(pathname, refresh_clicks, refresh_trigger, type_filter):
    sessions = get_recent_sessions(limit=100)
    sessions_with_recordings = [s for s in sessions if s.has_recording]
    
    if type_filter and type_filter != "all":
        sessions_with_recordings = [s for s in sessions_with_recordings if (s.recording_type or "Exercise") == type_filter]
    
    if not sessions_with_recordings:
        if type_filter and type_filter != "all":
            return dbc.Alert(f"No {type_filter.lower()} recordings yet.", color="info")
        return dbc.Alert("No recordings yet. Go to Practice tab to create one!", color="info")
    
    grouped = {}
    for s in sessions_with_recordings:
        rtype = s.recording_type or "Exercise"
        if rtype not in grouped: grouped[rtype] = []
        grouped[rtype].append(s)
    
    tables = []
    type_order = ["Performance", "Exercise", "Riff"]
    type_icons = {"Performance": "🎭", "Exercise": "🎯", "Riff": "🎸"}
    
    for rtype in type_order:
        if rtype not in grouped: continue
        sessions_of_type = grouped[rtype]
        rows = []
        for s in sessions_of_type:
            file_exists = any((RECORDINGS_DIR / f"{s.recording_filename}{ext}").exists() for ext in ["_final.mp4", "_video.mp4", "_video.avi", "_audio.m4a", "_audio.wav"])
            duration_str = f"{s.duration_minutes} min" if s.duration_minutes else "—"
            rating_str = "⭐" * (s.rating or 0) if s.rating else "—"
            media_badge = dbc.Badge("Missing", color="danger", className="ms-2") if not file_exists else (dbc.Badge("Video", color="info", className="ms-2") if s.has_video else dbc.Badge("Audio", color="secondary", className="ms-2"))
            title_input = dbc.Input(id={"type": "title-input", "index": s.id}, value=s.title or "Untitled", size="sm", className="bg-dark text-light border-secondary", style={"width": "200px"}, debounce=True)
            row = html.Tr([html.Td(str(s.date)), html.Td([title_input, media_badge]), html.Td(s.category or "—"), html.Td(duration_str), html.Td(rating_str), html.Td([dbc.Button("▶", id={"type": "btn-play", "index": s.id}, size="sm", color="primary", className="me-1", title="Play"), dbc.Button("🗑", id={"type": "btn-delete", "index": s.id}, size="sm", color="danger", outline=True, title="Delete")])])
            rows.append(row)
        
        table = dbc.Table([html.Thead(html.Tr([html.Th("Date", style={"width": "100px"}), html.Th("Title"), html.Th("Category", style={"width": "120px"}), html.Th("Duration", style={"width": "80px"}), html.Th("Rating", style={"width": "80px"}), html.Th("Actions", style={"width": "100px"})])), html.Tbody(rows)], bordered=True, hover=True, responsive=True, size="sm")
        if type_filter == "all":
            tables.append(html.H5(f"{type_icons.get(rtype, '📁')} {rtype}s ({len(sessions_of_type)})", className="mt-3 mb-2"))
        tables.append(table)
    
    return html.Div(tables)


@callback(Output("review-session-select", "data"), Input({"type": "btn-play", "index": ALL}, "n_clicks"), prevent_initial_call=True)
def handle_play_click(n_clicks):
    if not any(n_clicks): return dash.no_update
    triggered = ctx.triggered_id
    if triggered and isinstance(triggered, dict): return triggered["index"]
    return dash.no_update


@callback(Output({"type": "title-input", "index": MATCH}, "className"),
    Input({"type": "title-input", "index": MATCH}, "value"),
    State({"type": "title-input", "index": MATCH}, "id"), prevent_initial_call=True)
def save_title(new_title, input_id):
    if new_title is None: return dash.no_update
    session_id = input_id["index"]
    db = get_session()
    session = db.query(PracticeSession).get(session_id)
    if session:
        session.title = new_title.strip() or "Untitled"
        db.commit()
    return "border-0 bg-transparent p-0"


@callback(Output("table-refresh-trigger", "data"), Output("review-session-select", "data", allow_duplicate=True),
    Input({"type": "btn-delete", "index": ALL}, "n_clicks"),
    State("review-session-select", "data"), State("table-refresh-trigger", "data"), prevent_initial_call=True)
def handle_delete(delete_clicks, current_session, refresh_count):
    if not any(delete_clicks): return dash.no_update, dash.no_update
    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict): return dash.no_update, dash.no_update
    session_id = triggered["index"]
    db = get_session()
    session = db.query(PracticeSession).get(session_id)
    if session:
        if session.recording_filename:
            for ext in ["_final.mp4", "_video.mp4", "_video.avi", "_audio.wav", "_audio.m4a", "_audio.extracted.wav"]:
                filepath = RECORDINGS_DIR / f"{session.recording_filename}{ext}"
                if filepath.exists():
                    try: filepath.unlink()
                    except: pass
        db.delete(session)
        db.commit()
    new_selection = None if current_session == session_id else current_session
    return (refresh_count or 0) + 1, new_selection


@callback(
    Output("review-playback-area", "children"), Output("review-waveform-area", "children"),
    Output("review-controls-area", "children"), Output("review-session-details", "children"),
    Output("review-annotations-list", "children"), Output("review-audio-data", "data"),
    Output("review-time-interval", "disabled"), Input("review-session-select", "data"))
def load_review_session(session_id):
    empty_return = (dbc.Alert("Click ▶ on a recording above to review it", color="info"), None, None, None, None, None, True)
    if not session_id: return empty_return
    
    db = get_session()
    session = db.query(PracticeSession).get(session_id)
    if not session or not session.recording_filename: return dbc.Alert("Recording not found", color="warning"), None, None, None, None, None, True
    
    recording_path = None
    for ext in ["_final.mp4", "_video.mp4", "_video.avi", "_audio.m4a", "_audio.wav"]:
        potential_path = RECORDINGS_DIR / f"{session.recording_filename}{ext}"
        if potential_path.exists():
            recording_path = potential_path
            break
    
    if not recording_path: return dbc.Alert("Recording file not found on disk", color="warning"), None, None, None, None, None, True
    
    is_video = session.has_video or str(recording_path).endswith((".mp4", ".avi"))
    is_audio_only = str(recording_path).endswith((".m4a", ".wav"))
    media_id = "review-media-player"
    
    if is_video and not is_audio_only:
        playback_element = html.Video(id=media_id, src=f"/recordings/{recording_path.name}", controls=True, preload="metadata", style={"width": "100%", "maxHeight": "400px", "backgroundColor": "#000"})
    else:
        playback_element = html.Audio(id=media_id, src=f"/recordings/{recording_path.name}", controls=True, preload="metadata", style={"width": "100%"})
    
    type_icons = {"Performance": "🎭", "Exercise": "🎯", "Riff": "🎸"}
    rtype = session.recording_type or "Exercise"
    type_badge = dbc.Badge(f"{type_icons.get(rtype, '📁')} {rtype}", color="warning", className="ms-2")
    playback_area = dbc.Card([dbc.CardHeader([f"{'📹' if is_video else '🎵'} {session.title}", type_badge]), dbc.CardBody([playback_element])])
    
    waveform_area, audio_data_store = None, None
    audio_data, sr = load_audio(str(recording_path))
    if audio_data is not None:
        times, wf_min, wf_max = generate_waveform_data(audio_data, sr, num_points=800)
        duration = len(audio_data) / sr if len(audio_data.shape) == 1 else len(audio_data) / sr
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(times) + list(times)[::-1], y=list(wf_max) + list(wf_min)[::-1], fill='toself', fillcolor='rgba(52, 152, 219, 0.5)', line=dict(color='rgba(52, 152, 219, 0.8)', width=1), hoverinfo='x', name='Waveform'))
        fig.add_vline(x=0, line_width=2, line_color="red", annotation_text="", name="playhead")
        fig.update_layout(height=120, margin=dict(l=40, r=20, t=10, b=30), xaxis=dict(title="Time (s)", range=[0, duration], showgrid=True, gridcolor='rgba(128,128,128,0.2)'), yaxis=dict(title="", showticklabels=False, range=[-1, 1], fixedrange=True), showlegend=False, dragmode='select', selectdirection='h')
        
        waveform_area = dbc.Card([dbc.CardHeader(["Waveform ", html.Small("(click to seek • drag to select)", className="text-muted")]), dbc.CardBody([dcc.Graph(id="waveform-graph", figure=fig, config={'displayModeBar': True, 'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d'], 'displaylogo': False}, style={"height": "120px"}), html.Div([html.Span("Current: ", className="text-muted"), html.Span(id="current-time-display", children="0:00.0"), html.Span(" / ", className="text-muted"), html.Span(f"{int(duration//60)}:{duration%60:04.1f}")], className="mt-2 font-monospace")])])
        audio_data_store = {"duration": duration, "sample_rate": sr}
    
    controls_area = dbc.Card([dbc.CardBody([dbc.Row([dbc.Col([dbc.Label("Playback Speed"), dcc.Slider(id="playback-speed-slider", min=0.25, max=2.0, step=0.25, value=1.0, marks={0.25: "0.25x", 0.5: "0.5x", 0.75: "0.75x", 1.0: "1x", 1.5: "1.5x", 2.0: "2x"}, tooltip={"placement": "bottom", "always_visible": False})], md=6), dbc.Col([dbc.Label("Navigation"), html.Div([dbc.Button("⏮ -5s", id="btn-back-5", size="sm", color="secondary", className="me-1"), dbc.Button("+5s ⏭", id="btn-forward-5", size="sm", color="secondary")])], md=6)], className="mb-3"), html.Hr(), dbc.Row([dbc.Col([dbc.Label("Selection Controls"), html.Div(id="loop-range-display", className="small text-muted mb-2"), dbc.ButtonGroup([dbc.Button("⏮", id="btn-loop-start", size="sm", color="primary", title="Back to start"), dbc.Button("▶", id="btn-loop-play", size="sm", color="success", title="Play"), dbc.Button("⏸", id="btn-loop-pause", size="sm", color="warning", title="Pause")], className="me-3"), dbc.Checklist(id="loop-enabled", options=[{"label": " Loop", "value": "loop"}], value=[], inline=True, className="d-inline-block align-middle")], md=12)])])])
    
    details = dbc.Card([dbc.CardHeader("Session Info"), dbc.CardBody([html.P([html.Strong("Type: "), dbc.Badge(rtype, color="warning")]), html.P([html.Strong("Category: "), session.category]), html.P([html.Strong("Duration: "), f"{session.duration_minutes} min"]), html.P([html.Strong("Rating: "), "⭐" * (session.rating or 0) or "Not rated"]), html.P([html.Strong("Notes: "), session.notes or "None"])])])
    
    annotations = db.query(Annotation).filter(Annotation.session_id == session_id).order_by(Annotation.timestamp_seconds).all()
    if annotations:
        ann_items = [html.Li([dbc.Button(f"[{a.timestamp_seconds:.1f}s]", id={"type": "annotation-seek", "index": a.id}, color="link", size="sm", className="p-0 me-2 font-monospace"), html.Span({"issue": "🔴", "good": "🟢", "question": "❓", "note": "📝"}.get(a.annotation_type, "📝")), html.Span(f" {a.text}")], className="mb-2") for a in annotations]
        ann_list = dbc.Card([dbc.CardHeader(f"Annotations ({len(annotations)})"), dbc.CardBody(html.Ul(ann_items, className="ps-3 mb-0"))])
    else:
        ann_list = dbc.Card([dbc.CardHeader("Annotations"), dbc.CardBody("No annotations yet.")])
    
    return playback_area, waveform_area, controls_area, details, ann_list, audio_data_store, False


@callback(Output("annotation-status", "children"), Input("btn-add-annotation", "n_clicks"),
    State("review-session-select", "data"), State("annotation-timestamp", "value"),
    State("annotation-type", "value"), State("annotation-text", "value"), prevent_initial_call=True)
def save_annotation(n, session_id, timestamp, ann_type, text):
    if not all([session_id, timestamp is not None, text]): return dbc.Alert("Please fill in timestamp and note", color="warning")
    add_annotation(session_id, float(timestamp), text, ann_type)
    return dbc.Alert("✅ Annotation added!", color="success")


@callback(Output("loop-range-display", "children"), Input("review-loop-range", "data"))
def display_loop_range(loop_range):
    if loop_range and loop_range.get("start") is not None:
        start, end = loop_range["start"], loop_range["end"]
        return f"Selected: {start:.1f}s → {end:.1f}s ({end-start:.1f}s)"
    return "Drag on waveform to select a section"


# --- Stats callbacks ---

@callback(Output("stats-summary-cards", "children"), Output("stats-category-chart", "figure"), Output("stats-timeline-chart", "figure"),
    Input("btn-update-stats", "n_clicks"), State("stats-date-range", "start_date"), State("stats-date-range", "end_date"))
def update_stats(n, start_date, end_date):
    start = datetime.fromisoformat(start_date).date() if start_date else date.today() - timedelta(days=30)
    end = datetime.fromisoformat(end_date).date() if end_date else date.today()
    
    stats = get_practice_stats(start, end)
    sessions = get_sessions_by_date_range(start, end)
    
    summary = dbc.Row([
        dbc.Col(dbc.Card([dbc.CardBody([html.H4(stats["total_sessions"], className="text-primary"), html.P("Sessions", className="mb-0")])]), md=3),
        dbc.Col(dbc.Card([dbc.CardBody([html.H4(f"{stats['total_minutes']} min", className="text-success"), html.P("Total Practice", className="mb-0")])]), md=3),
        dbc.Col(dbc.Card([dbc.CardBody([html.H4(f"{stats['total_minutes'] // max(1, (end - start).days)} min", className="text-info"), html.P("Daily Average", className="mb-0")])]), md=3),
        dbc.Col(dbc.Card([dbc.CardBody([html.H4(f"{stats['avg_rating']:.1f}" if stats['avg_rating'] else "N/A", className="text-warning"), html.P("Avg Rating", className="mb-0")])]), md=3),
    ])
    
    if stats["by_category"]:
        cat_fig = px.pie(names=list(stats["by_category"].keys()), values=list(stats["by_category"].values()), title="")
    else:
        cat_fig = go.Figure()
        cat_fig.add_annotation(text="No data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
    
    if sessions:
        daily_data = {}
        for s in sessions:
            d = s.date.isoformat()
            daily_data[d] = daily_data.get(d, 0) + (s.duration_minutes or 0)
        timeline_fig = px.bar(x=list(daily_data.keys()), y=list(daily_data.values()), labels={"x": "Date", "y": "Minutes"}, title="")
    else:
        timeline_fig = go.Figure()
        timeline_fig.add_annotation(text="No data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
    
    return summary, cat_fig, timeline_fig


# Serve static files (recordings)
@app.server.route('/recordings/<path:filename>')
def serve_recording(filename):
    filepath = RECORDINGS_DIR / filename
    if not filepath.exists(): return "File not found", 404
    mime_type, _ = mimetypes.guess_type(str(filepath))
    if mime_type is None:
        if filename.endswith('.mp4'): mime_type = 'video/mp4'
        elif filename.endswith('.m4a'): mime_type = 'audio/mp4'
        elif filename.endswith('.wav'): mime_type = 'audio/wav'
        else: mime_type = 'application/octet-stream'
    response = send_from_directory(RECORDINGS_DIR, filename, mimetype=mime_type)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# ============================================================================
# CLIENTSIDE CALLBACKS FOR MEDIA CONTROL
# ============================================================================

app.clientside_callback(
    "function(speed) { const media = document.getElementById('review-media-player'); if (media) { media.playbackRate = speed; } return ''; }",
    Output("playback-speed-output", "children"), Input("playback-speed-slider", "value"), prevent_initial_call=True)

app.clientside_callback(
    "function(clickData) { if (clickData && clickData.points && clickData.points.length > 0) { const time = clickData.points[0].x; const media = document.getElementById('review-media-player'); if (media) { media.currentTime = time; } } return ''; }",
    Output("waveform-click-output", "children"), Input("waveform-graph", "clickData"), prevent_initial_call=True)

app.clientside_callback(
    "function(selectedData, loopEnabled) { if (selectedData && selectedData.range && selectedData.range.x) { return {start: selectedData.range.x[0], end: selectedData.range.x[1]}; } return {start: null, end: null}; }",
    Output("review-loop-range", "data"), Input("waveform-graph", "selectedData"), State("loop-enabled", "value"), prevent_initial_call=True)

app.clientside_callback(
    """function(loopEnabled, loopRange) {
        const media = document.getElementById('review-media-player');
        if (!media) return '';
        if (window.loopHandler) { media.removeEventListener('timeupdate', window.loopHandler); window.loopHandler = null; }
        if (loopRange && loopRange.start !== null && loopRange.end !== null) {
            const isLooping = loopEnabled && loopEnabled.includes('loop');
            window.loopHandler = function() {
                if (media.currentTime >= loopRange.end) {
                    if (isLooping) { media.currentTime = loopRange.start; }
                    else { media.pause(); media.currentTime = loopRange.start; }
                }
            };
            media.addEventListener('timeupdate', window.loopHandler);
        }
        return '';
    }""",
    Output("loop-handler-output", "children"), Input("loop-enabled", "value"), Input("review-loop-range", "data"), prevent_initial_call=True)

app.clientside_callback(
    """function(nStart, nPlay, nPause, loopRange) {
        const media = document.getElementById('review-media-player');
        if (!media) return '';
        const triggered = window.dash_clientside.callback_context.triggered;
        if (!triggered || triggered.length === 0) return '';
        const triggerId = triggered[0].prop_id.split('.')[0];
        if (triggerId === 'btn-loop-start') { media.currentTime = (loopRange && loopRange.start !== null) ? loopRange.start : 0; }
        else if (triggerId === 'btn-loop-play') {
            if (loopRange && loopRange.start !== null) { if (media.currentTime < loopRange.start || media.currentTime >= loopRange.end) { media.currentTime = loopRange.start; } }
            media.play();
        }
        else if (triggerId === 'btn-loop-pause') { media.pause(); }
        return '';
    }""",
    Output("loop-controls-output", "children"), Input("btn-loop-start", "n_clicks"), Input("btn-loop-play", "n_clicks"), Input("btn-loop-pause", "n_clicks"), State("review-loop-range", "data"), prevent_initial_call=True)

app.clientside_callback(
    """function(nBack, nForward) {
        const media = document.getElementById('review-media-player');
        if (!media) return '';
        const triggered = window.dash_clientside.callback_context.triggered;
        if (triggered && triggered.length > 0) {
            const triggerId = triggered[0].prop_id.split('.')[0];
            if (triggerId === 'btn-back-5') { media.currentTime = Math.max(0, media.currentTime - 5); }
            else if (triggerId === 'btn-forward-5') { media.currentTime = Math.min(media.duration, media.currentTime + 5); }
        }
        return '';
    }""",
    Output("skip-controls-output", "children"), Input("btn-back-5", "n_clicks"), Input("btn-forward-5", "n_clicks"), prevent_initial_call=True)

app.clientside_callback(
    "function(n) { const media = document.getElementById('review-media-player'); if (!media) return '0:00.0'; const time = media.currentTime; return Math.floor(time / 60) + ':' + (time % 60).toFixed(1).padStart(4, '0'); }",
    Output("current-time-display", "children"), Input("review-time-interval", "n_intervals"))

app.clientside_callback(
    "function(n) { const media = document.getElementById('review-media-player'); if (media) { return media.currentTime.toFixed(1); } return 0; }",
    Output("annotation-timestamp", "value"), Input("btn-get-current-time", "n_clicks"), prevent_initial_call=True)

app.clientside_callback(
    """function(n_clicks) {
        if (!n_clicks) return '';
        const triggered = window.dash_clientside.callback_context.triggered;
        if (triggered && triggered.length > 0) {
            const button = document.activeElement;
            if (button && button.textContent) {
                const match = button.textContent.match(/\\[([\\d.]+)s\\]/);
                if (match) {
                    const time = parseFloat(match[1]);
                    const media = document.getElementById('review-media-player');
                    if (media) { media.currentTime = time; media.play(); }
                }
            }
        }
        return '';
    }""",
    Output("annotation-seek-output", "children"), Input({"type": "annotation-seek", "index": ALL}, "n_clicks"), prevent_initial_call=True)


# ============================================================================
# DRUM MACHINE CLIENTSIDE CALLBACK (Tone.js)
# ============================================================================

app.clientside_callback(
    """
    function(playClicks, stopClicks, pattern, bpm, volume, countIn) {
        // Initialize drum machine with Tone.js
        if (!window.drumMachine) {
            window.drumMachine = {
                initialized: false,
                playing: false,
                currentBeat: 0,
                loopId: null,
                synths: {},
                
                // Drum patterns - extensible for future custom editor
                patterns: {
                    rock: {
                        name: "Rock 4/4",
                        beats: 8,
                        kick:   [1,0,0,0,1,0,0,0],
                        snare:  [0,0,1,0,0,0,1,0],
                        hihat:  [1,1,1,1,1,1,1,1],
                        accent: [1,0,0,0,0,0,0,0]
                    },
                    pop: {
                        name: "Pop 4/4",
                        beats: 8,
                        kick:   [1,0,0,0,1,0,1,0],
                        snare:  [0,0,1,0,0,0,1,0],
                        hihat:  [1,1,1,1,1,1,1,1],
                        accent: [1,0,0,0,0,0,0,0]
                    },
                    blues_shuffle: {
                        name: "Blues Shuffle",
                        beats: 12,
                        kick:   [1,0,0,0,0,0,1,0,0,0,0,0],
                        snare:  [0,0,0,1,0,0,0,0,0,1,0,0],
                        hihat:  [1,0,1,1,0,1,1,0,1,1,0,1],
                        accent: [1,0,0,0,0,0,0,0,0,0,0,0]
                    },
                    funk: {
                        name: "Funk",
                        beats: 16,
                        kick:   [1,0,0,1,0,0,1,0,0,0,1,0,0,0,0,0],
                        snare:  [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
                        hihat:  [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
                        accent: [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
                    },
                    jazz: {
                        name: "Jazz Swing",
                        beats: 12,
                        kick:   [1,0,0,0,0,0,1,0,0,0,0,0],
                        snare:  [0,0,0,0,0,0,0,0,0,0,0,0],
                        hihat:  [0,0,0,0,0,0,0,0,0,0,0,0],
                        accent: [1,0,0,0,0,0,0,0,0,0,0,0],
                        ride:   [1,0,1,1,0,1,1,0,1,1,0,1],
                        brush:  [0,0,0,1,0,0,0,0,0,1,0,0]
                    },
                    bossa: {
                        name: "Bossa Nova",
                        beats: 8,
                        kick:   [1,0,0,1,0,0,1,0],
                        snare:  [0,0,0,0,0,0,0,0],
                        hihat:  [1,0,1,0,1,0,1,0],
                        accent: [1,0,0,0,0,0,0,0],
                        rim:    [0,0,1,0,0,1,0,1]
                    },
                    metronome: {
                        name: "Metronome",
                        beats: 4,
                        kick:   [0,0,0,0],
                        snare:  [0,0,0,0],
                        hihat:  [1,1,1,1],
                        accent: [1,0,0,0]
                    }
                },
                
                initSynths: function() {
                    if (this.initialized) return;
                    
                    // Kick drum - punchy membrane synth
                    this.synths.kick = new Tone.MembraneSynth({
                        pitchDecay: 0.05,
                        octaves: 6,
                        oscillator: { type: 'sine' },
                        envelope: {
                            attack: 0.001,
                            decay: 0.3,
                            sustain: 0.01,
                            release: 0.5,
                            attackCurve: 'exponential'
                        }
                    }).toDestination();
                    
                    // Snare drum - noise + membrane combo
                    this.synths.snareNoise = new Tone.NoiseSynth({
                        noise: { type: 'white' },
                        envelope: {
                            attack: 0.001,
                            decay: 0.15,
                            sustain: 0,
                            release: 0.1
                        }
                    }).toDestination();
                    
                    this.synths.snareTone = new Tone.MembraneSynth({
                        pitchDecay: 0.008,
                        octaves: 2,
                        envelope: {
                            attack: 0.001,
                            decay: 0.1,
                            sustain: 0,
                            release: 0.1
                        }
                    }).toDestination();
                    
                    // Hi-hat - metallic noise
                    this.synths.hihat = new Tone.MetalSynth({
                        frequency: 250,
                        envelope: {
                            attack: 0.001,
                            decay: 0.05,
                            release: 0.01
                        },
                        harmonicity: 5.1,
                        modulationIndex: 32,
                        resonance: 4000,
                        octaves: 1.5
                    }).toDestination();
                    
                    // Open hi-hat - longer decay
                    this.synths.hihatOpen = new Tone.MetalSynth({
                        frequency: 250,
                        envelope: {
                            attack: 0.001,
                            decay: 0.3,
                            release: 0.1
                        },
                        harmonicity: 5.1,
                        modulationIndex: 32,
                        resonance: 4000,
                        octaves: 1.5
                    }).toDestination();
                    
                    // Ride cymbal - brighter, longer
                    this.synths.ride = new Tone.MetalSynth({
                        frequency: 300,
                        envelope: {
                            attack: 0.001,
                            decay: 0.6,
                            release: 0.2
                        },
                        harmonicity: 3.1,
                        modulationIndex: 16,
                        resonance: 5000,
                        octaves: 1
                    }).toDestination();
                    
                    // Rim shot - short, sharp
                    this.synths.rim = new Tone.MembraneSynth({
                        pitchDecay: 0.008,
                        octaves: 1,
                        oscillator: { type: 'square' },
                        envelope: {
                            attack: 0.001,
                            decay: 0.03,
                            sustain: 0,
                            release: 0.01
                        }
                    }).toDestination();
                    
                    // Brush/cross-stick for jazz
                    this.synths.brush = new Tone.NoiseSynth({
                        noise: { type: 'pink' },
                        envelope: {
                            attack: 0.01,
                            decay: 0.1,
                            sustain: 0,
                            release: 0.05
                        }
                    }).toDestination();
                    
                    // Click/accent for metronome
                    this.synths.click = new Tone.Synth({
                        oscillator: { type: 'sine' },
                        envelope: {
                            attack: 0.001,
                            decay: 0.05,
                            sustain: 0,
                            release: 0.01
                        }
                    }).toDestination();
                    
                    this.initialized = true;
                },
                
                setVolume: function(vol) {
                    const db = Tone.gainToDb(vol / 100);
                    for (const key in this.synths) {
                        if (this.synths[key] && this.synths[key].volume) {
                            this.synths[key].volume.value = db;
                        }
                    }
                },
                
                playSound: function(type, time) {
                    const t = time || Tone.now();
                    switch(type) {
                        case 'kick':
                            this.synths.kick.triggerAttackRelease('C1', '8n', t);
                            break;
                        case 'snare':
                            this.synths.snareNoise.triggerAttackRelease('8n', t);
                            this.synths.snareTone.triggerAttackRelease('E2', '16n', t);
                            break;
                        case 'hihat':
                            this.synths.hihat.triggerAttackRelease('16n', t, 0.3);
                            break;
                        case 'hihatOpen':
                            this.synths.hihatOpen.triggerAttackRelease('8n', t, 0.4);
                            break;
                        case 'ride':
                            this.synths.ride.triggerAttackRelease('8n', t, 0.25);
                            break;
                        case 'rim':
                            this.synths.rim.triggerAttackRelease('G4', '32n', t);
                            break;
                        case 'brush':
                            this.synths.brush.triggerAttackRelease('16n', t);
                            break;
                        case 'accent':
                            this.synths.click.triggerAttackRelease('G5', '32n', t);
                            break;
                        case 'click':
                            this.synths.click.triggerAttackRelease('C5', '32n', t);
                            break;
                    }
                },
                
                updateBeatIndicator: function(beat, totalBeats) {
                    const mappedBeat = Math.floor((beat / totalBeats) * 8);
                    for (let i = 0; i < 8; i++) {
                        const dot = document.querySelector('[id*="beat-indicator"][id*="\\"beat\\""][id*="\\"' + i + '\\""]');
                        if (!dot) {
                            // Try alternate selector
                            const dots = document.querySelectorAll('[id*="beat-indicator"]');
                            if (dots[i]) {
                                if (i === mappedBeat) {
                                    dots[i].style.backgroundColor = (beat === 0) ? '#ffc107' : '#28a745';
                                    dots[i].style.transform = 'scale(1.2)';
                                } else {
                                    dots[i].style.backgroundColor = '#444';
                                    dots[i].style.transform = 'scale(1)';
                                }
                            }
                        } else {
                            if (i === mappedBeat) {
                                dot.style.backgroundColor = (beat === 0) ? '#ffc107' : '#28a745';
                                dot.style.transform = 'scale(1.2)';
                            } else {
                                dot.style.backgroundColor = '#444';
                                dot.style.transform = 'scale(1)';
                            }
                        }
                    }
                },
                
                resetIndicators: function() {
                    const dots = document.querySelectorAll('[id*="beat-indicator"]');
                    dots.forEach(dot => {
                        dot.style.backgroundColor = '#444';
                        dot.style.transform = 'scale(1)';
                    });
                },
                
                stop: function() {
                    this.playing = false;
                    Tone.Transport.stop();
                    Tone.Transport.cancel();
                    this.currentBeat = 0;
                    this.resetIndicators();
                },
                
                play: async function(patternName, bpm, volume, useCountIn) {
                    // Start audio context
                    await Tone.start();
                    this.initSynths();
                    this.stop();
                    
                    const pat = this.patterns[patternName];
                    if (!pat) return;
                    
                    this.playing = true;
                    this.setVolume(volume);
                    
                    // Set tempo - adjust for subdivisions
                    const subdivision = pat.beats / 4; // 8 beats = 2 per quarter note
                    Tone.Transport.bpm.value = bpm * subdivision;
                    
                    const self = this;
                    let beat = 0;
                    
                    // Schedule the loop
                    this.loopId = Tone.Transport.scheduleRepeat((time) => {
                        if (!self.playing) return;
                        
                        const b = beat % pat.beats;
                        
                        // Play sounds
                        if (pat.accent && pat.accent[b]) self.playSound('accent', time);
                        if (pat.kick && pat.kick[b]) self.playSound('kick', time);
                        if (pat.snare && pat.snare[b]) self.playSound('snare', time);
                        if (pat.hihat && pat.hihat[b]) self.playSound('hihat', time);
                        if (pat.hihatOpen && pat.hihatOpen[b]) self.playSound('hihatOpen', time);
                        if (pat.rim && pat.rim[b]) self.playSound('rim', time);
                        if (pat.ride && pat.ride[b]) self.playSound('ride', time);
                        if (pat.brush && pat.brush[b]) self.playSound('brush', time);
                        
                        // Update visual on main thread
                        Tone.Draw.schedule(() => {
                            self.updateBeatIndicator(b, pat.beats);
                        }, time);
                        
                        beat++;
                    }, '8n');
                    
                    Tone.Transport.start();
                }
            };
        }
        
        // Handle button clicks
        const triggered = window.dash_clientside.callback_context.triggered;
        if (!triggered || triggered.length === 0) return '';
        
        const triggerId = triggered[0].prop_id.split('.')[0];
        
        if (triggerId === 'btn-drum-play') {
            const useCountIn = countIn && countIn.includes('countin');
            window.drumMachine.play(pattern, bpm, volume, useCountIn);
        } else if (triggerId === 'btn-drum-stop') {
            window.drumMachine.stop();
        }
        
        return '';
    }
    """,
    Output("drum-machine-output", "children"),
    Input("btn-drum-play", "n_clicks"),
    Input("btn-drum-stop", "n_clicks"),
    State("drum-pattern-select", "value"),
    State("drum-bpm-slider", "value"),
    State("drum-volume-slider", "value"),
    State("drum-count-in", "value"),
    prevent_initial_call=True
)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    print("🎸 Guitar Practice Studio")
    print(f"   Audio available: {AUDIO_AVAILABLE}")
    print(f"   Video available: {VIDEO_AVAILABLE}")
    print(f"   Data directory: {RECORDINGS_DIR.parent}")
    print("   Detecting devices...")
    cameras = recorder.get_available_cameras()
    audio_devs = recorder.get_available_audio_devices()
    print(f"   Cameras: {len(cameras)}")
    for c in cameras: print(f"      [{c['index']}] {c['name']}")
    print(f"   Audio inputs: {len(audio_devs)}")
    for a in audio_devs: print(f"      [{a['index']}] {a['name']}")
    print(f"   Starting server at http://{HOST}:{PORT}")
    app.run(debug=DEBUG, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
