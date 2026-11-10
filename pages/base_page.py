from __future__ import annotations

import json

import allure
from playwright.sync_api import Page, Response, expect


class BasePage:
    PATH = "/"
    LOADER = "[data-test=loader]"
    TABLE_RESPONSE_PART = "/api/applications?"

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def open(self, query: str = "") -> dict:
        """Open the page and return JSON of the table response that rendered it."""
        with allure.step(f"Открыть {self.PATH}{'?' + query if query else ''}"):
            with self.page.expect_response(self._is_table_response) as info:
                self.page.goto(f"{self.base_url}{self.PATH}{'?' + query if query else ''}")
            return self._finish_table_load(info.value)

    def reload(self) -> dict:
        with allure.step("Перезагрузить страницу"), self.page.expect_response(self._is_table_response) as info:
            self.page.reload()
        return self._finish_table_load(info.value)

    def _is_table_response(self, response: Response) -> bool:
        return self.TABLE_RESPONSE_PART in response.url and response.request.method == "GET"

    def _finish_table_load(self, response: Response) -> dict:
        """Wait for the specific table response and for the loader to disappear (no sleeps)."""
        expect(self.page.locator(self.LOADER)).to_be_hidden()
        body = response.json()
        allure.attach(
            json.dumps(
                {"url": response.url, "status": response.status, "total": body.get("total")}, ensure_ascii=False
            ),
            name="table response",
            attachment_type=allure.attachment_type.JSON,
        )
        return body
