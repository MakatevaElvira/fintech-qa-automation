"""Authorization without UI: login through the API, the session cookie is reused by API and browser."""

from __future__ import annotations

import logging

import allure
import requests

from helpers.config import EnvConfig

log = logging.getLogger(__name__)


@allure.step("Получить сессию через API")
def get_session_cookie(env: EnvConfig) -> str:
    response = requests.post(
        f"{env.base_url}/api/auth/login",
        json={"username": env.username, "password": env.password},
        timeout=env.timeout,
    )
    if response.status_code != 201 or "session" not in response.cookies:
        raise RuntimeError(f"authorization failed: HTTP {response.status_code} {response.text}")
    log.info("session received for %s", env.username)
    return response.cookies["session"]
