"""DB helper for checks on the data level (the source of truth for UI checks)."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


class LendingDb:
    def __init__(self, path: Path):
        self.path = path

    def _query(self, sql: str, params: list | tuple = ()) -> list[sqlite3.Row]:
        with closing(sqlite3.connect(self.path)) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(sql, params).fetchall()

    def _execute(self, sql: str, params: list | tuple = ()) -> None:
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(sql, params)
            conn.commit()

    @staticmethod
    def _marks(values) -> str:
        return ",".join("?" * len(values))

    def applications_without_products(self, check_uuids: list[str], products: list[str]) -> list[sqlite3.Row]:
        """Applications (found by their check UUIDs) where NONE of the checks has one of the products."""
        sql = f"""
            SELECT a.uuid, a.external_id, GROUP_CONCAT(c.product) AS products
            FROM applications a JOIN checks c ON c.application_id = a.id
            WHERE a.id IN (SELECT application_id FROM checks WHERE uuid IN ({self._marks(check_uuids)}))
            GROUP BY a.id
            HAVING SUM(c.product IN ({self._marks(products)})) = 0
        """
        return self._query(sql, [*check_uuids, *products])

    def applications_with_other_status(self, check_uuids: list[str], statuses: list[str]) -> list[sqlite3.Row]:
        sql = f"""
            SELECT DISTINCT a.uuid, a.status
            FROM applications a JOIN checks c ON c.application_id = a.id
            WHERE c.uuid IN ({self._marks(check_uuids)}) AND a.status NOT IN ({self._marks(statuses)})
        """
        return self._query(sql, [*check_uuids, *statuses])

    def applications_with_risk_flags(self, check_uuids: list[str]) -> list[sqlite3.Row]:
        """Applications that have at least one flagged check."""
        sql = f"""
            SELECT a.uuid, SUM(c.risk_flag) AS flags
            FROM applications a JOIN checks c ON c.application_id = a.id
            WHERE a.id IN (SELECT application_id FROM checks WHERE uuid IN ({self._marks(check_uuids)}))
            GROUP BY a.id HAVING SUM(c.risk_flag) > 0
        """
        return self._query(sql, check_uuids)

    def count_applications(self, where: str = "1=1", params: tuple = ()) -> int:
        return self._query(f"SELECT COUNT(*) FROM applications WHERE {where}", params)[0][0]

    def application_state(self, app_uuid: str) -> dict:
        app = self._query("SELECT id, status FROM applications WHERE uuid = ?", (app_uuid,))[0]
        flags = self._query("SELECT id, risk_flag FROM checks WHERE application_id = ? ORDER BY id", (app["id"],))
        return {"id": app["id"], "status": app["status"], "flags": {r["id"]: r["risk_flag"] for r in flags}}

    def restore_application_state(self, state: dict) -> None:
        self._execute("UPDATE applications SET status = ? WHERE id = ?", (state["status"], state["id"]))
        for check_id, flag in state["flags"].items():
            self._execute("UPDATE checks SET risk_flag = ? WHERE id = ?", (flag, check_id))

    def application_with_checks(self, min_checks: int) -> str:
        rows = self._query(
            "SELECT a.uuid FROM applications a JOIN checks c ON c.application_id = a.id "
            "GROUP BY a.id HAVING COUNT(c.id) >= ? ORDER BY a.id LIMIT 1",
            (min_checks,),
        )
        return rows[0]["uuid"]
