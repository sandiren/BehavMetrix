"""Compute Elo-style dominance ranks from aggression/submission logs."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models


@dataclass
class EloConfig:
    k_factor: float = 32.0
    base_score: float = 1000.0


def _expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))


async def compute_elo_scores(session: AsyncSession, config: EloConfig | None = None) -> Dict[int, float]:
    config = config or EloConfig()
    result = await session.execute(
        select(models.BehaviorLog).where(models.BehaviorLog.behavior.in_(["aggression", "submission"]))
    )
    logs = sorted(result.scalars().all(), key=lambda log: log.timestamp)

    scores: Dict[int, float] = defaultdict(lambda: config.base_score)

    for log in logs:
        if not log.actor_id or not log.target_id:
            continue

        attacker = log.actor_id
        recipient = log.target_id

        attacker_score = scores[attacker]
        recipient_score = scores[recipient]

        if log.behavior == "aggression":
            outcome_attacker = 1.0
        else:  # submission -> attacker loses dominance encounter
            outcome_attacker = 0.0

        expected_attacker = _expected_score(attacker_score, recipient_score)
        expected_recipient = 1.0 - expected_attacker

        scores[attacker] = attacker_score + config.k_factor * (outcome_attacker - expected_attacker)
        scores[recipient] = recipient_score + config.k_factor * ((1.0 - outcome_attacker) - expected_recipient)

    # Persist ranks to animals
    for animal_id, score in scores.items():
        await session.execute(
            models.Animal.__table__.update()
            .where(models.Animal.id == animal_id)
            .values(social_rank=score)
        )
    await session.commit()

    return dict(scores)


async def apply_rank_overrides(session: AsyncSession, overrides: Dict[int, float]) -> None:
    for animal_id, value in overrides.items():
        await session.execute(
            models.Animal.__table__.update().where(models.Animal.id == animal_id).values(social_rank=value)
        )
    await session.commit()
