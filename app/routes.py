from __future__ import annotations

import io
import json
import os
from datetime import datetime, timedelta

import pandas as pd
from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from sqlalchemy import create_engine, func, inspect, or_
from werkzeug.utils import secure_filename

from . import db
from .models import (
    Animal,
    AuditLog,
    BehaviorDefinition,
    BehaviorEvent,
    BehaviorLog,
    CustomSchemaField,
    DataIngestionSession,
    DatasetNote,
    EnrichmentItem,
    EnrichmentLog,
    IncidentObservation,
    ObservationSession,
    SessionNote,
    StressLog,
)
from .utils.analytics import build_rank_graph, colony_behavior_stats, compute_elo
from .utils.audit import log_audit
from .utils.ingestion import ingest_animals, read_sql, read_tabular
from .utils.validation import (
    build_sqlalchemy_uri,
    validate_custom_fields,
    validate_sql_credentials,
)

bp = Blueprint("routes", __name__)


def _save_media_file(file_storage) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secure_filename(file_storage.filename)}"
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, filename)
    file_storage.save(file_path)
    return filename


def _ensure_subject_fields(dataframe: pd.DataFrame, schema: list[CustomSchemaField]) -> None:
    missing = [field.label or field.field_name for field in schema if field.required and field.field_name not in dataframe.columns]
    if missing:
        raise ValueError(
            "Dataset missing required subject fields: " + ", ".join(sorted(missing))
        )


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

    recent_sessions = ObservationSession.query.order_by(ObservationSession.created_at.desc()).limit(5).all()
    recent_ingestions = DataIngestionSession.query.order_by(DataIngestionSession.created_at.desc()).limit(5).all()
    dataset_notes = DatasetNote.query.order_by(DatasetNote.created_at.desc()).limit(6).all()
    event_summary = (
        db.session.query(BehaviorEvent.custom_code, func.count(BehaviorEvent.id))
        .group_by(BehaviorEvent.custom_code)
        .order_by(func.count(BehaviorEvent.id).desc())
        .limit(6)
        .all()
    )

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
        recent_sessions=recent_sessions,
        recent_ingestions=recent_ingestions,
        dataset_notes=dataset_notes,
        event_summary=event_summary,
    )


@bp.route("/upload", methods=["GET", "POST"])
def upload() -> str:
    sql_hosts = ["localhost", "lab-db", "analysis-cluster"]
    sql_ports = ["5432", "5433", "3306", "1433"]
    sql_drivers = ["postgresql", "postgresql+psycopg2", "mysql", "sqlite"]

    subject_schema = (
        CustomSchemaField.query.filter_by(scope="subject").order_by(CustomSchemaField.label).all()
    )
    event_schema = (
        CustomSchemaField.query.filter_by(scope="event").order_by(CustomSchemaField.label).all()
    )

    preview_rows: list[dict] | None = None
    preview_columns: list[str] = []
    form_errors: dict[str, str] = {}
    ingestion_errors: list[str] = []

    sessions = (
        DataIngestionSession.query.order_by(DataIngestionSession.created_at.desc())
        .limit(12)
        .all()
    )
    error_logs = (
        AuditLog.query.filter(AuditLog.action.in_(["ingest_failed", "sql_preview_failed"]))
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )

    if request.method == "POST":
        action = request.form.get("action", "ingest")
        user = request.form.get("user", "unknown")
        notes = request.form.get("notes") or ""
        session_notes = request.form.getlist("session_notes")
        sql_payload = {
            "driver": request.form.get("sql_driver"),
            "host": request.form.get("sql_host"),
            "port": request.form.get("sql_port"),
            "username": request.form.get("sql_username"),
            "password": request.form.get("sql_password"),
            "database": request.form.get("sql_database"),
            "table": request.form.get("sql_table"),
        }

        try:
            if action == "preview-file":
                file = request.files.get("file")
                if not file or not file.filename:
                    raise ValueError("Select a CSV or Excel file to preview")
                dataframe = read_tabular(file)
                _ensure_subject_fields(dataframe, subject_schema)
                preview_rows = dataframe.head(15).to_dict(orient="records")
                preview_columns = list(dataframe.columns)
                flash("Preview generated. Review the data before ingesting.", "info")
            elif action == "preview-sql":
                form_errors = validate_sql_credentials(sql_payload)
                if form_errors:
                    raise ValueError("Resolve SQL issues before previewing")
                connection_uri = build_sqlalchemy_uri(sql_payload)
                dataframe = read_sql(connection_uri, sql_payload["table"])
                _ensure_subject_fields(dataframe, subject_schema)
                preview_rows = dataframe.head(15).to_dict(orient="records")
                preview_columns = list(dataframe.columns)
                flash("SQL preview generated successfully.", "info")
            else:
                source_type = request.form.get("source_type", "file")
                if source_type == "sql":
                    form_errors = validate_sql_credentials(sql_payload)
                    if form_errors:
                        raise ValueError("Resolve SQL issues before importing")
                    connection_uri = build_sqlalchemy_uri(sql_payload)
                    dataframe = read_sql(connection_uri, sql_payload["table"])
                    _ensure_subject_fields(dataframe, subject_schema)
                    ingest_animals(
                        dataframe,
                        user=user,
                        source=f"SQL:{sql_payload['table']}",
                        notes=notes,
                        session_notes=session_notes,
                    )
                    flash("Animal records imported from SQL", "success")
                else:
                    file = request.files.get("file")
                    if not file or not file.filename:
                        raise ValueError("Attach a CSV or Excel file to import")
                    dataframe = read_tabular(file)
                    _ensure_subject_fields(dataframe, subject_schema)
                    ingest_animals(
                        dataframe,
                        user=user,
                        source=file.filename,
                        notes=notes,
                        session_notes=session_notes,
                    )
                    flash("Animal records imported successfully", "success")
                return redirect(url_for("routes.upload"))
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            ingestion_errors.append(message)
            if action.startswith("preview"):
                log_audit(
                    "sql_preview_failed" if "sql" in action else "ingest_failed",
                    "DataIngestionSession",
                    "preview",
                    metadata={"error": message, "action": action},
                )
            else:
                log_audit(
                    "ingest_failed",
                    "DataIngestionSession",
                    "pending",
                    metadata={"error": message, "source_type": request.form.get("source_type")},
                )
            flash(f"Upload issue: {message}", "danger")

    return render_template(
        "upload.html",
        sql_hosts=sql_hosts,
        sql_ports=sql_ports,
        sql_drivers=sql_drivers,
        preview_rows=preview_rows,
        preview_columns=preview_columns,
        form_errors=form_errors,
        ingestion_errors=ingestion_errors,
        sessions=sessions,
        error_logs=error_logs,
        subject_schema=subject_schema,
        event_schema=event_schema,
    )


@bp.post("/upload/sql-discover")
def sql_discover() -> Response:
    payload = request.get_json() or {}
    errors = validate_sql_credentials(payload)
    if errors:
        return jsonify({"errors": errors}), 400
    connection_uri = build_sqlalchemy_uri(payload)
    try:
        engine = create_engine(connection_uri)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
    except Exception as exc:  # noqa: BLE001
        log_audit(
            "sql_preview_failed",
            "DataIngestionSession",
            "discover",
            metadata={"error": str(exc)},
        )
        return jsonify({"errors": {"connection": str(exc)}}), 400
    return jsonify({"tables": tables})


@bp.route("/sessions", methods=["GET", "POST"])
def session_dashboard() -> str:
    ingestion_choices = DataIngestionSession.query.order_by(DataIngestionSession.created_at.desc()).all()
    observation_sessions = (
        ObservationSession.query.order_by(ObservationSession.created_at.desc()).limit(25).all()
    )
    event_totals = (
        db.session.query(BehaviorEvent.custom_code, func.count(BehaviorEvent.id))
        .group_by(BehaviorEvent.custom_code)
        .order_by(func.count(BehaviorEvent.id).desc())
        .all()
    )
    recent_events = BehaviorEvent.query.order_by(BehaviorEvent.timestamp.desc()).limit(12).all()
    summary_stats = {
        "total_sessions": ObservationSession.query.count(),
        "total_events": BehaviorEvent.query.count(),
        "sessions_with_media": ObservationSession.query.filter(
            (ObservationSession.video_url.isnot(None)) | (ObservationSession.audio_url.isnot(None))
        ).count(),
    }

    if request.method == "POST":
        name = request.form.get("name")
        created_by = request.form.get("created_by", "unknown")
        status = request.form.get("status", "draft")
        session_notes = request.form.get("session_notes")
        ingestion_session_id = request.form.get("ingestion_session_id") or None
        if ingestion_session_id:
            ingestion_session_id = int(ingestion_session_id)
        video_url = None
        audio_url = None

        video_file = request.files.get("video_file")
        audio_file = request.files.get("audio_file")
        link_video = request.form.get("video_link")
        link_audio = request.form.get("audio_link")

        if video_file and video_file.filename:
            stored = _save_media_file(video_file)
            if stored:
                video_url = url_for("routes.media", filename=stored)
        elif link_video:
            video_url = link_video

        if audio_file and audio_file.filename:
            stored_audio = _save_media_file(audio_file)
            if stored_audio:
                audio_url = url_for("routes.media", filename=stored_audio)
        elif link_audio:
            audio_url = link_audio

        if not name:
            flash("Provide a session name", "danger")
        else:
            session = ObservationSession(
                name=name,
                created_by=created_by,
                status=status,
                notes=session_notes,
                video_url=video_url,
                audio_url=audio_url,
                ingestion_session_id=ingestion_session_id,
            )
            db.session.add(session)
            if session_notes:
                db.session.add(SessionNote(session=session, created_by=created_by, note=session_notes))
            db.session.commit()
            log_audit(
                "session_created",
                "ObservationSession",
                str(session.id),
                metadata={"status": status},
            )
            flash("Observation session created", "success")
            return redirect(url_for("routes.session_dashboard"))

    return render_template(
        "session_dashboard.html",
        ingestion_choices=ingestion_choices,
        observation_sessions=observation_sessions,
        event_totals=event_totals,
        recent_events=recent_events,
        summary_stats=summary_stats,
    )


@bp.route("/sessions/<int:session_id>", methods=["GET", "POST"])
def session_detail(session_id: int) -> str:
    session = ObservationSession.query.get_or_404(session_id)
    animals = Animal.query.order_by(Animal.persistent_id).all()
    behaviors = BehaviorDefinition.query.order_by(BehaviorDefinition.name).all()
    event_schema = CustomSchemaField.query.filter_by(scope="event").order_by(CustomSchemaField.label).all()

    custom_schema = [
        {
            "field_name": field.field_name,
            "label": field.label,
            "required": field.required,
            "data_type": field.data_type,
        }
        for field in event_schema
    ]

    event_errors: dict[str, str] = {}
    note_error: str | None = None

    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_event":
            custom_code = request.form.get("custom_code")
            timestamp_raw = request.form.get("timestamp")
            duration_raw = request.form.get("duration")
            description = request.form.get("description")
            animal_id = request.form.get("animal_id") or None
            behavior_id = request.form.get("behavior_id") or None

            metadata_payload = {
                schema_field["field_name"]: request.form.get(f"event_field_{schema_field['field_name']}")
                for schema_field in custom_schema
            }
            event_errors = validate_custom_fields(custom_schema, metadata_payload)

            if not custom_code:
                event_errors["custom_code"] = "Event code is required"

            try:
                timestamp_value = datetime.fromisoformat(timestamp_raw) if timestamp_raw else datetime.utcnow()
            except ValueError:
                event_errors["timestamp"] = "Timestamp must be ISO formatted (YYYY-MM-DD HH:MM:SS)"
                timestamp_value = datetime.utcnow()

            duration_value = None
            if duration_raw:
                try:
                    duration_value = float(duration_raw)
                except ValueError:
                    event_errors["duration"] = "Duration must be numeric"

            if not event_errors:
                clean_metadata = {k: v for k, v in metadata_payload.items() if v}
                event = BehaviorEvent(
                    session=session,
                    custom_code=custom_code,
                    description=description,
                    timestamp=timestamp_value,
                    duration_seconds=duration_value,
                    animal_id=animal_id,
                    behavior_id=behavior_id,
                    metadata=clean_metadata,
                )
                db.session.add(event)
                db.session.commit()
                log_audit(
                    "event_logged",
                    "ObservationSession",
                    str(session.id),
                    metadata={"event_id": event.id, "code": custom_code},
                )
                flash("Behavioral event recorded", "success")
                return redirect(url_for("routes.session_detail", session_id=session.id))
        elif action == "add_note":
            note_text = request.form.get("note")
            author = request.form.get("note_author", "observer")
            if not note_text or not note_text.strip():
                note_error = "Note text is required"
            else:
                note = SessionNote(session=session, created_by=author, note=note_text.strip())
                db.session.add(note)
                db.session.commit()
                log_audit(
                    "session_note_added",
                    "ObservationSession",
                    str(session.id),
                    metadata={"note_id": note.id},
                )
                flash("Note added to session", "success")
                return redirect(url_for("routes.session_detail", session_id=session.id))
        elif action == "update_status":
            session.status = request.form.get("status", session.status)
            db.session.commit()
            log_audit(
                "session_status_updated",
                "ObservationSession",
                str(session.id),
                metadata={"status": session.status},
            )
            flash("Session status updated", "success")
            return redirect(url_for("routes.session_detail", session_id=session.id))

    events = BehaviorEvent.query.filter_by(session_id=session.id).order_by(BehaviorEvent.timestamp.asc()).all()

    return render_template(
        "session_detail.html",
        session=session,
        animals=animals,
        behaviors=behaviors,
        events=events,
        event_schema=event_schema,
        event_errors=event_errors,
        note_error=note_error,
        datetime=datetime,
    )


@bp.get("/sessions/<int:session_id>/export")
def export_session_events(session_id: int) -> Response:
    export_format = request.args.get("format", "csv")
    session = ObservationSession.query.get_or_404(session_id)
    events = BehaviorEvent.query.filter_by(session_id=session.id).order_by(BehaviorEvent.timestamp.asc()).all()

    rows: list[dict[str, object]] = []
    for event in events:
        row = {
            "timestamp": event.timestamp.isoformat(),
            "custom_code": event.custom_code,
            "duration_seconds": event.duration_seconds,
            "description": event.description,
            "animal": event.animal.persistent_id if event.animal else None,
            "behavior": event.behavior.name if event.behavior else None,
        }
        for key, value in (event.metadata or {}).items():
            row[f"meta_{key}"] = value
        rows.append(row)

    dataframe = pd.DataFrame(rows)
    if export_format == "csv":
        return Response(
            dataframe.to_csv(index=False),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=session-{session.id}.csv"},
        )
    if export_format in {"xlsx", "xls"}:
        stream = io.BytesIO()
        with pd.ExcelWriter(stream) as writer:
            dataframe.to_excel(writer, index=False)
        stream.seek(0)
        return send_file(
            stream,
            as_attachment=True,
            download_name=f"session-{session.id}.{export_format}",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    flash("Unsupported export format", "warning")
    return redirect(url_for("routes.session_detail", session_id=session.id))


@bp.route("/schemas", methods=["GET", "POST"])
def schema_manager() -> str:
    subject_fields = CustomSchemaField.query.filter_by(scope="subject").order_by(CustomSchemaField.label).all()
    event_fields = CustomSchemaField.query.filter_by(scope="event").order_by(CustomSchemaField.label).all()
    errors: dict[str, str] = {}

    if request.method == "POST":
        scope = request.form.get("scope")
        field_name = request.form.get("field_name")
        label = request.form.get("label")
        data_type = request.form.get("data_type", "string")
        required = bool(request.form.get("required"))

        if scope not in {"subject", "event"}:
            errors["scope"] = "Select a valid scope"
        if not field_name:
            errors["field_name"] = "Field name is required"
        if not label:
            errors["label"] = "Label is required"

        if not errors:
            field = CustomSchemaField(
                scope=scope,
                field_name=field_name,
                label=label,
                data_type=data_type,
                required=required,
            )
            db.session.add(field)
            db.session.commit()
            log_audit(
                "schema_field_added",
                "CustomSchemaField",
                str(field.id),
                metadata={"scope": scope},
            )
            flash("Custom field saved", "success")
            return redirect(url_for("routes.schema_manager"))
        flash("Please resolve the highlighted issues", "danger")

    return render_template(
        "schema_manager.html",
        subject_fields=subject_fields,
        event_fields=event_fields,
        errors=errors,
    )


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


@bp.route("/media/<path:filename>")
def media(filename: str) -> Response:
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


def row_to_dict(row) -> dict:
    result = {}
    for column in row.__table__.columns:
        result[column.name] = getattr(row, column.name)
    return result
