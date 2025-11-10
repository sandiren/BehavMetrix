from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from . import db
from .models import Animal, AnimalSchema, BehaviorLog, BehaviorLogSchema, EnrichmentLog, EnrichmentLogSchema, BehaviorModifier
from . import ma

api_bp = Blueprint("api", __name__)

animal_schema = AnimalSchema(many=True)
behavior_schema = BehaviorLogSchema(many=True)
enrichment_schema = EnrichmentLogSchema(many=True)

class BehaviorModifierSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = BehaviorModifier

behavior_modifier_schema = BehaviorModifierSchema(many=True)

@api_bp.route("/ethograms/<int:ethogram_id>/behaviors")
def list_ethogram_behaviors(ethogram_id):
    print(f"Getting behaviors for ethogram {ethogram_id}")
    behaviors = BehaviorDefinition.query.filter_by(ethogram_id=ethogram_id).all()
    return jsonify(behavior_schema.dump(behaviors))

@api_bp.route("/behaviors/<int:behavior_id>/modifiers")
def list_behavior_modifiers(behavior_id):
    modifiers = BehaviorModifier.query.filter_by(behavior_definition_id=behavior_id).all()
    return jsonify(behavior_modifier_schema.dump(modifiers))

@api_bp.route("/ethograms/<int:ethogram_id>/behaviors", methods=["POST"])
def create_behavior(ethogram_id):
    behavior = BehaviorDefinition(
        ethogram_id=ethogram_id,
        name=request.json["name"],
        code=request.json["code"],
        description=request.json["description"],
        event_type=request.json["event_type"],
    )
    db.session.add(behavior)
    db.session.commit()
    return jsonify({"id": behavior.id}), 201


@api_bp.route("/behaviors/<int:behavior_id>", methods=["PUT"])
def update_behavior(behavior_id):
    behavior = BehaviorDefinition.query.get_or_404(behavior_id)
    behavior.name = request.json["name"]
    behavior.code = request.json["code"]
    behavior.description = request.json["description"]
    behavior.event_type = request.json["event_type"]
    db.session.commit()
    return jsonify({"id": behavior.id})


@api_bp.route("/behaviors/<int:behavior_id>", methods=["DELETE"])
def delete_behavior(behavior_id):
    behavior = BehaviorDefinition.query.get_or_404(behavior_id)
    db.session.delete(behavior)
    db.session.commit()
    return "", 204


@api_bp.route("/behaviors/<int:behavior_id>/modifiers", methods=["POST"])
def create_modifier(behavior_id):
    modifier = BehaviorModifier(
        behavior_definition_id=behavior_id,
        name=request.json["name"],
        modifier_type=request.json["modifier_type"],
        options=request.json["options"],
    )
    db.session.add(modifier)
    db.session.commit()
    return jsonify({"id": modifier.id}), 201


@api_bp.route("/modifiers/<int:modifier_id>", methods=["PUT"])
def update_modifier(modifier_id):
    modifier = BehaviorModifier.query.get_or_404(modifier_id)
    modifier.name = request.json["name"]
    modifier.modifier_type = request.json["modifier_type"]
    modifier.options = request.json["options"]
    db.session.commit()
    return jsonify({"id": modifier.id})


@api_bp.route("/modifiers/<int:modifier_id>", methods=["DELETE"])
def delete_modifier(modifier_id):
    modifier = BehaviorModifier.query.get_or_404(modifier_id)
    db.session.delete(modifier)
    db.session.commit()
    return "", 204


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
