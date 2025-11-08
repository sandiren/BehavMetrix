"""Generate CSV/Excel exports and PDF summaries."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Iterable, List

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .config import settings


async def export_animals(session: AsyncSession, path: str) -> str:
    result = await session.execute(select(models.Animal))
    animals = [
        {
            "Animal ID": animal.animal_id,
            "Cage ID": animal.cage_id,
            "Sex": animal.sex,
            "Age": animal.age,
            "Weight": animal.weight,
            "Welfare Score": animal.welfare_score,
            "Social Rank": animal.social_rank,
            "Enrichment Status": animal.enrichment_status,
        }
        for animal in result.scalars().all()
    ]
    df = pd.DataFrame(animals)
    ext = Path(path).suffix.lower()
    if ext == ".csv":
        df.to_csv(path, index=False)
    elif ext in {".xls", ".xlsx"}:
        df.to_excel(path, index=False)
    else:
        raise ValueError("Unsupported export extension")
    return path


async def export_behavior_logs(session: AsyncSession, path: str) -> str:
    result = await session.execute(select(models.BehaviorLog))
    logs = [
        {
            "Animal": log.animal_id,
            "Behavior": log.behavior,
            "Reason": log.reason,
            "Intensity": log.intensity,
            "Actor": log.actor_id,
            "Target": log.target_id,
            "Timestamp": log.timestamp.isoformat(),
        }
        for log in result.scalars().all()
    ]
    df = pd.DataFrame(logs)
    if Path(path).suffix.lower() == ".csv":
        df.to_csv(path, index=False)
    else:
        df.to_excel(path, index=False)
    return path


async def generate_weekly_pdf(session: AsyncSession) -> str:
    output_dir = Path(settings.pdf_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"weekly-summary-{dt.date.today().isoformat()}.pdf"

    animal_result = await session.execute(
        select(models.Animal).order_by(models.Animal.welfare_score.asc()).limit(5)
    )
    at_risk = animal_result.scalars().all()

    stress_result = await session.execute(
        select(models.StressLog).order_by(models.StressLog.timestamp.desc()).limit(20)
    )
    stress_logs = stress_result.scalars().all()

    doc = SimpleDocTemplate(str(filename), pagesize=letter)
    styles = getSampleStyleSheet()
    story: List = []

    story.append(Paragraph("Weekly Colony Welfare Summary", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Generated: {dt.datetime.utcnow().isoformat()}", styles["Normal"]))
    story.append(Spacer(1, 24))

    story.append(Paragraph("Top 5 Animals At Risk", styles["Heading2"]))
    table_data = [["Animal ID", "Welfare Score", "Cage", "Rank"]]
    for animal in at_risk:
        table_data.append([
            animal.animal_id,
            f"{animal.welfare_score or 0:.1f}",
            animal.cage_id,
            f"{animal.social_rank or 0:.1f}",
        ])
    story.append(Table(table_data))
    story.append(Spacer(1, 24))

    story.append(Paragraph("Recent Stress Indicators", styles["Heading2"]))
    stress_table = [["Animal", "Indicator", "Value", "Timestamp"]]
    for log in stress_logs:
        stress_table.append([
            log.animal_id,
            log.indicator,
            f"{log.value:.1f}",
            log.timestamp.isoformat(),
        ])
    story.append(Table(stress_table))

    doc.build(story)
    return str(filename)
