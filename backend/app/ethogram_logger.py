"""Utilities for capturing structured behavioral observations."""
from __future__ import annotations

import datetime as dt
from typing import Iterable, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from . import models, schemas

ETHOGRAM_BEHAVIORS = {
    "grooming",
    "aggression",
    "self-directed behavior",
    "play",
    "submission",
    "foraging",
    "vocalization",
}


async def log_behavior(
    session: AsyncSession,
    payload: schemas.BehaviorLogCreate,
) -> models.BehaviorLog:
    if payload.behavior not in ETHOGRAM_BEHAVIORS:
        raise ValueError("Unknown behavior: %s" % payload.behavior)

    db_log = models.BehaviorLog(
        animal_id=payload.animal_id,
        behavior=payload.behavior,
        intensity=payload.intensity,
        reason=payload.reason,
        actor_id=payload.actor_id,
        target_id=payload.target_id,
        timestamp=payload.timestamp or dt.datetime.utcnow(),
    )
    session.add(db_log)
    await session.commit()
    await session.refresh(db_log)
    return db_log


async def batch_log_behaviors(
    session: AsyncSession,
    logs: Iterable[schemas.BehaviorLogCreate],
) -> List[models.BehaviorLog]:
    entries: List[models.BehaviorLog] = []
    for payload in logs:
        entries.append(
            models.BehaviorLog(
                animal_id=payload.animal_id,
                behavior=payload.behavior,
                intensity=payload.intensity,
                reason=payload.reason,
                actor_id=payload.actor_id,
                target_id=payload.target_id,
                timestamp=payload.timestamp or dt.datetime.utcnow(),
            )
        )
    session.add_all(entries)
    await session.commit()
    for entry in entries:
        await session.refresh(entry)
    return entries


async def get_recent_behavior_logs(session: AsyncSession, limit: int = 100) -> List[models.BehaviorLog]:
    result = await session.execute(
        select(models.BehaviorLog).order_by(models.BehaviorLog.timestamp.desc()).limit(limit)
    )
    return list(result.scalars().all())
