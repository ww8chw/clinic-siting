from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SpecialtyScore:
    score: float
    factor_contributions: dict[str, float] = field(default_factory=dict)
    specialty: str | None = None


@dataclass
class Place:
    name: str
    lat: float
    lon: float
    source: str                      # "google" | "osm"
    types: list[str] = field(default_factory=list)
    rating: float | None = None
    rating_count: int | None = None
    address: str = ""


@dataclass
class TransitStop:
    name: str
    lat: float
    lon: float
    kind: str                        # "bus" | "metro" | "youbike"


@dataclass
class Clinic:
    code: str
    name: str
    kind: str                        # 醫事機構種類，如「西醫診所」
    address: str
    specialties: list[str] = field(default_factory=list)
    lat: float | None = None
    lon: float | None = None
