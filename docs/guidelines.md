# Guidelines for autotests

## Page Object
- Selectors are class constants in `UPPER_CASE`, preferably `data-test` attributes.
- No `assert` and no `sleep` inside Page Objects; waits via `expect(...)` and the table response.
- Complex checks return `(ok, message)`; the test makes the `assert`.

## Tests
- One behaviour per test; the docstring's first line is the test title in the report.
- Test data comes from `configs/<env>.json`.
- UI results are double-checked in the database.
- Assert messages contain context: row index, UUIDs, actual values.
- Tests that change data restore the original state in teardown.

## Before a PR
`ruff check . && ruff format .`, then `pytest -n 2 --dist loadgroup`.
