from __future__ import annotations

import io
import json
from datetime import datetime, timedelta
from uuid import uuid4

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
from .models import (
    Animal,
    BehaviorDefinition,
    BehaviorLog,
    EnrichmentEngagementSummary,
    EnrichmentItem,
    EnrichmentLog,
    EthogramVersion,
    IncidentObservation,
    ObservationAttachment,
    ObservationSession,
    StressLog,
)
from .utils.analytics import (
    build_rank_graph,
    colony_behavior_stats,
    compute_elo,
    enrichment_engagement_summary,
    stress_summary,
)
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
    stress_logs = StressLog.query.order_by(StressLog.date.desc()).limit(500).all()
    enrichment_logs = (
        EnrichmentLog.query.options()
        .order_by(EnrichmentLog.timestamp.desc())
        .limit(500)
        .all()
    )
    engagement_summary = enrichment_engagement_summary(enrichment_logs)
    stress_stats = stress_summary(stress_logs)
    recent_sessions = ObservationSession.query.order_by(ObservationSession.started_at.desc()).limit(10).all()

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
        davids_score = elo_result.davids_scores.get(animal.id, 0.0)
        indicator = "success"
        if welfare_flag:
            indicator = "danger"
        elif stress_stats.weighted_scores.get(animal.id, 0) >= 6:
            indicator = "warning"
        profiles.append(
            {
                "animal": animal,
                "stress_score": stress_score,
                "weight": animal.weight_kg,
                "rank": elo_result.scores.get(animal.id, 1000),
                "davids": davids_score,
                "enrichment_use": enrichment_use,
                "welfare_flag": welfare_flag,
                "indicator": indicator,
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
    matrilines = [row[0] for row in db.session.query(Animal.matriline).distinct() if row[0]]
    reason_history = [session.reason_for_observation for session in recent_sessions if session.reason_for_observation]
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
        davids_scores=elo_result.davids_scores,
        rank_timeline=json.dumps(elo_result.timeline),
        stress_summary=stress_stats,
        enrichment_summary=engagement_summary,
        observation_sessions=recent_sessions,
        search_term=search_term or "",
        cage_filter=cage_filter or "",
        sex_filter=sex_filter or "",
        cage_choices=cages,
        sex_choices=sexes,
        matriline_choices=matrilines,
        reason_history=reason_history,
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
    ethograms = EthogramVersion.query.order_by(EthogramVersion.created_at.desc()).all()
    sessions = ObservationSession.query.order_by(ObservationSession.started_at.desc()).limit(20).all()
    reason_history = [session.reason_for_observation for session in sessions if session.reason_for_observation]
    if request.method == "POST":
        behavior_id = request.form.get("behavior_id")
        if not behavior_id:
            flash("Behavior is required", "warning")
            return redirect(url_for("routes.behavior_log"))

        session_id = request.form.get("session_id")
        reason = request.form.get("reason_for_observation")
        tags_raw = request.form.get("event_tags") or ""
        tag_list = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]
        metadata = {"event_tags": tag_list} if tag_list else {}
        session: ObservationSession | None = None
        if session_id:
            session = ObservationSession.query.get(session_id)
        if session is None:
            session = ObservationSession(
                started_at=datetime.utcnow(),
                observer_name=request.form.get("observer_name"),
                cage_id=request.form.get("group_cage") or None,
                matriline=request.form.get("group_matriline") or None,
                reason_for_observation=reason,
                observation_notes=request.form.get("session_notes"),
                fair_identifier=request.form.get("fair_identifier") or str(uuid4()),
                session_metadata=metadata,
            )
            ethogram_version_id = request.form.get("ethogram_version_id")
            if ethogram_version_id:
                session.ethogram_version_id = ethogram_version_id
            db.session.add(session)
            db.session.flush()
        else:
            if metadata:
                session.session_metadata = {
                    **(session.session_metadata or {}),
                    **metadata,
                }
            if reason and not session.reason_for_observation:
                session.reason_for_observation = reason

        actor_ids = [value for value in request.form.getlist("actor_ids") if value]
        if not actor_ids:
            flash("Select at least one actor", "warning")
            return redirect(url_for("routes.behavior_log"))
        receiver_ids = [value for value in request.form.getlist("receiver_ids") if value]
        if receiver_ids and len(receiver_ids) != len(actor_ids) and len(receiver_ids) != 1:
            flash("Receiver selection must match actors", "warning")
            return redirect(url_for("routes.behavior_log"))
        created = 0
        batch_identifier = str(uuid4())
        for index, actor_id in enumerate(actor_ids or []):
            receiver_id = None
            if receiver_ids:
                receiver_id = receiver_ids[index] if len(receiver_ids) > 1 else receiver_ids[0]
            log = BehaviorLog(
                animal_id=actor_id,
                behavior_id=behavior_id,
                observer_id=None,
                timestamp=datetime.utcnow(),
                sample_type=request.form.get("sample_type", "focal"),
                context=request.form.get("context"),
                interaction_partner_id=receiver_id or None,
                receiver_id=receiver_id or None,
                session_id=session.id,
                reason_for_observation=reason or session.reason_for_observation,
                event_tags=",".join(tag_list) if tag_list else None,
                observer_notes=request.form.get("observer_notes"),
                batch_identifier=batch_identifier,
            )
            db.session.add(log)
            created += 1
        db.session.commit()
        flash(f"Logged {created} behavior events", "success")
        return redirect(url_for("routes.behavior_log"))
    return render_template(
        "behavior_log.html",
        animals=animals,
        behaviors=behaviors,
        ethograms=ethograms,
        sessions=sessions,
        reason_history=reason_history,
    )


@bp.route("/enrichment", methods=["GET", "POST"])
def enrichment() -> str:
    animals = Animal.query.order_by(Animal.persistent_id).all()
    items = EnrichmentItem.query.order_by(EnrichmentItem.name).all()
    sessions = ObservationSession.query.order_by(ObservationSession.started_at.desc()).limit(10).all()
    stress_view = stress_summary(
        StressLog.query.order_by(StressLog.date.desc()).limit(200).all()
    )
    snapshots = (
        EnrichmentEngagementSummary.query.order_by(EnrichmentEngagementSummary.calculated_at.desc())
        .limit(20)
        .all()
    )
    engagement_view = enrichment_engagement_summary(
        EnrichmentLog.query.order_by(EnrichmentLog.timestamp.desc()).limit(200).all()
    )
    if request.method == "POST":
        duration_raw = request.form.get("duration")
        frequency_raw = request.form.get("frequency")
        log = EnrichmentLog(
            animal_id=request.form.get("animal_id"),
            enrichment_item_id=request.form.get("item_id"),
            duration_minutes=float(duration_raw) if duration_raw else None,
            response=request.form.get("response"),
            notes=request.form.get("notes"),
            tag=request.form.get("tag"),
            engagement_type=request.form.get("engagement_type"),
            frequency=int(frequency_raw) if frequency_raw else None,
            session_id=request.form.get("session_id") or None,
        )
        db.session.add(log)
        db.session.commit()
        recalc_engagement(log.animal_id)
        flash("Enrichment logged", "success")
        return redirect(url_for("routes.enrichment"))
    return render_template(
        "enrichment.html",
        animals=animals,
        items=items,
        sessions=sessions,
        snapshots=snapshots,
        engagement_view=engagement_view,
    )


@bp.route("/stress", methods=["GET", "POST"])
def stress() -> str:
    animals = Animal.query.order_by(Animal.persistent_id).all()
    sessions = ObservationSession.query.order_by(ObservationSession.started_at.desc()).limit(10).all()
    if request.method == "POST":
        session_id = request.form.get("session_id") or None
        cortisol_raw = request.form.get("cortisol_level")
        log = StressLog(
            animal_id=request.form.get("animal_id"),
            date=datetime.strptime(request.form.get("date"), "%Y-%m-%d"),
            stress_score=int(request.form.get("stress_score", 0)),
            withdrawal=bool(request.form.get("withdrawal")),
            fear_grimace=bool(request.form.get("fear_grimace")),
            self_biting=bool(request.form.get("self_biting")),
            pacing=bool(request.form.get("pacing")),
            isolation=bool(request.form.get("isolation")),
            cortisol_level=float(cortisol_raw) if cortisol_raw else None,
            notes=request.form.get("notes"),
            session_id=session_id,
        )
        db.session.add(log)
        db.session.commit()
        stress_stats = stress_summary([log])
        if stress_stats.alerts:
            flash("Stress threshold exceeded", "warning")
        flash("Stress log saved", "success")
        return redirect(url_for("routes.stress"))
    return render_template(
        "stress.html",
        animals=animals,
        today=datetime.utcnow().date(),
        sessions=sessions,
        stress_view=stress_view,
    )


@bp.route("/incident", methods=["GET", "POST"])
def incident() -> str:
    animals = Animal.query.order_by(Animal.persistent_id).all()
    sessions = ObservationSession.query.order_by(ObservationSession.started_at.desc()).limit(10).all()
    if request.method == "POST":
        session_id = request.form.get("session_id") or None
        attachment_url = request.form.get("attachment_url")
        log = IncidentObservation(
            animal_id=request.form.get("animal_id") or None,
            reason=request.form.get("reason"),
            description=request.form.get("description"),
            attachment_url=attachment_url,
            media_type=request.form.get("media_type"),
            tags=request.form.get("tags"),
            session_id=session_id,
        )
        db.session.add(log)
        if attachment_url:
            attachment = ObservationAttachment(
                media_url=attachment_url,
                media_type=request.form.get("media_type"),
                description=request.form.get("description"),
                tags=request.form.get("tags"),
                session_id=session_id,
                animal_id=request.form.get("animal_id") or None,
            )
            db.session.add(attachment)
        db.session.commit()
        flash("Observation recorded", "success")
        return redirect(url_for("routes.incident"))
    return render_template(
        "incident.html",
        animals=animals,
        sessions=sessions,
        attachments=attachments,
    )


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


def recalc_engagement(animal_id: int | None) -> None:
    if not animal_id:
        return
    logs = EnrichmentLog.query.filter(EnrichmentLog.animal_id == animal_id).order_by(EnrichmentLog.timestamp).all()
    summary = enrichment_engagement_summary(logs)
    score = 0.0
    for entry in summary.rolling_scores.get(animal_id, []):
        duration = entry.get("duration") or 0
        score += float(duration)
    existing = (
        EnrichmentEngagementSummary.query.filter(EnrichmentEngagementSummary.animal_id == animal_id)
        .order_by(EnrichmentEngagementSummary.calculated_at.desc())
        .first()
    )
    snapshot = EnrichmentEngagementSummary(
        calculated_at=datetime.utcnow(),
        engagement_score=round(score, 2),
        alert_triggered=bool(summary.alerts),
        animal_id=animal_id,
    )
    if existing:
        existing.calculated_at = snapshot.calculated_at
        existing.engagement_score = snapshot.engagement_score
        existing.alert_triggered = snapshot.alert_triggered
    else:
        db.session.add(snapshot)
    db.session.commit()
