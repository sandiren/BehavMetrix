"""Alert evaluation for welfare and stress thresholds."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models


@dataclass
class AlertThresholds:
    welfare_watch: float = 60.0
    welfare_alert: float = 40.0
    stress_alert: float = 70.0


async def evaluate_animal_flags(session: AsyncSession, thresholds: AlertThresholds | None = None) -> Dict[int, str]:
    thresholds = thresholds or AlertThresholds()
    result = await session.execute(select(models.Animal.id, models.Animal.welfare_score))
    flags: Dict[int, str] = {}
    for animal_id, score in result:
        if score is None:
            flags[animal_id] = "yellow"
        elif score < thresholds.welfare_alert:
            flags[animal_id] = "red"
        elif score < thresholds.welfare_watch:
            flags[animal_id] = "yellow"
        else:
            flags[animal_id] = "green"
    return flags


async def stress_alerts(session: AsyncSession, thresholds: AlertThresholds | None = None) -> List[Tuple[int, str]]:
    thresholds = thresholds or AlertThresholds()
    result = await session.execute(
        select(models.StressLog.animal_id, func.avg(models.StressLog.value))
        .group_by(models.StressLog.animal_id)
    )
    alerts: List[Tuple[int, str]] = []
    for animal_id, avg_value in result:
        if avg_value is not None and avg_value >= thresholds.stress_alert:
            alerts.append((animal_id, f"Average stress score {avg_value:.1f} exceeds threshold"))
    return alerts
