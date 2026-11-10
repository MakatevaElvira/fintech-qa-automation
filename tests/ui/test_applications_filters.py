"""UI: filters of the applications list with double validation UI + DB."""

from __future__ import annotations

import allure
import pytest
from playwright.sync_api import expect

from pages.data.cases import AmountFilterCase, ProductFilterCase, StatusFilterCase

pytestmark = [
    allure.feature("UI: список заявок"),
    allure.label("layer", "ui"),
    pytest.mark.ui,
    pytest.mark.xdist_group("ui_applications"),
]


@allure.story("Фильтр «Продукт»")
@pytest.mark.parametrize("case", ["pdl_only", "pdl_and_credit_line"])
def test_filter_by_product(applications_page, db, ui_data, case):
    """Фильтр «Продукт» показывает только заявки с проверками выбранных продуктов"""
    data = ProductFilterCase(**ui_data(case))
    applications_page.open()

    filter_name = applications_page.product.title
    with allure.step(f"Фильтрация по «{filter_name}»"):
        table_json = applications_page.filter_by_products(data.products)

    with allure.step("Проверить, что есть заявки и строки UI совпадают с ответом таблицы"):
        assert applications_page.table.count() > 0, f"по фильтру {data.products} нет заявок"
        ok, msg = applications_page.rows_match_response(table_json)
        assert ok, msg

    with allure.step("UI: у первой валидной заявки раскрыть проверки и найти выбранный продукт"):
        valid = applications_page.table.valid_row_indexes()
        if not valid:
            pytest.skip("на первой странице нет заявок с внешним ID")
        products = applications_page.table.check_products(valid[0])
        assert set(products) & set(data.products), (
            f"заявка #{valid[0]}: у проверок продукты {products}, ожидался хотя бы один из {data.products}"
        )

    with allure.step("БД: нет заявок, у которых ни одна проверка не относится к выбранным продуктам"):
        check_uuids = applications_page.check_uuids(table_json)
        wrong = db.applications_without_products(check_uuids, data.products)
        assert not wrong, "заявки без выбранных продуктов: " + ", ".join(
            f"{r['uuid']} (продукты проверок: {r['products']})" for r in wrong
        )


@allure.story("Фильтр «Статус»")
@pytest.mark.parametrize("case", ["approved", "rejected_and_pending"])
def test_filter_by_status(applications_page, db, ui_data, case):
    """Фильтр «Статус»: UI-метки и статусы в БД совпадают с выбором"""
    data = StatusFilterCase(**ui_data(case))
    applications_page.open()

    filter_name = applications_page.status.title
    with allure.step(f"Фильтрация по «{filter_name}»"):
        table_json = applications_page.filter_by_statuses(data.statuses)

    assert applications_page.table.count() > 0, f"по статусам {data.statuses} нет заявок"
    if data.label:
        ok, msg = applications_page.all_rows_have_status(data.label)
        assert ok, msg
    wrong = db.applications_with_other_status(applications_page.check_uuids(table_json), data.statuses)
    assert not wrong, f"в БД у заявок другой статус: {[(r['uuid'], r['status']) for r in wrong]}"


@allure.story("Фильтр «Риск-флаги»")
@pytest.mark.parametrize("option", ["with", "without"])
def test_filter_by_risk_flags(applications_page, db, option):
    """Фильтр «Риск-флаги»: с флагами / без флагов"""
    applications_page.open()
    filter_name = applications_page.risk.title
    with allure.step(f"Фильтрация по «{filter_name}»"):
        applications_page.risk.select([option])
        table_json = applications_page.apply(applications_page.risk)

    flagged = {r["uuid"] for r in db.applications_with_risk_flags(applications_page.check_uuids(table_json))}
    shown = {i["uuid"] for i in table_json["items"]}
    assert shown, f"по фильтру «{option}» нет заявок"
    if option == "with":
        assert shown == flagged, f"без флагов в БД: {sorted(shown - flagged)}"
    else:
        assert not flagged, f"с флагами в БД: {sorted(flagged)}"


@allure.story("Фильтр «Сумма»")
def test_filter_by_amount(applications_page, db, ui_data):
    """Фильтр «Сумма»: все суммы в диапазоне, счётчик совпадает с БД"""
    data = AmountFilterCase(**ui_data("middle_range"))
    applications_page.open()
    filter_name = applications_page.amount.title
    with allure.step(f"Фильтрация по «{filter_name}»"):
        applications_page.amount.fill_range(data.amount_min, data.amount_max)
        applications_page.apply(applications_page.amount)

    ok, msg = applications_page.all_amounts_in_range(data.amount_min, data.amount_max)
    assert ok, msg
    expected = db.count_applications("amount BETWEEN ? AND ?", (data.amount_min, data.amount_max))
    assert applications_page.table.total() == expected, (
        f"счётчик в UI {applications_page.table.total()}, в БД {expected}"
    )


@allure.story("Состояние фильтров")
class TestFilterState:
    def test_change_value(self, applications_page):
        """Смена значения фильтра заменяет выдачу"""
        applications_page.open()
        applications_page.filter_by_products(["PDL"])

        applications_page.product.unselect(["PDL"])
        applications_page.product.select(["Installment"])
        table_json = applications_page.apply(applications_page.product)

        assert applications_page.product.selected_values() == ["Installment"]
        expect(applications_page.product.toggle).to_have_text("Продукт: 1")
        products = {c["product"] for i in table_json["items"] for c in i["checks"]}
        assert "Installment" in products, f"после смены на Installment продукты в выдаче: {products}"

    def test_clear(self, applications_page, db):
        """Очистка фильтра возвращает полную выдачу"""
        applications_page.open()
        applications_page.filter_by_products(["PDL"])

        applications_page.clear(applications_page.product)

        expect(applications_page.product.toggle).to_have_text("Продукт")
        assert applications_page.table.total() == db.count_applications(), "после очистки выдача не полная"

    def test_select_all_equals_no_filter(self, applications_page, db):
        """«Выбрать всё» в продуктах даёт ту же выдачу, что и без фильтра"""
        applications_page.open()
        applications_page.product.select_all()

        applications_page.apply(applications_page.product)

        assert applications_page.table.total() == db.count_applications()

    def test_two_filters_are_independent(self, applications_page):
        """Очистка одного фильтра не сбрасывает другой"""
        applications_page.open()
        applications_page.filter_by_products(["PDL"])
        applications_page.filter_by_statuses(["approved"])

        applications_page.clear(applications_page.product)

        assert applications_page.status.selected_values() == ["approved"], "фильтр «Статус» сбросился"
        ok, msg = applications_page.all_rows_have_status("Одобрена")
        assert ok, msg

    def test_state_persists_after_reload(self, applications_page):
        """Фильтры сохраняются после перезагрузки страницы"""
        applications_page.open()
        applications_page.filter_by_products(["Credit line"])
        before = applications_page.filter_by_statuses(["rejected"])

        after = applications_page.reload()

        assert applications_page.product.selected_values() == ["Credit line"]
        assert applications_page.status.selected_values() == ["rejected"]
        assert after["total"] == before["total"], f"до перезагрузки {before['total']}, после {after['total']}"


@allure.story("Блок проверок")
def test_ai_scoring_verdict_is_shown(applications_page):
    """AI-проверка показывает вердикт после асинхронной загрузки блока"""
    table_json = applications_page.open()
    with_ai = [
        i for i, item in enumerate(table_json["items"]) if any(c["check_type"] == "ai_scoring" for c in item["checks"])
    ]
    index = with_ai[0] if with_ai else None
    if index is None:
        pytest.skip("на первой странице нет заявок с AI-скорингом")

    block = applications_page.table.expand_checks(index)

    expected = next(c["ai_verdict"] for c in table_json["items"][index]["checks"] if c["check_type"] == "ai_scoring")
    expect(block.get_by_test_id("check-ai-verdict")).to_have_text(expected)
