"""Utilities for importing animal data from CSV, Excel, or SQL sources."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterable, List, Sequence

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from . import models

REQUIRED_COLUMNS = {"Animal ID", "Cage ID", "Sex", "Age", "Weight"}


class ImportValidationError(RuntimeError):
    """Raised when a dataset does not contain the required structure."""


def _normalise_columns(columns: Sequence[str]) -> List[str]:
    return [col.strip() for col in columns]


def _validate_columns(columns: Iterable[str]) -> None:
    missing = REQUIRED_COLUMNS.difference({c.strip() for c in columns})
    if missing:
        raise ImportValidationError(f"Missing required columns: {', '.join(sorted(missing))}")


def _frame_from_source(source: str) -> pd.DataFrame:
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(source)

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    elif path.suffix.lower() in {".xls", ".xlsx"}:
        df = pd.read_excel(path)
    else:
        raise ImportValidationError("Unsupported file extension. Provide CSV or Excel.")

    df.columns = _normalise_columns(df.columns)
    _validate_columns(df.columns)
    return df


async def import_animals_from_file(session: AsyncSession, source: str) -> None:
    """Import animals from a CSV or Excel file into the database."""

    df = _frame_from_source(source)
    await _bulk_upsert_animals(session, df.to_dict(orient="records"))


async def import_animals_from_sql(session: AsyncSession, query: str) -> None:
    """Import animals using a SQL query against the configured database."""

    result = await session.execute(text(query))
    records = [dict(row._mapping) for row in result]
    if not records:
        return
    _validate_columns(records[0].keys())
    await _bulk_upsert_animals(session, records)


async def _bulk_upsert_animals(session: AsyncSession, records: Iterable[dict]) -> None:
    for record in records:
        animal = await session.execute(
            text("SELECT * FROM animals WHERE animal_id = :animal_id"),
            {"animal_id": record["Animal ID"]},
        )
        mapped = {
            "animal_id": record["Animal ID"],
            "cage_id": record["Cage ID"],
            "sex": record["Sex"].upper(),
            "age": float(record["Age"]),
            "weight": float(record["Weight"]),
        }
        db_record = animal.fetchone()
        if db_record:
            await session.execute(
                text(
                    "UPDATE animals SET cage_id=:cage_id, sex=:sex, age=:age, weight=:weight "
                    "WHERE animal_id=:animal_id"
                ),
                mapped,
            )
        else:
            session.add(models.Animal(**mapped))
    await session.commit()
