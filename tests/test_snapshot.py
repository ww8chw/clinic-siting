from clinic_siting.analysis.factors import FactorResult
from clinic_siting.snapshot import (
    append_snapshot,
    load_last_snapshot,
    fill_degraded,
)


def test_append_and_load_roundtrip(tmp_path):
    path = tmp_path / "history.jsonl"
    s1 = {"date": "2026-05-01", "scores": {"family_medicine": 60.0}, "factors": {}}
    s2 = {"date": "2026-06-01", "scores": {"family_medicine": 62.0}, "factors": {}}
    append_snapshot(path, s1)
    append_snapshot(path, s2)
    last = load_last_snapshot(path)
    assert last["date"] == "2026-06-01"
    assert last["scores"]["family_medicine"] == 62.0
    # 兩行
    assert path.read_text(encoding="utf-8").strip().count("\n") == 1


def test_load_last_returns_none_when_no_file(tmp_path):
    assert load_last_snapshot(tmp_path / "nope.jsonl") is None


def test_fill_degraded_uses_last_real_value():
    factors = {
        "competition": FactorResult(50.0, "missing"),
        "purchasing_power": FactorResult(72.0, "real"),
    }
    last = {
        "factors": {
            "competition": {"score": 81.0, "source": "real"},
            "purchasing_power": {"score": 70.0, "source": "real"},
        }
    }
    out = fill_degraded(factors, last)
    # missing 因子沿用上次真值並標 degraded
    assert out["competition"].score == 81.0
    assert out["competition"].source == "degraded"
    # real 因子不動
    assert out["purchasing_power"].score == 72.0
    assert out["purchasing_power"].source == "real"


def test_fill_degraded_keeps_missing_when_no_last():
    factors = {"competition": FactorResult(50.0, "missing")}
    out = fill_degraded(factors, None)
    assert out["competition"].source == "missing"
    assert out["competition"].score == 50.0


def test_fill_degraded_skips_when_last_also_missing():
    factors = {"competition": FactorResult(50.0, "missing")}
    last = {"factors": {"competition": {"score": 50.0, "source": "missing"}}}
    out = fill_degraded(factors, last)
    assert out["competition"].source == "missing"
