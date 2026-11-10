"""Registry of API endpoints: one place for method, path and response model."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from pages.api.models import Application, ApplicationsList, SessionCreated


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    model: type[BaseModel] | None = None

    def url(self, base_url: str, **path_params) -> str:
        return base_url + self.path.format(**path_params)


ENDPOINTS: dict[str, Endpoint] = {
    "auth_login": Endpoint("POST", "/api/auth/login", SessionCreated),
    "applications_list": Endpoint("GET", "/api/applications", ApplicationsList),
    "application": Endpoint("GET", "/api/applications/{uuid}", Application),
    "application_update": Endpoint("PUT", "/api/applications/{uuid}", Application),
}
