from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON

from sqlalchemy import event
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

    behavior_logs: Mapped[list[BehaviorLog]] = relationship(
        "BehaviorLog",
        back_populates="animal",
        foreign_keys="BehaviorLog.animal_id",
    )
    enrichment_logs: Mapped[list[EnrichmentLog]] = relationship("EnrichmentLog", back_populates="animal")
    stress_logs: Mapped[list[StressLog]] = relationship("StressLog", back_populates="animal")
    incidents: Mapped[list[IncidentObservation]] = relationship("IncidentObservation", back_populates="animal")


class Observer(db.Model):
    __tablename__ = "observers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    affiliation: Mapped[Optional[str]]

    behavior_logs: Mapped[list[BehaviorLog]] = relationship("BehaviorLog", back_populates="observer")


class Ethogram(db.Model):
    __tablename__ = "ethograms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    version: Mapped[str] = mapped_column(unique=True, nullable=False)
    description: Mapped[Optional[str]]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    created_by: Mapped[Optional[str]]

    behaviors: Mapped[list["BehaviorDefinition"]] = relationship("BehaviorDefinition", back_populates="ethogram")
    observation_sessions: Mapped[list["ObservationSession"]] = relationship(
        "ObservationSession", back_populates="ethogram"
    )


class BehaviorModifier(db.Model):
    __tablename__ = "behavior_modifiers"

    id: Mapped[int] = mapped_column(primary_key=True)
    behavior_definition_id: Mapped[int] = mapped_column(db.ForeignKey("behavior_definitions.id"), nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    modifier_type: Mapped[str] = mapped_column(nullable=False, default="select")
    options: Mapped[dict | None] = mapped_column(JSON, default=dict)


class BehaviorDefinition(db.Model):
    __tablename__ = "behavior_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[Optional[str]]
    ontology_reference: Mapped[Optional[str]]
    category: Mapped[Optional[str]]
    event_type: Mapped[str] = mapped_column(default="point")

    ethogram_id: Mapped[int | None] = mapped_column(db.ForeignKey("ethograms.id"))
    ethogram: Mapped[Optional[Ethogram]] = relationship("Ethogram", back_populates="behaviors")

    logs: Mapped[list["BehaviorLog"]] = relationship("BehaviorLog", back_populates="behavior")
    modifiers: Mapped[list["BehaviorModifier"]] = relationship("BehaviorModifier")


class ObservationSession(db.Model):
    __tablename__ = "observation_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False, index=True)
    ended_at: Mapped[Optional[datetime]]
    observer_name: Mapped[Optional[str]]
    observer_id: Mapped[int | None] = mapped_column(db.ForeignKey("observers.id"))
    cage_id: Mapped[Optional[str]]
    matriline: Mapped[Optional[str]]
    reason_for_observation: Mapped[Optional[str]]
    observation_notes: Mapped[Optional[str]]
    session_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSON, default=dict
    )
    fair_identifier: Mapped[Optional[str]]

    ethogram_id: Mapped[int | None] = mapped_column(db.ForeignKey("ethograms.id"))

    observer: Mapped[Optional[Observer]] = relationship("Observer")
    ethogram: Mapped[Optional[Ethogram]] = relationship(
        "Ethogram", back_populates="observation_sessions"
    )
    behavior_logs: Mapped[list["BehaviorLog"]] = relationship("BehaviorLog", back_populates="session")
    stress_logs: Mapped[list["StressLog"]] = relationship("StressLog", back_populates="session")
    enrichment_logs: Mapped[list["EnrichmentLog"]] = relationship("EnrichmentLog", back_populates="session")
    incidents: Mapped[list["IncidentObservation"]] = relationship(
        "IncidentObservation", back_populates="session"
    )


class BehaviorLog(db.Model):
    __tablename__ = "behavior_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    end_timestamp: Mapped[Optional[datetime]]
    duration_seconds: Mapped[Optional[float]]
    modifiers: Mapped[dict | None] = mapped_column(JSON, default=dict)
    context: Mapped[Optional[str]]
    sample_type: Mapped[str] = mapped_column(default="focal")
    reason_for_observation: Mapped[Optional[str]]
    event_tags: Mapped[Optional[str]]
    observer_notes: Mapped[Optional[str]]

    animal_id: Mapped[int] = mapped_column(db.ForeignKey("animals.id"))
    behavior_id: Mapped[int] = mapped_column(db.ForeignKey("behavior_definitions.id"))
    observer_id: Mapped[int | None] = mapped_column(db.ForeignKey("observers.id"))
    receiver_id: Mapped[int | None] = mapped_column(db.ForeignKey("animals.id"))
    session_id: Mapped[int | None] = mapped_column(db.ForeignKey("observation_sessions.id"))
    batch_identifier: Mapped[Optional[str]]

    animal: Mapped[Animal] = relationship(
        "Animal",
        back_populates="behavior_logs",
        foreign_keys=[animal_id],
    )
    behavior: Mapped[BehaviorDefinition] = relationship("BehaviorDefinition", back_populates="logs")
    observer: Mapped[Optional[Observer]] = relationship("Observer", back_populates="behavior_logs")

    interaction_partner_id: Mapped[int | None] = mapped_column(db.ForeignKey("animals.id"))
    interaction_partner: Mapped[Optional[Animal]] = relationship("Animal", foreign_keys=[interaction_partner_id])
    receiver: Mapped[Optional[Animal]] = relationship("Animal", foreign_keys=[receiver_id])
    session: Mapped[Optional[ObservationSession]] = relationship("ObservationSession", back_populates="behavior_logs")


class EnrichmentItem(db.Model):
    __tablename__ = "enrichment_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[Optional[str]]
    category: Mapped[Optional[str]]
    success_indicator: Mapped[Optional[str]]

    logs: Mapped[list[EnrichmentLog]] = relationship("EnrichmentLog", back_populates="item")


class EnrichmentLog(db.Model):
    __tablename__ = "enrichment_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    duration_minutes: Mapped[Optional[float]]
    response: Mapped[Optional[str]]
    notes: Mapped[Optional[str]]
    tag: Mapped[Optional[str]]
    engagement_type: Mapped[Optional[str]]
    frequency: Mapped[Optional[int]]
    session_id: Mapped[int | None] = mapped_column(db.ForeignKey("observation_sessions.id"))

    animal_id: Mapped[int] = mapped_column(db.ForeignKey("animals.id"))
    enrichment_item_id: Mapped[int] = mapped_column(db.ForeignKey("enrichment_items.id"))

    animal: Mapped[Animal] = relationship("Animal", back_populates="enrichment_logs")
    item: Mapped[EnrichmentItem] = relationship("EnrichmentItem", back_populates="logs")
    session: Mapped[Optional[ObservationSession]] = relationship("ObservationSession", back_populates="enrichment_logs")


class StressLog(db.Model):
    __tablename__ = "stress_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    stress_score: Mapped[int] = mapped_column(default=0)
    weighted_score: Mapped[Optional[float]]
    withdrawal: Mapped[bool] = mapped_column(default=False)
    fear_grimace: Mapped[bool] = mapped_column(default=False)
    self_biting: Mapped[bool] = mapped_column(default=False)
    pacing: Mapped[bool] = mapped_column(default=False)
    isolation: Mapped[bool] = mapped_column(default=False)
    cortisol_level: Mapped[Optional[float]]
    notes: Mapped[Optional[str]]
    auto_generated: Mapped[bool] = mapped_column(default=False)

    animal_id: Mapped[int] = mapped_column(db.ForeignKey("animals.id"))
    session_id: Mapped[int | None] = mapped_column(db.ForeignKey("observation_sessions.id"))

    animal: Mapped[Animal] = relationship("Animal", back_populates="stress_logs")
    session: Mapped[Optional[ObservationSession]] = relationship("ObservationSession", back_populates="stress_logs")


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
    media_type: Mapped[Optional[str]]
    tags: Mapped[Optional[str]]

    animal_id: Mapped[int | None] = mapped_column(db.ForeignKey("animals.id"))
    session_id: Mapped[int | None] = mapped_column(db.ForeignKey("observation_sessions.id"))
    animal: Mapped[Optional[Animal]] = relationship("Animal", back_populates="incidents")
    session: Mapped[Optional[ObservationSession]] = relationship("ObservationSession", back_populates="incidents")


class ObservationAttachment(db.Model):
    __tablename__ = "observation_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    description: Mapped[Optional[str]]
    media_url: Mapped[str]
    media_type: Mapped[Optional[str]]
    tags: Mapped[Optional[str]]

    session_id: Mapped[int | None] = mapped_column(db.ForeignKey("observation_sessions.id"))
    animal_id: Mapped[int | None] = mapped_column(db.ForeignKey("animals.id"))

    session: Mapped[Optional[ObservationSession]] = relationship("ObservationSession")
    animal: Mapped[Optional[Animal]] = relationship("Animal")


class EnrichmentEngagementSummary(db.Model):
    __tablename__ = "enrichment_engagement_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    calculated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    window_days: Mapped[int] = mapped_column(default=7)
    engagement_score: Mapped[float] = mapped_column(default=0.0)
    alert_triggered: Mapped[bool] = mapped_column(default=False)

    animal_id: Mapped[int | None] = mapped_column(db.ForeignKey("animals.id"))
    cage_id: Mapped[Optional[str]]
    enrichment_item_id: Mapped[int | None] = mapped_column(db.ForeignKey("enrichment_items.id"))

    animal: Mapped[Optional[Animal]] = relationship("Animal")
    item: Mapped[Optional[EnrichmentItem]] = relationship("EnrichmentItem")


class RankScore(db.Model):
    __tablename__ = "rank_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    elo_score: Mapped[float] = mapped_column(default=1000.0)
    davids_score: Mapped[Optional[float]]
    instability_flag: Mapped[bool] = mapped_column(default=False)

    animal_id: Mapped[int] = mapped_column(db.ForeignKey("animals.id"), nullable=False)
    animal: Mapped[Animal] = relationship("Animal")


@event.listens_for(BehaviorLog, "before_insert")
def set_behavior_timestamp(mapper, connection, target) -> None:  # noqa: WPS463
    if target.timestamp is None:
        target.timestamp = datetime.utcnow()
    if target.reason_for_observation is None and target.session and target.session.reason_for_observation:
        target.reason_for_observation = target.session.reason_for_observation
    if (
        target.event_tags is None
        and target.session
        and target.session.session_metadata
    ):
        tags = target.session.session_metadata.get("event_tags")
        if tags:
            target.event_tags = ",".join(tags) if isinstance(tags, list) else str(tags)


@event.listens_for(EnrichmentLog, "before_insert")
def set_enrichment_timestamp(mapper, connection, target) -> None:  # noqa: WPS463
    if target.timestamp is None:
        target.timestamp = datetime.utcnow()
    if target.session and target.session.reason_for_observation and not target.tag:
        target.tag = target.session.reason_for_observation


@event.listens_for(StressLog, "before_insert")
def set_stress_date(mapper, connection, target) -> None:  # noqa: WPS463
    if target.date is None:
        target.date = datetime.utcnow()
    if target.weighted_score is None:
        weight = 0
        weight += 2 if target.withdrawal else 0
        weight += 3 if target.fear_grimace else 0
        weight += 4 if target.self_biting else 0
        weight += 2 if target.pacing else 0
        weight += 1 if target.isolation else 0
        if target.cortisol_level:
            weight += min(target.cortisol_level / 10, 5)
        target.weighted_score = round(weight or target.stress_score, 2)


class BehaviorLogSchema(ma.SQLAlchemySchema):
    class Meta:
        model = BehaviorLog
        load_instance = True

    id = ma.auto_field()
    timestamp = ma.auto_field()
    sample_type = ma.auto_field()
    context = ma.auto_field()
    animal_id = ma.auto_field()
    behavior_id = ma.auto_field()
    observer_id = ma.auto_field()


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
    duration_minutes = ma.auto_field()
    response = ma.auto_field()
    notes = ma.auto_field()
    tag = ma.auto_field()
    animal_id = ma.auto_field()
    enrichment_item_id = ma.auto_field()
