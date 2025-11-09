from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Sequence

import networkx as nx

from ..models import Animal, BehaviorLog, BehaviorSession, EnrichmentLog, RankScore, StressLog


@dataclass
class EloResult:
    scores: dict[int, float]
    instability_flags: set[int]
    davids_scores: dict[int, float]
    alerts: dict[int, str]


def compute_elo(logs: Iterable[BehaviorLog], base_score: float = 1000.0, k_factor: float = 24.0) -> EloResult:
    scores: dict[int, float] = defaultdict(lambda: base_score)
    instability_flags: set[int] = set()
    davids_scores: dict[int, float] = defaultdict(lambda: 0.0)
    alerts: dict[int, str] = {}
    sorted_logs = sorted(logs, key=lambda log: log.timestamp)
    previous_scores: dict[int, float] = {}
    win_counts: Counter = Counter()
    loss_counts: Counter = Counter()

    for log in sorted_logs:
        if log.behavior and log.behavior.code not in {"AGG", "DOM", "SUB"}:
            continue
        winner = log.animal_id
        loser = log.interaction_partner_id
        if winner is None or loser is None:
            continue
        winner_score = scores[winner]
        loser_score = scores[loser]
        expected_winner = 1 / (1 + 10 ** ((loser_score - winner_score) / 400))
        expected_loser = 1 - expected_winner
        scores[winner] = winner_score + k_factor * (1 - expected_winner)
        scores[loser] = loser_score + k_factor * (0 - expected_loser)
        win_counts[winner] += 1
        loss_counts[loser] += 1
        if previous_scores.get(winner) and abs(scores[winner] - previous_scores[winner]) > 50:
            instability_flags.add(winner)
            alerts[winner] = "Rapid ELO increase"
        if previous_scores.get(loser) and abs(scores[loser] - previous_scores[loser]) > 50:
            instability_flags.add(loser)
            alerts[loser] = "Rapid ELO drop"
        previous_scores[winner] = scores[winner]
        previous_scores[loser] = scores[loser]

    for animal_id in set(list(win_counts) + list(loss_counts)):
        wins = win_counts.get(animal_id, 0)
        losses = loss_counts.get(animal_id, 0)
        total = wins + losses
        davids_scores[animal_id] = (wins - losses) / total if total else 0.0

    return EloResult(scores=dict(scores), instability_flags=instability_flags, davids_scores=dict(davids_scores), alerts=alerts)


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
        "Aggression / Day": counts.get("AGG", 0),
        "Enrichment": counts.get("ENRICH", 0),
        "Play Count": counts.get("PLAY", 0),
    }


def stress_trend(animal: Animal, window_days: int = 14) -> list[dict[str, float]]:
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    trend = (
        StressLog.query.filter(StressLog.animal_id == animal.id, StressLog.date >= cutoff)
        .order_by(StressLog.date.asc())
        .all()
    )
    return [
        {
            "date": log.date.strftime("%Y-%m-%d"),
            "score": log.stress_score,
        }
        for log in trend
    ]


def behavior_heatmap(animal: Animal, behaviors: Sequence[BehaviorLog], window_days: int = 7) -> dict[str, dict[str, int]]:
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    relevant = [log for log in behaviors if log.animal_id == animal.id and log.timestamp >= cutoff and log.behavior]
    heatmap: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for log in relevant:
        day = log.timestamp.strftime("%a")
        category = log.behavior.category.name if log.behavior and log.behavior.category else "Other"
        heatmap[category][day] += 1
    return {category: dict(days) for category, days in heatmap.items()}


def enrichment_summary(animal: Animal, logs: Sequence[EnrichmentLog]) -> dict[str, float]:
    total_sessions = 0
    total_minutes = 0.0
    for log in logs:
        if log.animal_id != animal.id:
            continue
        total_sessions += 1
        if log.duration_minutes:
            total_minutes += log.duration_minutes
    return {
        "sessions": total_sessions,
        "minutes": round(total_minutes, 1),
    }


def progress_tracker(total_animals: int, todays_logs: Sequence[BehaviorLog]) -> dict[str, int]:
    observed_animals = {log.animal_id for log in todays_logs}
    return {
        "observed": len(observed_animals),
        "total": total_animals,
    }


def update_rank_snapshots(elo: EloResult, animals: Sequence[Animal], session: BehaviorSession | None = None) -> list[RankScore]:
    snapshots: list[RankScore] = []
    for animal in animals:
        score = RankScore(
            animal_id=animal.id,
            elo_score=elo.scores.get(animal.id, 1000.0),
            davids_score=elo.davids_scores.get(animal.id),
            instability_flag=animal.id in elo.instability_flags,
            alert_flag=animal.id in elo.alerts,
            source="auto",
            session_id=session.id if session else None,
        )
        snapshots.append(score)
    return snapshots
