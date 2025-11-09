from __future__ import annotations

from datetime import datetime, timedelta
import random

from faker import Faker

from . import db
from .models import (
    Animal,
    BehaviorCategory,
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
        "category": "Affiliative",
    },
    {
        "code": "AGG",
        "name": "Aggression",
        "description": "Physical aggression or threat",
        "ontology_reference": "NBO:0000797",
        "category": "Aggressive",
        "is_dyadic": True,
    },
    {
        "code": "PLAY",
        "name": "Play",
        "description": "Social play",
        "ontology_reference": "NBO:0000333",
        "category": "Affiliative",
    },
    {
        "code": "PACE",
        "name": "Pacing",
        "description": "Stereotypic pacing",
        "ontology_reference": "NBO:0000384",
        "category": "Abnormal",
    },
    {
        "code": "SDB",
        "name": "Self-Directed Behavior",
        "description": "Scratching or self-grooming",
        "ontology_reference": "NBO:0000372",
        "category": "Abnormal",
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

    category_palette = {
        "Affiliative": "#198754",
        "Aggressive": "#dc3545",
        "Abnormal": "#6f42c1",
    }
    categories = {name: BehaviorCategory(name=name, color=color) for name, color in category_palette.items()}
    db.session.add_all(categories.values())

    behaviors: list[BehaviorDefinition] = []
    for definition in BEHAVIOR_DEFINITIONS:
        payload = definition.copy()
        category_name = payload.pop("category", None)
        behavior = BehaviorDefinition(**payload)
        if category_name:
            behavior.category = categories[category_name]
        behaviors.append(behavior)
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
                pacing=random.choice([True, False]),
                self_biting=random.choice([True, False]),
                scratching=random.choice([True, False]),
                vocalization=random.choice([True, False]),
            )
            db.session.add(stress)

            start = timestamp + timedelta(minutes=random.randint(1, 120))
            end = start + timedelta(minutes=random.randint(5, 25))
            enrichment_log = EnrichmentLog(
                animal=animal,
                item=random.choice(items),
                start_time=start,
                end_time=end,
                duration_minutes=(end - start).total_seconds() / 60,
                response=random.choice(["engaged", "ignored", "agitated"]),
                outcome=random.choice(["positive", "neutral", "negative"]),
                frequency=random.choice(["once", "daily", "weekly"]),
                tag="mock",
                notes="Auto-generated mock enrichment interaction",
                metadata_json={"source": "mock"},
            )
            db.session.add(enrichment_log)

    db.session.commit()
