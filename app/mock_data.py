from __future__ import annotations

from datetime import datetime, timedelta
import random

from faker import Faker

from . import db
from .models import (
    Animal,
    BehaviorDefinition,
    BehaviorLog,
    EnrichmentItem,
    EnrichmentLog,
    Observer,
    StressLog,
)


fake = Faker()


BEHAVIOR_DEFINITIONS = [
    {
        "code": "GROOM",
        "name": "Grooming",
        "description": "Affiliative grooming per NC3Rs ethogram",
        "ontology_reference": "NBO:0000369",
    },
    {
        "code": "AGG",
        "name": "Aggression",
        "description": "Physical aggression or threat",
        "ontology_reference": "NBO:0000797",
    },
    {
        "code": "PLAY",
        "name": "Play",
        "description": "Social play",
        "ontology_reference": "NBO:0000333",
    },
    {
        "code": "PACE",
        "name": "Pacing",
        "description": "Stereotypic pacing",
        "ontology_reference": "NBO:0000384",
    },
    {
        "code": "SDB",
        "name": "Self-Directed Behavior",
        "description": "Scratching or self-grooming",
        "ontology_reference": "NBO:0000372",
    },
]


ENRICHMENTS = [
    {"name": "Puzzle Feeder", "category": "Foraging", "success_indicator": "All food retrieved"},
    {"name": "Mirror", "category": "Visual", "success_indicator": "Interaction observed"},
    {"name": "Foraging Board", "category": "Foraging", "success_indicator": "Engagement >5 min"},
]


OBSERVER_NAMES = ["Dr. Rivers", "A. Chen", "M. Gupta"]


def create_mock_data(population: int = 20) -> None:
    db.drop_all()
    db.create_all()

    observers = [Observer(name=name, affiliation="BehavLab") for name in OBSERVER_NAMES]
    db.session.add_all(observers)

    behaviors = [BehaviorDefinition(**behavior) for behavior in BEHAVIOR_DEFINITIONS]
    db.session.add_all(behaviors)

    items = [EnrichmentItem(**item) for item in ENRICHMENTS]
    db.session.add_all(items)

    animals: list[Animal] = []
    for idx in range(population):
        animal = Animal(
            persistent_id=f"BM-{idx+1:03d}",
            name=fake.first_name(),
            cage_id=f"C{random.randint(1, 5)}",
            sex=random.choice(["M", "F"]),
            age=random.randint(2, 18),
            weight_kg=round(random.uniform(4.0, 12.0), 1),
            matriline=random.choice(["Alpha", "Beta", "Gamma"]),
            photo_url="https://placehold.co/200x200",
        )
        animals.append(animal)
    db.session.add_all(animals)
    db.session.commit()

    start_time = datetime.utcnow() - timedelta(days=30)
    for day in range(30):
        for animal in animals:
            timestamp = start_time + timedelta(days=day, minutes=random.randint(0, 600))
            behavior = random.choice(behaviors)
            log = BehaviorLog(
                animal=animal,
                behavior=behavior,
                observer=random.choice(observers),
                timestamp=timestamp,
                sample_type=random.choice(["focal", "scan"]),
                context=random.choice(["colony", "feeding", "rest"]),
            )
            if behavior.code == "AGG":
                partner = random.choice([a for a in animals if a.id != animal.id])
                log.interaction_partner = partner
            db.session.add(log)

            stress = StressLog(
                animal=animal,
                date=timestamp,
                stress_score=random.randint(1, 5),
                withdrawal=random.choice([True, False]),
                fear_grimace=random.choice([True, False]),
                self_biting=random.choice([True, False]),
            )
            db.session.add(stress)

            enrichment_log = EnrichmentLog(
                animal=animal,
                item=random.choice(items),
                duration_minutes=random.uniform(5, 30),
                response=random.choice(["engaged", "ignored", "agitated"]),
                tag="mock",
                notes="Auto-generated mock enrichment interaction",
            )
            db.session.add(enrichment_log)

    db.session.commit()
