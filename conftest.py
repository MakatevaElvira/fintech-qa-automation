"""Shared fixtures. Scope is chosen by cost:
session  - service, env config, browser
module   - authorized API session and authorized browser context (login once per module)
function - page under test (opened fresh in the already authorized context)
"""

from __future__ import annotations

import logging
import re
import warnings
from pathlib import Path

import allure
import pytest
import requests
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from app import server as sut
from helpers.auth import get_session_cookie
from helpers.config import EnvConfig, load_env
from helpers.db import LendingDb
from helpers.http_client import make_request
from pages.applications_page import ApplicationsPage

log = logging.getLogger(__name__)
ARTIFACTS = Path("test-results")


def pytest_addoption(parser):
    parser.addoption("--env", default="local", help="environment config from configs/<env>.json")
    parser.addoption("--headed", action="store_true", help="run browser with UI")
    parser.addoption("--slowmo", type=int, default=0, help="slow down browser actions, ms")
    parser.addoption("--channel", default="chrome", help="browser channel: chrome (Google Chrome) or chromium")
    parser.addoption("--tracing", choices=["retain-on-failure", "on"], default="retain-on-failure")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


# ---------------- session ----------------
@pytest.fixture(scope="session", autouse=True)
def _quiet_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning)


@pytest.fixture(scope="session")
def service(request):
    """Local env: start the demo service with a fresh seeded DB. Other envs would point to a stand."""
    if request.config.getoption("--env") != "local":
        pytest.skip("only the local env is available in the public showcase")
    srv, db_path = sut.start()
    yield srv.server_address[1], db_path
    srv.shutdown()


@pytest.fixture(scope="session")
def env(request, service) -> EnvConfig:
    port, _ = service
    config = load_env(request.config.getoption("--env"), port=port)
    sut.preflight(config.base_url)  # fail fast: network problem != test failure
    return config


@pytest.fixture(scope="session")
def db(service) -> LendingDb:
    return LendingDb(service[1])


@pytest.fixture(scope="session")
def browser(request) -> Browser:
    with sync_playwright() as pw:
        channel = request.config.getoption("--channel")
        browser = pw.chromium.launch(
            channel=None if channel == "chromium" else channel,
            headless=not request.config.getoption("--headed"),
            slow_mo=request.config.getoption("--slowmo"),
        )
        pw.selectors.set_test_id_attribute("data-test")
        yield browser
        browser.close()


# ---------------- module ----------------
@pytest.fixture(scope="module")
def session_cookie(env) -> str:
    return get_session_cookie(env)


@pytest.fixture(scope="module")
def api(env, session_cookie) -> requests.Session:
    session = requests.Session()
    session.cookies.set("session", session_cookie)
    yield session
    session.close()


@pytest.fixture(scope="module")
def auth_context(browser, env, session_cookie) -> BrowserContext:
    """Authorized browser context: cookie from the API is put into the browser, no UI login."""
    context = browser.new_context(viewport={"width": 1920, "height": 1080}, locale="ru-RU")
    context.add_cookies([{"name": "session", "value": session_cookie, "url": env.base_url}])
    context.tracing.start(screenshots=True, snapshots=True)
    yield context
    context.tracing.stop()
    context.close()


# ---------------- function ----------------
@pytest.fixture
def page(auth_context, request) -> Page:
    auth_context.tracing.start_chunk()
    page = auth_context.new_page()
    yield page
    failed = getattr(request.node, "rep_call", None) and request.node.rep_call.failed
    if failed or request.config.getoption("--tracing") == "on":
        ARTIFACTS.mkdir(exist_ok=True)
        trace = ARTIFACTS / f"{re.sub(r'[^\w.-]', '_', request.node.name)}.zip"
        auth_context.tracing.stop_chunk(path=trace)
        allure.attach.file(trace, name="playwright trace", extension="zip")
    else:
        auth_context.tracing.stop_chunk()
    page.close()


@pytest.fixture
def applications_page(page, env) -> ApplicationsPage:
    return ApplicationsPage(page, env.base_url)


@pytest.fixture
def ui_data(env, request):
    """ui_data(case) -> data of this test's case from the env config."""
    test_name = request.node.originalname
    return lambda case: env.ui_data(test_name, case)


@pytest.fixture
def api_data(env, request):
    test_name = request.node.originalname
    return lambda case: env.api_data(test_name, case)


@pytest.fixture
def application_with_status(api, env, db):
    """Factory: move an application to the given status; the original state is restored after the test."""
    snapshots = []

    def factory(status: str) -> str:
        app_uuid = db.application_with_checks(min_checks=1)
        snapshots.append(db.application_state(app_uuid))
        make_request(
            api,
            env.base_url,
            "application_update",
            expected_status=200,
            path_params={"uuid": app_uuid},
            json={"status": status},
        )
        return app_uuid

    yield factory
    for state in reversed(snapshots):
        db.restore_application_state(state)


@pytest.fixture(autouse=True)
def _allure_title_from_docstring(request):
    """Report name = first line of the docstring + case id."""
    doc = (request.node.function.__doc__ or "").strip().splitlines()
    if doc:
        case = getattr(request.node, "callspec", None)
        allure.dynamic.title(f"{doc[0]} [{case.id}]" if case else doc[0])
