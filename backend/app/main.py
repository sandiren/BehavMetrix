from __future__ import annotations

import asyncio
from typing import Dict, List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import alerts_engine, data_import, elo_ranker, ethogram_logger, models, reporting, schemas
from .config import settings
from .database import Base, engine, get_session

app = FastAPI(title="BehavMetrix Welfare Monitor")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/animals", response_model=List[schemas.Animal])
async def list_animals(session: AsyncSession = Depends(get_session)) -> List[schemas.Animal]:
    result = await session.execute(select(models.Animal))
    return list(result.scalars().all())


@app.post("/animals", response_model=schemas.Animal)
async def create_animal(animal: schemas.AnimalCreate, session: AsyncSession = Depends(get_session)):
    db_animal = models.Animal(**animal.dict())
    session.add(db_animal)
    await session.commit()
    await session.refresh(db_animal)
    return db_animal


@app.patch("/animals/{animal_id}", response_model=schemas.Animal)
async def update_animal(animal_id: int, payload: schemas.AnimalUpdate, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(models.Animal).where(models.Animal.id == animal_id))
    db_animal = result.scalar_one_or_none()
    if not db_animal:
        raise HTTPException(status_code=404, detail="Animal not found")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(db_animal, field, value)
    await session.commit()
    await session.refresh(db_animal)
    return db_animal


@app.post("/import")
async def import_animals(source: str, session: AsyncSession = Depends(get_session)):
    await data_import.import_animals_from_file(session, source)
    return {"status": "ok"}


@app.post("/import/sql")
async def import_from_sql(query: str, session: AsyncSession = Depends(get_session)):
    await data_import.import_animals_from_sql(session, query)
    return {"status": "ok"}


@app.post("/behaviors", response_model=schemas.BehaviorLog)
async def log_behavior(payload: schemas.BehaviorLogCreate, session: AsyncSession = Depends(get_session)):
    return await ethogram_logger.log_behavior(session, payload)


@app.post("/behaviors/batch")
async def log_behavior_batch(payload: List[schemas.BehaviorLogCreate], session: AsyncSession = Depends(get_session)):
    logs = await ethogram_logger.batch_log_behaviors(session, payload)
    return {"count": len(logs)}


@app.get("/behaviors/recent", response_model=List[schemas.BehaviorLog])
async def recent_behaviors(session: AsyncSession = Depends(get_session)):
    return await ethogram_logger.get_recent_behavior_logs(session)


@app.post("/elo/recalculate")
async def recalculate_elo(session: AsyncSession = Depends(get_session)):
    scores = await elo_ranker.compute_elo_scores(session)
    return scores


@app.post("/elo/overrides")
async def override_elo(overrides: Dict[int, float], session: AsyncSession = Depends(get_session)):
    await elo_ranker.apply_rank_overrides(session, overrides)
    return {"status": "ok"}


@app.post("/enrichment", response_model=schemas.EnrichmentLog)
async def track_enrichment(payload: schemas.EnrichmentLogCreate, session: AsyncSession = Depends(get_session)):
    log = models.EnrichmentLog(**payload.dict())
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


@app.get("/enrichment", response_model=List[schemas.EnrichmentLog])
async def enrichment_logs(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(models.EnrichmentLog))
    return list(result.scalars().all())


@app.post("/stress", response_model=schemas.StressLog)
async def log_stress(payload: schemas.StressLogCreate, session: AsyncSession = Depends(get_session)):
    log = models.StressLog(**payload.dict())
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


@app.get("/stress", response_model=List[schemas.StressLog])
async def stress_logs(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(models.StressLog))
    return list(result.scalars().all())


@app.get("/alerts/flags")
async def welfare_flags(session: AsyncSession = Depends(get_session)):
    return await alerts_engine.evaluate_animal_flags(session)


@app.get("/alerts/stress")
async def stress_alerts(session: AsyncSession = Depends(get_session)):
    alerts = await alerts_engine.stress_alerts(session)
    return {"alerts": alerts}


@app.get("/exports/animals")
async def export_animals_endpoint(path: str, session: AsyncSession = Depends(get_session)):
    location = await reporting.export_animals(session, path)
    return {"path": location}


@app.get("/exports/behaviors")
async def export_behaviors_endpoint(path: str, session: AsyncSession = Depends(get_session)):
    location = await reporting.export_behavior_logs(session, path)
    return {"path": location}


@app.get("/exports/weekly-pdf")
async def generate_pdf(session: AsyncSession = Depends(get_session)):
    location = await reporting.generate_weekly_pdf(session)
    return {"path": location}


@app.get("/dashboard/summary")
async def dashboard_summary(session: AsyncSession = Depends(get_session)):
    animal_result = await session.execute(select(models.Animal))
    animals = animal_result.scalars().all()

    flags = await alerts_engine.evaluate_animal_flags(session)

    return {
        "animals": [
            {
                "id": animal.id,
                "animalId": animal.animal_id,
                "cageId": animal.cage_id,
                "sex": animal.sex,
                "age": animal.age,
                "weight": animal.weight,
                "welfareScore": animal.welfare_score,
                "socialRank": animal.social_rank,
                "enrichmentStatus": animal.enrichment_status,
                "flag": flags.get(animal.id, "yellow"),
            }
            for animal in animals
        ]
    }
