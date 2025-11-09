from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

import networkx as nx

from ..models import Animal, BehaviorLog


@dataclass
class EloResult:
    scores: dict[int, float]
    instability_flags: set[int]


def compute_elo(logs: Iterable[BehaviorLog], base_score: float = 1000.0, k_factor: float = 24.0) -> EloResult:
    scores: dict[int, float] = defaultdict(lambda: base_score)
    instability_flags: set[int] = set()
    sorted_logs = sorted(logs, key=lambda log: log.timestamp)
    previous_scores: dict[int, float] = {}

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
        if previous_scores.get(winner) and abs(scores[winner] - previous_scores[winner]) > 50:
            instability_flags.add(winner)
        if previous_scores.get(loser) and abs(scores[loser] - previous_scores[loser]) > 50:
            instability_flags.add(loser)
        previous_scores[winner] = scores[winner]
        previous_scores[loser] = scores[loser]

    return EloResult(scores=dict(scores), instability_flags=instability_flags)


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
