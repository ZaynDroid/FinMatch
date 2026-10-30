"""
SQLite database connection and schema initialization.
Ensures foreign keys and strict schemas.
"""

from __future__ import annotations
import sqlite3
from typing import Optional

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS import_batches (
    batch_id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL, -- 'INVOICE' or 'PAYMENT'
    row_count INTEGER NOT NULL,
    valid_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    warning_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL REFERENCES import_batches(batch_id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    field_name TEXT,
    error_type TEXT NOT NULL,
    message TEXT NOT NULL,
    raw_data TEXT NOT NULL,
    is_warning INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES import_batches(batch_id),
    row_index INTEGER NOT NULL,
    customer_id TEXT,
    customer_name TEXT NOT NULL,
    customer_name_normalized TEXT NOT NULL,
    amount TEXT NOT NULL, -- Exact Decimal string e.g. '12500.00'
    issue_date TEXT NOT NULL, -- 'YYYY-MM-DD'
    due_date TEXT,
    reference TEXT,
    note TEXT,
    raw_data TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES import_batches(batch_id),
    row_index INTEGER NOT NULL,
    customer_id TEXT,
    customer_name TEXT,
    customer_name_normalized TEXT,
    amount TEXT NOT NULL, -- Exact Decimal string e.g. '12500.00'
    payment_date TEXT NOT NULL, -- 'YYYY-MM-DD'
    reference TEXT,
    payment_method TEXT,
    note TEXT,
    raw_data TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_suggestions (
    suggestion_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(invoice_id),
    payment_id TEXT NOT NULL REFERENCES payments(payment_id),
    score REAL NOT NULL,
    confidence_tier TEXT NOT NULL,
    is_ambiguous INTEGER NOT NULL,
    amount_mismatch INTEGER NOT NULL,
    explanation TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_decisions (
    decision_id TEXT PRIMARY KEY,
    suggestion_id TEXT,
    invoice_id TEXT NOT NULL REFERENCES invoices(invoice_id),
    payment_id TEXT NOT NULL REFERENCES payments(payment_id),
    action TEXT NOT NULL, -- 'CONFIRM', 'REJECT', 'MANUAL_ALLOCATION', 'UNALLOCATE'
    amount TEXT, -- Decimal string
    reviewer TEXT NOT NULL,
    notes TEXT,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS confirmed_allocations (
    allocation_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(invoice_id),
    payment_id TEXT NOT NULL REFERENCES payments(payment_id),
    allocated_amount TEXT NOT NULL, -- Exact Decimal string
    confirmed_at TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    decision_id TEXT REFERENCES review_decisions(decision_id),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    mobile TEXT UNIQUE NOT NULL,
    business_name TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user', -- 'user' or 'admin'
    status TEXT NOT NULL DEFAULT 'Active', -- 'Active' or 'Disabled'
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_mobile ON users(mobile);
CREATE INDEX IF NOT EXISTS idx_invoices_batch ON invoices(batch_id);
CREATE INDEX IF NOT EXISTS idx_payments_batch ON payments(batch_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_inv ON match_suggestions(invoice_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_pay ON match_suggestions(payment_id);
CREATE INDEX IF NOT EXISTS idx_allocations_inv ON confirmed_allocations(invoice_id);
CREATE INDEX IF NOT EXISTS idx_allocations_pay ON confirmed_allocations(payment_id);
"""


class DatabaseManager:
    """Manages SQLite database connections and table lifecycle."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
            self._mem_conn.execute("PRAGMA foreign_keys = ON;")
        else:
            self._mem_conn = None
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        conn = self.get_connection()
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        self._seed_default_users(conn)

    def _seed_default_users(self, conn: sqlite3.Connection) -> None:
        """Seed default admin and demo user accounts if table is empty."""
        cursor = conn.execute("SELECT COUNT(*) AS cnt FROM users;")
        if cursor.fetchone()["cnt"] > 0:
            return

        from backend.auth import hash_password, _utc_now

        default_accounts = [
            (
                "ADM-DEMO01",
                "admin@finmatch.demo",
                "9999999999",
                "FinMatch Administration",
                "Super Administrator",
                "admin123",
                "admin",
            ),
            (
                "USR-DEMO01",
                "user@finmatch.demo",
                "9876543210",
                "Sharma Traders",
                "Rajesh Sharma",
                "demo123",
                "user",
            ),
            (
                "USR-DEMO02",
                "gupta@finmatch.demo",
                "9811100002",
                "Gupta Hardware",
                "Anil Gupta",
                "gupta123",
                "user",
            ),
            (
                "USR-DEMO03",
                "verma@finmatch.demo",
                "9811100003",
                "Verma Medical Hall",
                "Sunita Verma",
                "verma123",
                "user",
            ),
            (
                "USR-DEMO04",
                "rawat@finmatch.demo",
                "9811100004",
                "Rawat Wholesale",
                "Mohan Rawat",
                "rawat123",
                "user",
            ),
        ]

        now_str = _utc_now().isoformat()
        for uid, email, mobile, bname, oname, pwd, role in default_accounts:
            pwd_hash, salt = hash_password(pwd)
            conn.execute(
                """
                INSERT INTO users 
                (user_id, email, mobile, business_name, owner_name, password_hash, password_salt, role, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (uid, email, mobile, bname, oname, pwd_hash, salt, role, "Active", now_str),
            )
        conn.commit()

    def reset_db(self) -> None:
        """Clear all tables (useful for tests and resetting demo state)."""
        conn = self.get_connection()
        tables = [
            "confirmed_allocations",
            "review_decisions",
            "match_suggestions",
            "payments",
            "invoices",
            "import_errors",
            "import_batches",
            "users",
        ]
        for t in tables:
            conn.execute(f"DROP TABLE IF EXISTS {t};")
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        self._seed_default_users(conn)
