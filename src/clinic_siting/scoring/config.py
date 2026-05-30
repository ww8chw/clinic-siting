from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class SpecialtyConfig:
    factors: list[str]
    negative_factors: list[str]
    specialties: dict[str, dict[str, int]]  # specialty -> factor -> numeric weight


def load_specialty_config(path: Path) -> SpecialtyConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    levels = raw["weight_levels"]
    factors = raw["factors"]
    specialties = {
        name: {factor: levels[level] for factor, level in weights.items()}
        for name, weights in raw["specialties"].items()
    }
    return SpecialtyConfig(
        factors=factors,
        negative_factors=raw.get("negative_factors", []),
        specialties=specialties,
    )
