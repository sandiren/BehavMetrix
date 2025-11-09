from __future__ import annotations

import io
import json
from collections import defaultdict
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
from .models import (
    Animal,
    AnimalNote,
    BehaviorDefinition,
    BehaviorLog,
    BehaviorSession,
    EnrichmentItem,
    EnrichmentLog,
    IncidentObservation,
    RankScore,
    SessionParticipant,
    StressLog,
    VideoClip,
    VoiceTranscript,
)
from .utils.analytics import (
    behavior_heatmap,
    build_rank_graph,
    colony_behavior_stats,
    compute_elo,
    enrichment_summary,
    progress_tracker,
    stress_trend,
    update_rank_snapshots,
)
from .utils.ingestion import ingest_animals, read_sql, read_tabular

bp = Blueprint("routes", __name__)


@bp.route("/")
def dashboard() -> str:
    search_term = request.args.get("search")
    cage_filter = request.args.get("cage")
    sex_filter = request.args.get("sex")
    pinned_raw = request.args.get("pinned", "")
    pinned_ids = {int(pid) for pid in pinned_raw.split(",") if pid.isdigit()}

    all_animals = Animal.query.order_by(Animal.persistent_id).all()
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
    now = datetime.utcnow()
    behavior_cutoff = now - timedelta(days=30)
    behavior_logs = (
        BehaviorLog.query.filter(BehaviorLog.timestamp >= behavior_cutoff)
        .order_by(BehaviorLog.timestamp.desc())
        .all()
    )
    enrichment_logs = (
        EnrichmentLog.query.filter(EnrichmentLog.timestamp >= behavior_cutoff)
        .order_by(EnrichmentLog.timestamp.desc())
        .all()
    )
    stats = colony_behavior_stats(behavior_logs)
    elo_result = compute_elo(behavior_logs)

    # Persist daily snapshots for exportable FAIR reporting
    latest_snapshot = db.session.query(func.max(RankScore.created_at)).scalar()
    if not latest_snapshot or latest_snapshot.date() != now.date():
        snapshots = update_rank_snapshots(elo_result, all_animals)
        db.session.add_all(snapshots)
        db.session.commit()

    today_start = datetime(now.year, now.month, now.day)
    todays_logs = [log for log in behavior_logs if log.timestamp >= today_start]
    progress = progress_tracker(len(all_animals), todays_logs)

    animal_lookup = {animal.id: animal for animal in all_animals}
    profiles: list[dict[str, object]] = []
    for animal in animals:
        stress_series = stress_trend(animal)
        heatmap = behavior_heatmap(animal, behavior_logs)
        enrichment = enrichment_summary(animal, enrichment_logs)
        recent_note = (
            AnimalNote.query.filter(AnimalNote.animal_id == animal.id)
            .order_by(AnimalNote.created_at.desc())
            .first()
        )
        stress_score = stress_series[-1]["score"] if stress_series else 0
        welfare_flag = stress_score >= 4 or not heatmap
        profiles.append(
            {
                "animal": animal,
                "stress_score": stress_score,
                "stress_series": stress_series,
                "heatmap": heatmap,
                "rank": round(elo_result.scores.get(animal.id, 1000), 1),
                "davids": round(elo_result.davids_scores.get(animal.id, 0.0), 2),
                "enrichment": enrichment,
                "welfare_flag": welfare_flag,
                "latest_note": recent_note,
            }
        )

    profiles.sort(key=lambda profile: profile["animal"].persistent_id)
    pinned_profiles = [profile for profile in profiles if profile["animal"].id in pinned_ids]
    unpinned_profiles = [profile for profile in profiles if profile["animal"].id not in pinned_ids]

    graph = build_rank_graph(animals, elo_result.scores)
    network_data = json.dumps(
        {
            "nodes": [
                {
                    "id": node,
                    "label": data["label"],
                    "elo": data.get("elo", 1000),
                    "alert": elo_result.alerts.get(node),
                }
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

    recent_sessions = BehaviorSession.query.order_by(BehaviorSession.started_at.desc()).limit(5).all()

    return render_template(
        "dashboard.html",
        pinned_profiles=pinned_profiles,
        profiles=unpinned_profiles,
        stats=stats,
        network_data=network_data,
        instability_flags=instability_labels,
        progress=progress,
        elo_alerts=elo_result.alerts,
        animal_lookup=animal_lookup,
        search_term=search_term or "",
        cage_filter=cage_filter or "",
        sex_filter=sex_filter or "",
        cage_choices=cages,
        sex_choices=sexes,
        recent_sessions=recent_sessions,
        pinned_ids=pinned_ids,
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
    ethogram_map: dict[str, list[BehaviorDefinition]] = defaultdict(list)
    for behavior in behaviors:
        key = behavior.category.name if behavior.category else "Uncategorized"
        ethogram_map[key].append(behavior)

    active_session = (
        BehaviorSession.query.filter(BehaviorSession.ended_at.is_(None))
        .order_by(BehaviorSession.started_at.desc())
        .first()
    )
    if request.method == "POST":
        action = request.form.get("action", "log")
        if action == "start-session":
            session = BehaviorSession(
                name=request.form.get("session_name"),
                mode=request.form.get("mode", "real_time"),
                observer_id=None,
                cage_id=request.form.get("session_cage"),
                group_label=request.form.get("session_group"),
                notes=request.form.get("session_notes"),
                metadata_json={"device": request.form.get("device", "web")},
            )
            db.session.add(session)
            db.session.flush()
            for animal_id in request.form.getlist("session_animals"):
                if animal_id:
                    db.session.add(SessionParticipant(session_id=session.id, animal_id=int(animal_id)))
            db.session.commit()
            flash("Real-time session started", "success")
            return redirect(url_for("routes.behavior_log", session_id=session.id))
        if action == "end-session" and request.form.get("session_id"):
            session = BehaviorSession.query.get(int(request.form.get("session_id")))
            if session:
                session.ended_at = datetime.utcnow()
                session.notes = request.form.get("session_notes") or session.notes
                db.session.commit()
                flash("Session closed", "info")
            return redirect(url_for("routes.behavior_log"))
        if action == "undo" and request.form.get("log_id"):
            log = BehaviorLog.query.get(int(request.form.get("log_id")))
            if log:
                db.session.delete(log)
                db.session.commit()
                flash("Last entry removed", "warning")
            return redirect(url_for("routes.behavior_log", session_id=request.form.get("session_id")))
        if action == "voice-transcript" and request.form.get("voice_text"):
            transcript = VoiceTranscript(
                session_id=request.form.get("session_id") or (active_session.id if active_session else None),
                transcript_text=request.form.get("voice_text"),
            )
            db.session.add(transcript)
            db.session.commit()
            flash("Transcript captured", "success")
            return redirect(url_for("routes.behavior_log", session_id=request.form.get("session_id")))

        selected_animals = request.form.getlist("animal_ids") or [request.form.get("animal_id")]
        partner_id_raw = request.form.get("partner_id")
        partner_id = int(partner_id_raw) if partner_id_raw else None
        mode = request.form.get("mode", "real_time")
        session_id = request.form.get("session_id") or (active_session.id if active_session else None)
        duration_raw = request.form.get("duration_seconds")
        metadata = {"notes": request.form.get("context")}
        behavior_id_raw = request.form.get("behavior_id") or request.form.get("behavior_select")
        if not behavior_id_raw:
            flash("Select a behavior before logging.", "warning")
            return redirect(url_for("routes.behavior_log", session_id=session_id))
        created = 0
        for animal_id in filter(None, selected_animals):
            log = BehaviorLog(
                animal_id=int(animal_id),
                behavior_id=int(behavior_id_raw),
                observer_id=None,
                timestamp=datetime.utcnow(),
                sample_type=request.form.get("sample_type", "focal"),
                context=request.form.get("context"),
                interaction_partner_id=partner_id,
                mode=mode,
                session_id=int(session_id) if session_id else None,
                duration_seconds=float(duration_raw) if duration_raw else None,
                metadata_json=metadata,
            )
            db.session.add(log)
            created += 1
        if request.form.get("note") and selected_animals:
            db.session.add(
                AnimalNote(
                    animal_id=int(selected_animals[0]),
                    session_id=int(session_id) if session_id else None,
                    content=request.form.get("note"),
                    created_by="observer",
                )
            )
        db.session.commit()
        flash(f"Logged {created} behavior events", "success")
        return redirect(url_for("routes.behavior_log", session_id=session_id))

    session_id_param = request.args.get("session_id")
    if session_id_param:
        active_session = BehaviorSession.query.get(int(session_id_param))

    session_logs: list[BehaviorLog] = []
    if active_session:
        session_logs = (
            BehaviorLog.query.filter(BehaviorLog.session_id == active_session.id)
            .order_by(BehaviorLog.timestamp.desc())
            .limit(100)
            .all()
        )
    else:
        session_logs = (
            BehaviorLog.query.order_by(BehaviorLog.timestamp.desc()).limit(50).all()
        )

    frequency_stats: dict[str, int] = defaultdict(int)
    for log in session_logs:
        if log.behavior:
            frequency_stats[log.behavior.code] += 1

    transcripts = (
        VoiceTranscript.query.order_by(VoiceTranscript.created_at.desc()).limit(10).all()
    )

    return render_template(
        "behavior_log.html",
        animals=animals,
        behaviors=behaviors,
        ethogram_map=ethogram_map,
        active_session=active_session,
        session_logs=session_logs,
        frequency_stats=frequency_stats,
        transcripts=transcripts,
    )


@bp.route("/enrichment", methods=["GET", "POST"])
def enrichment() -> str:
    cage_filter = request.args.get("cage")
    animal_query = Animal.query
    if cage_filter:
        animal_query = animal_query.filter(Animal.cage_id == cage_filter)
    animals = animal_query.order_by(Animal.persistent_id).all()
    items = EnrichmentItem.query.order_by(EnrichmentItem.name).all()
    if request.method == "POST":
        selected_animals = request.form.getlist("animal_ids") or [request.form.get("animal_id")]
        start_raw = request.form.get("start_time")
        end_raw = request.form.get("end_time")
        duration_raw = request.form.get("duration")
        start_time = datetime.fromisoformat(start_raw) if start_raw else None
        end_time = datetime.fromisoformat(end_raw) if end_raw else None
        duration_minutes = float(duration_raw) if duration_raw else None
        created = 0
        for animal_id in filter(None, selected_animals):
            log = EnrichmentLog(
                animal_id=int(animal_id),
                enrichment_item_id=request.form.get("item_id"),
                start_time=start_time,
                end_time=end_time,
                duration_minutes=duration_minutes,
                response=request.form.get("response"),
                outcome=request.form.get("outcome"),
                notes=request.form.get("notes"),
                tag=request.form.get("tag"),
                frequency=request.form.get("frequency"),
                metadata_json={"delivery": request.form.get("delivery_method")},
            )
            db.session.add(log)
            created += 1
        db.session.commit()
        flash(f"Logged enrichment for {created} animals", "success")
        return redirect(url_for("routes.enrichment", cage=cage_filter))

    recent_logs = (
        EnrichmentLog.query.order_by(EnrichmentLog.timestamp.desc()).limit(25).all()
    )
    cage_totals: dict[str, int] = defaultdict(int)
    for log in recent_logs:
        if log.animal:
            cage_totals[log.animal.cage_id] += 1

    cages = [row[0] for row in db.session.query(Animal.cage_id).distinct().order_by(Animal.cage_id)]
    return render_template(
        "enrichment.html",
        animals=animals,
        items=items,
        recent_logs=recent_logs,
        cage_totals=cage_totals,
        cages=cages,
        cage_filter=cage_filter or "",
    )


@bp.route("/stress", methods=["GET", "POST"])
def stress() -> str:
    animals = Animal.query.order_by(Animal.persistent_id).all()
    if request.method == "POST":
        date_str = request.form.get("date")
        log = StressLog(
            animal_id=request.form.get("animal_id"),
            date=datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.utcnow(),
            stress_score=int(request.form.get("stress_score", 0)) or None,
            withdrawal=bool(request.form.get("withdrawal")),
            fear_grimace=bool(request.form.get("fear_grimace")),
            pacing=bool(request.form.get("pacing")),
            self_biting=bool(request.form.get("self_biting")),
            scratching=bool(request.form.get("scratching")),
            vocalization=bool(request.form.get("vocalization")),
            linked_cortisol=float(request.form.get("cortisol")) if request.form.get("cortisol") else None,
            notes=request.form.get("notes"),
        )
        db.session.add(log)
        db.session.commit()
        flash("Stress log saved", "success")
        return redirect(url_for("routes.stress"))

    recent_logs = (
        StressLog.query.order_by(StressLog.date.desc()).limit(60).all()
    )
    daily_index: dict[str, list[int]] = defaultdict(list)
    for entry in recent_logs:
        day = entry.date.strftime("%Y-%m-%d")
        daily_index[day].append(entry.stress_score)
    daily_summary = {
        day: round(sum(values) / len(values), 2) if values else 0 for day, values in daily_index.items()
    }
    alerts = [entry for entry in recent_logs if entry.stress_score >= 5]

    return render_template(
        "stress.html",
        animals=animals,
        today=datetime.utcnow().date(),
        recent_logs=recent_logs,
        daily_summary=daily_summary,
        alerts=alerts,
    )


@bp.route("/incident", methods=["GET", "POST"])
def incident() -> str:
    animals = Animal.query.order_by(Animal.persistent_id).all()
    if request.method == "POST":
        log = IncidentObservation(
            animal_id=request.form.get("animal_id") or None,
            reason=request.form.get("reason"),
            description=request.form.get("description"),
            attachment_url=request.form.get("attachment_url"),
            video_url=request.form.get("video_url"),
            tags=request.form.get("tags"),
        )
        db.session.add(log)
        if request.form.get("note") and request.form.get("animal_id"):
            db.session.add(
                AnimalNote(
                    animal_id=int(request.form.get("animal_id")),
                    content=request.form.get("note"),
                    note_type="incident",
                )
            )
        db.session.commit()
        flash("Observation recorded", "success")
        return redirect(url_for("routes.incident"))

    incidents = (
        IncidentObservation.query.order_by(IncidentObservation.created_at.desc()).limit(40).all()
    )
    return render_template("incident.html", animals=animals, incidents=incidents)


@bp.route("/export/<string:resource>.<string:ext>")
def export_resource(resource: str, ext: str) -> Response:
    query_map = {
        "animals": Animal,
        "behaviors": BehaviorLog,
        "enrichments": EnrichmentLog,
        "stress": StressLog,
        "ranks": RankScore,
        "incidents": IncidentObservation,
        "notes": AnimalNote,
        "videos": VideoClip,
        "voice": VoiceTranscript,
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
