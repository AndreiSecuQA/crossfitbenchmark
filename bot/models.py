from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float,
    ForeignKey, Integer, String, Text, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(64))
    first_name = Column(String(128), nullable=False)
    height_cm = Column(Float)
    language = Column(String(4), default="en", nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    weights = relationship("Weight", back_populates="user", order_by="Weight.measured_at")
    measurements = relationship("Measurement", back_populates="user")
    user_sessions = relationship("UserSession", back_populates="user")

    @property
    def latest_weight(self):
        return self.weights[-1].weight_kg if self.weights else None


class Weight(Base):
    __tablename__ = "weights"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    weight_kg = Column(Float, nullable=False)
    measured_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="weights")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    custom_message = Column(Text)
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reminder_sent_at = Column(DateTime)

    admin = relationship("User")
    user_sessions = relationship("UserSession", back_populates="session")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(16), default="pending", nullable=False)  # pending/in_progress/completed
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    __table_args__ = (UniqueConstraint("session_id", "user_id"),)

    session = relationship("Session", back_populates="user_sessions")
    user = relationship("User", back_populates="user_sessions")
    measurements = relationship("Measurement", back_populates="user_session")


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True)
    key = Column(String(32), unique=True, nullable=False)
    measurement_type = Column(String(16), nullable=False)  # reps / seconds / distance_time
    sort_order = Column(Integer, default=0)

    measurements = relationship("Measurement", back_populates="exercise")


class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True)
    user_session_id = Column(Integer, ForeignKey("user_sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    value_reps = Column(Integer)
    value_seconds = Column(Integer)
    value_distance_m = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user_session = relationship("UserSession", back_populates="measurements")
    user = relationship("User", back_populates="measurements")
    exercise = relationship("Exercise", back_populates="measurements")
