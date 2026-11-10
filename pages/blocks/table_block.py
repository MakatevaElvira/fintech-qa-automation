"""Applications table: rows, cells and the asynchronous checks block."""

from __future__ import annotations

import allure
from playwright.sync_api import Locator, Page, expect


class ApplicationsTable:
    ROW = "[data-test=application-row]"
    CELL = "[data-test=cell-{name}]"
    EXPAND = "[data-test=expand-checks]"
    CHECKS_BLOCK = "[data-test=checks-block]"
    CHECK_ROW = "[data-test=check-row]"
    CHECK_PRODUCT = "[data-test=check-product]"
    EMPTY = "[data-test=empty]"
    TOTAL = "[data-test=total]"

    def __init__(self, page: Page):
        self.page = page

    @property
    def rows(self) -> Locator:
        return self.page.locator(self.ROW)

    def count(self) -> int:
        return self.rows.count()

    def total(self) -> int:
        return int(self.page.locator(self.TOTAL).inner_text())

    def column(self, name: str) -> list[str]:
        return [t.strip() for t in self.rows.locator(self.CELL.format(name=name)).all_inner_texts()]

    def row_uuids(self) -> list[str]:
        return self.rows.evaluate_all("rows => rows.map(r => r.dataset.uuid)")

    def valid_row_indexes(self) -> list[int]:
        """Rows that can be traced to the source system (have an external id)."""
        return [i for i, ext in enumerate(self.column("external")) if ext]

    def expand_checks(self, index: int) -> Locator:
        """Open the checks block of a row and wait until it is computed (loading -> ready)."""
        with allure.step(f"Раскрыть проверки заявки #{index}"):
            row = self.rows.nth(index)
            row.locator(self.EXPAND).click()
            block = row.locator("xpath=following-sibling::tr[1]").locator(self.CHECKS_BLOCK)
            expect(block).to_have_attribute("data-state", "ready")
            return block

    def check_products(self, index: int) -> list[str]:
        block = self.expand_checks(index)
        return [t.strip() for t in block.locator(self.CHECK_PRODUCT).all_inner_texts()]
