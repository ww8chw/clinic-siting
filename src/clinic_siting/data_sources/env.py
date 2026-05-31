from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


def load_env() -> dict[str, str]:
    """讀專案根 .env，回傳 dict（值為 None 的鍵會被濾掉）。"""
    return {k: v for k, v in dotenv_values(_ENV_PATH).items() if v}


def get_key(name: str) -> str | None:
    """取單一金鑰：環境變數優先（供 CI/GitHub Actions secrets），其次本地 .env；
    皆無回 None（讓 fetch 層決定要不要 skip）。"""
    return os.environ.get(name) or load_env().get(name)
