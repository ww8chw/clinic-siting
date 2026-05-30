from pathlib import Path
from clinic_siting.scoring.config import load_specialty_config

CONFIG = Path(__file__).resolve().parents[2] / "config" / "specialties.yaml"


def test_loads_all_five_specialties():
    cfg = load_specialty_config(CONFIG)
    assert set(cfg.specialties.keys()) == {
        "family_medicine", "functional_medicine", "weight_loss",
        "psychiatry", "aesthetics",
    }


def test_weights_resolved_to_numbers():
    cfg = load_specialty_config(CONFIG)
    # 醫美的消費力是「最高」= 5
    assert cfg.specialties["aesthetics"]["purchasing_power"] == 5
    # 家醫科的便利超商是「高」= 4
    assert cfg.specialties["family_medicine"]["convenience_density"] == 4


def test_competition_marked_negative():
    cfg = load_specialty_config(CONFIG)
    assert "competition" in cfg.negative_factors


def test_every_specialty_covers_all_factors():
    cfg = load_specialty_config(CONFIG)
    for name, weights in cfg.specialties.items():
        assert set(weights.keys()) == set(cfg.factors), f"{name} 缺因子"
