from datetime import date, datetime
from typing import Literal
import re
from pydantic import BaseModel, Field, field_validator, model_validator

TravelMode = Literal["train", "bus", "flight", "any"]

class TravelRequest(BaseModel):
    origin: str = Field(min_length=2, max_length=80)
    destination: str = Field(min_length=2, max_length=80)
    travel_date: date
    budget_inr: int | None = Field(default=None, ge=0, le=10_000_000)
    mode: TravelMode = "any"

    @field_validator("origin", "destination")
    @classmethod
    def normalize_city(cls, value: str) -> str:
        normalized = " ".join(value.strip().split()).title()
        # Station codes in labels such as "Surat (ST)" are identifiers, not words.
        match = re.fullmatch(r"(.+?)\s*\(([A-Za-z0-9]{2,6})\)", normalized)
        if match:
            return f"{match.group(1).strip()} ({match.group(2).upper()})"
        return normalized

    @model_validator(mode="after")
    def different_cities(self):
        if self.origin.casefold() == self.destination.casefold():
            raise ValueError("Origin and destination must be different.")
        return self

class TravelOption(BaseModel):
    provider: str
    mode: Literal["train", "bus", "flight"]
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    price_inr: int | None = Field(default=None, ge=0)
    source: str
    is_demo: bool = False

    @property
    def duration_minutes(self) -> int:
        return max(0, int((self.arrival - self.departure).total_seconds() // 60))
