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


# Database operations
def init_db():
    """Create all tables"""
    Base.metadata.create_all(engine)


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
