"""月度刷新編排：抓取→算分→寫快照→重建靜態站。

由 macOS launchd 每月觸發（見 deploy/）。站台由常駐靜態伺服器提供，隨時可看。
對應設計規格 §4 資料流步驟 1、4。
"""
from __future__ import annotations

from pathlib import Path

from clinic_siting.pipeline import run_pipeline

_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = _ROOT / "data" / "reference"
HISTORY_PATH = _ROOT / "history.jsonl"
CONFIG_PATH = _ROOT / "config" / "specialties.yaml"
SITE_DIR = _ROOT / "site"


def run_refresh(live: bool = True,
                reference_dir=REFERENCE_DIR, history_path=HISTORY_PATH,
                config_path=CONFIG_PATH, site_dir=SITE_DIR) -> dict:
    """單次刷新：抓取算分、寫快照、重建 site/，回傳本次 snapshot。"""
    return run_pipeline(reference_dir, history_path, config_path,
                        live=live, site_dir=site_dir)


def main():
    snap = run_refresh()
    for name, score in sorted(snap["scores"].items(), key=lambda x: -x[1]):
        print(f"{name:20s} {score:5.1f}")


if __name__ == "__main__":
    main()
