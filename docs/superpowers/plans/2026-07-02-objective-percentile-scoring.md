# 客觀化計分：統計型 5 因子改百分位 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 5 個「統計型」因子（消費力、人口、屋齡、年齡性別、晝夜落差）的計分，從人工拍板的 `minmax_score(lo, hi)` 絕對門檻，改為「該值在全桃園分布中的百分位」，讓分數客觀、可稽核。

**Architecture:** 新增 `percentile` 核心（Distribution 資料類 + `percentile_score`）與 `distribution_builder`（從既有政府資料建分布檔）。分布檔存 `data/reference/distributions/*.json`，帶 `source/unit/n/generated` metadata。`build_factors(raw, dist=None)` 與 `factor_explanation(name, raw, dist=None)` 新增選用參數：有分布檔就走百分位、否則沿用現行 minmax（向後相容，既有測試全綠）。`run_pipeline` 與 `site_export.build_site` 載入分布並下傳，快照 schema 不變（仍為 `{score, source}`），只是分數與說明文字變客觀。

**Tech Stack:** Python 3.9.6（`python3`；需 `from __future__ import annotations`）、pytest（`python3 -m pytest`，pytest.ini 已設 `pythonpath=src`）、既有 dataclass/JSON 慣例。

**母體範圍：** 全桃園。里級因子（消費力 N=544、年齡性別 N=544）N 大；區級因子（人口/屋齡/晝夜 N=13）較粗，說明文字如實標註 N。

**百分位語意：**
- 單調正向（消費力、人口）：值越大 → 百分位越高 → 分數越高。
- 反向（屋齡）：`invert=True`，屋齡越新 → 分數越高。
- 非單調（晝夜）：先取 `|ln(比值)|` 偏離量，對「全桃園各區偏離量」取百分位再 `invert`，保留「比值≈1 最佳」語意。
- 複合（年齡性別）：壯年占比、女性占比各自對母體取百分位，再 `0.7:0.3` 加權。

---

## Task 1: 百分位核心 percentile.py

**Files:**
- Create: `src/site_siting/analysis/percentile.py`
- Test: `tests/analysis/test_percentile.py`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/analysis/test_percentile.py
import json
from site_siting.analysis.percentile import (
    Distribution, percentile_score, load_distribution, load_distributions)


def _dist(values):
    return Distribution(factor="x", unit="里", source="測試",
                        generated="2026-07-02", values=sorted(values))


def test_percentile_below_min_near_zero():
    d = _dist([10, 20, 30, 40, 50])
    assert percentile_score(5, d) == 0.0


def test_percentile_above_max_is_hundred():
    d = _dist([10, 20, 30, 40, 50])
    assert percentile_score(99, d) == 100.0


def test_percentile_midrank_of_median():
    # 5 值，query=30 在第 3 位：midrank=(2+3)/2=2.5 → 50
    d = _dist([10, 20, 30, 40, 50])
    assert percentile_score(30, d) == 50.0


def test_percentile_invert_flips():
    d = _dist([10, 20, 30, 40, 50])
    assert percentile_score(10, d, invert=True) == 90.0


def test_percentile_empty_distribution_is_neutral():
    d = _dist([])
    assert percentile_score(42, d) == 50.0


def test_distribution_n_property():
    assert _dist([1, 2, 3]).n == 3


def test_load_roundtrip(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({
        "factor": "purchasing_power", "unit": "里", "source": "財政部",
        "generated": "2026-07-02", "values": [40, 10, 30]}), encoding="utf-8")
    d = load_distribution(p)
    assert d.factor == "purchasing_power"
    assert d.values == [10.0, 30.0, 40.0]   # 載入即排序


def test_load_distributions_keys_by_factor(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({
        "factor": "population_density", "unit": "區", "source": "s",
        "generated": "2026-07-02", "values": [1, 2]}), encoding="utf-8")
    got = load_distributions(tmp_path)
    assert set(got.keys()) == {"population_density"}


def test_load_distributions_missing_dir_returns_empty(tmp_path):
    assert load_distributions(tmp_path / "nope") == {}
```

- [ ] **Step 2: 執行確認失敗**

Run: `python3 -m pytest tests/analysis/test_percentile.py -q`
Expected: FAIL（`ModuleNotFoundError: site_siting.analysis.percentile`）

- [ ] **Step 3: 實作**

```python
# src/site_siting/analysis/percentile.py
from __future__ import annotations

import json
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from pathlib import Path

# 分布檔預設目錄（專案根 /data/reference/distributions）
DISTRIBUTIONS_DIR = (Path(__file__).resolve().parents[2]
                     / "data" / "reference" / "distributions")


@dataclass
class Distribution:
    factor: str        # 對映因子鍵（如 purchasing_power / age_prime）
    unit: str          # 母體單位："里" / "區"
    source: str        # 資料出處（稽核用）
    generated: str     # 產生日期 ISO
    values: list[float]  # 排序後的母體值

    @property
    def n(self) -> int:
        return len(self.values)


def percentile_score(value: float, dist: Distribution,
                     invert: bool = False) -> float:
    """value 在 dist.values 中的百分位（midrank，0–100）。
    空母體回中性 50。invert=True 用於反向因子（值越大分越低）。"""
    v = dist.values
    n = len(v)
    if n == 0:
        return 50.0
    lo = bisect_left(v, value)
    hi = bisect_right(v, value)
    rank = (lo + hi) / 2.0
    pct = max(0.0, min(100.0, rank / n * 100.0))
    return 100.0 - pct if invert else pct


def load_distribution(path) -> Distribution:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return Distribution(
        factor=d["factor"], unit=d["unit"], source=d["source"],
        generated=d["generated"],
        values=sorted(float(x) for x in d["values"]),
    )


def load_distributions(directory=DISTRIBUTIONS_DIR) -> dict[str, Distribution]:
    """讀目錄下所有 *.json → {factor: Distribution}。目錄不存在回 {}。"""
    directory = Path(directory)
    out: dict[str, Distribution] = {}
    if not directory.exists():
        return out
    for p in sorted(directory.glob("*.json")):
        dist = load_distribution(p)
        out[dist.factor] = dist
    return out
```

- [ ] **Step 4: 執行確認通過**

Run: `python3 -m pytest tests/analysis/test_percentile.py -q`
Expected: PASS（9 passed）

- [ ] **Step 5: Commit**

```bash
git add src/site_siting/analysis/percentile.py tests/analysis/test_percentile.py
git commit -m "feat: 百分位核心 Distribution + percentile_score（midrank）"
```

---

## Task 2: 分布建構器 + 消費力/人口真實分布檔

**Files:**
- Create: `src/site_siting/data_sources/distribution_builder.py`
- Test: `tests/data_sources/test_distribution_builder.py`
- Generate: `data/reference/distributions/purchasing_power.json`, `data/reference/distributions/population_density.json`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/data_sources/test_distribution_builder.py
import json
from site_siting.data_sources.distribution_builder import (
    make_distribution, income_median_values, population_values,
    write_distribution)


def test_income_median_values_extracts_medians():
    income = {
        "甲里": {"district": "桃園市A區", "households": 100, "mean": 700, "median": 480},
        "乙里": {"district": "桃園市A區", "households": 200, "mean": 900, "median": 696},
        "丙里": {"district": "桃園市B區", "households": 50, "mean": 600, "median": 0},
    }
    vals = income_median_values(income)
    assert sorted(vals) == [480.0, 696.0]   # median==0 視為無資料略過


def test_population_values_extracts_population():
    pop = {
        "龜山區": {"population": 189052, "households": 87815},
        "桃園區": {"population": 478664, "households": 210351},
        "空區": {"population": 0, "households": 0},
    }
    assert sorted(population_values(pop)) == [189052.0, 478664.0]


def test_make_distribution_sorts_and_counts():
    d = make_distribution("purchasing_power", "里", "財政部",
                          [40, 10, 30], generated="2026-07-02")
    assert d.values == [10.0, 30.0, 40.0]
    assert d.n == 3
    assert d.unit == "里"


def test_write_distribution_roundtrip(tmp_path):
    d = make_distribution("population_density", "區", "內政部",
                          [3, 1, 2], generated="2026-07-02")
    p = tmp_path / "population_density.json"
    write_distribution(d, p)
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert loaded["factor"] == "population_density"
    assert loaded["source"] == "內政部"
    assert loaded["values"] == [1.0, 2.0, 3.0]
    assert loaded["generated"] == "2026-07-02"
```

- [ ] **Step 2: 執行確認失敗**

Run: `python3 -m pytest tests/data_sources/test_distribution_builder.py -q`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 實作**

```python
# src/site_siting/data_sources/distribution_builder.py
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from site_siting.analysis.percentile import Distribution


def make_distribution(factor: str, unit: str, source: str,
                      values, generated: str | None = None) -> Distribution:
    vals = sorted(float(v) for v in values)
    return Distribution(factor=factor, unit=unit, source=source,
                        generated=generated or date.today().isoformat(),
                        values=vals)


def income_median_values(income: dict[str, dict]) -> list[float]:
    """parse_income_csv 產出 → 各里中位所得（median>0 者）。"""
    return [float(r["median"]) for r in income.values() if r.get("median")]


def population_values(population: dict[str, dict]) -> list[float]:
    """parse_population_csv 產出 → 各區人口（>0 者）。"""
    return [float(r["population"]) for r in population.values()
            if r.get("population")]


def write_distribution(dist: Distribution, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "factor": dist.factor, "unit": dist.unit, "source": dist.source,
        "generated": dist.generated, "values": dist.values,
    }, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 4: 執行確認通過**

Run: `python3 -m pytest tests/data_sources/test_distribution_builder.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 產生消費力與人口真實分布檔（離線、用已提交 CSV）**

Run:
```bash
python3 - <<'PY'
from pathlib import Path
from site_siting.data_sources.reference import parse_income_csv, parse_population_csv
from site_siting.data_sources.distribution_builder import (
    make_distribution, income_median_values, population_values, write_distribution)

ref = Path("data/reference")
out = Path("data/reference/distributions")

income = parse_income_csv((ref / "income_taoyuan_111.csv").read_text(encoding="utf-8-sig"))
inc_vals = income_median_values(income)
write_distribution(make_distribution(
    "purchasing_power", "里", "財政部111年綜合所得稅各村里統計（桃園市）", inc_vals),
    out / "purchasing_power.json")
print("purchasing_power N =", len(inc_vals))

pop = parse_population_csv((ref / "population_taoyuan_latest.csv").read_text(encoding="utf-8-sig"))
pop_vals = population_values(pop)
write_distribution(make_distribution(
    "population_density", "區", "內政部戶政司桃園市各區現住人口", pop_vals),
    out / "population_density.json")
print("population_density N =", len(pop_vals))
PY
```
Expected 輸出含：`purchasing_power N = 544`（±，視 CSV 實際里數）與 `population_density N = 13`。
確認檔案存在：`ls data/reference/distributions/`（應有兩檔）。

- [ ] **Step 6: Commit**

```bash
git add src/site_siting/data_sources/distribution_builder.py tests/data_sources/test_distribution_builder.py data/reference/distributions/purchasing_power.json data/reference/distributions/population_density.json
git commit -m "feat: 分布建構器 + 消費力/人口全桃園分布檔"
```

---

## Task 3: build_factors 接百分位（消費力 + 人口）與說明文字

**Files:**
- Modify: `src/site_siting/analysis/factors.py`
- Test: `tests/analysis/test_factors_percentile.py`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/analysis/test_factors_percentile.py
from site_siting.analysis.percentile import Distribution
from site_siting.analysis.factors import build_factors, factor_explanation


def _dist(factor, unit, values):
    return Distribution(factor=factor, unit=unit, source="測試",
                        generated="2026-07-02", values=sorted(values))


DIST = {
    "purchasing_power": _dist("purchasing_power", "里", [400, 500, 600, 700, 800]),
    "population_density": _dist("population_density", "區", [50000, 100000, 200000, 300000]),
}
RAW = {"weighted_median_income": 700.0, "population": 200000}


def test_percentile_used_when_distribution_present():
    # 700 在 [400..800] 第 4 位 midrank=(3+4)/2=3.5 → 70
    f = build_factors(RAW, dist=DIST)
    assert f["purchasing_power"].score == 70.0
    assert f["purchasing_power"].source == "real"


def test_minmax_fallback_without_distribution():
    # 無 dist → 沿用舊 minmax（700 對 350–800 → (700-350)/450*100 ≈ 77.8）
    f = build_factors(RAW)
    assert abs(f["purchasing_power"].score - 77.78) < 0.1


def test_population_percentile():
    # 200000 在 [50k,100k,200k,300k] midrank=(2+3)/2=2.5 → 62.5
    f = build_factors(RAW, dist=DIST)
    assert f["population_density"].score == 62.5


def test_explanation_shows_percentile_and_n():
    exp = factor_explanation("purchasing_power", RAW, dist=DIST)
    assert "百分位" in exp["basis"]
    assert "5" in exp["basis"]   # N=5


def test_explanation_falls_back_without_dist():
    exp = factor_explanation("purchasing_power", RAW)
    assert "線性映射" in exp["basis"]
```

- [ ] **Step 2: 執行確認失敗**

Run: `python3 -m pytest tests/analysis/test_factors_percentile.py -q`
Expected: FAIL（`build_factors() got an unexpected keyword argument 'dist'`）

- [ ] **Step 3: 實作 — 改 factors.py**

在 `factors.py` 頂部 import 區加入：

```python
from site_siting.analysis.percentile import percentile_score
```

把 `build_factors` 的簽名改為 `def build_factors(raw: dict, dist: dict | None = None) -> dict[str, FactorResult]:`，並在函式開頭定義小工具：

```python
    dist = dist or {}

    def _pctl_or_minmax(factor, value, lo, hi, invert=False):
        d = dist.get(factor)
        if d is not None:
            return percentile_score(value, d, invert=invert)
        return minmax_score(value, lo, hi, invert=invert)
```

把現有 `purchasing_power` 區塊改為：

```python
    inc = raw.get("weighted_median_income")
    if inc is not None:
        out["purchasing_power"] = FactorResult(
            _pctl_or_minmax("purchasing_power", inc, INCOME_LO, INCOME_HI), "real")
    else:
        out["purchasing_power"] = FactorResult(NEUTRAL, "missing")
```

把現有 `population_density` 區塊改為：

```python
    pop_v = raw.get("population")
    if pop_v is not None:
        out["population_density"] = FactorResult(
            _pctl_or_minmax("population_density", pop_v, POP_LO, POP_HI), "real")
    else:
        out["population_density"] = FactorResult(NEUTRAL, "missing")
```

- [ ] **Step 4: 實作 — factor_explanation 加 dist 說明**

把 `factor_explanation` 簽名改為 `def factor_explanation(name: str, raw: dict, dist: dict | None = None) -> dict:`，在函式開頭加：

```python
    dist = dist or {}

    def _pctl_basis(factor, value, invert=False):
        d = dist.get(factor)
        if d is None or value is None:
            return None
        p = percentile_score(value, d, invert=invert)
        return f"全桃園 {d.n} 個{d.unit}中第 {p:.0f} 百分位（{d.source}）"
```

在 `purchasing_power` 分支的 return 前，改成優先用百分位說明：

```python
    if name == "purchasing_power":
        v = g("weighted_median_income")
        pb = _pctl_basis("purchasing_power", v)
        return {
            "raw": f"戶中位所得 {v:,.0f} 千元" if v is not None else "無資料",
            "basis": pb or f"線性映射 {INCOME_LO:.0f}–{INCOME_HI:.0f} 千元 → 0–100",
        }
```

在 `population_density` 分支，把 `basis` 改為 `_pctl_basis("population_density", v) or （原本的線性映射字串）`：

```python
    if name == "population_density":
        v = g("population")
        vh = g("village_households")
        vp = g("village_population_est")
        village_txt = ""
        if vh is not None:
            village_txt = f"｜所在里 {vh:,.0f} 戶"
            if vp is not None:
                village_txt += f"、約 {vp:,.0f} 人（估）"
        pb = _pctl_basis("population_density", v)
        return {
            "raw": (f"區人口 {v:,.0f} 人{village_txt}" if v is not None else "無資料"),
            "basis": pb or (f"線性映射 {POP_LO:,.0f}–{POP_HI:,.0f} 人 → 0–100"
                            f"（里級戶數為財政部實數、人口按戶數比例估算）"),
        }
```

- [ ] **Step 5: 執行確認通過（含既有測試不回歸）**

Run: `python3 -m pytest tests/analysis/test_factors_percentile.py tests/analysis/test_factors.py -q`
Expected: PASS（新 5 + 既有全綠；既有測試未傳 dist，走 minmax 不變）

- [ ] **Step 6: Commit**

```bash
git add src/site_siting/analysis/factors.py tests/analysis/test_factors_percentile.py
git commit -m "feat: 消費力/人口改百分位計分，說明標註 N 與出處"
```

---

## Task 4: 屋齡分布 + redevelopment_stage 反向百分位

**Files:**
- Modify: `src/site_siting/data_sources/distribution_builder.py`
- Modify: `src/site_siting/analysis/factors.py`
- Test: `tests/data_sources/test_distribution_builder.py`（追加）、`tests/analysis/test_factors_percentile.py`（追加）
- Generate（選用，需網路）: `data/reference/distributions/redevelopment_stage.json`

- [ ] **Step 1: 寫失敗測試（builder）**

在 `tests/data_sources/test_distribution_builder.py` 追加：

```python
from site_siting.data_sources.distribution_builder import building_age_values


def test_building_age_values_per_district_median():
    records = [
        {"district": "龜山區", "completion_date": "0900101"},  # 屋齡舊
        {"district": "龜山區", "completion_date": "1100101"},
        {"district": "桃園區", "completion_date": "1120101"},  # 屋齡新
        {"district": "無日期區", "completion_date": ""},        # 略過
    ]
    vals = building_age_values(records, as_of_year=2026,
                               districts=["龜山區", "桃園區", "無日期區"])
    # 龜山區 median(屋齡[26,15])=20.5、桃園區=3；無日期區無值不計
    assert sorted(vals) == [3.0, 20.5]
```

- [ ] **Step 2: 執行確認失敗**

Run: `python3 -m pytest tests/data_sources/test_distribution_builder.py::test_building_age_values_per_district_median -q`
Expected: FAIL（`ImportError: cannot import name 'building_age_values'`）

- [ ] **Step 3: 實作 builder**

在 `distribution_builder.py` 加入（沿用 realprice 的解析函式）：

```python
from site_siting.data_sources.realprice import district_median_building_age


def building_age_values(records, as_of_year: int, districts) -> list[float]:
    """各行政區成交屋齡中位 → list（有值者）。"""
    out = []
    for d in districts:
        age = district_median_building_age(records, d, as_of_year)
        if age is not None:
            out.append(float(age))
    return out
```

- [ ] **Step 4: 執行確認通過（builder）**

Run: `python3 -m pytest tests/data_sources/test_distribution_builder.py -q`
Expected: PASS

- [ ] **Step 5: 寫失敗測試（factors 反向百分位）**

在 `tests/analysis/test_factors_percentile.py` 追加：

```python
def test_building_age_percentile_inverts():
    d = _dist("redevelopment_stage", "區", [5, 10, 20, 30, 40])
    raw = {"building_age_median": 10.0}
    f = build_factors(raw, dist={"redevelopment_stage": d})
    # 10 在第2位 midrank=(1+2)/2=1.5 → pctl 30 → invert 70
    assert f["redevelopment_stage"].score == 70.0
    assert f["redevelopment_stage"].source == "degraded"
```

- [ ] **Step 6: 執行確認失敗**

Run: `python3 -m pytest tests/analysis/test_factors_percentile.py::test_building_age_percentile_inverts -q`
Expected: FAIL（分數仍為舊 minmax 值）

- [ ] **Step 7: 實作 factors — 改 redevelopment_stage 區塊**

把現有 `redevelopment_stage` 建構區塊改為：

```python
    if raw.get("building_age_median") is not None:
        score = _pctl_or_minmax("redevelopment_stage", raw["building_age_median"],
                                REDEV_AGE_LO, REDEV_AGE_HI, invert=True)
        out["redevelopment_stage"] = FactorResult(score, "degraded")
    else:
        out["redevelopment_stage"] = FactorResult(NEUTRAL, "manual")
```

在 `factor_explanation` 的 `redevelopment_stage` 分支，把 `basis` 改為百分位優先：

```python
    if name == "redevelopment_stage":
        v = g("building_age_median")
        if v is None:
            return {"raw": "待人工填入", "basis": "中性 50（手動因子，未來由介面覆寫）"}
        pb = _pctl_basis("redevelopment_stage", v, invert=True)
        return {
            "raw": f"區內成交屋齡中位 {v:.0f} 年",
            "basis": pb or (f"實價登錄屋齡映射 {REDEV_AGE_LO:.0f}–{REDEV_AGE_HI:.0f} 年"
                            f"（反向，越新越高）；區級代理標 degraded"),
        }
```

- [ ] **Step 8: 執行確認通過（含既有不回歸）**

Run: `python3 -m pytest tests/analysis/ -q`
Expected: PASS（既有 test_factors.py 的 `test_redevelopment_from_building_age` 未傳 dist、仍走 minmax，通過）

- [ ] **Step 9: 產生屋齡分布檔（選用，需網路；無網路可略過，計分自動回退 minmax）**

Run:
```bash
python3 - <<'PY'
from datetime import date
from pathlib import Path
from site_siting.data_sources import realprice
from site_siting.data_sources.distribution_builder import (
    make_distribution, building_age_values, write_distribution)

DISTRICTS = ["桃園區","中壢區","大溪區","楊梅區","蘆竹區","大園區","龜山區",
             "八德區","龍潭區","平鎮區","新屋區","觀音區","復興區"]
today = date.today()
recs = None
for season in realprice.recent_seasons(today.year, today.month, n=4):
    try:
        recs = realprice.parse_lvr_main_csv(realprice.fetch_lvr_main_csv(season))
        if recs:
            break
    except Exception:
        continue
if recs:
    vals = building_age_values(recs, today.year, DISTRICTS)
    write_distribution(make_distribution(
        "redevelopment_stage", "區", "內政部實價登錄桃園市各區成交屋齡中位", vals),
        Path("data/reference/distributions/redevelopment_stage.json"))
    print("redevelopment_stage N =", len(vals))
else:
    print("實價登錄下載失敗，略過（計分回退 minmax）")
PY
```
Expected: 印出 `redevelopment_stage N = 13`（或下載失敗訊息）。若成功則 `git add data/reference/distributions/redevelopment_stage.json`。

- [ ] **Step 10: Commit**

```bash
git add src/site_siting/data_sources/distribution_builder.py src/site_siting/analysis/factors.py tests/data_sources/test_distribution_builder.py tests/analysis/test_factors_percentile.py
# 若 Step 9 成功：git add data/reference/distributions/redevelopment_stage.json
git commit -m "feat: 屋齡改反向百分位（越新越高），全桃園各區母體"
```

---

## Task 5: 年齡性別分布（壯年/女性雙母體）+ 複合百分位

**Files:**
- Modify: `src/site_siting/data_sources/distribution_builder.py`
- Modify: `src/site_siting/analysis/factors.py`
- Test: `tests/data_sources/test_distribution_builder.py`（追加）、`tests/analysis/test_factors_percentile.py`（追加）
- Generate（選用，需網路）: `data/reference/distributions/age_prime.json`, `age_female.json`

- [ ] **Step 1: 寫失敗測試（builder）**

在 `tests/data_sources/test_distribution_builder.py` 追加：

```python
from site_siting.data_sources.distribution_builder import age_share_values


def test_age_share_values_prime_and_female_per_village():
    # ODRP052 列：{site_id, village, sex, age, population}
    rows = [
        {"site_id": "A", "village": "甲", "sex": "男", "age": "30~34歲", "population": "40"},
        {"site_id": "A", "village": "甲", "sex": "女", "age": "30~34歲", "population": "60"},
        {"site_id": "A", "village": "乙", "sex": "女", "age": "10~14歲", "population": "50"},
        {"site_id": "A", "village": "乙", "sex": "男", "age": "10~14歲", "population": "50"},
    ]
    prime, female = age_share_values(rows)
    # 甲里：壯年100/100=1.0、女60/100=0.6；乙里：壯年0/100=0、女50/100=0.5
    assert sorted(prime) == [0.0, 1.0]
    assert sorted(female) == [0.5, 0.6]
```

- [ ] **Step 2: 執行確認失敗**

Run: `python3 -m pytest tests/data_sources/test_distribution_builder.py::test_age_share_values_prime_and_female_per_village -q`
Expected: FAIL（`ImportError: age_share_values`）

- [ ] **Step 3: 實作 builder**

在 `distribution_builder.py` 加入（沿用 moi_agegender 的壯年定義）：

```python
from site_siting.data_sources.moi_agegender import PRIME_AGES


def age_share_values(rows) -> tuple[list[float], list[float]]:
    """ODRP052 列 → 各里(壯年占比, 女性占比) 兩條母體。
    以 (site_id, village) 分組跨婚姻狀況/年齡加總。"""
    agg: dict[tuple, dict] = {}
    for x in rows:
        key = (x.get("site_id"), x.get("village"))
        pop = int(x.get("population") or 0)
        a = agg.setdefault(key, {"total": 0, "female": 0, "prime": 0})
        a["total"] += pop
        if x.get("sex") == "女":
            a["female"] += pop
        if x.get("age") in PRIME_AGES:
            a["prime"] += pop
    prime, female = [], []
    for a in agg.values():
        if a["total"] > 0:
            prime.append(a["prime"] / a["total"])
            female.append(a["female"] / a["total"])
    return prime, female
```

- [ ] **Step 4: 執行確認通過（builder）**

Run: `python3 -m pytest tests/data_sources/test_distribution_builder.py -q`
Expected: PASS

- [ ] **Step 5: 寫失敗測試（factors 複合百分位）**

在 `tests/analysis/test_factors_percentile.py` 追加：

```python
def test_age_gender_composite_percentile():
    dp = _dist("age_prime", "里", [0.30, 0.35, 0.40, 0.45, 0.50])
    df = _dist("age_female", "里", [0.46, 0.48, 0.50, 0.52, 0.54])
    raw = {"age_prime_share": 0.45, "female_share": 0.52}
    f = build_factors(raw, dist={"age_prime": dp, "age_female": df})
    # 壯年 0.45 midrank=(3+4)/2=3.5→70；女 0.52 →70；0.7*70+0.3*70=70
    assert f["age_gender"].score == 70.0
    assert f["age_gender"].source == "real"
```

- [ ] **Step 6: 執行確認失敗**

Run: `python3 -m pytest tests/analysis/test_factors_percentile.py::test_age_gender_composite_percentile -q`
Expected: FAIL（走舊 age_gender_score，分數不等 70）

- [ ] **Step 7: 實作 factors — 改 age_gender 區塊**

把現有 `age_gender` 建構區塊改為：

```python
    prime = raw.get("age_prime_share")
    female = raw.get("female_share")
    if prime is not None and female is not None:
        dp = dist.get("age_prime")
        df = dist.get("age_female")
        if dp is not None and df is not None:
            pc = percentile_score(prime, dp)
            fc = percentile_score(female, df)
            score = AGE_PRIME_WEIGHT * pc + (1.0 - AGE_PRIME_WEIGHT) * fc
        else:
            score = age_gender_score(prime, female)
        out["age_gender"] = FactorResult(score, "real")
    else:
        out["age_gender"] = FactorResult(NEUTRAL, "missing")
```

在 `factor_explanation` 的 `age_gender` 分支，`basis` 改為百分位優先：

```python
    if name == "age_gender":
        prime = g("age_prime_share")
        if prime is None:
            return {"raw": "無資料", "basis": "沿用上次快照值或中性 50"}
        fem = g("female_share")
        tot = g("age_pop_total")
        tot_txt = f"（村里 {tot:,} 人）" if tot else ""
        dp = dist.get("age_prime")
        df = dist.get("age_female")
        if dp is not None and df is not None and fem is not None:
            pp = percentile_score(prime, dp)
            pf = percentile_score(fem, df)
            basis = (f"壯年占比全桃園 {dp.n} 里第 {pp:.0f} 百分位、女性第 {pf:.0f} 百分位，"
                     f"加權 {AGE_PRIME_WEIGHT:.0%}:{1 - AGE_PRIME_WEIGHT:.0%}（{dp.source}）")
        else:
            basis = (f"自費客群代理：壯年占比映射 {AGE_PRIME_LO:.0%}–{AGE_PRIME_HI:.0%}、"
                     f"女性占比映射 {FEMALE_LO:.0%}–{FEMALE_HI:.0%}，"
                     f"加權 {AGE_PRIME_WEIGHT:.0%}:{1 - AGE_PRIME_WEIGHT:.0%} → 0–100")
        return {
            "raw": (f"壯年 25–49 占 {prime * 100:.1f}%、女性占 "
                    f"{(fem or 0) * 100:.1f}%{tot_txt}"),
            "basis": basis,
        }
```

- [ ] **Step 8: 執行確認通過（含既有不回歸）**

Run: `python3 -m pytest tests/analysis/ -q`
Expected: PASS（既有 `test_age_gender_*` 未傳 dist、走舊公式，通過）

- [ ] **Step 9: 產生年齡分布檔（選用，需網路；掃全桃園各里 ODRP052）**

Run:
```bash
python3 - <<'PY'
from pathlib import Path
from site_siting.data_sources import moi_agegender
from site_siting.data_sources.distribution_builder import (
    make_distribution, age_share_values, write_distribution)

# 掃全檔（totalPage），收桃園市所有里；量大，可能數分鐘
meta = moi_agegender.fetch_page(moi_agegender.DEFAULT_YEAR, 1)
total = int(meta.get("totalPage") or 1)
rows = []
for p in range(1, total + 1):
    try:
        rows.extend(moi_agegender.fetch_page(moi_agegender.DEFAULT_YEAR, p).get("responseData") or [])
    except Exception:
        continue
# 僅保留桃園市（site_id 以「桃園市」開頭）
rows = [r for r in rows if str(r.get("site_id", "")).startswith("桃園市")]
prime, female = age_share_values(rows)
out = Path("data/reference/distributions")
write_distribution(make_distribution(
    "age_prime", "里", "內政部ODRP052桃園市各里壯年(25–49)占比", prime), out / "age_prime.json")
write_distribution(make_distribution(
    "age_female", "里", "內政部ODRP052桃園市各里女性占比", female), out / "age_female.json")
print("age_prime N =", len(prime), " age_female N =", len(female))
PY
```
Expected: 印出兩條 N（數百）。成功則 `git add data/reference/distributions/age_prime.json data/reference/distributions/age_female.json`。

- [ ] **Step 10: Commit**

```bash
git add src/site_siting/data_sources/distribution_builder.py src/site_siting/analysis/factors.py tests/data_sources/test_distribution_builder.py tests/analysis/test_factors_percentile.py
# 若 Step 9 成功一併 add 兩個分布檔
git commit -m "feat: 年齡性別改雙母體複合百分位（壯年/女性各自對全桃園里）"
```

---

## Task 6: 晝夜落差分布（偏離量母體）+ 反向百分位

**Files:**
- Modify: `src/site_siting/data_sources/fia_business.py`（加多區計數）
- Modify: `src/site_siting/data_sources/distribution_builder.py`
- Modify: `src/site_siting/analysis/factors.py`
- Test: `tests/data_sources/test_distribution_builder.py`（追加）、`tests/analysis/test_factors_percentile.py`（追加）
- Generate（選用，需網路）: `data/reference/distributions/day_night_gap.json`

- [ ] **Step 1: 寫失敗測試（builder：偏離量母體）**

在 `tests/data_sources/test_distribution_builder.py` 追加：

```python
import math
from site_siting.data_sources.distribution_builder import daynight_deviation_values


def test_daynight_deviation_values():
    # ratio=1 偏離0；ratio=e 偏離1；ratio=0/負 略過
    vals = daynight_deviation_values([1.0, math.e, 0.0, -1.0])
    assert sorted(round(v, 6) for v in vals) == [0.0, 1.0]
```

- [ ] **Step 2: 執行確認失敗**

Run: `python3 -m pytest tests/data_sources/test_distribution_builder.py::test_daynight_deviation_values -q`
Expected: FAIL（`ImportError: daynight_deviation_values`）

- [ ] **Step 3: 實作 builder**

在 `distribution_builder.py` 加入：

```python
import math


def daynight_deviation_values(ratios) -> list[float]:
    """各區每千人營業家數相對全國比值 → |ln(比值)| 偏離量母體（比值>0 者）。"""
    return [abs(math.log(r)) for r in ratios if r and r > 0]
```

- [ ] **Step 4: 執行確認通過（builder）**

Run: `python3 -m pytest tests/data_sources/test_distribution_builder.py -q`
Expected: PASS

- [ ] **Step 5: 寫失敗測試（fia 多區計數）**

Create `tests/data_sources/test_fia_multi.py`:

```python
from site_siting.data_sources.fia_business import count_all_districts


def test_count_all_districts_one_pass():
    rows = [
        ["營業地址", "其他"],                    # 表頭略過
        ["桃園市龜山區樂善里1號", "x"],
        ["桃園市龜山區山頂里2號", "x"],
        ["桃園市中壢區中央路3號", "x"],
        ["新北市板橋區4號", "x"],
    ]
    counts, total = count_all_districts(rows, ["龜山區", "中壢區", "大溪區"])
    assert counts == {"龜山區": 2, "中壢區": 1, "大溪區": 0}
    assert total == 4   # 全國總筆數（扣表頭）
```

- [ ] **Step 6: 執行確認失敗**

Run: `python3 -m pytest tests/data_sources/test_fia_multi.py -q`
Expected: FAIL（`ImportError: count_all_districts`）

- [ ] **Step 7: 實作 fia 多區計數**

在 `fia_business.py` 加入：

```python
def count_all_districts(rows, districts) -> tuple[dict[str, int], int]:
    """單次掃描同時計各行政區與全國總家數。回傳 ({區: 家數}, 全國總數)。"""
    counts = {d: 0 for d in districts}
    total = 0
    for i, row in enumerate(rows):
        if i == 0 or not row:
            continue
        total += 1
        addr = row[_ADDRESS_COL] if len(row) > _ADDRESS_COL else ""
        for d in districts:
            if d in addr:
                counts[d] += 1
    return counts, total
```

- [ ] **Step 8: 執行確認通過（fia）**

Run: `python3 -m pytest tests/data_sources/test_fia_multi.py tests/data_sources/test_fia_business.py -q`
Expected: PASS

- [ ] **Step 9: 寫失敗測試（factors 晝夜反向百分位）**

在 `tests/analysis/test_factors_percentile.py` 追加：

```python
import math as _math


def test_day_night_percentile_inverts_on_deviation():
    # 偏離量母體 [0,0.2,0.5,1.0]；ratio=1 偏離0 → pctl 0 → invert 100
    d = _dist("day_night_gap", "區", [0.0, 0.2, 0.5, 1.0])
    f = build_factors({"business_ratio": 1.0}, dist={"day_night_gap": d})
    assert f["day_night_gap"].score == 100.0
    assert f["day_night_gap"].source == "real"
```

- [ ] **Step 10: 執行確認失敗**

Run: `python3 -m pytest tests/analysis/test_factors_percentile.py::test_day_night_percentile_inverts_on_deviation -q`
Expected: FAIL（走舊 day_night_score，分數非 100）

- [ ] **Step 11: 實作 factors — 改 day_night_gap 區塊**

確認 `factors.py` 頂部已 `import math`（現況已有）。把現有 `day_night_gap` 建構區塊改為：

```python
    ratio = raw.get("business_ratio")
    if ratio is not None:
        d = dist.get("day_night_gap")
        if d is not None and ratio > 0:
            score = percentile_score(abs(math.log(ratio)), d, invert=True)
        else:
            score = day_night_score(ratio)
        out["day_night_gap"] = FactorResult(score, "real")
    else:
        out["day_night_gap"] = FactorResult(NEUTRAL, "missing")
```

在 `factor_explanation` 的 `day_night_gap` 分支，`basis` 改為百分位優先：

```python
    if name == "day_night_gap":
        ratio = g("business_ratio")
        if ratio is None:
            return {"raw": "無資料", "basis": "沿用上次快照值或中性 50"}
        lean = "日夜均衡" if 0.85 <= ratio <= 1.15 else (
            "就業聚集型" if ratio > 1.15 else "住宅睡城型")
        d = dist.get("day_night_gap")
        if d is not None and ratio > 0:
            p = percentile_score(abs(math.log(ratio)), d, invert=True)
            basis = (f"日夜均衡度（|ln(比值)| 偏離量）全桃園 {d.n} 區第 {p:.0f} 百分位"
                     f"（越均衡越高，{d.source}）")
        else:
            basis = "比值=1 日夜最均衡得分最高；偏離以 |ln(比值)| 線性扣分"
        return {
            "raw": f"營業家數每千人為全國 {ratio:.2f} 倍（{lean}）",
            "basis": basis,
        }
```

- [ ] **Step 12: 執行確認通過（含既有不回歸）**

Run: `python3 -m pytest tests/analysis/ tests/data_sources/ -q`
Expected: PASS

- [ ] **Step 13: 產生晝夜分布檔（選用，需網路；下載財政部 320MB 掃一次）**

Run:
```bash
python3 - <<'PY'
from pathlib import Path
from site_siting.data_sources import fia_business
from site_siting.data_sources.reference import parse_population_csv
from site_siting.data_sources.distribution_builder import (
    make_distribution, daynight_deviation_values, write_distribution)
import csv, io, urllib.request

DISTRICTS = ["桃園區","中壢區","大溪區","楊梅區","蘆竹區","大園區","龜山區",
             "八德區","龍潭區","平鎮區","新屋區","觀音區","復興區"]
NATIONAL_POP = 23_400_000

pop = parse_population_csv(Path("data/reference/population_taoyuan_latest.csv").read_text(encoding="utf-8-sig"))
req = urllib.request.Request(fia_business.BUSINESS_CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=600) as r:
    reader = csv.reader(io.TextIOWrapper(r, encoding="utf-8", errors="replace"))
    counts, total = fia_business.count_all_districts(list(reader), DISTRICTS)

ratios = []
for d in DISTRICTS:
    dp = pop.get(d, {}).get("population", 0)
    ratio = fia_business.business_ratio(counts[d], total, dp, NATIONAL_POP)
    if ratio is not None:
        ratios.append(ratio)
vals = daynight_deviation_values(ratios)
write_distribution(make_distribution(
    "day_night_gap", "區", "財政部營業稅籍桃園市各區日夜均衡偏離量", vals),
    Path("data/reference/distributions/day_night_gap.json"))
print("day_night_gap N =", len(vals))
PY
```
Expected: 印出 `day_night_gap N = 13`（或下載失敗；失敗則計分回退舊公式）。成功則 add 分布檔。

- [ ] **Step 14: Commit**

```bash
git add src/site_siting/data_sources/fia_business.py src/site_siting/data_sources/distribution_builder.py src/site_siting/analysis/factors.py tests/data_sources/test_distribution_builder.py tests/data_sources/test_fia_multi.py tests/analysis/test_factors_percentile.py
# 若 Step 13 成功一併 add day_night_gap.json
git commit -m "feat: 晝夜落差改偏離量反向百分位，全桃園各區母體"
```

---

## Task 7: 串接 pipeline 與 site_export（快照與說明皆客觀）

**Files:**
- Modify: `src/site_siting/pipeline.py`
- Modify: `src/site_siting/site_export.py`
- Test: `tests/test_pipeline.py`（追加）、`tests/test_site_export.py`（追加）

- [ ] **Step 1: 寫失敗測試（pipeline 用分布計分）**

在 `tests/test_pipeline.py` 追加（沿用檔內既有 `REF`/`HIST`/`CONFIG` 慣例；若無則自建最小 reference。以下用既有離線 fixture）：

```python
def test_run_pipeline_uses_committed_distributions(tmp_path):
    import site_siting.pipeline as pl
    hist = tmp_path / "history.jsonl"
    snap = pl.run_pipeline(REFERENCE_DIR, hist, CONFIG_PATH, live=False)
    pp = snap["location"]["factors"]["purchasing_power"]
    # 已提交 purchasing_power.json → 分數應為百分位（非舊 minmax 77.78）
    assert pp["source"] == "real"
    assert pp["score"] != 77.78
```

> 註：`REFERENCE_DIR`、`CONFIG_PATH` 沿用 `tests/test_pipeline.py` 檔頭既有常數；若名稱不同，用該檔實際常數名。

- [ ] **Step 2: 執行確認失敗**

Run: `python3 -m pytest tests/test_pipeline.py::test_run_pipeline_uses_committed_distributions -q`
Expected: FAIL（run_pipeline 尚未載入分布，purchasing_power 仍為 minmax 77.78）

- [ ] **Step 3: 實作 pipeline — 載入分布並下傳 build_factors**

在 `pipeline.py` import 區加入：

```python
from site_siting.analysis.percentile import load_distributions
```

在 `run_pipeline` 內，`config = load_industry_config(config_path)` 之後加：

```python
    dist = load_distributions()
```

把兩處 `build_factors(...)` 呼叫改為傳 dist：
- 地點因子：`loc_factors = build_factors(raw, dist)`
- 行業迴圈：`factors = build_factors(ind_raw, dist)`

- [ ] **Step 4: 執行確認通過（pipeline）**

Run: `python3 -m pytest tests/test_pipeline.py -q`
Expected: PASS

- [ ] **Step 5: 寫失敗測試（site_export 說明顯示百分位）**

在 `tests/test_site_export.py` 追加：

```python
def test_location_factor_basis_shows_percentile():
    payload = build_payload(
        [_snap("2026-06-01", 70.0), _snap("2026-07-01", 72.0)], CONFIG)
    rows = {r["factor"]: r for r in payload["location_factors"]}
    # 已提交分布檔 → purchasing_power 說明含「百分位」
    assert "百分位" in rows["purchasing_power"]["basis_text"]
```

> 註：`_snap` 需在 location.raw 內含 `weighted_median_income`。既有 `_snap` 已含 `purchasing_power` factor 與 `weighted_median_income`（見 Task 7 前置測試檔）；若缺，於 `_snap` 的 `location.raw` 補 `"weighted_median_income": 568.0`。

- [ ] **Step 6: 執行確認失敗**

Run: `python3 -m pytest tests/test_site_export.py::test_location_factor_basis_shows_percentile -q`
Expected: FAIL（factor_explanation 未收到 dist，basis 仍為線性映射字串）

- [ ] **Step 7: 實作 site_export — 載入分布並下傳 factor_explanation**

在 `site_export.py` import 區加入：

```python
from site_siting.analysis.percentile import load_distributions
```

把 `_factor_row` 簽名改為 `def _factor_row(name, factors, prev_factors, raw, dist=None):`，內部呼叫改為 `exp = factor_explanation(name, raw, dist)`。

把 `_location_factor_table`、`_industry_factor_table` 簽名各加 `dist=None`，並在迴圈把 `dist` 傳入 `_factor_row(name, factors, prev_factors, raw, dist)`。

把 `build_payload` 簽名改為 `def build_payload(snapshots, config=None, dist=None):`，在函式開頭加 `dist = dist if dist is not None else load_distributions()`，並把兩處表格呼叫改為：
- `"factors": _industry_factor_table(snapshots, iid, dist),`
- `"location_factors": _location_factor_table(snapshots, dist),`

把 `build_site` 簽名改為 `def build_site(history_path, site_dir, config=None, dist=None):`，在讀完 snapshots 後加 `dist = dist if dist is not None else load_distributions()`，並把 `build_payload(snapshots, config)` 改為 `build_payload(snapshots, config, dist)`。

- [ ] **Step 8: 執行確認通過（含既有不回歸）**

Run: `python3 -m pytest tests/test_site_export.py tests/test_pipeline.py -q`
Expected: PASS（既有 site_export 測試未傳 dist，`build_payload` 會自動 `load_distributions()`；因已提交 purchasing_power/population 分布檔，basis 文字改為百分位，但既有測試斷言的是結構與 delta，不受影響）

- [ ] **Step 9: 全套件回歸**

Run: `python3 -m pytest -q`
Expected: PASS（全綠）

- [ ] **Step 10: Commit**

```bash
git add src/site_siting/pipeline.py src/site_siting/site_export.py tests/test_pipeline.py tests/test_site_export.py
git commit -m "feat: pipeline/site_export 載入分布，快照分數與說明改客觀百分位"
```

---

## Task 8: 分布檔稽核 metadata 測試

**Files:**
- Test: `tests/test_distributions_manifest.py`

- [ ] **Step 1: 寫測試**

```python
# tests/test_distributions_manifest.py
from pathlib import Path
from site_siting.analysis.percentile import load_distributions

DIST_DIR = Path(__file__).resolve().parents[1] / "data" / "reference" / "distributions"


def test_committed_distributions_have_full_metadata():
    dists = load_distributions(DIST_DIR)
    # 至少已提交消費力與人口兩檔
    assert "purchasing_power" in dists
    assert "population_density" in dists
    for factor, d in dists.items():
        assert d.unit in {"里", "區"}, f"{factor} 單位異常"
        assert d.source, f"{factor} 缺出處"
        assert d.generated, f"{factor} 缺產生日期"
        assert d.n > 0, f"{factor} 母體為空"
        # values 排序遞增（load 時已排序）
        assert d.values == sorted(d.values)


def test_income_distribution_is_village_level():
    d = load_distributions(DIST_DIR)["purchasing_power"]
    assert d.unit == "里"
    assert d.n >= 100   # 全桃園數百里
```

- [ ] **Step 2: 執行確認通過**

Run: `python3 -m pytest tests/test_distributions_manifest.py -q`
Expected: PASS（消費力/人口分布檔已於 Task 2 提交）

- [ ] **Step 3: 全套件回歸**

Run: `python3 -m pytest -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_distributions_manifest.py
git commit -m "test: 分布檔稽核 — 每檔須具備出處/單位/N/日期 metadata"
```

---

## 完成後

- 已提交、零網路即客觀化的因子：**消費力、人口**（分布檔在 repo）。
- 需網路一次性建母體的因子：**屋齡、年齡性別、晝夜**（Task 4/5/6 的 Step 9/13 產生分布檔；未產生時計分自動回退舊 minmax，不影響全綠）。執行者若在有網路環境，跑各該 Step 產生並提交分布檔，即完成全 5 因子客觀化。
- 更新分布：日後重跑對應 builder 產生新 JSON、覆蓋提交即可；`generated` 欄記錄版本日期供稽核。
- 未納入本次：地理掃描型 8 因子（超商/商業/學校/公車/競爭/錨點/能見度/土地混合）仍為 minmax；如需客觀化，另立計畫建「掃 K 個桃園抽樣點自建分布」的 harness。
- 權重仍為人工分級（AHP 有紀律化為另一獨立方向，未在本計畫範圍）。
```

