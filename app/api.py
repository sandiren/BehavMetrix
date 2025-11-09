from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from . import db
from .models import (
    Animal,
    AnimalNote,
    AnimalSchema,
    BehaviorDefinition,
    BehaviorLog,
    BehaviorLogSchema,
    BehaviorSession,
    BehaviorSessionSchema,
    SessionParticipant,
    EnrichmentLog,
    EnrichmentLogSchema,
    Ethogram,
    StressLog,
    StressLogSchema,
    VoiceTranscript,
)

api_bp = Blueprint("api", __name__)

animal_schema = AnimalSchema(many=True)
behavior_schema = BehaviorLogSchema(many=True)
enrichment_schema = EnrichmentLogSchema(many=True)
stress_schema = StressLogSchema(many=True)
session_schema = BehaviorSessionSchema(many=True)


@api_bp.get("/animals")
def list_animals():
    animals = Animal.query.order_by(Animal.persistent_id).all()
    return jsonify(animal_schema.dump(animals))


@api_bp.post("/animals")
def create_animal():
    payload = request.get_json() or {}
    animal = Animal(
        persistent_id=payload.get("persistent_id"),
        name=payload.get("name"),
        cage_id=payload.get("cage_id", ""),
        sex=payload.get("sex", ""),
        age=payload.get("age"),
        weight_kg=payload.get("weight_kg"),
        species=payload.get("species", "Macaca mulatta"),
        matriline=payload.get("matriline"),
    )
    db.session.add(animal)
    db.session.commit()
    return jsonify({"id": animal.id}), 201


@api_bp.get("/behaviors")
def list_behaviors():
    logs = BehaviorLog.query.order_by(BehaviorLog.timestamp.desc()).limit(500).all()
    return jsonify(behavior_schema.dump(logs))


@api_bp.post("/behaviors")
def create_behavior_log():
    payload = request.get_json() or {}
    session_id = payload.get("session_id")
    targets = payload.get("animal_ids") or [payload.get("animal_id")]
    created_ids: list[int] = []
    for target in filter(None, targets):
        log = BehaviorLog(
            animal_id=target,
            behavior_id=payload.get("behavior_id"),
            observer_id=payload.get("observer_id"),
            context=payload.get("context"),
            sample_type=payload.get("sample_type", "focal"),
            mode=payload.get("mode", "real_time"),
            session_id=session_id,
            intensity=payload.get("intensity"),
            duration_seconds=payload.get("duration_seconds"),
            interaction_partner_id=payload.get("interaction_partner_id"),
            metadata=payload.get("metadata"),
            timestamp=
            datetime.fromisoformat(payload.get("timestamp"))
            if payload.get("timestamp")
            else datetime.utcnow(),
        )
        db.session.add(log)
        db.session.flush()
        created_ids.append(log.id)
    db.session.commit()
    return jsonify({"ids": created_ids}), 201


@api_bp.get("/enrichment")
def list_enrichment_logs():
    logs = EnrichmentLog.query.order_by(EnrichmentLog.timestamp.desc()).limit(500).all()
    return jsonify(enrichment_schema.dump(logs))


@api_bp.post("/enrichment")
def create_enrichment_log():
    payload = request.get_json() or {}
    log = EnrichmentLog(
        animal_id=payload.get("animal_id"),
        enrichment_item_id=payload.get("enrichment_item_id"),
        start_time=datetime.fromisoformat(payload.get("start_time")) if payload.get("start_time") else None,
        end_time=datetime.fromisoformat(payload.get("end_time")) if payload.get("end_time") else None,
        duration_minutes=payload.get("duration_minutes"),
        response=payload.get("response"),
        outcome=payload.get("outcome"),
        notes=payload.get("notes"),
        tag=payload.get("tag"),
        frequency=payload.get("frequency"),
        metadata=payload.get("metadata"),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({"id": log.id}), 201


@api_bp.get("/stress")
def list_stress_logs():
    logs = StressLog.query.order_by(StressLog.date.desc()).limit(500).all()
    return jsonify(stress_schema.dump(logs))


@api_bp.post("/stress")
def create_stress_log():
    payload = request.get_json() or {}
    log = StressLog(
        animal_id=payload.get("animal_id"),
        date=datetime.fromisoformat(payload.get("date")) if payload.get("date") else datetime.utcnow(),
        stress_score=payload.get("stress_score"),
        withdrawal=payload.get("withdrawal", False),
        fear_grimace=payload.get("fear_grimace", False),
        pacing=payload.get("pacing", False),
        self_biting=payload.get("self_biting", False),
        scratching=payload.get("scratching", False),
        vocalization=payload.get("vocalization", False),
        linked_cortisol=payload.get("linked_cortisol"),
        notes=payload.get("notes"),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({"id": log.id}), 201


@api_bp.get("/sessions")
def list_sessions():
    query = BehaviorSession.query.order_by(BehaviorSession.started_at.desc()).limit(50)
    return jsonify(session_schema.dump(query))


@api_bp.post("/sessions")
def create_session():
    payload = request.get_json() or {}
    session = BehaviorSession(
        name=payload.get("name"),
        mode=payload.get("mode", "real_time"),
        observer_id=payload.get("observer_id"),
        cage_id=payload.get("cage_id"),
        group_label=payload.get("group_label"),
        notes=payload.get("notes"),
        metadata=payload.get("metadata"),
    )
    db.session.add(session)
    for animal_id in payload.get("animal_ids", []):
        if animal_id:
            db.session.add(SessionParticipant(session=session, animal_id=int(animal_id)))
    db.session.commit()
    return jsonify({"id": session.id}), 201


@api_bp.patch("/sessions/<int:session_id>")
def close_session(session_id: int):
    session = BehaviorSession.query.get_or_404(session_id)
    payload = request.get_json() or {}
    session.ended_at = datetime.fromisoformat(payload.get("ended_at")) if payload.get("ended_at") else datetime.utcnow()
    session.notes = payload.get("notes", session.notes)
    db.session.commit()
    return jsonify({"id": session.id, "ended_at": session.ended_at.isoformat()})


@api_bp.get("/ethogram")
def get_ethogram():
    ethogram = Ethogram.query.filter_by(is_default=True).first() or Ethogram.query.first()
    if not ethogram:
        behaviors = BehaviorDefinition.query.order_by(BehaviorDefinition.name).all()
        return jsonify(
            {
                "behaviors": [
                    {
                        "id": behavior.id,
                        "code": behavior.code,
                        "name": behavior.name,
                        "category": behavior.category.name if behavior.category else None,
                        "color": behavior.category.color if behavior.category else "#0d6efd",
                        "is_dyadic": behavior.is_dyadic,
                    }
                    for behavior in behaviors
                ]
            }
        )
    return jsonify(
        {
            "id": ethogram.id,
            "name": ethogram.name,
            "behaviors": [
                {
                    "id": entry.behavior_id,
                    "display_name": entry.display_name or entry.behavior.name,
                    "code": entry.behavior.code,
                    "category": entry.behavior.category.name if entry.behavior.category else None,
                    "color": entry.color_override or (entry.behavior.category.color if entry.behavior.category else "#0d6efd"),
                    "is_dyadic": entry.behavior.is_dyadic,
                    "keyboard_shortcut": entry.behavior.keyboard_shortcut,
                }
                for entry in ethogram.behaviors
                if entry.is_active
            ],
        }
    )


@api_bp.post("/voice-transcripts")
def create_voice_transcript():
    payload = request.get_json() or {}
    transcript = VoiceTranscript(
        session_id=payload.get("session_id"),
        transcript_text=payload.get("transcript_text", ""),
        confidence=payload.get("confidence"),
    )
    db.session.add(transcript)
    db.session.commit()
    return jsonify({"id": transcript.id}), 201


@api_bp.post("/notes")
def create_animal_note():
    payload = request.get_json() or {}
    note = AnimalNote(
        animal_id=payload.get("animal_id"),
        session_id=payload.get("session_id"),
        note_type=payload.get("note_type", "general"),
        content=payload.get("content", ""),
        created_by=payload.get("created_by"),
    )
    db.session.add(note)
    db.session.commit()
    return jsonify({"id": note.id}), 201
