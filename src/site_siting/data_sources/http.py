from __future__ import annotations

import requests

USER_AGENT = "clinic-siting/1.0 (research)"
DEFAULT_TIMEOUT = 30


def get_json(url: str, params: dict | None = None, headers: dict | None = None) -> dict:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    resp = requests.get(url, params=params, headers=h, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def post_json(url: str, json_body: dict | None = None, data: dict | None = None,
              headers: dict | None = None) -> dict:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    resp = requests.post(url, json=json_body, data=data, headers=h, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_text(url: str, params: dict | None = None, headers: dict | None = None) -> str:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    resp = requests.get(url, params=params, headers=h, timeout=120)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text
