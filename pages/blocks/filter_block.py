"""Reusable filter dropdown: multi-select (checkboxes), single (radio) or range (inputs)."""

from __future__ import annotations

import allure
from playwright.sync_api import Locator, Page


class FilterBlock:
    TOGGLE = "[data-test=filter-toggle]"
    PANEL = "[data-test=filter-panel]"
    OPTION = "[data-test='option-{value}']"
    SELECT_ALL = "[data-test=select-all]"
    CLEAR = "[data-test=clear]"
    APPLY = "[data-test=apply]"
    AMOUNT_MIN = "[data-test=amount-min]"
    AMOUNT_MAX = "[data-test=amount-max]"
    CHECKED = "input:checked"

    def __init__(self, page: Page, root_test_id: str, title: str):
        self.page = page
        self.title = title
        self.root: Locator = page.locator(f"[data-test={root_test_id}]")

    @property
    def toggle(self) -> Locator:
        return self.root.locator(self.TOGGLE)

    @property
    def panel(self) -> Locator:
        return self.root.locator(self.PANEL)

    def open(self) -> None:
        if not self.panel.is_visible():
            self.toggle.click()
        self.panel.wait_for(state="visible")

    def option(self, value: str) -> Locator:
        return self.root.locator(self.OPTION.format(value=value))

    def select(self, values: list[str]) -> None:
        with allure.step(f"Фильтр «{self.title}»: выбрать {values}"):
            self.open()
            for value in values:
                self.option(value).check()

    def unselect(self, values: list[str]) -> None:
        with allure.step(f"Фильтр «{self.title}»: снять {values}"):
            self.open()
            for value in values:
                self.option(value).uncheck()

    def select_all(self) -> None:
        with allure.step(f"Фильтр «{self.title}»: выбрать всё"):
            self.open()
            self.root.locator(self.SELECT_ALL).click()

    def fill_range(self, amount_min: int | None, amount_max: int | None) -> None:
        with allure.step(f"Фильтр «{self.title}»: от {amount_min} до {amount_max}"):
            self.open()
            self.root.locator(self.AMOUNT_MIN).fill("" if amount_min is None else str(amount_min))
            self.root.locator(self.AMOUNT_MAX).fill("" if amount_max is None else str(amount_max))

    def click_apply(self) -> None:
        self.root.locator(self.APPLY).click()

    def click_clear(self) -> None:
        self.open()
        self.root.locator(self.CLEAR).click()

    def selected_values(self) -> list[str]:
        """Values checked in the panel (opens the panel if needed)."""
        self.open()
        values = [v for v in self.root.locator(self.CHECKED).evaluate_all("els => els.map(e => e.value)") if v]
        self.toggle.click()  # close the panel back
        return values

    def button_text(self) -> str:
        return self.toggle.inner_text().strip()
