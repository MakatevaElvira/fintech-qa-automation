"""SQLite storage of the demo lending back-office (system under test).

An application has several scoring checks (one-to-many), like
"order -> items" or "call -> records": UI shows applications, but the
truth for validation lives at the level of checks.
"""

from __future__ import annotations

import random
import sqlite3
import uuid
from pathlib import Path

PRODUCTS = ["PDL", "Installment", "Credit line"]
STATUSES = ["approved", "rejected", "pending"]
CHANNELS = ["web", "mobile", "partner"]
CHECK_TYPES = ["bureau", "antifraud", "income", "ai_scoring"]
AI_VERDICTS = ["low risk", "medium risk", "high risk"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY,
    uuid TEXT UNIQUE NOT NULL,
    external_id TEXT,
    client_name TEXT NOT NULL,
    product TEXT NOT NULL,
    status TEXT NOT NULL,
    channel TEXT NOT NULL,
    amount INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY,
    uuid TEXT UNIQUE NOT NULL,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    check_type TEXT NOT NULL,
    product TEXT NOT NULL,
    risk_flag INTEGER NOT NULL DEFAULT 0,
    ai_verdict TEXT
);
"""

FIRST_NAMES = ["Anna", "Ivan", "Elena", "Pavel", "Olga", "Timur", "Maria", "Denis", "Irina", "Oleg"]
LAST_NAMES = ["Smirnova", "Petrov", "Kuznetsova", "Volkov", "Sokolova", "Lebedev", "Novikova", "Morozov"]


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def seed(path: Path, applications: int = 60, seed_value: int = 42) -> None:
    """Create a fresh database with deterministic data."""
    path.unlink(missing_ok=True)
    rnd = random.Random(seed_value)
    conn = connect(path)
    conn.executescript(SCHEMA)
    for app_id in range(1, applications + 1):
        product = rnd.choice(PRODUCTS)
        conn.execute(
            "INSERT INTO applications VALUES (?,?,?,?,?,?,?,?,?)",
            (
                app_id,
                str(uuid.UUID(int=rnd.getrandbits(128))),
                # ~10% of applications came without external id (broken integration case)
                None if rnd.random() < 0.1 else f"EXT-{100000 + app_id}",
                f"{rnd.choice(FIRST_NAMES)} {rnd.choice(LAST_NAMES)}",
                product,
                rnd.choice(STATUSES),
                rnd.choice(CHANNELS),
                rnd.randrange(5_000, 500_000, 1_000),
                f"2026-10-{rnd.randint(1, 31):02d}",
            ),
        )
        # An application has 1-3 checks; usually of its own product, sometimes of a cross-sell product
        for check_type in rnd.sample(CHECK_TYPES, rnd.randint(1, 3)):
            check_product = product if rnd.random() < 0.85 else rnd.choice(PRODUCTS)
            conn.execute(
                "INSERT INTO checks (uuid, application_id, check_type, product, risk_flag, ai_verdict) "
                "VALUES (?,?,?,?,?,?)",
                (
                    str(uuid.UUID(int=rnd.getrandbits(128))),
                    app_id,
                    check_type,
                    check_product,
                    int(rnd.random() < 0.25),
                    rnd.choice(AI_VERDICTS) if check_type == "ai_scoring" else None,
                ),
            )
    conn.commit()
    conn.close()
