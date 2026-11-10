"""One wrapper for all API calls: status check, schema validation, Allure attachments."""

from __future__ import annotations

import json
import logging

import allure
import requests
from pydantic import ValidationError

from pages.api.endpoints import ENDPOINTS
from pages.api.models import ErrorResponse

log = logging.getLogger(__name__)


def _pretty(text: str) -> str:
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    except ValueError:
        return text


def make_request(
    session: requests.Session,
    base_url: str,
    endpoint: str,
    *,
    expected_status: int,
    negative: bool = False,
    validate_schema: bool = True,
    path_params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 10,
    **kwargs,
) -> requests.Response:
    """Send a request to an endpoint from the registry.

    negative=True -> the body is validated as ErrorResponse instead of the endpoint model.
    """
    ep = ENDPOINTS[endpoint]
    url = ep.url(base_url, **(path_params or {}))
    with allure.step(f"{ep.method} {ep.path} -> ожидаем {expected_status}"):
        response = session.request(ep.method, url, headers=headers, timeout=timeout, **kwargs)
        log.info("%s %s -> %s", ep.method, response.url, response.status_code)
        allure.attach(
            f"{ep.method} {response.url}\n\n{_pretty(response.text)}",
            name=f"response {response.status_code}",
            attachment_type=allure.attachment_type.TEXT,
        )

        assert response.status_code == expected_status, (
            f"{ep.method} {ep.path}: ожидался статус {expected_status}, получен {response.status_code}. "
            f"Тело ответа: {response.text[:500]}"
        )

        if validate_schema:
            model = ErrorResponse if negative else ep.model
            if model is not None:
                try:
                    model.model_validate(response.json())
                except ValidationError as err:
                    raise AssertionError(
                        f"ответ {ep.path} не соответствует контракту {model.__name__}:\n{err}"
                    ) from err
    return response
