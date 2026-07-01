from pathlib import Path
from site_siting.scoring.config import load_industry_config

CONFIG = Path(__file__).resolve().parents[2] / "config" / "industries.yaml"


def test_loads_all_industries():
    cfg = load_industry_config(CONFIG)
    assert set(cfg.industries) >= {
        "family_medicine", "aesthetics", "restaurant", "bubble_tea",
        "cafe", "gym", "cram_school", "hair_beauty",
    }


def test_weights_mapped_to_numbers():
    cfg = load_industry_config(CONFIG)
    fam = cfg.industries["family_medicine"]
    assert fam.weights["accessibility"] == 4   # 高
    assert fam.weights["competition"] == 3      # 中


def test_competitor_pools_parsed():
    cfg = load_industry_config(CONFIG)
    aes = cfg.industries["aesthetics"]
    assert len(aes.competitors) == 2
    assert {p["pool"] for p in aes.competitors} == {"western", "aesthetic"}
    bt = cfg.industries["bubble_tea"].competitors[0]
    assert bt["source"] == "google_places"
    assert "手搖" in bt["keywords"]


def test_group_and_label():
    cfg = load_industry_config(CONFIG)
    assert cfg.industries["restaurant"].group == "food"
    assert cfg.industries["restaurant"].label == "餐飲"


def test_groups_helper():
    cfg = load_industry_config(CONFIG)
    groups = cfg.groups()
    assert "medical" in groups and "food" in groups
    assert "family_medicine" in groups["medical"]
