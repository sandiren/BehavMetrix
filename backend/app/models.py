import datetime as dt
from typing import Optional

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class Animal(Base):
    __tablename__ = "animals"

    id = Column(Integer, primary_key=True, index=True)
    animal_id = Column(String(50), unique=True, nullable=False, index=True)
    cage_id = Column(String(50), nullable=False)
    sex = Column(Enum("M", "F", name="sex_enum"), nullable=False)
    age = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)
    welfare_score = Column(Float, nullable=True, default=0.0)
    social_rank = Column(Float, nullable=True, default=0.0)
    enrichment_status = Column(String(120), nullable=True)

    behavior_logs = relationship("BehaviorLog", back_populates="animal", cascade="all, delete-orphan")
    enrichment_logs = relationship("EnrichmentLog", back_populates="animal", cascade="all, delete-orphan")
    stress_logs = relationship("StressLog", back_populates="animal", cascade="all, delete-orphan")


class BehaviorLog(Base):
    __tablename__ = "behavior_logs"

    id = Column(Integer, primary_key=True)
    animal_id = Column(Integer, ForeignKey("animals.id"), index=True)
    timestamp = Column(DateTime, default=dt.datetime.utcnow, index=True)
    behavior = Column(String(50), nullable=False)
    intensity = Column(Integer, default=1)
    reason = Column(String(120), nullable=True)
    actor_id = Column(Integer, ForeignKey("animals.id"), nullable=True)
    target_id = Column(Integer, ForeignKey("animals.id"), nullable=True)

    animal = relationship("Animal", foreign_keys=[animal_id], back_populates="behavior_logs")


class EnrichmentLog(Base):
    __tablename__ = "enrichment_logs"

    id = Column(Integer, primary_key=True)
    animal_id = Column(Integer, ForeignKey("animals.id"), index=True)
    item = Column(String(120), nullable=False)
    category = Column(String(120), nullable=False)
    duration_minutes = Column(Float, nullable=True)
    frequency = Column(Integer, default=1)
    timestamp = Column(DateTime, default=dt.datetime.utcnow, index=True)

    animal = relationship("Animal", back_populates="enrichment_logs")


class StressLog(Base):
    __tablename__ = "stress_logs"

    id = Column(Integer, primary_key=True)
    animal_id = Column(Integer, ForeignKey("animals.id"), index=True)
    indicator = Column(String(120), nullable=False)
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=dt.datetime.utcnow, index=True)
    notes = Column(Text, nullable=True)

    animal = relationship("Animal", back_populates="stress_logs")


class WelfareScoreHistory(Base):
    __tablename__ = "welfare_scores"

    id = Column(Integer, primary_key=True)
    animal_id = Column(Integer, ForeignKey("animals.id"), index=True)
    timestamp = Column(DateTime, default=dt.datetime.utcnow, index=True)
    score = Column(Float, nullable=False)

    animal = relationship("Animal")
