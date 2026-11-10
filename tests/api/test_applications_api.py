"""API: applications list, card, update and authorization."""

from __future__ import annotations

import allure
import pytest
import requests

from helpers.http_client import make_request
from pages.api.models import Application, ApplicationsList
from pages.data.cases import ApiListCase

pytestmark = [allure.feature("API: заявки"), allure.label("layer", "api"), pytest.mark.api]


@allure.story("Список заявок")
@pytest.mark.parametrize("case", ["positive", "filter_by_status", "unknown_product", "invalid_amount", "invalid_page"])
def test_applications_list(api, env, api_data, case):
    """Список заявок: позитивные кейсы и валидация параметров"""
    data = ApiListCase(**api_data(case))

    response = make_request(
        api,
        env.base_url,
        "applications_list",
        expected_status=data.expected_status,
        negative=data.negative,
        params=data.params,
        timeout=env.timeout,
    )

    body = response.json()
    match case:
        case "positive":
            result = ApplicationsList.model_validate(body)
            assert result.total > 0, "ожидались заявки в выдаче"
            assert len(result.items) == min(result.total, result.page_size)
        case "filter_by_status":
            wrong = [(i.uuid, i.status) for i in ApplicationsList.model_validate(body).items if i.status != "approved"]
            assert not wrong, f"в выдаче по status=approved есть заявки с другим статусом: {wrong}"
        case _:
            assert data.error_field in body["fields"], (
                f"ожидалась ошибка по полю {data.error_field}, получено: {body['fields']}"
            )


@allure.story("Авторизация")
@pytest.mark.parametrize("case", ["no_cookie", "wrong_password", "unknown_user", "missing_fields", "positive"])
def test_auth(env, case):
    """Авторизация: сессия, неверные данные, валидация"""
    session = requests.Session()
    match case:
        case "no_cookie":
            make_request(session, env.base_url, "applications_list", expected_status=401, negative=True)
        case "wrong_password":
            make_request(
                session,
                env.base_url,
                "auth_login",
                expected_status=401,
                negative=True,
                json={"username": env.username, "password": "wrong"},
            )
        case "unknown_user":
            make_request(
                session,
                env.base_url,
                "auth_login",
                expected_status=401,
                negative=True,
                json={"username": "nobody", "password": env.password},
            )
        case "missing_fields":
            response = make_request(
                session, env.base_url, "auth_login", expected_status=422, negative=True, json={"username": env.username}
            )
            assert "password" in response.json()["fields"], "ожидалась ошибка по полю password"
        case "positive":
            response = make_request(
                session,
                env.base_url,
                "auth_login",
                expected_status=201,
                json={"username": env.username, "password": env.password},
            )
            assert "session" in response.cookies, "в ответе нет cookie сессии"
            make_request(session, env.base_url, "applications_list", expected_status=200)


@allure.story("Карточка заявки")
def test_application_card_matches_db(api, env, db):
    """Карточка заявки совпадает с данными в БД"""
    app_uuid = db.application_with_checks(min_checks=2)

    response = make_request(api, env.base_url, "application", expected_status=200, path_params={"uuid": app_uuid})

    card = Application.model_validate(response.json())
    state = db.application_state(app_uuid)
    assert card.status == state["status"], f"статус в API {card.status}, в БД {state['status']}"
    assert card.risk_flags == sum(state["flags"].values()), (
        f"risk_flags в API {card.risk_flags}, в БД {sum(state['flags'].values())} (заявка {app_uuid})"
    )


@allure.story("Карточка заявки")
def test_unknown_application_returns_404(api, env):
    """Несуществующая заявка -> 404"""
    make_request(
        api,
        env.base_url,
        "application",
        expected_status=404,
        negative=True,
        path_params={"uuid": "00000000-0000-0000-0000-000000000000"},
    )


@allure.story("Изменение заявки")
@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"status": "archived"}, 422),
        ({"risk_flags": -1}, 422),
        ({"risk_flags": True}, 422),
        ({"risk_flags": 99}, 409),
    ],
    ids=["unknown_status", "negative_flags", "bool_flags", "more_flags_than_checks"],
)
def test_update_validation(api, env, db, payload, expected_status):
    """Изменение заявки: невалидные данные не меняют состояние"""
    app_uuid = db.application_with_checks(min_checks=1)
    before = db.application_state(app_uuid)

    make_request(
        api,
        env.base_url,
        "application_update",
        expected_status=expected_status,
        negative=True,
        path_params={"uuid": app_uuid},
        json=payload,
    )

    assert db.application_state(app_uuid) == before, "состояние заявки изменилось после невалидного запроса"


@allure.story("Изменение заявки")
def test_changed_status_is_found_by_filter(api, env, application_with_status):
    """Заявка, переведённая в pending, находится фильтром по статусу"""
    app_uuid = application_with_status("pending")

    response = make_request(
        api, env.base_url, "applications_list", expected_status=200, params={"status": "pending", "page": 1}
    )

    total = ApplicationsList.model_validate(response.json()).total
    found = []
    for page in range(1, total // 20 + 2):
        body = make_request(
            api, env.base_url, "applications_list", expected_status=200, params={"status": "pending", "page": page}
        ).json()
        found += [i for i in body["items"] if i["uuid"] == app_uuid]
    assert found, f"заявка {app_uuid} не найдена по фильтру status=pending"
