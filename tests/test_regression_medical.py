from pathlib import Path

from site_siting.scoring.config import load_industry_config, load_specialty_config

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "config" / "specialties.yaml"
NEW = ROOT / "config" / "industries.yaml"

MEDICAL = ["family_medicine", "functional_medicine", "weight_loss",
           "psychiatry", "aesthetics"]


def test_medical_weights_preserved():
    new = load_industry_config(NEW)
    old = load_specialty_config(OLD)
    for name in MEDICAL:
        w_old = dict(old.specialties[name])
        # 舊 aesthetics 的 competition_aesthetic 對映新第二池；此處僅比對非競爭因子權重一致
        for f, v in new.industries[name].weights.items():
            if f == "competition":
                continue
            assert w_old[f] == v, f"{name}.{f} 權重變動"
