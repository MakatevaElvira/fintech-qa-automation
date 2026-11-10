# Fintech QA Automation

[![tests](https://github.com/MakatevaElvira/fintech-qa-automation/actions/workflows/tests.yml/badge.svg)](https://github.com/MakatevaElvira/fintech-qa-automation/actions/workflows/tests.yml)

A portfolio project showing my approach to test automation:
**UI tests of list filters with double validation UI + database**, API tests with contract checks,
and a framework structure that scales (configs per environment, data factories, CI, reports).

The system under test is a small **educational lending back-office** included in the repo (`app/`):
a list of loan applications with filters, where each application has several scoring checks.

**Stack:** Python 3.13 · uv · pytest · pytest-xdist · Playwright (sync) · requests · pydantic 2 · Allure · ruff · pre-commit · GitHub Actions

---

## What is tested

### UI — filters of the applications list (`tests/ui`)
| Test | Idea |
|---|---|
| Product filter | UI shows only matching applications; the first valid row is expanded to check products of its checks; then the **DB** confirms there is no application where none of the checks has the selected product (checked by UUIDs of all checks of every row) |
| Status filter | UI labels + statuses in the DB |
| Risk flags filter | "with" / "without" flags compared with the DB |
| Amount range | every amount in range, counter equals `COUNT(*)` in the DB |
| Filter state | change value, clear, "select all" = no filter, two filters are independent, state persists after reload |
| Async AI block | the scoring block goes `loading -> ready` and shows the verdict from the API |

### API (`tests/api`)
- One wrapper `make_request(...)`: endpoint from the registry, expected status, negative flag, schema validation by pydantic model.
- Positive and negative cases as `parametrize` by `case` + `match`: list, filters, 401 without session, wrong credentials, validation 422, 404, conflict 409.
- Card of an application compared with the DB; invalid updates must not change the state.
- Data factory: an application is moved to another status and **restored after the test**.

## How the framework is built

```
app/                 demo service under test (stdlib HTTP + SQLite, seeded deterministically)
configs/local.json   env config: common / auth / ui cases / api cases
helpers/
  auth.py            authorization without UI: API login -> session cookie
  http_client.py     make_request: status check, pydantic validation, Allure attachments
  db.py              DB checks (the source of truth for UI assertions)
  config.py          env loading, ui_data / api_data
pages/
  base_page.py       open/reload with waiting for the exact table response + loader
  applications_page.py  Page Object: UPPER_CASE selectors, no asserts/sleeps, checks return (ok, message)
  blocks/            reusable blocks: filter dropdown, table with async checks block
  api/               endpoint registry and pydantic response models
  data/              dataclasses of test data
tests/api, tests/ui
docs/guidelines.md   rules for writing autotests in this project
```

**Fixture scopes by cost:** service, config and browser — `session`; authorized API session and browser context — `module`
(login once per module, cookie from the API is put into the browser); page — `function`.
Playwright trace is saved only for failed tests (`--tracing on` to keep always). Test titles in Allure come from docstrings + case id.

**CI** (GitHub Actions): lint → preflight check that the service answers → tests in parallel
(`-n N --dist loadgroup`, number of workers is chosen at manual run) → Allure results, HTML report and traces as artifacts.
UI regression also runs on schedule on weekdays.

## Run locally

```bash
uv sync
uv run playwright install chrome     # tests run in Google Chrome by default
uv run pytest                          # all tests
uv run pytest -m ui --headed --slowmo 300
uv run pytest --channel chromium       # bundled Chromium instead of Chrome
uv run pytest -n 2 --dist loadgroup --alluredir=allure-results && allure serve allure-results
uv run python -m app.server            # open http://127.0.0.1:8080/applications (needs a session cookie)
```

## How AI was used
This project was built together with an AI assistant (Claude) as a pair programmer.

## Contacts
Elvira Mak — QA Automation Engineer (fintech, AI-powered systems) · Telegram [@elvira_mak](https://t.me/elvira_mak)
