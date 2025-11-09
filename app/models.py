from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import JSON, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import db, ma


class DataIngestionSession(db.Model):
    __tablename__ = "data_ingestion_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(nullable=False)
    notes: Mapped[Optional[str]]

    animals: Mapped[list[Animal]] = relationship("Animal", back_populates="ingestion_session")


class Animal(db.Model):
    __tablename__ = "animals"

    id: Mapped[int] = mapped_column(primary_key=True)
    persistent_id: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[Optional[str]]
    cage_id: Mapped[str] = mapped_column(index=True)
    sex: Mapped[str]
    age: Mapped[Optional[int]]
    weight_kg: Mapped[Optional[float]]
    species: Mapped[str] = mapped_column(default="Macaca mulatta")
    matriline: Mapped[Optional[str]]
    date_of_birth: Mapped[Optional[datetime]]
    photo_url: Mapped[Optional[str]]

    ingestion_session_id: Mapped[int | None] = mapped_column(db.ForeignKey("data_ingestion_sessions.id"))
    ingestion_session: Mapped[Optional[DataIngestionSession]] = relationship(
        "DataIngestionSession", back_populates="animals"
    )

    behavior_logs: Mapped[list[BehaviorLog]] = relationship("BehaviorLog", back_populates="animal")
    enrichment_logs: Mapped[list[EnrichmentLog]] = relationship("EnrichmentLog", back_populates="animal")
    stress_logs: Mapped[list[StressLog]] = relationship("StressLog", back_populates="animal")
    incidents: Mapped[list[IncidentObservation]] = relationship("IncidentObservation", back_populates="animal")
    rank_scores: Mapped[list[RankScore]] = relationship("RankScore", back_populates="animal")
    notes: Mapped[list[AnimalNote]] = relationship("AnimalNote", back_populates="animal")
    video_clips: Mapped[list[VideoClip]] = relationship("VideoClip", back_populates="animal")


class Observer(db.Model):
    __tablename__ = "observers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    affiliation: Mapped[Optional[str]]

    behavior_logs: Mapped[list[BehaviorLog]] = relationship("BehaviorLog", back_populates="observer")


class BehaviorCategory(db.Model):
    __tablename__ = "behavior_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    color: Mapped[str] = mapped_column(default="#0d6efd")
    description: Mapped[Optional[str]]
    icon: Mapped[Optional[str]]

    behaviors: Mapped[list[BehaviorDefinition]] = relationship("BehaviorDefinition", back_populates="category")


class BehaviorDefinition(db.Model):
    __tablename__ = "behavior_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[Optional[str]]
    ontology_reference: Mapped[Optional[str]]
    is_dyadic: Mapped[bool] = mapped_column(default=False)
    default_duration_seconds: Mapped[Optional[int]]
    keyboard_shortcut: Mapped[Optional[str]]
    category_id: Mapped[int | None] = mapped_column(db.ForeignKey("behavior_categories.id"))

    category: Mapped[Optional[BehaviorCategory]] = relationship("BehaviorCategory", back_populates="behaviors")
    logs: Mapped[list[BehaviorLog]] = relationship("BehaviorLog", back_populates="behavior")


class Ethogram(db.Model):
    __tablename__ = "ethograms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[Optional[str]]
    is_default: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    behaviors: Mapped[list[EthogramBehavior]] = relationship("EthogramBehavior", back_populates="ethogram")


class EthogramBehavior(db.Model):
    __tablename__ = "ethogram_behaviors"

    id: Mapped[int] = mapped_column(primary_key=True)
    ethogram_id: Mapped[int] = mapped_column(db.ForeignKey("ethograms.id"), nullable=False)
    behavior_id: Mapped[int] = mapped_column(db.ForeignKey("behavior_definitions.id"), nullable=False)
    display_name: Mapped[Optional[str]]
    color_override: Mapped[Optional[str]]
    is_active: Mapped[bool] = mapped_column(default=True)

    ethogram: Mapped[Ethogram] = relationship("Ethogram", back_populates="behaviors")
    behavior: Mapped[BehaviorDefinition] = relationship("BehaviorDefinition")


class BehaviorSession(db.Model):
    __tablename__ = "behavior_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[Optional[str]]
    mode: Mapped[str] = mapped_column(default="real_time")
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]]
    observer_id: Mapped[int | None] = mapped_column(db.ForeignKey("observers.id"))
    cage_id: Mapped[Optional[str]]
    group_label: Mapped[Optional[str]]
    notes: Mapped[Optional[str]]
    metadata: Mapped[dict | None] = mapped_column(JSON)

    observer: Mapped[Optional[Observer]] = relationship("Observer")
    logs: Mapped[list[BehaviorLog]] = relationship("BehaviorLog", back_populates="session")
    participants: Mapped[list[SessionParticipant]] = relationship("SessionParticipant", back_populates="session")


class SessionParticipant(db.Model):
    __tablename__ = "session_participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(db.ForeignKey("behavior_sessions.id"), nullable=False)
    animal_id: Mapped[int] = mapped_column(db.ForeignKey("animals.id"), nullable=False)

    session: Mapped[BehaviorSession] = relationship("BehaviorSession", back_populates="participants")
    animal: Mapped[Animal] = relationship("Animal")


class BehaviorLog(db.Model):
    __tablename__ = "behavior_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    context: Mapped[Optional[str]]
    sample_type: Mapped[str] = mapped_column(default="focal")
    mode: Mapped[str] = mapped_column(default="real_time")
    session_id: Mapped[int | None] = mapped_column(db.ForeignKey("behavior_sessions.id"))
    intensity: Mapped[Optional[int]]
    duration_seconds: Mapped[Optional[float]]
    metadata: Mapped[dict | None] = mapped_column(JSON)

    animal_id: Mapped[int] = mapped_column(db.ForeignKey("animals.id"))
    behavior_id: Mapped[int] = mapped_column(db.ForeignKey("behavior_definitions.id"))
    observer_id: Mapped[int | None] = mapped_column(db.ForeignKey("observers.id"))

    animal: Mapped[Animal] = relationship("Animal", back_populates="behavior_logs")
    behavior: Mapped[BehaviorDefinition] = relationship("BehaviorDefinition", back_populates="logs")
    observer: Mapped[Optional[Observer]] = relationship("Observer", back_populates="behavior_logs")

    interaction_partner_id: Mapped[int | None] = mapped_column(db.ForeignKey("animals.id"))
    interaction_partner: Mapped[Optional[Animal]] = relationship("Animal", foreign_keys=[interaction_partner_id])
    session: Mapped[Optional[BehaviorSession]] = relationship("BehaviorSession", back_populates="logs")


class EnrichmentItem(db.Model):
    __tablename__ = "enrichment_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[Optional[str]]
    category: Mapped[Optional[str]]
    success_indicator: Mapped[Optional[str]]
    delivery_method: Mapped[Optional[str]]
    default_duration: Mapped[Optional[int]]

    logs: Mapped[list[EnrichmentLog]] = relationship("EnrichmentLog", back_populates="item")


class EnrichmentLog(db.Model):
    __tablename__ = "enrichment_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    start_time: Mapped[Optional[datetime]]
    end_time: Mapped[Optional[datetime]]
    duration_minutes: Mapped[Optional[float]]
    response: Mapped[Optional[str]]
    outcome: Mapped[Optional[str]]
    notes: Mapped[Optional[str]]
    tag: Mapped[Optional[str]]
    frequency: Mapped[Optional[str]]
    metadata: Mapped[dict | None] = mapped_column(JSON)

    animal_id: Mapped[int] = mapped_column(db.ForeignKey("animals.id"))
    enrichment_item_id: Mapped[int] = mapped_column(db.ForeignKey("enrichment_items.id"))

    animal: Mapped[Animal] = relationship("Animal", back_populates="enrichment_logs")
    item: Mapped[EnrichmentItem] = relationship("EnrichmentItem", back_populates="logs")


class StressLog(db.Model):
    __tablename__ = "stress_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    stress_score: Mapped[int] = mapped_column(default=0)
    withdrawal: Mapped[bool] = mapped_column(default=False)
    fear_grimace: Mapped[bool] = mapped_column(default=False)
    pacing: Mapped[bool] = mapped_column(default=False)
    self_biting: Mapped[bool] = mapped_column(default=False)
    scratching: Mapped[bool] = mapped_column(default=False)
    vocalization: Mapped[bool] = mapped_column(default=False)
    linked_cortisol: Mapped[Optional[float]]
    notes: Mapped[Optional[str]]

    animal_id: Mapped[int] = mapped_column(db.ForeignKey("animals.id"))

    animal: Mapped[Animal] = relationship("Animal", back_populates="stress_logs")


class HormoneMeasurement(db.Model):
    __tablename__ = "hormone_measurements"

    id: Mapped[int] = mapped_column(primary_key=True)
    collected_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    hormone: Mapped[str] = mapped_column(default="cortisol")
    value: Mapped[float]
    unit: Mapped[str] = mapped_column(default="ng/mL")

    animal_id: Mapped[int] = mapped_column(db.ForeignKey("animals.id"))
    animal: Mapped[Animal] = relationship("Animal")


class IncidentObservation(db.Model):
    __tablename__ = "incident_observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    reason: Mapped[str]
    description: Mapped[Optional[str]]
    attachment_url: Mapped[Optional[str]]
    video_url: Mapped[Optional[str]]
    tags: Mapped[Optional[str]]

    animal_id: Mapped[int | None] = mapped_column(db.ForeignKey("animals.id"))
    animal: Mapped[Optional[Animal]] = relationship("Animal", back_populates="incidents")


class RankScore(db.Model):
    __tablename__ = "rank_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    elo_score: Mapped[float] = mapped_column(default=1000.0)
    davids_score: Mapped[Optional[float]]
    instability_flag: Mapped[bool] = mapped_column(default=False)
    alert_flag: Mapped[bool] = mapped_column(default=False)
    source: Mapped[Optional[str]]
    session_id: Mapped[int | None] = mapped_column(db.ForeignKey("behavior_sessions.id"))

    animal_id: Mapped[int] = mapped_column(db.ForeignKey("animals.id"), nullable=False)
    animal: Mapped[Animal] = relationship("Animal", back_populates="rank_scores")
    session: Mapped[Optional[BehaviorSession]] = relationship("BehaviorSession")


class VoiceTranscript(db.Model):
    __tablename__ = "voice_transcripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int | None] = mapped_column(db.ForeignKey("behavior_sessions.id"))
    transcript_text: Mapped[str]
    confidence: Mapped[Optional[float]]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    processed: Mapped[bool] = mapped_column(default=False)

    session: Mapped[Optional[BehaviorSession]] = relationship("BehaviorSession")


class VideoClip(db.Model):
    __tablename__ = "video_clips"

    id: Mapped[int] = mapped_column(primary_key=True)
    animal_id: Mapped[int | None] = mapped_column(db.ForeignKey("animals.id"))
    session_id: Mapped[int | None] = mapped_column(db.ForeignKey("behavior_sessions.id"))
    url: Mapped[str]
    recorded_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    duration_seconds: Mapped[Optional[float]]
    notes: Mapped[Optional[str]]

    animal: Mapped[Optional[Animal]] = relationship("Animal", back_populates="video_clips")
    session: Mapped[Optional[BehaviorSession]] = relationship("BehaviorSession")


class AnimalNote(db.Model):
    __tablename__ = "animal_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    animal_id: Mapped[int] = mapped_column(db.ForeignKey("animals.id"), nullable=False)
    session_id: Mapped[int | None] = mapped_column(db.ForeignKey("behavior_sessions.id"))
    note_type: Mapped[str] = mapped_column(default="general")
    content: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by: Mapped[Optional[str]]

    animal: Mapped[Animal] = relationship("Animal", back_populates="notes")
    session: Mapped[Optional[BehaviorSession]] = relationship("BehaviorSession")


@event.listens_for(BehaviorLog, "before_insert")
def set_behavior_timestamp(mapper, connection, target) -> None:  # noqa: WPS463
    if target.timestamp is None:
        target.timestamp = datetime.utcnow()
    if target.duration_seconds is None and target.behavior and target.behavior.default_duration_seconds:
        target.duration_seconds = target.behavior.default_duration_seconds


@event.listens_for(EnrichmentLog, "before_insert")
def set_enrichment_timestamp(mapper, connection, target) -> None:  # noqa: WPS463
    now = datetime.utcnow()
    if target.timestamp is None:
        target.timestamp = now
    if target.start_time is None:
        target.start_time = target.timestamp
    if target.end_time is None and target.duration_minutes:
        target.end_time = target.start_time + timedelta(minutes=target.duration_minutes)
    if target.end_time and target.start_time and not target.duration_minutes:
        delta = target.end_time - target.start_time
        target.duration_minutes = round(delta.total_seconds() / 60, 2)


@event.listens_for(StressLog, "before_insert")
def set_stress_date(mapper, connection, target) -> None:  # noqa: WPS463
    if target.date is None:
        target.date = datetime.utcnow()
    if target.stress_score is None:
        target.stress_score = sum(
            [
                target.withdrawal,
                target.fear_grimace,
                target.pacing,
                target.self_biting,
                target.scratching,
                target.vocalization,
            ]
        )


class BehaviorLogSchema(ma.SQLAlchemySchema):
    class Meta:
        model = BehaviorLog
        load_instance = True

    id = ma.auto_field()
    timestamp = ma.auto_field()
    sample_type = ma.auto_field()
    context = ma.auto_field()
    mode = ma.auto_field()
    session_id = ma.auto_field()
    intensity = ma.auto_field()
    duration_seconds = ma.auto_field()
    metadata = ma.auto_field()
    animal_id = ma.auto_field()
    behavior_id = ma.auto_field()
    observer_id = ma.auto_field()
    interaction_partner_id = ma.auto_field()


class BehaviorSessionSchema(ma.SQLAlchemySchema):
    class Meta:
        model = BehaviorSession
        load_instance = True

    id = ma.auto_field()
    name = ma.auto_field()
    mode = ma.auto_field()
    started_at = ma.auto_field()
    ended_at = ma.auto_field()
    observer_id = ma.auto_field()
    cage_id = ma.auto_field()
    group_label = ma.auto_field()
    notes = ma.auto_field()
    metadata = ma.auto_field()


class AnimalSchema(ma.SQLAlchemySchema):
    class Meta:
        model = Animal
        load_instance = True

    id = ma.auto_field()
    persistent_id = ma.auto_field()
    name = ma.auto_field()
    cage_id = ma.auto_field()
    sex = ma.auto_field()
    age = ma.auto_field()
    weight_kg = ma.auto_field()
    species = ma.auto_field()
    matriline = ma.auto_field()
    date_of_birth = ma.auto_field()
    photo_url = ma.auto_field()


class EnrichmentLogSchema(ma.SQLAlchemySchema):
    class Meta:
        model = EnrichmentLog
        load_instance = True

    id = ma.auto_field()
    timestamp = ma.auto_field()
    start_time = ma.auto_field()
    end_time = ma.auto_field()
    duration_minutes = ma.auto_field()
    response = ma.auto_field()
    outcome = ma.auto_field()
    notes = ma.auto_field()
    tag = ma.auto_field()
    frequency = ma.auto_field()
    metadata = ma.auto_field()
    animal_id = ma.auto_field()
    enrichment_item_id = ma.auto_field()


class StressLogSchema(ma.SQLAlchemySchema):
    class Meta:
        model = StressLog
        load_instance = True

    id = ma.auto_field()
    date = ma.auto_field()
    stress_score = ma.auto_field()
    withdrawal = ma.auto_field()
    fear_grimace = ma.auto_field()
    pacing = ma.auto_field()
    self_biting = ma.auto_field()
    scratching = ma.auto_field()
    vocalization = ma.auto_field()
    linked_cortisol = ma.auto_field()
    notes = ma.auto_field()
    animal_id = ma.auto_field()
