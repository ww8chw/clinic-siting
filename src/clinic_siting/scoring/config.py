from __future__ import annotations

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


@dataclass
class IndustryProfile:
    id: str
    group: str
    label: str
    competitors: list[dict]      # 每池: {source, pool?, types?, tags?, keywords?, classify?}
    anchors: dict                # {source, types?/tags?}
    weights: dict[str, int]      # factor -> numeric weight


@dataclass
class IndustryConfig:
    factors: list[str]
    negative_factors: list[str]
    industries: dict[str, IndustryProfile]

    def groups(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for iid, p in self.industries.items():
            out.setdefault(p.group, []).append(iid)
        return out


def load_industry_config(path: Path) -> IndustryConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    levels = raw["weight_levels"]
    profiles: dict[str, IndustryProfile] = {}
    for iid, body in raw["industries"].items():
        profiles[iid] = IndustryProfile(
            id=iid,
            group=body["group"],
            label=body["label"],
            competitors=body.get("competitors", []),
            anchors=body.get("anchors", {}),
            weights={f: levels[lv] for f, lv in body["weights"].items()},
        )
    return IndustryConfig(
        factors=raw["factors"],
        negative_factors=raw.get("negative_factors", []),
        industries=profiles,
    )
