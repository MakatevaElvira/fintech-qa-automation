"""Environment configs: configs/<env>.json split into common / auth / ui / api."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path

CONFIGS = Path(__file__).resolve().parent.parent / "configs"


@dataclass(frozen=True)
class EnvConfig:
    name: str
    raw: dict
    base_url: str

    @property
    def timeout(self) -> float:
        return self.raw["common"]["timeout_sec"]

    @property
    def username(self) -> str:
        return self.raw["auth"]["username"]

    @property
    def password(self) -> str:
        auth = self.raw["auth"]
        return os.getenv(auth["password_env"]) or auth["password_default"]

    def ui_data(self, test: str, case: str) -> dict:
        return self.raw["ui"][test][case]

    def api_data(self, test: str, case: str) -> dict:
        return self.raw["api"][test][case]

    def cases(self, layer: str, test: str) -> list[str]:
        return list(self.raw[layer][test])


@cache
def load_raw(env: str) -> dict:
    path = CONFIGS / f"{env}.json"
    if not path.exists():
        raise FileNotFoundError(f"no config for env '{env}': {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_env(env: str, port: int | None = None) -> EnvConfig:
    raw = load_raw(env)
    base_url = raw["common"]["base_url"]
    if "{port}" in base_url:
        base_url = base_url.format(port=port)
    return EnvConfig(env, raw, base_url.rstrip("/"))
