import datetime as dt
from typing import List, Optional

from pydantic import BaseModel


class AnimalBase(BaseModel):
    animal_id: str
    cage_id: str
    sex: str
    age: float
    weight: float
    welfare_score: Optional[float] = None
    social_rank: Optional[float] = None
    enrichment_status: Optional[str] = None


class AnimalCreate(AnimalBase):
    pass


class AnimalUpdate(BaseModel):
    cage_id: Optional[str]
    sex: Optional[str]
    age: Optional[float]
    weight: Optional[float]
    welfare_score: Optional[float]
    social_rank: Optional[float]
    enrichment_status: Optional[str]


class Animal(AnimalBase):
    id: int

    class Config:
        orm_mode = True


class BehaviorLogBase(BaseModel):
    animal_id: int
    behavior: str
    intensity: int = 1
    reason: Optional[str]
    actor_id: Optional[int]
    target_id: Optional[int]
    timestamp: Optional[dt.datetime]


class BehaviorLogCreate(BehaviorLogBase):
    pass


class BehaviorLog(BehaviorLogBase):
    id: int

    class Config:
        orm_mode = True


class EnrichmentLogBase(BaseModel):
    animal_id: int
    item: str
    category: str
    duration_minutes: Optional[float]
    frequency: Optional[int] = 1
    timestamp: Optional[dt.datetime]


class EnrichmentLogCreate(EnrichmentLogBase):
    pass


class EnrichmentLog(EnrichmentLogBase):
    id: int

    class Config:
        orm_mode = True


class StressLogBase(BaseModel):
    animal_id: int
    indicator: str
    value: float
    timestamp: Optional[dt.datetime]
    notes: Optional[str]


class StressLogCreate(StressLogBase):
    pass


class StressLog(StressLogBase):
    id: int

    class Config:
        orm_mode = True


class WelfareScoreHistory(BaseModel):
    id: int
    animal_id: int
    timestamp: dt.datetime
    score: float

    class Config:
        orm_mode = True
