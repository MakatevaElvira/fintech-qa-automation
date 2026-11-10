"""Page Object of the applications list. No asserts and no sleeps here:
complex checks return (ok, message) and the test decides."""

from __future__ import annotations

import allure

from pages.base_page import BasePage
from pages.blocks.filter_block import FilterBlock
from pages.blocks.table_block import ApplicationsTable


class ApplicationsPage(BasePage):
    PATH = "/applications"
    RESET_ALL = "[data-test=reset-all]"

    def __init__(self, page, base_url: str):
        super().__init__(page, base_url)
        self.table = ApplicationsTable(page)
        self.product = FilterBlock(page, "filter-product", "Продукт")
        self.status = FilterBlock(page, "filter-status", "Статус")
        self.risk = FilterBlock(page, "filter-risk", "Риск-флаги")
        self.amount = FilterBlock(page, "filter-amount", "Сумма")

    # ---------- actions that reload the table ----------
    def apply(self, block: FilterBlock) -> dict:
        """Click «Применить» and wait for that exact table response."""
        with (
            allure.step(f"Применить фильтр «{block.title}»"),
            self.page.expect_response(self._is_table_response) as info,
        ):
            block.click_apply()
        return self._finish_table_load(info.value)

    def clear(self, block: FilterBlock) -> dict:
        with allure.step(f"Очистить фильтр «{block.title}»"):
            block.open()
            with self.page.expect_response(self._is_table_response) as info:
                block.click_clear()
        return self._finish_table_load(info.value)

    def reset_all(self) -> dict:
        with allure.step("Сбросить все фильтры"), self.page.expect_response(self._is_table_response) as info:
            self.page.locator(self.RESET_ALL).click()
        return self._finish_table_load(info.value)

    def filter_by_products(self, products: list[str]) -> dict:
        self.product.select(products)
        return self.apply(self.product)

    def filter_by_statuses(self, statuses: list[str]) -> dict:
        self.status.select(statuses)
        return self.apply(self.status)

    # ---------- data collection ----------
    @staticmethod
    def check_uuids(table_json: dict) -> list[str]:
        """UUIDs of all checks of every application shown in the table (application -> many checks)."""
        return [c["uuid"] for item in table_json["items"] for c in item["checks"]]

    # ---------- complex checks: (ok, message) ----------
    def rows_match_response(self, table_json: dict) -> tuple[bool, str]:
        ui, api = self.table.row_uuids(), [i["uuid"] for i in table_json["items"]]
        if ui != api:
            return False, f"строки таблицы не совпадают с ответом API: UI={ui[:5]}…, API={api[:5]}…"
        return True, ""

    def all_rows_have_status(self, label: str) -> tuple[bool, str]:
        wrong = [(i, s) for i, s in enumerate(self.table.column("status")) if s != label]
        return (not wrong, f"строки с другим статусом (индекс, статус): {wrong}")

    def all_amounts_in_range(self, amount_min: int, amount_max: int) -> tuple[bool, str]:
        amounts = [int(a.replace(" ", "").replace(" ", "")) for a in self.table.column("amount")]
        wrong = [(i, a) for i, a in enumerate(amounts) if not amount_min <= a <= amount_max]
        return (not wrong, f"суммы вне диапазона {amount_min}–{amount_max} (индекс, сумма): {wrong}")
