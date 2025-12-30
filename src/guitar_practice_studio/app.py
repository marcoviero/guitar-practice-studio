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
    PRACTICE_CATEGORIES, PIECE_TYPES, PIECE_STATUSES
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
            # Reorder and remove buttons
            controls = html.Div([
                dbc.Button(
                    "↑", 
                    id={"type": "today-move-up", "entry": ex["entry_id"]},
                    size="sm", 
                    color="secondary", 
                    outline=True,
                    className="me-1 py-0 px-1",
                    disabled=(i == 0),
                    style={"fontSize": "0.7rem", "lineHeight": "1"}
                ),
                dbc.Button(
                    "↓", 
                    id={"type": "today-move-down", "entry": ex["entry_id"]},
                    size="sm", 
                    color="secondary", 
                    outline=True,
                    className="me-2 py-0 px-1",
                    disabled=(i == len(today_exercises) - 1),
                    style={"fontSize": "0.7rem", "lineHeight": "1"}
                ),
            ], className="d-inline-flex me-2")
            
            today_items.append(
                dbc.ListGroupItem([
                    controls,
                    dbc.Checkbox(
                        id={"type": "today-complete", "entry": ex["entry_id"]},
                        value=ex["completed"],
                        className="me-2"
                    ),
                    html.Span(
                        ex["name"], 
                        className="text-decoration-line-through flex-grow-1" if ex["completed"] else "flex-grow-1"
                    ),
                    dbc.Badge(f"{ex['duration']} min", color="secondary", className="ms-2"),
                    dbc.Badge(ex["category"], color="info", className="ms-1"),
                    dbc.Button(
                        "✕",
                        id={"type": "today-remove", "entry": ex["entry_id"], "exercise": ex["exercise_id"]},
                        size="sm",
                        color="danger",
                        outline=True,
                        className="ms-2 py-0 px-1",
                        style={"fontSize": "0.7rem", "lineHeight": "1"}
                    ),
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
    """Build the category grid cards - extracted for dynamic updates"""
    exercises_by_cat = get_exercises_by_category()
    entries = get_week_plan_entries(plan_id)
    category_targets = get_category_targets()
    
    # Build lookup: (exercise_id, day) -> entry exists
    scheduled = {(e.exercise_id, e.day_of_week) for e in entries}
    
    # Calculate totals per category per day: {category: {day: total_minutes}}
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
    
    # Create a card for each category with its exercise grid
    category_cards = []
    
    for category in PRACTICE_CATEGORIES:
        exercises = exercises_by_cat.get(category, [])
        if not exercises:
            continue
        
        target_mins = category_targets.get(category, 15)
        cat_daily = daily_totals.get(category, {})
        
        # Header with target info
        header_content = html.Div([
            html.H5(category, className="mb-0 d-inline"),
            dbc.Badge(f"Target: {target_mins} min/day", color="secondary", className="ms-2"),
        ])
        
        # Table header: Days as columns with per-day progress
        day_headers = [html.Th("Exercise", style={"minWidth": "150px"})]
        for day_idx, day_name in enumerate(DAY_NAMES):
            day_total = cat_daily.get(day_idx, 0)
            day_met = day_total >= target_mins
            
            # Style for header cell - green when target met
            header_style = {
                "width": "55px",
                "backgroundColor": "rgba(40, 167, 69, 0.35)" if day_met else "transparent",
                "textAlign": "center",
                "verticalAlign": "middle"
            }
            
            # Show day name and minutes scheduled
            header_text = html.Div([
                html.Div(day_name[:3], style={"fontWeight": "bold"}),
                html.Small(
                    f"{day_total}m", 
                    className="text-success" if day_met else "text-muted",
                    style={"fontSize": "0.75em"}
                )
            ])
            
            day_headers.append(html.Th(header_text, style=header_style))
        
        header = html.Thead(html.Tr(day_headers))
        
        # Table body: one row per exercise
        rows = []
        for ex in exercises:
            cells = [html.Td([
                ex.name,
                html.Small(f" ({ex.default_duration_minutes}m)", className="text-muted")
            ], className="text-nowrap")]
            
            for day_idx in range(7):
                is_checked = (ex.id, day_idx) in scheduled
                day_total = cat_daily.get(day_idx, 0)
                day_met = day_total >= target_mins
                
                checkbox = dbc.Checkbox(
                    id={"type": "plan-checkbox", "exercise": ex.id, "day": day_idx},
                    value=is_checked,
                    className="m-0"
                )
                
                # Cell style - highlight column if target met
                cell_style = {
                    "textAlign": "center",
                    "backgroundColor": "rgba(40, 167, 69, 0.15)" if day_met else "transparent"
                }
                
                cells.append(html.Td(checkbox, style=cell_style))
            rows.append(html.Tr(cells))
        
        body = html.Tbody(rows)
        
        table = dbc.Table(
            [header, body],
            bordered=True,
            hover=True,
            size="sm",
            className="mb-0"
        )
        
        card = dbc.Card([
            dbc.CardHeader(header_content),
            dbc.CardBody(table, className="p-2")
        ], className="mb-3")
        
        category_cards.append(card)
    
    return category_cards


def create_planner_page():
    """Weekly planner page with exercise grid by category"""
    plan_id, week_start = get_or_create_current_week_plan()
    
    # Week navigation
    week_end = week_start + timedelta(days=6)
    week_nav = dbc.Row([
        dbc.Col([
            dbc.Button("← Prev Week", id="btn-prev-week", color="secondary", size="sm"),
        ], width="auto"),
        dbc.Col([
            html.H4(f"Week of {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}", 
                   className="text-center mb-0"),
        ]),
        dbc.Col([
            dbc.Button("Next Week →", id="btn-next-week", color="secondary", size="sm"),
        ], width="auto"),
    ], className="mb-4 align-items-center")
    
    return dbc.Container([
        html.H2("Weekly Planner", className="mb-3"),
        
        # Store current plan ID
        dcc.Store(id="current-plan-id", data=plan_id),
        
        # Today's summary (dynamic)
        html.Div(_build_today_card(plan_id), id="today-card-container"),
        
        # Week navigation
        week_nav,
        
        # Category grids (dynamic)
        html.Div(_build_category_grids(plan_id), id="planner-grids"),
        
    ], fluid=True, className="py-3")


# ============================================================================
# REPERTOIRE PAGE
# ============================================================================

def create_repertoire_page():
    """Repertoire management page for songs, etudes, and suites"""
    pieces = get_all_repertoire()
    
    # Group by status
    by_status = {}
    for piece in pieces:
        status = piece.status or "Learning"
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(piece)
    
    # Create table for each status group
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
                    dbc.Button("Edit", id={"type": "edit-piece", "id": piece.id}, 
                              size="sm", color="secondary", className="me-1"),
                    dbc.Button("✓", id={"type": "advance-piece", "id": piece.id},
                              size="sm", color="success", className="me-1",
                              title="Advance to next status"),
                    dbc.Button("🗑", id={"type": "delete-piece", "id": piece.id},
                              size="sm", color="danger", outline=True),
                ])
            ])
            rows.append(row)
        
        table = dbc.Table([
            html.Thead(html.Tr([
                html.Th("Title"),
                html.Th("Artist/Composer"),
                html.Th("Type"),
                html.Th("Difficulty"),
                html.Th("Genre"),
                html.Th("Actions", style={"width": "150px"})
            ])),
            html.Tbody(rows) if rows else html.Tbody([
                html.Tr([html.Td("No pieces in this category", colSpan=6, className="text-muted text-center")])
            ])
        ], bordered=True, hover=True, size="sm")
        
        # Color code by status
        status_colors = {
            "Learning": "warning",
            "Review": "info",
            "Mastered": "success",
            "Want to Learn": "secondary"
        }
        
        card = dbc.Card([
            dbc.CardHeader([
                html.H5(status, className="mb-0 d-inline"),
                dbc.Badge(str(len(status_pieces)), color=status_colors.get(status, "secondary"), className="ms-2")
            ]),
            dbc.CardBody(table, className="p-2")
        ], className="mb-3")
        
        status_tables.append(card)
    
    # Add new piece form
    add_form = dbc.Card([
        dbc.CardHeader(html.H5("Add New Piece", className="mb-0")),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Title *"),
                    dbc.Input(id="new-piece-title", placeholder="Song/Etude title")
                ], md=4),
                dbc.Col([
                    dbc.Label("Artist/Composer"),
                    dbc.Input(id="new-piece-artist", placeholder="Artist or composer")
                ], md=4),
                dbc.Col([
                    dbc.Label("Type"),
                    dcc.Dropdown(
                        id="new-piece-type",
                        options=[{"label": t, "value": t} for t in PIECE_TYPES],
                        value="Song",
                        clearable=False
                    )
                ], md=4),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Genre"),
                    dbc.Input(id="new-piece-genre", placeholder="e.g., Rock, Classical, Blues")
                ], md=3),
                dbc.Col([
                    dbc.Label("Difficulty (1-5)"),
                    dcc.Slider(
                        id="new-piece-difficulty",
                        min=1, max=5, step=1, value=3,
                        marks={i: str(i) for i in range(1, 6)}
                    )
                ], md=3),
                dbc.Col([
                    dbc.Label("Status"),
                    dcc.Dropdown(
                        id="new-piece-status",
                        options=[{"label": s, "value": s} for s in PIECE_STATUSES if s != "Archived"],
                        value="Learning",
                        clearable=False
                    )
                ], md=3),
                dbc.Col([
                    dbc.Label("Link (optional)"),
                    dbc.Input(id="new-piece-link", placeholder="YouTube, tab URL, etc.")
                ], md=3),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Notes"),
                    dbc.Textarea(id="new-piece-notes", placeholder="Any notes about this piece...", rows=2)
                ])
            ], className="mb-3"),
            dbc.Button("Add to Repertoire", id="btn-add-piece", color="primary")
        ])
    ], className="mb-4")
    
    return dbc.Container([
        html.H2("Repertoire", className="mb-3"),
        html.P("Manage your songs, etudes, and suites. Pieces here will appear in the Songs section of your practice planner.",
              className="text-muted mb-4"),
        
        # Add form
        add_form,
        
        # Status message
        html.Div(id="repertoire-status", className="mb-3"),
        
        # Pieces by status
        html.Div(status_tables, id="repertoire-tables"),
        
    ], fluid=True, className="py-3")


def create_record_page():
    """Recording page with today's practice checklist and optional timer"""
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
    
    # Get today's exercises from planner
    plan_id, _ = get_or_create_current_week_plan()
    today_exercises = get_today_exercises(plan_id)
    
    # Build today's checklist for sidebar
    if today_exercises:
        checklist_items = []
        for ex in today_exercises:
            checklist_items.append(
                dbc.ListGroupItem([
                    dbc.Checkbox(
                        id={"type": "practice-complete", "entry": ex["entry_id"]},
                        value=ex["completed"],
                        className="me-2"
                    ),
                    html.Span(
                        ex["name"],
                        className="text-decoration-line-through" if ex["completed"] else "",
                        style={"flex": "1"}
                    ),
                    dbc.Badge(f"{ex['duration']}m", color="secondary", className="ms-auto"),
                ], className="d-flex align-items-center py-2")
            )
        total_mins = sum(ex["duration"] for ex in today_exercises)
        completed_mins = sum(ex["duration"] for ex in today_exercises if ex["completed"])
        
        today_checklist = html.Div([
            dbc.Progress(
                value=(completed_mins / total_mins * 100) if total_mins > 0 else 0,
                label=f"{completed_mins}/{total_mins} min",
                className="mb-3",
                color="success" if completed_mins >= total_mins else "primary"
            ),
            dbc.ListGroup(checklist_items, flush=True)
        ])
    else:
        today_checklist = html.P(
            "No exercises scheduled. Visit the Planner to set up your practice routine!",
            className="text-muted"
        )
    
    return dbc.Container([
        dbc.Row([
            # Main content area
            dbc.Col([
                html.H3("Practice Session", className="mb-4"),
                
                # Practice Timer Card (countdown)
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("Practice Timer", className="me-auto"),
                        dbc.Checklist(
                            id="timer-sync-recording",
                            options=[{"label": " Sync with recording", "value": "sync"}],
                            value=[],
                            inline=True,
                            className="ms-2 small"
                        ),
                    ], className="d-flex align-items-center"),
                    dbc.CardBody([
                        # Timer duration setting
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    dbc.Button("−", id="btn-timer-minus", color="secondary", 
                                              outline=True, size="sm", className="me-2"),
                                    dbc.Input(
                                        id="timer-duration-input",
                                        type="number",
                                        value=5,
                                        min=1,
                                        max=120,
                                        style={"width": "70px", "display": "inline-block", "textAlign": "center"}
                                    ),
                                    html.Span(" min", className="ms-1 me-2"),
                                    dbc.Button("+", id="btn-timer-plus", color="secondary", 
                                              outline=True, size="sm"),
                                ], className="d-flex align-items-center justify-content-center mb-3")
                            ])
                        ]),
                        # Timer display
                        html.Div(
                            id="practice-timer-display",
                            className="display-3 text-center font-monospace mb-3",
                            children="05:00"
                        ),
                        dbc.ButtonGroup([
                            dbc.Button("▶ Start", id="btn-timer-start", color="success", outline=True),
                            dbc.Button("⏸ Pause", id="btn-timer-pause", color="warning", outline=True, disabled=True),
                            dbc.Button("⏹ Reset", id="btn-timer-reset", color="secondary", outline=True),
                        ], className="w-100"),
                    ])
                ], className="mb-4"),
                
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
                
                # Device selection (collapsible, open by default)
                dbc.Card([
                    dbc.CardHeader(
                        dbc.Button(
                            "▼ Recording Devices",
                            id="collapse-devices-btn",
                            color="link",
                            className="p-0 text-decoration-none"
                        )
                    ),
                    dbc.Collapse(
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
                        ]),
                        id="collapse-devices",
                        is_open=True
                    ),
                ], className="mb-4"),
                
                # Recording controls
                dbc.Card([
                    dbc.CardHeader("Recording (Optional)"),
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
                        
                        dcc.Loading(
                            id="loading-record",
                            type="default",
                            children=[
                                dbc.ButtonGroup([
                                    dbc.Button("⏺ Start Recording", id="btn-start-record", color="danger", size="lg"),
                                    dbc.Button("⏹ Stop & Save", id="btn-stop-record", color="primary", size="lg", disabled=True),
                                    dbc.Button("🗑 Stop & Discard", id="btn-stop-discard", color="secondary", size="lg", disabled=True),
                                ], className="w-100"),
                                
                                # Status message
                                html.Div(id="record-status", className="mt-3 text-center"),
                            ]
                        ),
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
            
            # Sidebar
            dbc.Col([
                # Today's Practice checklist
                dbc.Card([
                    dbc.CardHeader([
                        "Today's Practice",
                        dbc.Badge(
                            f"{len([e for e in today_exercises if e['completed']])}/{len(today_exercises)}",
                            color="success" if all(e["completed"] for e in today_exercises) and today_exercises else "primary",
                            className="ms-2"
                        ) if today_exercises else None
                    ]),
                    dbc.CardBody(today_checklist, id="practice-today-checklist"),
                ], className="mb-4"),
                
                # Quick links
                dbc.Card([
                    dbc.CardHeader("Quick Links"),
                    dbc.CardBody([
                        dbc.Nav([
                            dbc.NavItem(dbc.NavLink("📅 Weekly Planner", href="/planner")),
                            dbc.NavItem(dbc.NavLink("🎵 Repertoire", href="/repertoire")),
                            dbc.NavItem(dbc.NavLink("🔍 Review Recordings", href="/review")),
                        ], vertical=True, pills=True)
                    ])
                ]),
            ], lg=4),
        ]),
        
        # Interval for timer updates
        dcc.Interval(id="timer-interval", interval=1000, disabled=True),
        
        # Interval for practice timer
        dcc.Interval(id="practice-timer-interval", interval=1000, disabled=True),
        
        # Store for recording state
        dcc.Store(id="recording-state", data={"is_recording": False, "start_time": None, "result": None}),
        
        # Store for practice timer state
        dcc.Store(id="practice-timer-state", data={"running": False, "remaining_seconds": 300, "duration_seconds": 300, "last_tick": None}),
        
        # Store for device selections
        dcc.Store(id="device-state", data={"camera": 0, "audio": None}),
        
        # Store plan ID for checklist updates
        dcc.Store(id="practice-plan-id", data=plan_id),
    ])


def create_journal_page():
    """Practice journal with weekly overview and daily details"""
    today = date.today()
    # Get current week (Monday start)
    week_start = today - timedelta(days=today.weekday())
    
    return dbc.Container([
        html.H3("Practice Journal", className="mb-4"),
        
        # Week selector and overview
        dbc.Card([
            dbc.CardBody([
                # Week navigation
                dbc.Row([
                    dbc.Col([
                        dbc.Button("← Prev", id="journal-prev-week", size="sm", color="secondary"),
                    ], width="auto"),
                    dbc.Col([
                        html.H5(id="journal-week-label", className="text-center mb-0"),
                    ]),
                    dbc.Col([
                        dbc.Button("Next →", id="journal-next-week", size="sm", color="secondary"),
                    ], width="auto"),
                ], className="mb-3 align-items-center"),
                
                # Week overview - clickable days
                html.Div(id="journal-week-overview"),
            ])
        ], className="mb-4"),
        
        # Selected day details
        html.Div(id="journal-day-details"),
        
        # Store for selected date and week
        dcc.Store(id="journal-selected-date", data=today.isoformat()),
        dcc.Store(id="journal-week-start", data=week_start.isoformat()),
    ])


def _build_week_overview(week_start: date, selected_date: date) -> html.Div:
    """Build the week overview row with clickable days"""
    from .database import get_week_summary
    
    week_summary = get_week_summary(week_start)
    day_buttons = []
    
    for i, day_data in enumerate(week_summary):
        day = day_data["date"]
        mins = day_data["total_minutes"]
        is_selected = day == selected_date
        is_today = day == date.today()
        is_future = day > date.today()
        
        # Determine style
        if is_selected:
            color = "primary"
            outline = False
        elif is_future:
            color = "secondary"
            outline = True
        elif mins > 0:
            color = "success"
            outline = True
        else:
            color = "secondary"
            outline = True
        
        day_btn = dbc.Col([
            dbc.Button(
                html.Div([
                    html.Div(DAY_NAMES[i][:3], style={"fontWeight": "bold"}),
                    html.Div(day.strftime("%d"), style={"fontSize": "1.2em"}),
                    html.Div(f"{mins}m" if mins > 0 else "—", 
                            style={"fontSize": "0.8em"}, 
                            className="text-muted" if outline else ""),
                ]),
                id={"type": "journal-day-btn", "date": day.isoformat()},
                color=color,
                outline=outline,
                className="w-100 py-2" + (" border-warning border-2" if is_today else ""),
                disabled=is_future
            )
        ], className="px-1")
        day_buttons.append(day_btn)
    
    return dbc.Row(day_buttons, className="g-1")


def _build_day_details(target_date: date) -> html.Div:
    """Build the detailed view for a specific day"""
    from .database import get_daily_summary
    
    summary = get_daily_summary(target_date)
    is_today = target_date == date.today()
    is_future = target_date > date.today()
    
    if is_future:
        return dbc.Alert("Select a past or current day to view practice details.", color="info")
    
    # Group completed exercises by category
    exercises_by_cat = {}
    for ex in summary["completed_exercises"]:
        cat = ex["category"]
        if cat not in exercises_by_cat:
            exercises_by_cat[cat] = []
        exercises_by_cat[cat].append(ex)
    
    # Build sections
    sections = []
    
    # Header with date and total
    date_str = target_date.strftime("%A, %B %d, %Y")
    header = dbc.Row([
        dbc.Col([
            html.H5(date_str, className="mb-0"),
            html.Small("Today" if is_today else "", className="text-muted"),
        ]),
        dbc.Col([
            dbc.Badge(f"Total: {summary['total_minutes']} min", 
                     color="success" if summary['total_minutes'] > 0 else "secondary",
                     className="fs-6")
        ], width="auto"),
    ], className="mb-3 align-items-center")
    sections.append(header)
    
    # Completed exercises from planner
    if exercises_by_cat:
        ex_section = dbc.Card([
            dbc.CardHeader("From Planner", className="py-2"),
            dbc.CardBody([
                html.Div([
                    html.Div([
                        dbc.Badge(cat, color="info", className="me-2"),
                        html.Span(f"{sum(e['duration'] for e in exs)} min — "),
                        html.Span(", ".join(e["name"] for e in exs), className="text-muted"),
                    ], className="mb-2")
                    for cat, exs in exercises_by_cat.items()
                ])
            ], className="py-2")
        ], className="mb-3")
        sections.append(ex_section)
    
    # Recordings
    if summary["recordings"]:
        rec_items = []
        for rec in summary["recordings"]:
            badges = []
            if rec["has_video"]:
                badges.append(dbc.Badge("🎬 Video", color="info", className="me-1"))
            elif rec["has_recording"]:
                badges.append(dbc.Badge("🎵 Audio", color="secondary", className="me-1"))
            if rec["rating"]:
                badges.append(html.Span("⭐" * rec["rating"], className="ms-1"))
            
            rec_items.append(
                dbc.ListGroupItem([
                    html.Div([
                        html.Strong(rec["title"] or "Untitled"),
                        *badges,
                        html.Span(f" • {rec['duration'] or 0} min", className="text-muted"),
                    ]),
                    html.Small(rec["notes"], className="text-muted") if rec["notes"] else None,
                    dbc.Button("Review →", href="/review", size="sm", color="link", className="p-0 float-end")
                ])
            )
        
        rec_section = dbc.Card([
            dbc.CardHeader("Recordings", className="py-2"),
            dbc.CardBody([
                dbc.ListGroup(rec_items, flush=True)
            ], className="p-0")
        ], className="mb-3")
        sections.append(rec_section)
    
    # Manual practice entries
    manual_items = []
    for m in summary["manual_entries"]:
        manual_items.append(
            dbc.ListGroupItem([
                dbc.Row([
                    dbc.Col([
                        dbc.Badge(m["category"] or "Other", color="secondary", className="me-2"),
                        html.Span(f"{m['duration']} min"),
                        html.Span(f" — {m['description']}" if m['description'] else "", className="text-muted"),
                    ]),
                    dbc.Col([
                        dbc.Button("✎", id={"type": "edit-manual", "id": m["id"]}, 
                                  size="sm", color="link", className="p-0 me-2"),
                        dbc.Button("🗑", id={"type": "delete-manual", "id": m["id"]}, 
                                  size="sm", color="link", className="p-0 text-danger"),
                    ], width="auto"),
                ], className="align-items-center")
            ])
        )
    
    # Add entry form
    add_form = dbc.Row([
        dbc.Col([
            dcc.Dropdown(
                id="manual-category",
                options=[{"label": c, "value": c} for c in PRACTICE_CATEGORIES],
                placeholder="Category",
                className="mb-2 mb-md-0"
            ),
        ], md=3),
        dbc.Col([
            dbc.Input(id="manual-duration", type="number", min=1, placeholder="Min", 
                     style={"width": "80px"}),
        ], md=2),
        dbc.Col([
            dbc.Input(id="manual-description", placeholder="What did you practice?"),
        ], md=5),
        dbc.Col([
            dbc.Button("+ Add", id="btn-add-manual", color="success", size="sm"),
        ], md=2),
    ], className="g-2 mt-2")
    
    manual_section = dbc.Card([
        dbc.CardHeader("Additional Practice", className="py-2"),
        dbc.CardBody([
            dbc.ListGroup(manual_items, flush=True) if manual_items else html.P("No manual entries", className="text-muted mb-2"),
            add_form,
            html.Div(id="manual-status", className="mt-2"),
        ])
    ], className="mb-3")
    sections.append(manual_section)
    
    # Daily notes
    notes_section = dbc.Card([
        dbc.CardHeader("Daily Notes", className="py-2"),
        dbc.CardBody([
            dbc.Textarea(
                id="journal-notes",
                value=summary["journal_notes"] or "",
                placeholder="How did practice go today? Any insights or things to work on?",
                rows=3,
                className="mb-2"
            ),
            dbc.Button("Save Notes", id="btn-save-notes", color="primary", size="sm"),
            html.Span(id="notes-status", className="ms-2 text-muted"),
        ])
    ], className="mb-3")
    sections.append(notes_section)
    
    return html.Div(sections)


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
    if pathname == "/planner":
        return create_planner_page()
    elif pathname == "/repertoire":
        return create_repertoire_page()
    elif pathname == "/journal":
        return create_journal_page()
    elif pathname == "/review":
        return create_review_page()
    elif pathname == "/stats":
        return create_stats_page()
    else:
        return create_record_page()


# --- Planner callbacks ---

@callback(
    Output("today-card-container", "children"),
    Output("planner-grids", "children"),
    Input({"type": "plan-checkbox", "exercise": ALL, "day": ALL}, "value"),
    State({"type": "plan-checkbox", "exercise": ALL, "day": ALL}, "id"),
    State("current-plan-id", "data"),
    prevent_initial_call=True
)
def handle_plan_checkbox(values, ids, plan_id):
    """Handle checkbox changes in the planner grid - updates UI dynamically"""
    if not ctx.triggered_id or not plan_id:
        return dash.no_update, dash.no_update
    
    # Find which checkbox was changed
    triggered = ctx.triggered_id
    exercise_id = triggered["exercise"]
    day = triggered["day"]
    
    # Find the new value
    for i, id_dict in enumerate(ids):
        if id_dict["exercise"] == exercise_id and id_dict["day"] == day:
            new_value = values[i]
            break
    else:
        return dash.no_update, dash.no_update
    
    # Update database
    set_plan_entry(plan_id, exercise_id, day, new_value)
    
    # Return updated components
    return _build_today_card(plan_id), _build_category_grids(plan_id)


@callback(
    Output({"type": "today-complete", "entry": MATCH}, "value"),
    Input({"type": "today-complete", "entry": MATCH}, "value"),
    State({"type": "today-complete", "entry": MATCH}, "id"),
    prevent_initial_call=True
)
def handle_today_complete(value, id_dict):
    """Handle completion checkbox for today's exercises"""
    entry_id = id_dict["entry"]
    toggle_entry_completed(entry_id, value)
    return value


@callback(
    Output("today-card-container", "children", allow_duplicate=True),
    Input({"type": "today-move-up", "entry": ALL}, "n_clicks"),
    State({"type": "today-move-up", "entry": ALL}, "id"),
    State("current-plan-id", "data"),
    prevent_initial_call=True
)
def handle_move_up(n_clicks_list, ids, plan_id):
    """Move an exercise up in today's list"""
    if not ctx.triggered_id or not any(n for n in n_clicks_list if n) or not plan_id:
        return dash.no_update
    
    entry_id = ctx.triggered_id["entry"]
    reorder_today_entry(entry_id, "up")
    return _build_today_card(plan_id)


@callback(
    Output("today-card-container", "children", allow_duplicate=True),
    Input({"type": "today-move-down", "entry": ALL}, "n_clicks"),
    State({"type": "today-move-down", "entry": ALL}, "id"),
    State("current-plan-id", "data"),
    prevent_initial_call=True
)
def handle_move_down(n_clicks_list, ids, plan_id):
    """Move an exercise down in today's list"""
    if not ctx.triggered_id or not any(n for n in n_clicks_list if n) or not plan_id:
        return dash.no_update
    
    entry_id = ctx.triggered_id["entry"]
    reorder_today_entry(entry_id, "down")
    return _build_today_card(plan_id)


@callback(
    Output("today-card-container", "children", allow_duplicate=True),
    Output("planner-grids", "children", allow_duplicate=True),
    Input({"type": "today-remove", "entry": ALL, "exercise": ALL}, "n_clicks"),
    State({"type": "today-remove", "entry": ALL, "exercise": ALL}, "id"),
    State("current-plan-id", "data"),
    prevent_initial_call=True
)
def handle_remove_today(n_clicks_list, ids, plan_id):
    """Remove an exercise from today's schedule"""
    if not ctx.triggered_id or not any(n for n in n_clicks_list if n) or not plan_id:
        return dash.no_update, dash.no_update
    
    exercise_id = ctx.triggered_id["exercise"]
    remove_today_entry(plan_id, exercise_id)
    
    # Update both today's card and grids (checkbox needs to uncheck)
    return _build_today_card(plan_id), _build_category_grids(plan_id)


# --- Repertoire callbacks ---

@callback(
    Output("repertoire-status", "children"),
    Output("new-piece-title", "value"),
    Output("new-piece-artist", "value"),
    Output("new-piece-genre", "value"),
    Output("new-piece-link", "value"),
    Output("new-piece-notes", "value"),
    Input("btn-add-piece", "n_clicks"),
    State("new-piece-title", "value"),
    State("new-piece-artist", "value"),
    State("new-piece-type", "value"),
    State("new-piece-genre", "value"),
    State("new-piece-difficulty", "value"),
    State("new-piece-status", "value"),
    State("new-piece-link", "value"),
    State("new-piece-notes", "value"),
    prevent_initial_call=True
)
def add_piece(n_clicks, title, artist, piece_type, genre, difficulty, status, link, notes):
    """Add a new piece to the repertoire"""
    if not title:
        return dbc.Alert("Please enter a title", color="warning"), dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    add_repertoire_piece(
        title=title,
        artist=artist,
        piece_type=piece_type,
        genre=genre,
        difficulty=difficulty,
        status=status,
        link=link,
        notes=notes
    )
    
    return (
        dbc.Alert(f"Added '{title}' to repertoire!", color="success", duration=3000),
        "",  # Clear title
        "",  # Clear artist
        "",  # Clear genre
        "",  # Clear link
        ""   # Clear notes
    )


@callback(
    Output("url", "pathname", allow_duplicate=True),
    Input({"type": "advance-piece", "id": ALL}, "n_clicks"),
    State({"type": "advance-piece", "id": ALL}, "id"),
    prevent_initial_call=True
)
def advance_piece_status(n_clicks_list, ids):
    """Advance a piece to the next status"""
    if not ctx.triggered_id or not any(n_clicks_list):
        return dash.no_update
    
    piece_id = ctx.triggered_id["id"]
    
    # Get current status and advance
    db = get_session()
    piece = db.query(RepertoirePiece).get(piece_id)
    if piece:
        status_order = ["Want to Learn", "Learning", "Review", "Mastered"]
        current_idx = status_order.index(piece.status) if piece.status in status_order else 0
        if current_idx < len(status_order) - 1:
            new_status = status_order[current_idx + 1]
            piece.status = new_status
            if new_status == "Learning" and not piece.date_started:
                piece.date_started = date.today()
            elif new_status == "Mastered":
                piece.date_mastered = date.today()
            db.commit()
    db.close()
    
    return "/repertoire"  # Refresh page


@callback(
    Output("url", "pathname", allow_duplicate=True),
    Input({"type": "delete-piece", "id": ALL}, "n_clicks"),
    State({"type": "delete-piece", "id": ALL}, "id"),
    prevent_initial_call=True
)
def delete_piece(n_clicks_list, ids):
    """Delete a piece from repertoire"""
    if not ctx.triggered_id or not any(n_clicks_list):
        return dash.no_update
    
    piece_id = ctx.triggered_id["id"]
    delete_repertoire_piece(piece_id)
    
    return "/repertoire"  # Refresh page


# --- Practice Page callbacks ---

@callback(
    Output("collapse-devices", "is_open"),
    Output("collapse-devices-btn", "children"),
    Input("collapse-devices-btn", "n_clicks"),
    State("collapse-devices", "is_open"),
    prevent_initial_call=True
)
def toggle_devices_collapse(n_clicks, is_open):
    """Toggle the devices section collapse"""
    new_state = not is_open
    icon = "▼" if new_state else "▶"
    return new_state, f"{icon} Recording Devices"


@callback(
    Output("timer-duration-input", "value"),
    Input("btn-timer-minus", "n_clicks"),
    Input("btn-timer-plus", "n_clicks"),
    State("timer-duration-input", "value"),
    prevent_initial_call=True
)
def adjust_timer_duration(minus_clicks, plus_clicks, current_value):
    """Adjust timer duration with +/- buttons"""
    if current_value is None:
        current_value = 5
    
    triggered = ctx.triggered_id
    if triggered == "btn-timer-minus":
        return max(1, current_value - 1)
    elif triggered == "btn-timer-plus":
        return min(120, current_value + 1)
    return current_value


@callback(
    Output("practice-timer-display", "children"),
    Output("practice-timer-display", "style"),
    Output("practice-timer-state", "data"),
    Output("btn-timer-start", "disabled"),
    Output("btn-timer-pause", "disabled"),
    Output("btn-timer-start", "children"),
    Output("practice-timer-interval", "disabled"),
    Input("btn-timer-start", "n_clicks"),
    Input("btn-timer-pause", "n_clicks"),
    Input("btn-timer-reset", "n_clicks"),
    Input("practice-timer-interval", "n_intervals"),
    Input("timer-duration-input", "value"),
    Input("btn-start-record", "n_clicks"),
    Input("btn-stop-record", "n_clicks"),
    Input("btn-stop-discard", "n_clicks"),
    State("practice-timer-state", "data"),
    State("timer-sync-recording", "value"),
    prevent_initial_call=True
)
def handle_practice_timer(start_clicks, pause_clicks, reset_clicks, n_intervals,
                          duration_input, rec_start, rec_stop, rec_discard,
                          timer_state, sync_options):
    """Handle countdown timer with optional sync to recording"""
    import time
    
    triggered = ctx.triggered_id
    sync_with_recording = "sync" in (sync_options or [])
    
    # Default state
    if timer_state is None:
        timer_state = {
            "running": False, 
            "remaining_seconds": (duration_input or 5) * 60,
            "duration_seconds": (duration_input or 5) * 60,
            "last_tick": None
        }
    
    running = timer_state.get("running", False)
    remaining = timer_state.get("remaining_seconds", 300)
    duration = timer_state.get("duration_seconds", 300)
    last_tick = timer_state.get("last_tick")
    
    # Handle duration input change (reset timer to new duration)
    if triggered == "timer-duration-input":
        new_duration = (duration_input or 5) * 60
        return (
            f"{duration_input or 5:02d}:00",
            {},
            {"running": False, "remaining_seconds": new_duration, "duration_seconds": new_duration, "last_tick": None},
            False,  # start enabled
            True,   # pause disabled
            "▶ Start",
            True    # interval disabled
        )
    
    # Handle recording sync
    if sync_with_recording:
        if triggered == "btn-start-record":
            running = True
            last_tick = time.time()
        elif triggered in ["btn-stop-record", "btn-stop-discard"]:
            running = False
            last_tick = None
    
    # Handle timer buttons
    if triggered == "btn-timer-start":
        if not running and remaining > 0:
            running = True
            last_tick = time.time()
    elif triggered == "btn-timer-pause":
        running = False
        last_tick = None
    elif triggered == "btn-timer-reset":
        running = False
        remaining = duration
        last_tick = None
    
    # Update remaining time on interval tick
    if triggered == "practice-timer-interval" and running and last_tick:
        now = time.time()
        elapsed_since_tick = now - last_tick
        remaining = max(0, remaining - elapsed_since_tick)
        last_tick = now
        
        # Auto-stop when timer reaches zero
        if remaining <= 0:
            running = False
            remaining = 0
            last_tick = None
    
    # Format display
    mins = int(remaining // 60)
    secs = int(remaining % 60)
    display = f"{mins:02d}:{secs:02d}"
    
    # Style - flash red when time's up
    style = {"color": "#dc3545"} if remaining == 0 else {}
    
    # Button states
    start_disabled = running or remaining == 0
    pause_disabled = not running
    if remaining == 0:
        start_text = "✓ Done"
    elif remaining < duration and not running:
        start_text = "▶ Resume"
    else:
        start_text = "▶ Start"
    interval_disabled = not running
    
    new_state = {
        "running": running,
        "remaining_seconds": remaining,
        "duration_seconds": duration,
        "last_tick": last_tick
    }
    
    return display, style, new_state, start_disabled, pause_disabled, start_text, interval_disabled


@callback(
    Output({"type": "practice-complete", "entry": MATCH}, "value"),
    Input({"type": "practice-complete", "entry": MATCH}, "value"),
    State({"type": "practice-complete", "entry": MATCH}, "id"),
    prevent_initial_call=True
)
def handle_practice_complete(value, id_dict):
    """Handle completion checkbox for today's exercises on Practice page"""
    entry_id = id_dict["entry"]
    toggle_entry_completed(entry_id, value)
    return value


# --- Recording callbacks ---

@callback(
    Output("recording-state", "data"),
    Output("btn-start-record", "disabled"),
    Output("btn-stop-record", "disabled"),
    Output("btn-stop-discard", "disabled"),
    Output("record-status", "children"),
    Output("post-record-form", "style"),
    Output("recording-preview", "children"),
    Input("btn-start-record", "n_clicks"),
    Input("btn-stop-record", "n_clicks"),
    Input("btn-stop-discard", "n_clicks"),
    Input("btn-discard-retry", "n_clicks"),
    Input("btn-discard", "n_clicks"),
    State("record-options", "value"),
    State("recording-state", "data"),
    State("camera-select", "value"),
    State("audio-select", "value"),
    prevent_initial_call=True
)
def handle_recording(start_clicks, stop_clicks, stop_discard_clicks, retry_clicks, discard_clicks, 
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
            True,   # disable start
            False,  # enable stop
            False,  # enable stop & discard
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
            True,   # disable stop
            True,   # disable stop & discard
            dbc.Alert(f"Recording complete: {result['duration_seconds']:.1f}s — Review below", color="success") if result else dbc.Alert("Recording failed", color="danger"),
            {"display": "block"},
            preview
        )
    
    elif triggered == "btn-stop-discard":
        # Stop recording and discard immediately
        result = recorder.stop()
        _delete_recording_files(result)
        
        return (
            {"is_recording": False, "start_time": None, "result": None},
            False,  # enable start
            True,   # disable stop
            True,   # disable stop & discard
            dbc.Alert("Recording discarded", color="secondary"),
            {"display": "none"},
            None
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
            True,   # disable start
            False,  # enable stop
            False,  # enable stop & discard
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
            False,  # enable start
            True,   # disable stop
            True,   # disable stop & discard
            dbc.Alert("Recording discarded", color="secondary"),
            {"display": "none"},
            None
        )
    
    return (dash.no_update,) * 7


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


# --- Journal callbacks ---

@callback(
    Output("journal-week-label", "children"),
    Output("journal-week-overview", "children"),
    Output("journal-day-details", "children"),
    Output("journal-selected-date", "data"),
    Output("journal-week-start", "data"),
    Input("journal-prev-week", "n_clicks"),
    Input("journal-next-week", "n_clicks"),
    Input({"type": "journal-day-btn", "date": ALL}, "n_clicks"),
    Input("url", "pathname"),
    State("journal-selected-date", "data"),
    State("journal-week-start", "data"),
    prevent_initial_call=False
)
def update_journal_view(prev_clicks, next_clicks, day_clicks, pathname,
                        selected_date_str, week_start_str):
    """Handle week navigation and day selection"""
    if pathname != "/journal":
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Parse stored dates
    today = date.today()
    
    if selected_date_str:
        selected_date = date.fromisoformat(selected_date_str)
    else:
        selected_date = today
    
    if week_start_str:
        week_start = date.fromisoformat(week_start_str)
    else:
        week_start = today - timedelta(days=today.weekday())
    
    triggered = ctx.triggered_id
    
    # Handle week navigation
    if triggered == "journal-prev-week":
        week_start = week_start - timedelta(days=7)
        selected_date = week_start  # Select Monday of new week
    elif triggered == "journal-next-week":
        new_week_start = week_start + timedelta(days=7)
        if new_week_start <= today:
            week_start = new_week_start
            selected_date = week_start
    elif isinstance(triggered, dict) and triggered.get("type") == "journal-day-btn":
        selected_date = date.fromisoformat(triggered["date"])
    
    # Build week label
    week_end = week_start + timedelta(days=6)
    week_label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"
    
    # Build components
    week_overview = _build_week_overview(week_start, selected_date)
    day_details = _build_day_details(selected_date)
    
    return week_label, week_overview, day_details, selected_date.isoformat(), week_start.isoformat()


@callback(
    Output("manual-status", "children"),
    Output("journal-day-details", "children", allow_duplicate=True),
    Input("btn-add-manual", "n_clicks"),
    State("manual-category", "value"),
    State("manual-duration", "value"),
    State("manual-description", "value"),
    State("journal-selected-date", "data"),
    prevent_initial_call=True
)
def add_manual_entry(n_clicks, category, duration, description, selected_date_str):
    """Add a manual practice entry"""
    if not n_clicks:
        return dash.no_update, dash.no_update
    
    if not category or not duration:
        return dbc.Alert("Please select a category and enter duration", color="warning", duration=3000), dash.no_update
    
    selected_date = date.fromisoformat(selected_date_str) if selected_date_str else date.today()
    
    add_manual_practice(
        target_date=selected_date,
        category=category,
        duration_minutes=int(duration),
        description=description or ""
    )
    
    # Rebuild day details
    day_details = _build_day_details(selected_date)
    
    return dbc.Alert("✓ Added", color="success", duration=2000), day_details


@callback(
    Output("journal-day-details", "children", allow_duplicate=True),
    Input({"type": "delete-manual", "id": ALL}, "n_clicks"),
    State({"type": "delete-manual", "id": ALL}, "id"),
    State("journal-selected-date", "data"),
    prevent_initial_call=True
)
def delete_manual_entry(n_clicks_list, ids, selected_date_str):
    """Delete a manual practice entry"""
    if not ctx.triggered_id or not any(n for n in n_clicks_list if n):
        return dash.no_update
    
    entry_id = ctx.triggered_id["id"]
    delete_manual_practice(entry_id)
    
    selected_date = date.fromisoformat(selected_date_str) if selected_date_str else date.today()
    return _build_day_details(selected_date)


@callback(
    Output("notes-status", "children"),
    Input("btn-save-notes", "n_clicks"),
    State("journal-notes", "value"),
    State("journal-selected-date", "data"),
    prevent_initial_call=True
)
def save_journal_notes(n_clicks, notes, selected_date_str):
    """Save daily journal notes"""
    if not n_clicks:
        return dash.no_update
    
    selected_date = date.fromisoformat(selected_date_str) if selected_date_str else date.today()
    save_daily_notes(selected_date, notes or "")
    
    return "✓ Saved"


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
            className="bg-dark text-light border-secondary",
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
    
    # Show detected devices
    print("   Detecting devices...")
    cameras = recorder.get_available_cameras()
    audio_devs = recorder.get_available_audio_devices()
    print(f"   Cameras: {len(cameras)}")
    for c in cameras:
        print(f"      [{c['index']}] {c['name']}")
    print(f"   Audio inputs: {len(audio_devs)}")
    for a in audio_devs:
        print(f"      [{a['index']}] {a['name']}")
    
    print(f"   Starting server at http://{HOST}:{PORT}")
    
    app.run(debug=DEBUG, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
