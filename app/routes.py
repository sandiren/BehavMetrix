from __future__ import annotations

import io
import json
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    Response,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from sqlalchemy import func, or_

from . import db
from .models import Animal, BehaviorDefinition, BehaviorLog, EnrichmentItem, EnrichmentLog, IncidentObservation, StressLog
from .utils.analytics import build_rank_graph, colony_behavior_stats, compute_elo
from .utils.ingestion import ingest_animals, read_sql, read_tabular

bp = Blueprint("routes", __name__)


@bp.route("/")
def dashboard() -> str:
    search_term = request.args.get("search")
    cage_filter = request.args.get("cage")
    sex_filter = request.args.get("sex")

    query = Animal.query
    if search_term:
        like_pattern = f"%{search_term}%"
        query = query.filter(
            or_(
                Animal.persistent_id.ilike(like_pattern),
                Animal.name.ilike(like_pattern),
                Animal.matriline.ilike(like_pattern),
            )
        )
    if cage_filter:
        query = query.filter(Animal.cage_id == cage_filter)
    if sex_filter:
        query = query.filter(Animal.sex == sex_filter)

    animals = query.order_by(Animal.persistent_id).all()
    behavior_logs = BehaviorLog.query.order_by(BehaviorLog.timestamp.desc()).limit(500).all()
    stats = colony_behavior_stats(behavior_logs)
    elo_result = compute_elo(behavior_logs)

    animal_lookup = {animal.id: animal for animal in animals}

    profiles: list[dict[str, object]] = []
    for animal in animals:
        recent_window = datetime.utcnow() - timedelta(days=7)
        recent_stress = (
            db.session.query(func.avg(StressLog.stress_score))
            .filter(StressLog.animal_id == animal.id)
            .filter(StressLog.date >= recent_window)
            .scalar()
        )
        stress_score = round(recent_stress or 0, 2)
        enrichment_use = (
            db.session.query(func.count(EnrichmentLog.id))
            .filter(EnrichmentLog.animal_id == animal.id)
            .scalar()
        )
        grooming_count = sum(
            1 for log in behavior_logs if log.animal_id == animal.id and getattr(log.behavior, "code", "") == "GROOM"
        )
        welfare_flag = stress_score >= 4 or grooming_count == 0
        profiles.append(
            {
                "animal": animal,
                "stress_score": stress_score,
                "weight": animal.weight_kg,
                "rank": elo_result.scores.get(animal.id, 1000),
                "enrichment_use": enrichment_use,
                "welfare_flag": welfare_flag,
            }
        )

    graph = build_rank_graph(animals, elo_result.scores)
    network_data = json.dumps(
        {
            "nodes": [
                {"id": node, "label": data["label"], "elo": data.get("elo", 1000)}
                for node, data in graph.nodes(data=True)
            ],
            "edges": [
                {"source": u, "target": v, "weight": data.get("weight", 0)}
                for u, v, data in graph.edges(data=True)
            ],
        }
    )

    cages = [row[0] for row in db.session.query(Animal.cage_id).distinct().order_by(Animal.cage_id)]
    sexes = [row[0] for row in db.session.query(Animal.sex).distinct() if row[0]]
    instability_labels = [
        (animal_lookup.get(flag).name or animal_lookup.get(flag).persistent_id)
        for flag in elo_result.instability_flags
        if animal_lookup.get(flag)
    ]

    return render_template(
        "dashboard.html",
        profiles=profiles,
        stats=stats,
        network_data=network_data,
        instability_flags=instability_labels,
        search_term=search_term or "",
        cage_filter=cage_filter or "",
        sex_filter=sex_filter or "",
        cage_choices=cages,
        sex_choices=sexes,
    )


@bp.route("/upload", methods=["GET", "POST"])
def upload() -> str:
    if request.method == "POST":
        user = request.form.get("user", "unknown")
        notes = request.form.get("notes")
        connection_uri = request.form.get("connection_uri")
        table_name = request.form.get("table_name")
        if connection_uri and table_name:
            try:
                dataframe = read_sql(connection_uri, table_name)
                ingest_animals(dataframe, user=user, source=f"SQL:{table_name}", notes=notes)
                flash("Animal records imported from SQL", "success")
                return redirect(url_for("routes.dashboard"))
            except Exception as exc:  # noqa: BLE001
                flash(f"SQL import failed: {exc}", "danger")
        if request.files:
            file = request.files.get("file")
            if file and file.filename:
                try:
                    dataframe = read_tabular(file)
                    ingest_animals(dataframe, user=user, source=file.filename, notes=notes)
                    flash("Animal records imported successfully", "success")
                    return redirect(url_for("routes.dashboard"))
                except Exception as exc:  # noqa: BLE001
                    flash(f"Upload failed: {exc}", "danger")
        flash("No file selected or unsupported format", "warning")
    return render_template("upload.html")


@bp.route("/behavior-log", methods=["GET", "POST"])
def behavior_log() -> str:
    animals = Animal.query.order_by(Animal.persistent_id).all()
    behaviors = BehaviorDefinition.query.order_by(BehaviorDefinition.name).all()
    if request.method == "POST":
        log = BehaviorLog(
            animal_id=request.form.get("animal_id"),
            behavior_id=request.form.get("behavior_id"),
            observer_id=None,
            timestamp=datetime.utcnow(),
            sample_type=request.form.get("sample_type", "focal"),
            context=request.form.get("context"),
            interaction_partner_id=request.form.get("partner_id") or None,
        )
        db.session.add(log)
        db.session.commit()
        flash("Behavior logged", "success")
        return redirect(url_for("routes.behavior_log"))
    return render_template("behavior_log.html", animals=animals, behaviors=behaviors)


@bp.route("/enrichment", methods=["GET", "POST"])
def enrichment() -> str:
    animals = Animal.query.order_by(Animal.persistent_id).all()
    items = EnrichmentItem.query.order_by(EnrichmentItem.name).all()
    if request.method == "POST":
        duration_raw = request.form.get("duration")
        log = EnrichmentLog(
            animal_id=request.form.get("animal_id"),
            enrichment_item_id=request.form.get("item_id"),
            duration_minutes=float(duration_raw) if duration_raw else None,
            response=request.form.get("response"),
            notes=request.form.get("notes"),
            tag=request.form.get("tag"),
        )
        db.session.add(log)
        db.session.commit()
        flash("Enrichment logged", "success")
        return redirect(url_for("routes.enrichment"))
    return render_template("enrichment.html", animals=animals, items=items)


@bp.route("/stress", methods=["GET", "POST"])
def stress() -> str:
    animals = Animal.query.order_by(Animal.persistent_id).all()
    if request.method == "POST":
        log = StressLog(
            animal_id=request.form.get("animal_id"),
            date=datetime.strptime(request.form.get("date"), "%Y-%m-%d"),
            stress_score=int(request.form.get("stress_score", 0)),
            withdrawal=bool(request.form.get("withdrawal")),
            fear_grimace=bool(request.form.get("fear_grimace")),
            self_biting=bool(request.form.get("self_biting")),
            notes=request.form.get("notes"),
        )
        db.session.add(log)
        db.session.commit()
        flash("Stress log saved", "success")
        return redirect(url_for("routes.stress"))
    return render_template("stress.html", animals=animals, today=datetime.utcnow().date())


@bp.route("/incident", methods=["GET", "POST"])
def incident() -> str:
    animals = Animal.query.order_by(Animal.persistent_id).all()
    if request.method == "POST":
        log = IncidentObservation(
            animal_id=request.form.get("animal_id") or None,
            reason=request.form.get("reason"),
            description=request.form.get("description"),
            attachment_url=request.form.get("attachment_url"),
            tags=request.form.get("tags"),
        )
        db.session.add(log)
        db.session.commit()
        flash("Observation recorded", "success")
        return redirect(url_for("routes.incident"))
    return render_template("incident.html", animals=animals)


@bp.route("/export/<string:resource>.<string:ext>")
def export_resource(resource: str, ext: str) -> Response:
    query_map = {
        "animals": Animal,
        "behaviors": BehaviorLog,
        "enrichments": EnrichmentLog,
        "stress": StressLog,
    }
    model = query_map.get(resource)
    if not model:
        flash("Unsupported export resource", "warning")
        return redirect(url_for("routes.dashboard"))
    rows = model.query.all()
    if ext == "json":
        payload = [row_to_dict(row) for row in rows]
        return Response(json.dumps(payload, default=str), mimetype="application/json")
    import pandas as pd

    df = pd.DataFrame([row_to_dict(row) for row in rows])
    if ext == "csv":
        return Response(df.to_csv(index=False), mimetype="text/csv")
    if ext in {"xlsx", "xls"}:
        stream = io.BytesIO()
        with pd.ExcelWriter(stream) as writer:
            df.to_excel(writer, index=False)
        stream.seek(0)
        return send_file(stream, as_attachment=True, download_name=f"{resource}.{ext}")
    flash("Unsupported export format", "warning")
    return redirect(url_for("routes.dashboard"))


def row_to_dict(row) -> dict:
    result = {}
    for column in row.__table__.columns:
        result[column.name] = getattr(row, column.name)
    return result
