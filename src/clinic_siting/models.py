from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SpecialtyScore:
    score: float
    factor_contributions: dict[str, float] = field(default_factory=dict)
    specialty: str | None = None
