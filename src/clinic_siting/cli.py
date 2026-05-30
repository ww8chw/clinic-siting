from pathlib import Path
from clinic_siting.scoring.config import load_specialty_config
from clinic_siting.scoring.engine import score_all_specialties

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "specialties.yaml"

# Plan 2 前的範例正規化因子值（0–100，負向因子已 invert）
SAMPLE_FACTORS = {
    "population_density": 75.0,
    "age_gender": 70.0,
    "day_night_gap": 60.0,
    "purchasing_power": 80.0,
    "business_density": 65.0,
    "land_use_mix": 60.0,
    "competition": 55.0,
    "complementary_anchors": 60.0,
    "convenience_density": 85.0,
    "accessibility": 70.0,
    "redevelopment_stage": 90.0,
    "visibility": 50.0,
}


def run_demo():
    config = load_specialty_config(CONFIG_PATH)
    results = score_all_specialties(SAMPLE_FACTORS, config)
    ranking = sorted(
        ((name, s.score) for name, s in results.items()),
        key=lambda x: x[1],
        reverse=True,
    )
    return ranking


def main():
    for name, score in run_demo():
        print(f"{name:20s} {score:5.1f}")


if __name__ == "__main__":
    main()
