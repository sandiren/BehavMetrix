from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from . import db
from .models import Animal, AnimalSchema, BehaviorLog, BehaviorLogSchema, EnrichmentLog, EnrichmentLogSchema

api_bp = Blueprint("api", __name__)

animal_schema = AnimalSchema(many=True)
behavior_schema = BehaviorLogSchema(many=True)
enrichment_schema = EnrichmentLogSchema(many=True)


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
    log = BehaviorLog(
        animal_id=payload.get("animal_id"),
        behavior_id=payload.get("behavior_id"),
        observer_id=payload.get("observer_id"),
        context=payload.get("context"),
        sample_type=payload.get("sample_type", "focal"),
        timestamp=datetime.fromisoformat(payload.get("timestamp")) if payload.get("timestamp") else datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({"id": log.id}), 201


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
        duration_minutes=payload.get("duration_minutes"),
        response=payload.get("response"),
        notes=payload.get("notes"),
        tag=payload.get("tag"),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({"id": log.id}), 201
