from __future__ import annotations

import io
from datetime import datetime
import io
from typing import Any

import pandas as pd
from flask import current_app
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import Animal, DataIngestionSession, DatasetNote
from .audit import log_audit
from .validation import validate_dataframe, validate_sqlalchemy_uri


REQUIRED_COLUMNS = {"Animal ID", "Cage ID", "Sex", "Age", "Weight"}


def _normalize_columns(columns: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for column in columns:
        normalized = column.strip()
        mapping[column] = normalized
    return mapping


def read_tabular(file_storage) -> pd.DataFrame:
    """Read CSV or Excel uploads into a DataFrame."""
    filename = file_storage.filename or ""
    stream = io.BytesIO(file_storage.read())
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(stream)
    else:
        df = pd.read_excel(stream)
    df.rename(columns=_normalize_columns(list(df.columns)), inplace=True)
    errors = validate_dataframe(df, REQUIRED_COLUMNS)
    if errors:
        raise ValueError("; ".join(errors))
    return df


def read_sql(connection_uri: str, table_name: str) -> pd.DataFrame:
    """Load animals from a SQL table using SQLAlchemy engines."""
    uri_error = validate_sqlalchemy_uri(connection_uri)
    if uri_error:
        raise ValueError(uri_error)
    engine = create_engine(connection_uri)
    with engine.connect() as connection:
        df = pd.read_sql_table(table_name, connection)
    df.rename(columns=_normalize_columns(list(df.columns)), inplace=True)
    errors = validate_dataframe(df, REQUIRED_COLUMNS)
    if errors:
        raise ValueError("; ".join(errors))
    return df


def ingest_animals(
    dataframe: pd.DataFrame,
    user: str,
    source: str,
    notes: str | None = None,
    session_notes: list[str] | None = None,
) -> DataIngestionSession:
    """Persist animals from a dataframe and return the ingestion session."""
    session = DataIngestionSession(created_by=user, source=source, notes=notes)
    db.session.add(session)

    if session_notes:
        for note in session_notes:
            if note.strip():
                db.session.add(
                    DatasetNote(ingestion_session=session, created_by=user, note=note.strip())
                )

    for _, row in dataframe.iterrows():
        persistent_id = str(row.get("Animal ID"))
        animal = Animal.query.filter_by(persistent_id=persistent_id).one_or_none()
        if animal is None:
            animal = Animal(persistent_id=persistent_id)
        animal.cage_id = str(row.get("Cage ID"))
        animal.sex = str(row.get("Sex"))
        animal.age = int(row.get("Age")) if not pd.isna(row.get("Age")) else None
        animal.weight_kg = float(row.get("Weight")) if not pd.isna(row.get("Weight")) else None
        animal.name = row.get("Name") if "Name" in row and not pd.isna(row.get("Name")) else None
        animal.matriline = (
            row.get("Matriline") if "Matriline" in row and not pd.isna(row.get("Matriline")) else None
        )
        dob = row.get("DOB") if "DOB" in row else None
        if pd.notna(dob):
            if isinstance(dob, datetime):
                animal.date_of_birth = dob
            else:
                animal.date_of_birth = pd.to_datetime(dob)
        animal.ingestion_session = session
        db.session.add(animal)

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to ingest animals", exc_info=exc)
        raise
    else:
        log_audit(
            action="ingest_animals",
            target_type="DataIngestionSession",
            target_id=str(session.id),
            metadata={"source": source, "records": len(dataframe)},
        )
    return session
