"""
Database models and operations for Guitar Practice Studio
"""
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, Float, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from .config import DATABASE_PATH

Base = declarative_base()
engine = create_engine(f"sqlite:///{DATABASE_PATH}", echo=False)
Session = sessionmaker(bind=engine)


class PracticeSession(Base):
    """A single practice session with optional recording"""
    __tablename__ = "practice_sessions"
    
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.now)
    date = Column(Date, default=date.today)
    
    # What was practiced
    title = Column(String(200))
    category = Column(String(50))  # From PRACTICE_CATEGORIES
    description = Column(Text)
    
    # Duration tracking
    duration_minutes = Column(Integer)  # Actual practice time
    
    # Recording info (optional)
    has_recording = Column(Boolean, default=False)
    recording_filename = Column(String(255))  # Base filename (audio/video use same base)
    has_video = Column(Boolean, default=False)
    
    # Self-assessment
    notes = Column(Text)  # Post-practice reflection
    rating = Column(Integer)  # 1-5 how it went
    
    # Relationships
    annotations = relationship("Annotation", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PracticeSession {self.id}: {self.title} ({self.date})>"


class Annotation(Base):
    """Time-stamped annotations on recordings"""
    __tablename__ = "annotations"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("practice_sessions.id"))
    
    timestamp_seconds = Column(Float)  # Position in recording
    text = Column(Text)
    annotation_type = Column(String(50))  # "issue", "good", "question", "note"
    
    created_at = Column(DateTime, default=datetime.now)
    
    session = relationship("PracticeSession", back_populates="annotations")
    
    def __repr__(self):
        return f"<Annotation @{self.timestamp_seconds}s: {self.text[:30]}>"


class Goal(Base):
    """Practice goals (weekly/monthly)"""
    __tablename__ = "goals"
    
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.now)
    
    title = Column(String(200))
    description = Column(Text)
    category = Column(String(50))
    
    # Timeframe
    goal_type = Column(String(20))  # "weekly", "monthly", "ongoing"
    start_date = Column(Date)
    end_date = Column(Date)
    
    # Target
    target_minutes = Column(Integer)  # Optional: target practice time
    target_sessions = Column(Integer)  # Optional: target number of sessions
    
    # Status
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime)
    completion_notes = Column(Text)
    
    def __repr__(self):
        return f"<Goal {self.id}: {self.title}>"


class Exercise(Base):
    """A specific exercise that can be practiced"""
    __tablename__ = "exercises"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)  # Technique, Chord Perfect, Songs, Ear Training, Theory, Transcribing
    description = Column(Text)
    default_duration_minutes = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)  # Can hide exercises without deleting
    sort_order = Column(Integer, default=0)
    
    # Relationships
    plan_entries = relationship("WeeklyPlanEntry", back_populates="exercise")
    
    def __repr__(self):
        return f"<Exercise {self.id}: {self.name} ({self.category})>"


class WeeklyPlan(Base):
    """A weekly practice plan"""
    __tablename__ = "weekly_plans"
    
    id = Column(Integer, primary_key=True)
    week_start = Column(Date, nullable=False)  # Monday of the week
    name = Column(String(100))  # Optional name like "Technique Focus Week"
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    entries = relationship("WeeklyPlanEntry", back_populates="plan", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<WeeklyPlan {self.id}: week of {self.week_start}>"


class WeeklyPlanEntry(Base):
    """A single exercise scheduled for a specific day"""
    __tablename__ = "weekly_plan_entries"
    
    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("weekly_plans.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    duration_minutes = Column(Integer)  # Override default if set
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime)
    sort_order = Column(Integer, default=0)  # Order within the day
    
    # Relationships
    plan = relationship("WeeklyPlan", back_populates="entries")
    exercise = relationship("Exercise", back_populates="plan_entries")
    
    def __repr__(self):
        return f"<WeeklyPlanEntry {self.exercise_id} on day {self.day_of_week}>"


class RepertoirePiece(Base):
    """A song, etude, or suite in the repertoire"""
    __tablename__ = "repertoire"
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    artist = Column(String(200))  # Artist/Composer
    piece_type = Column(String(50))  # Song, Etude, Suite, Exercise, etc.
    genre = Column(String(50))
    difficulty = Column(Integer)  # 1-5
    status = Column(String(50), default="Learning")  # Learning, Review, Mastered, Archived
    notes = Column(Text)
    link = Column(String(500))  # YouTube, tab link, etc.
    date_added = Column(Date, default=date.today)
    date_started = Column(Date)
    date_mastered = Column(Date)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<RepertoirePiece {self.id}: {self.title}>"


# Database operations
def init_db():
    """Create all tables and run migrations"""
    Base.metadata.create_all(engine)
    
    # Run migrations for schema changes
    _run_migrations()


def _run_migrations():
    """Add missing columns to existing tables"""
    import sqlite3
    from .config import DATABASE_PATH
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Check if sort_order column exists in weekly_plan_entries
    cursor.execute("PRAGMA table_info(weekly_plan_entries)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if columns and "sort_order" not in columns:
        print("Migration: Adding sort_order column to weekly_plan_entries...")
        cursor.execute("ALTER TABLE weekly_plan_entries ADD COLUMN sort_order INTEGER DEFAULT 0")
        conn.commit()
        print("Migration complete.")
    
    # Check if repertoire table exists (new table)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='repertoire'")
    if not cursor.fetchone():
        print("Migration: Creating repertoire table...")
        cursor.execute("""
            CREATE TABLE repertoire (
                id INTEGER PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                artist VARCHAR(200),
                piece_type VARCHAR(50),
                genre VARCHAR(50),
                difficulty INTEGER,
                status VARCHAR(50) DEFAULT 'Learning',
                notes TEXT,
                link VARCHAR(500),
                date_added DATE,
                date_started DATE,
                date_mastered DATE,
                is_active BOOLEAN DEFAULT 1,
                sort_order INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        print("Migration complete.")
    
    conn.close()


def get_session():
    """Get a new database session"""
    return Session()


# Convenience functions
def create_practice_session(
    title: str,
    category: str,
    duration_minutes: int,
    description: str = "",
    notes: str = "",
    rating: int = None,
    recording_filename: str = None,
    has_video: bool = False
) -> PracticeSession:
    """Create a new practice session"""
    session = get_session()
    practice = PracticeSession(
        title=title,
        category=category,
        duration_minutes=duration_minutes,
        description=description,
        notes=notes,
        rating=rating,
        has_recording=recording_filename is not None,
        recording_filename=recording_filename,
        has_video=has_video
    )
    session.add(practice)
    session.commit()
    session.refresh(practice)
    return practice


def get_recent_sessions(limit: int = 20) -> List[PracticeSession]:
    """Get most recent practice sessions"""
    session = get_session()
    return session.query(PracticeSession).order_by(
        PracticeSession.created_at.desc()
    ).limit(limit).all()


def get_sessions_by_date_range(start: date, end: date) -> List[PracticeSession]:
    """Get sessions within a date range"""
    session = get_session()
    return session.query(PracticeSession).filter(
        PracticeSession.date >= start,
        PracticeSession.date <= end
    ).order_by(PracticeSession.date.desc()).all()


def add_annotation(session_id: int, timestamp: float, text: str, ann_type: str = "note") -> Annotation:
    """Add an annotation to a session's recording"""
    session = get_session()
    annotation = Annotation(
        session_id=session_id,
        timestamp_seconds=timestamp,
        text=text,
        annotation_type=ann_type
    )
    session.add(annotation)
    session.commit()
    return annotation


def get_active_goals() -> List[Goal]:
    """Get all non-completed goals"""
    session = get_session()
    return session.query(Goal).filter(Goal.is_completed == False).all()


def get_practice_stats(start: date, end: date) -> dict:
    """Get practice statistics for a date range"""
    session = get_session()
    sessions = session.query(PracticeSession).filter(
        PracticeSession.date >= start,
        PracticeSession.date <= end
    ).all()
    
    total_minutes = sum(s.duration_minutes or 0 for s in sessions)
    by_category = {}
    for s in sessions:
        cat = s.category or "Uncategorized"
        by_category[cat] = by_category.get(cat, 0) + (s.duration_minutes or 0)
    
    return {
        "total_sessions": len(sessions),
        "total_minutes": total_minutes,
        "by_category": by_category,
        "avg_rating": sum(s.rating for s in sessions if s.rating) / len([s for s in sessions if s.rating]) if any(s.rating for s in sessions) else None
    }


# ============================================================================
# EXERCISE AND WEEKLY PLAN FUNCTIONS
# ============================================================================

PRACTICE_CATEGORIES = [
    "Technique",
    "Chord Perfect",
    "Songs",
    "Ear Training",
    "Theory",
    "Transcribing"
]

# Category targets (default, can be overridden by TOML)
CATEGORY_TARGETS = {
    "Technique": 15,
    "Chord Perfect": 10,
    "Songs": 20,
    "Ear Training": 10,
    "Theory": 10,
    "Transcribing": 15,
}


def load_exercises_config():
    """Load exercises and category config from TOML file"""
    import tomllib
    from pathlib import Path
    
    # Look for exercises.toml in several locations
    possible_paths = [
        Path(__file__).parent.parent.parent / "exercises.toml",  # Project root
        Path.home() / ".guitar-practice-studio" / "exercises.toml",  # User config
        Path(__file__).parent / "exercises.toml",  # Package dir
    ]
    
    for toml_path in possible_paths:
        if toml_path.exists():
            with open(toml_path, "rb") as f:
                return tomllib.load(f)
    
    return None


def get_category_targets() -> dict:
    """Get target minutes per category from config"""
    config = load_exercises_config()
    if config and "categories" in config:
        targets = {}
        for key, cat_config in config["categories"].items():
            if "name" in cat_config and "target_minutes" in cat_config:
                targets[cat_config["name"]] = cat_config["target_minutes"]
        if targets:
            return targets
    return CATEGORY_TARGETS


def init_default_exercises():
    """Initialize exercises from TOML config or defaults"""
    from datetime import timedelta
    db = get_session()
    
    # Check if exercises already exist
    if db.query(Exercise).count() > 0:
        db.close()
        return
    
    # Try to load from TOML
    config = load_exercises_config()
    
    if config and "exercises" in config:
        exercises_data = config["exercises"]
        print(f"Loading {len(exercises_data)} exercises from exercises.toml")
    else:
        # Fallback defaults
        exercises_data = [
            {"name": "Spider Exercise", "category": "Technique", "duration": 5},
            {"name": "One Minute Changes", "category": "Chord Perfect", "duration": 5},
            {"name": "New Piece - Learning", "category": "Songs", "duration": 15},
            {"name": "Interval Recognition", "category": "Ear Training", "duration": 5},
            {"name": "Fretboard Notes", "category": "Theory", "duration": 5},
            {"name": "Transcribe Melody", "category": "Transcribing", "duration": 10},
        ]
        print("Using default exercises (exercises.toml not found)")
    
    for i, ex in enumerate(exercises_data):
        exercise = Exercise(
            name=ex["name"],
            category=ex["category"],
            default_duration_minutes=ex.get("duration", ex.get("default_duration_minutes", 5)),
            description=ex.get("description", ""),
            sort_order=i
        )
        db.add(exercise)
    
    db.commit()
    db.close()
    print(f"Initialized {len(exercises_data)} exercises")


def get_or_create_current_week_plan() -> tuple:
    """Get or create the plan for the current week. Returns (plan_id, week_start_date)"""
    from datetime import timedelta
    db = get_session()
    
    # Find Monday of current week
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    
    plan = db.query(WeeklyPlan).filter(WeeklyPlan.week_start == monday).first()
    
    if not plan:
        plan = WeeklyPlan(week_start=monday)
        db.add(plan)
        db.commit()
        db.refresh(plan)
    
    plan_id = plan.id
    db.close()
    return plan_id, monday


def get_all_exercises() -> List[Exercise]:
    """Get all active exercises grouped by category"""
    db = get_session()
    exercises = db.query(Exercise).filter(Exercise.is_active == True).order_by(
        Exercise.category, Exercise.sort_order
    ).all()
    db.close()
    return exercises


def get_exercises_by_category() -> dict:
    """Get exercises organized by category"""
    exercises = get_all_exercises()
    by_category = {}
    for ex in exercises:
        if ex.category not in by_category:
            by_category[ex.category] = []
        by_category[ex.category].append(ex)
    return by_category


def get_week_plan_entries(plan_id: int) -> List[WeeklyPlanEntry]:
    """Get all entries for a week plan"""
    db = get_session()
    entries = db.query(WeeklyPlanEntry).filter(
        WeeklyPlanEntry.plan_id == plan_id
    ).all()
    db.close()
    return entries


def get_week_category_totals(plan_id: int) -> dict:
    """Get total scheduled minutes per category for the week"""
    db = get_session()
    entries = db.query(WeeklyPlanEntry).filter(
        WeeklyPlanEntry.plan_id == plan_id
    ).all()
    
    totals = {}
    for entry in entries:
        exercise = db.query(Exercise).get(entry.exercise_id)
        if exercise:
            cat = exercise.category
            duration = entry.duration_minutes or exercise.default_duration_minutes
            totals[cat] = totals.get(cat, 0) + duration
    
    db.close()
    return totals


def set_plan_entry(plan_id: int, exercise_id: int, day_of_week: int, enabled: bool):
    """Add or remove an exercise from a day in the plan"""
    db = get_session()
    
    existing = db.query(WeeklyPlanEntry).filter(
        WeeklyPlanEntry.plan_id == plan_id,
        WeeklyPlanEntry.exercise_id == exercise_id,
        WeeklyPlanEntry.day_of_week == day_of_week
    ).first()
    
    if enabled and not existing:
        # Add entry
        entry = WeeklyPlanEntry(
            plan_id=plan_id,
            exercise_id=exercise_id,
            day_of_week=day_of_week
        )
        db.add(entry)
    elif not enabled and existing:
        # Remove entry
        db.delete(existing)
    
    db.commit()
    db.close()


def toggle_entry_completed(entry_id: int, completed: bool):
    """Mark an entry as completed or not"""
    db = get_session()
    entry = db.query(WeeklyPlanEntry).get(entry_id)
    if entry:
        entry.completed = completed
        entry.completed_at = datetime.now() if completed else None
        db.commit()
    db.close()


def get_today_exercises(plan_id: int) -> List[dict]:
    """Get exercises scheduled for today with completion status, ordered by sort_order"""
    db = get_session()
    today_dow = date.today().weekday()  # 0=Monday
    
    entries = db.query(WeeklyPlanEntry).filter(
        WeeklyPlanEntry.plan_id == plan_id,
        WeeklyPlanEntry.day_of_week == today_dow
    ).order_by(WeeklyPlanEntry.sort_order).all()
    
    result = []
    for entry in entries:
        exercise = db.query(Exercise).get(entry.exercise_id)
        if exercise:
            result.append({
                "entry_id": entry.id,
                "exercise_id": exercise.id,
                "name": exercise.name,
                "category": exercise.category,
                "duration": entry.duration_minutes or exercise.default_duration_minutes,
                "completed": entry.completed,
                "sort_order": entry.sort_order
            })
    
    db.close()
    return result


def reorder_today_entry(entry_id: int, direction: str):
    """Move an entry up or down in today's list. direction is 'up' or 'down'"""
    db = get_session()
    entry = db.query(WeeklyPlanEntry).get(entry_id)
    if not entry:
        db.close()
        return
    
    # Get all entries for the same day, ordered
    entries = db.query(WeeklyPlanEntry).filter(
        WeeklyPlanEntry.plan_id == entry.plan_id,
        WeeklyPlanEntry.day_of_week == entry.day_of_week
    ).order_by(WeeklyPlanEntry.sort_order).all()
    
    # Find current position
    current_idx = None
    for i, e in enumerate(entries):
        if e.id == entry_id:
            current_idx = i
            break
    
    if current_idx is None:
        db.close()
        return
    
    # Calculate new position
    if direction == "up" and current_idx > 0:
        swap_idx = current_idx - 1
    elif direction == "down" and current_idx < len(entries) - 1:
        swap_idx = current_idx + 1
    else:
        db.close()
        return
    
    # Swap sort_order values
    entries[current_idx].sort_order, entries[swap_idx].sort_order = \
        entries[swap_idx].sort_order, entries[current_idx].sort_order
    
    db.commit()
    db.close()


def remove_today_entry(plan_id: int, exercise_id: int):
    """Remove an exercise from today's schedule"""
    db = get_session()
    today_dow = date.today().weekday()
    
    entry = db.query(WeeklyPlanEntry).filter(
        WeeklyPlanEntry.plan_id == plan_id,
        WeeklyPlanEntry.exercise_id == exercise_id,
        WeeklyPlanEntry.day_of_week == today_dow
    ).first()
    
    if entry:
        db.delete(entry)
        db.commit()
    
    db.close()


# ============================================================================
# REPERTOIRE FUNCTIONS
# ============================================================================

PIECE_TYPES = ["Song", "Etude", "Suite", "Riff", "Exercise", "Other"]
PIECE_STATUSES = ["Want to Learn", "Learning", "Review", "Mastered", "Archived"]


def get_all_repertoire(include_archived: bool = False) -> List[RepertoirePiece]:
    """Get all repertoire pieces"""
    db = get_session()
    query = db.query(RepertoirePiece)
    if not include_archived:
        query = query.filter(RepertoirePiece.status != "Archived")
    pieces = query.order_by(RepertoirePiece.status, RepertoirePiece.sort_order).all()
    db.close()
    return pieces


def get_repertoire_by_status(status: str) -> List[RepertoirePiece]:
    """Get repertoire pieces by status"""
    db = get_session()
    pieces = db.query(RepertoirePiece).filter(
        RepertoirePiece.status == status
    ).order_by(RepertoirePiece.sort_order).all()
    db.close()
    return pieces


def get_active_repertoire() -> List[RepertoirePiece]:
    """Get pieces that are actively being worked on (Learning or Review)"""
    db = get_session()
    pieces = db.query(RepertoirePiece).filter(
        RepertoirePiece.status.in_(["Learning", "Review"])
    ).order_by(RepertoirePiece.status, RepertoirePiece.sort_order).all()
    db.close()
    return pieces


def add_repertoire_piece(
    title: str,
    artist: str = None,
    piece_type: str = "Song",
    genre: str = None,
    difficulty: int = None,
    status: str = "Learning",
    notes: str = None,
    link: str = None
) -> RepertoirePiece:
    """Add a new piece to the repertoire"""
    db = get_session()
    piece = RepertoirePiece(
        title=title,
        artist=artist,
        piece_type=piece_type,
        genre=genre,
        difficulty=difficulty,
        status=status,
        notes=notes,
        link=link,
        date_started=date.today() if status == "Learning" else None
    )
    db.add(piece)
    db.commit()
    db.refresh(piece)
    piece_id = piece.id
    db.close()
    return piece_id


def update_repertoire_piece(piece_id: int, **kwargs):
    """Update a repertoire piece"""
    db = get_session()
    piece = db.query(RepertoirePiece).get(piece_id)
    if piece:
        for key, value in kwargs.items():
            if hasattr(piece, key):
                setattr(piece, key, value)
        # Auto-set dates based on status changes
        if "status" in kwargs:
            if kwargs["status"] == "Learning" and not piece.date_started:
                piece.date_started = date.today()
            elif kwargs["status"] == "Mastered" and not piece.date_mastered:
                piece.date_mastered = date.today()
        db.commit()
    db.close()


def delete_repertoire_piece(piece_id: int):
    """Delete a repertoire piece"""
    db = get_session()
    piece = db.query(RepertoirePiece).get(piece_id)
    if piece:
        db.delete(piece)
        db.commit()
    db.close()
