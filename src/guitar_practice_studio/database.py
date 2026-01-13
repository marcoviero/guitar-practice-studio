"""
Database models and operations for Guitar Practice Studio
"""
from datetime import datetime, date, timedelta
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
    recording_type = Column(String(50), default="Exercise")  # Performance, Exercise, Riff
    
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
    guitars = Column(String(200), default="all")  # Comma-separated: "classical,electric,steel" or "all"
    
    # Relationships
    plan_entries = relationship("WeeklyPlanEntry", back_populates="exercise")
    
    def matches_guitar(self, guitar_type: str) -> bool:
        """Check if this exercise applies to a guitar type"""
        if not self.guitars or self.guitars == "all":
            return True
        guitar_list = [g.strip().lower() for g in self.guitars.split(",")]
        return guitar_type.lower() in guitar_list or "all" in guitar_list
    
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


class ManualPractice(Base):
    """Manual practice entry for offline/unrecorded practice"""
    __tablename__ = "manual_practice"
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, default=date.today)
    category = Column(String(50))
    duration_minutes = Column(Integer, default=0)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<ManualPractice {self.id}: {self.date} - {self.category}>"


class DailyJournal(Base):
    """Daily practice journal notes"""
    __tablename__ = "daily_journal"
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True)
    notes = Column(Text)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<DailyJournal {self.date}>"


class BackingTrack(Base):
    """Saved YouTube backing tracks"""
    __tablename__ = "backing_tracks"
    
    id = Column(Integer, primary_key=True)
    url = Column(String(500), nullable=False)
    title = Column(String(300))  # User-provided title
    video_id = Column(String(20))  # YouTube video ID
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<BackingTrack {self.id}: {self.title or self.url}>"


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
    
    # Check if recording_type column exists in practice_sessions
    cursor.execute("PRAGMA table_info(practice_sessions)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if columns and "recording_type" not in columns:
        print("Migration: Adding recording_type column to practice_sessions...")
        cursor.execute("ALTER TABLE practice_sessions ADD COLUMN recording_type VARCHAR(50) DEFAULT 'Exercise'")
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
    
    # Check if guitars column exists in exercises
    cursor.execute("PRAGMA table_info(exercises)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if columns and "guitars" not in columns:
        print("Migration: Adding guitars column to exercises...")
        cursor.execute("ALTER TABLE exercises ADD COLUMN guitars VARCHAR(200) DEFAULT 'all'")
        conn.commit()
        print("Migration complete.")
    
    # Check if backing_tracks table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backing_tracks'")
    if not cursor.fetchone():
        print("Migration: Creating backing_tracks table...")
        cursor.execute("""
            CREATE TABLE backing_tracks (
                id INTEGER PRIMARY KEY,
                url VARCHAR(500) NOT NULL,
                title VARCHAR(300),
                video_id VARCHAR(20),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
    has_video: bool = False,
    recording_type: str = "Exercise"
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
        has_video=has_video,
        recording_type=recording_type
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
    "Knowledge",
    "Songs",
    "Ear Training",
    "Time/Rythm",
    "Improvisation"
]

# Category targets (default, can be overridden by TOML)
CATEGORY_TARGETS = {
    "Technique": 15,
    "Knowledge": 10,
    "Songs": 20,
    "Ear Training": 10,
    "Time/Rythm": 10,
    "Improvisation": 20,
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
    """Initialize or sync exercises from TOML config"""
    db = get_session()
    
    # Try to load from TOML
    config = load_exercises_config()
    
    if config and "exercises" in config:
        exercises_data = config["exercises"]
        print(f"Syncing {len(exercises_data)} exercises from exercises.toml")
    else:
        # Fallback defaults only if no TOML and no existing exercises
        if db.query(Exercise).count() > 0:
            db.close()
            return
        exercises_data = [
            {"name": "Spider Exercise", "category": "Technique", "duration": 5},
            {"name": "One Minute Changes", "category": "Technique", "duration": 5},
            {"name": "New Piece - Learning", "category": "Songs", "duration": 15},
            {"name": "Interval Recognition", "category": "Ear Training", "duration": 5},
            {"name": "Fretboard Notes", "category": "Knowledge", "duration": 5},
            {"name": "Improvisation", "category": "Improvisation", "duration": 10},
        ]
        print("Using default exercises (exercises.toml not found)")
    
    # Get existing exercises by name
    existing = {ex.name: ex for ex in db.query(Exercise).all()}
    
    updated = 0
    added = 0
    
    for i, ex in enumerate(exercises_data):
        name = ex["name"]
        category = ex["category"]
        duration = ex.get("duration", ex.get("default_duration_minutes", 5))
        description = ex.get("description", "")
        # Handle guitars - can be a list or string
        guitars_raw = ex.get("guitars", "all")
        if isinstance(guitars_raw, list):
            guitars = ",".join(guitars_raw)
        else:
            guitars = guitars_raw
        
        if name in existing:
            # Update existing exercise
            exercise = existing[name]
            if (exercise.category != category or 
                exercise.default_duration_minutes != duration or
                exercise.description != description or
                exercise.sort_order != i or
                exercise.guitars != guitars):
                exercise.category = category
                exercise.default_duration_minutes = duration
                exercise.description = description
                exercise.sort_order = i
                exercise.guitars = guitars
                updated += 1
        else:
            # Add new exercise
            exercise = Exercise(
                name=name,
                category=category,
                default_duration_minutes=duration,
                description=description,
                sort_order=i,
                guitars=guitars
            )
            db.add(exercise)
            added += 1
    
    # Remove exercises not in TOML
    toml_names = {ex["name"] for ex in exercises_data}
    removed = 0
    for name, exercise in existing.items():
        if name not in toml_names:
            # Also remove any plan entries referencing this exercise
            db.query(WeeklyPlanEntry).filter(WeeklyPlanEntry.exercise_id == exercise.id).delete()
            db.delete(exercise)
            removed += 1
    
    db.commit()
    db.close()
    
    if added or updated or removed:
        print(f"Exercises: {added} added, {updated} updated, {removed} removed")


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


def get_or_create_week_plan(week_start: date) -> int:
    """Get or create a plan for a specific week. Returns plan_id"""
    from datetime import timedelta
    db = get_session()
    
    # Ensure we have a Monday
    monday = week_start - timedelta(days=week_start.weekday())
    
    plan = db.query(WeeklyPlan).filter(WeeklyPlan.week_start == monday).first()
    
    if not plan:
        plan = WeeklyPlan(week_start=monday)
        db.add(plan)
        db.commit()
        db.refresh(plan)
    
    plan_id = plan.id
    db.close()
    return plan_id


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
RECORDING_TYPES = ["Performance", "Exercise", "Riff"]


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


# ============================================================================
# JOURNAL FUNCTIONS
# ============================================================================

def get_daily_summary(target_date: date) -> dict:
    """Get a complete summary of practice for a specific date"""
    db = get_session()
    
    # Get completed exercises from planner
    day_of_week = target_date.weekday()
    # Find the plan for the week containing target_date
    week_start = target_date - timedelta(days=day_of_week)
    
    plan = db.query(WeeklyPlan).filter(
        WeeklyPlan.week_start == week_start
    ).first()
    
    completed_exercises = []
    if plan:
        entries = db.query(WeeklyPlanEntry).filter(
            WeeklyPlanEntry.plan_id == plan.id,
            WeeklyPlanEntry.day_of_week == day_of_week,
            WeeklyPlanEntry.completed == True
        ).all()
        
        for entry in entries:
            exercise = db.query(Exercise).get(entry.exercise_id)
            if exercise:
                completed_exercises.append({
                    "name": exercise.name,
                    "category": exercise.category,
                    "duration": entry.duration_minutes or exercise.default_duration_minutes,
                    "completed_at": entry.completed_at
                })
    
    # Get recordings from PracticeSession
    recordings = db.query(PracticeSession).filter(
        PracticeSession.date == target_date
    ).all()
    
    recording_list = [{
        "id": r.id,
        "title": r.title,
        "category": r.category,
        "duration": r.duration_minutes,
        "has_recording": r.has_recording,
        "has_video": r.has_video,
        "recording_filename": r.recording_filename,
        "recording_type": r.recording_type,
        "rating": r.rating,
        "notes": r.notes
    } for r in recordings]
    
    # Get manual practice entries
    manual_entries = db.query(ManualPractice).filter(
        ManualPractice.date == target_date
    ).all()
    
    manual_list = [{
        "id": m.id,
        "category": m.category,
        "duration": m.duration_minutes,
        "description": m.description
    } for m in manual_entries]
    
    # Get daily journal notes
    journal = db.query(DailyJournal).filter(
        DailyJournal.date == target_date
    ).first()
    
    db.close()
    
    # Calculate totals by category
    category_totals = {}
    for ex in completed_exercises:
        cat = ex["category"]
        category_totals[cat] = category_totals.get(cat, 0) + ex["duration"]
    for m in manual_list:
        cat = m["category"] or "Other"
        category_totals[cat] = category_totals.get(cat, 0) + m["duration"]
    for r in recording_list:
        if r["duration"]:
            cat = r["category"] or "Other"
            category_totals[cat] = category_totals.get(cat, 0) + r["duration"]
    
    total_minutes = sum(category_totals.values())
    
    return {
        "date": target_date,
        "completed_exercises": completed_exercises,
        "recordings": recording_list,
        "manual_entries": manual_list,
        "journal_notes": journal.notes if journal else "",
        "category_totals": category_totals,
        "total_minutes": total_minutes
    }


def get_week_summary(week_start: date) -> List[dict]:
    """Get daily totals for a week (Mon-Sun)"""
    summaries = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        summary = get_daily_summary(day)
        summaries.append({
            "date": day,
            "total_minutes": summary["total_minutes"],
            "has_practice": summary["total_minutes"] > 0
        })
    return summaries


def save_daily_notes(target_date: date, notes: str):
    """Save or update daily journal notes"""
    db = get_session()
    journal = db.query(DailyJournal).filter(
        DailyJournal.date == target_date
    ).first()
    
    if journal:
        journal.notes = notes
        journal.updated_at = datetime.now()
    else:
        journal = DailyJournal(date=target_date, notes=notes)
        db.add(journal)
    
    db.commit()
    db.close()


def add_manual_practice(target_date: date, category: str, duration_minutes: int, description: str = "") -> int:
    """Add a manual practice entry"""
    db = get_session()
    entry = ManualPractice(
        date=target_date,
        category=category,
        duration_minutes=duration_minutes,
        description=description
    )
    db.add(entry)
    db.commit()
    entry_id = entry.id
    db.close()
    return entry_id


def update_manual_practice(entry_id: int, category: str = None, duration_minutes: int = None, description: str = None):
    """Update a manual practice entry"""
    db = get_session()
    entry = db.query(ManualPractice).get(entry_id)
    if entry:
        if category is not None:
            entry.category = category
        if duration_minutes is not None:
            entry.duration_minutes = duration_minutes
        if description is not None:
            entry.description = description
        db.commit()
    db.close()


def delete_manual_practice(entry_id: int):
    """Delete a manual practice entry"""
    db = get_session()
    entry = db.query(ManualPractice).get(entry_id)
    if entry:
        db.delete(entry)
        db.commit()
    db.close()


# Backing Track functions
def get_all_backing_tracks() -> List[BackingTrack]:
    """Get all saved backing tracks"""
    db = get_session()
    tracks = db.query(BackingTrack).order_by(BackingTrack.created_at.desc()).all()
    db.close()
    return tracks


def add_backing_track(url: str, title: str = None, video_id: str = None) -> int:
    """Add a new backing track"""
    db = get_session()
    track = BackingTrack(url=url, title=title, video_id=video_id)
    db.add(track)
    db.commit()
    track_id = track.id
    db.close()
    return track_id


def delete_backing_track(track_id: int):
    """Delete a backing track"""
    db = get_session()
    track = db.query(BackingTrack).get(track_id)
    if track:
        db.delete(track)
        db.commit()
    db.close()


def get_exercises_for_guitar(guitar_type: str) -> List[Exercise]:
    """Get all exercises that match a guitar type"""
    db = get_session()
    exercises = db.query(Exercise).filter(Exercise.is_active == True).order_by(
        Exercise.category, Exercise.sort_order
    ).all()
    # Filter by guitar type
    if guitar_type and guitar_type != "all":
        exercises = [ex for ex in exercises if ex.matches_guitar(guitar_type)]
    db.close()
    return exercises
