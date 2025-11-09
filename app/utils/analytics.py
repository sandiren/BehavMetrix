from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from statistics import mean
from typing import Iterable, Sequence

import networkx as nx

from ..models import Animal, BehaviorLog, EnrichmentLog, StressLog


@dataclass
class EloResult:
    scores: dict[int, float]
    instability_flags: set[int]
    davids_scores: dict[int, float]
    timeline: list[dict[str, object]]


@dataclass
class EnrichmentEngagement:
    rolling_scores: dict[int, list[dict[str, object]]]
    alerts: list[dict[str, object]]


@dataclass
class StressSummary:
    weighted_scores: dict[int, float]
    alerts: list[dict[str, object]]


def compute_elo(
    logs: Iterable[BehaviorLog], base_score: float = 1000.0, k_factor: float = 24.0
) -> EloResult:
    scores: dict[int, float] = defaultdict(lambda: base_score)
    instability_flags: set[int] = set()
    davids_matrix: dict[tuple[int, int], list[int]] = defaultdict(list)
    sorted_logs = sorted(logs, key=lambda log: log.timestamp)
    previous_scores: dict[int, float] = {}
    timeline: list[dict[str, object]] = []

    def resolve_actor(log: BehaviorLog) -> int | None:
        if log.animal_id:
            return int(log.animal_id)
        if hasattr(log, "actor_id") and log.actor_id:
            return int(log.actor_id)
        return None

    def resolve_receiver(log: BehaviorLog) -> int | None:
        if log.receiver_id:
            return int(log.receiver_id)
        if log.interaction_partner_id:
            return int(log.interaction_partner_id)
        return None

    for log in sorted_logs:
        if log.behavior and log.behavior.code not in {"AGG", "DOM", "SUB"}:
            continue
        winner = resolve_actor(log)
        loser = resolve_receiver(log)
        if winner is None or loser is None:
            continue
        winner_score = scores[winner]
        loser_score = scores[loser]
        expected_winner = 1 / (1 + 10 ** ((loser_score - winner_score) / 400))
        expected_loser = 1 - expected_winner
        scores[winner] = winner_score + k_factor * (1 - expected_winner)
        scores[loser] = loser_score + k_factor * (0 - expected_loser)
        davids_matrix[(winner, loser)].append(1)
        davids_matrix[(loser, winner)].append(0)
        if previous_scores.get(winner) and abs(scores[winner] - previous_scores[winner]) > 50:
            instability_flags.add(winner)
        if previous_scores.get(loser) and abs(scores[loser] - previous_scores[loser]) > 50:
            instability_flags.add(loser)
        previous_scores[winner] = scores[winner]
        previous_scores[loser] = scores[loser]
        timeline.append(
            {
                "timestamp": log.timestamp.isoformat(),
                "winner": winner,
                "loser": loser,
                "elo_winner": scores[winner],
                "elo_loser": scores[loser],
            }
        )

    davids_scores = compute_davids_scores(scores, davids_matrix)

    return EloResult(
        scores=dict(scores),
        instability_flags=instability_flags,
        davids_scores=davids_scores,
        timeline=timeline,
    )


def compute_davids_scores(
    elo_scores: dict[int, float],
    davids_matrix: dict[tuple[int, int], list[int]],
) -> dict[int, float]:
    dominance_totals: dict[int, float] = defaultdict(float)
    win_ratios: dict[tuple[int, int], float] = {}

    opponents: set[int] = set()
    for (winner, loser), results in davids_matrix.items():
        opponents.add(winner)
        opponents.add(loser)
        wins = sum(results)
        total = len(results)
        win_ratios[(winner, loser)] = wins / total if total else 0.0

    for i in opponents:
        direct_wins = 0.0
        indirect_wins = 0.0
        direct_losses = 0.0
        indirect_losses = 0.0
        for j in opponents:
            if i == j:
                continue
            p_ij = win_ratios.get((i, j), 0.0)
            p_ji = win_ratios.get((j, i), 0.0)
            direct_wins += p_ij
            direct_losses += p_ji
            for k in opponents:
                if k in {i, j}:
                    continue
                indirect_wins += p_ij * win_ratios.get((j, k), 0.0)
                indirect_losses += p_ji * win_ratios.get((k, j), 0.0)
        dominance_totals[i] = (direct_wins + indirect_wins) - (direct_losses + indirect_losses)

    if not dominance_totals:
        return {}

    min_score = min(dominance_totals.values())
    max_score = max(dominance_totals.values())
    span = max_score - min_score if max_score != min_score else 1
    return {animal_id: round((score - min_score) / span, 3) for animal_id, score in dominance_totals.items()}


def build_rank_graph(animals: list[Animal], scores: dict[int, float]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for animal in animals:
        graph.add_node(animal.id, label=animal.name or animal.persistent_id, elo=scores.get(animal.id, 1000))
    for source in animals:
        for target in animals:
            if source.id == target.id:
                continue
            weight = max(scores.get(source.id, 0) - scores.get(target.id, 0), 0)
            if weight > 0:
                graph.add_edge(source.id, target.id, weight=weight)
    return graph


def colony_behavior_stats(logs: Iterable[BehaviorLog]) -> dict[str, float]:
    counts = defaultdict(int)
    total = 0
    for log in logs:
        total += 1
        if log.behavior:
            counts[log.behavior.code] += 1
    return {
        "% Grooming": round(100 * counts.get("GROOM", 0) / total, 2) if total else 0.0,
        "Aggression Count": counts.get("AGG", 0),
        "Play Count": counts.get("PLAY", 0),
    }


def enrichment_engagement_summary(
    logs: Sequence[EnrichmentLog], window_days: int = 14, alert_threshold: int = 3
) -> EnrichmentEngagement:
    per_animal: dict[int, list[dict[str, object]]] = defaultdict(list)
    alerts: list[dict[str, object]] = []
    sorted_logs = sorted(logs, key=lambda item: item.timestamp)
    for log in sorted_logs:
        if not log.animal_id:
            continue
        per_animal[log.animal_id].append(
            {
                "timestamp": log.timestamp.isoformat(),
                "item": log.item.name if log.item else None,
                "engagement_type": log.engagement_type,
                "duration": log.duration_minutes,
            }
        )

    for animal_id, entries in per_animal.items():
        streak = 0
        last_timestamp: datetime | None = None
        for entry in entries:
            ts = datetime.fromisoformat(entry["timestamp"])
            if last_timestamp and (ts - last_timestamp).days > alert_threshold:
                alerts.append(
                    {
                        "animal_id": animal_id,
                        "message": "Engagement gap detected",
                        "last_seen": last_timestamp.isoformat(),
                    }
                )
            last_timestamp = ts
        if last_timestamp:
            streak = (datetime.utcnow() - last_timestamp).days
            if streak >= alert_threshold:
                alerts.append(
                    {
                        "animal_id": animal_id,
                        "message": "No enrichment interaction in recent days",
                        "gap_days": streak,
                    }
                )

    return EnrichmentEngagement(rolling_scores=dict(per_animal), alerts=alerts)


def stress_summary(logs: Sequence[StressLog], threshold: float = 8.0) -> StressSummary:
    per_animal: dict[int, list[float]] = defaultdict(list)
    alerts: list[dict[str, object]] = []
    for log in logs:
        if not log.animal_id:
            continue
        score = log.weighted_score if log.weighted_score is not None else log.stress_score
        per_animal[log.animal_id].append(score)
    averages = {animal_id: round(mean(scores), 2) for animal_id, scores in per_animal.items() if scores}
    for animal_id, score in averages.items():
        if score >= threshold:
            alerts.append(
                {
                    "animal_id": animal_id,
                    "score": score,
                    "message": "Stress threshold exceeded",
                }
            )
    return StressSummary(weighted_scores=averages, alerts=alerts)
