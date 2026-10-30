"""
Repository handling all database CRUD operations, transactions, and entity mapping.
Ensures Decimal amounts and dates are preserved with zero float corruption.
"""

from __future__ import annotations
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

from backend.models import (
    ConfirmedAllocation,
    EvidenceItem,
    ImportBatch,
    ImportRowError,
    Invoice,
    MatchSuggestion,
    Payment,
    ReviewDecision,
)
from backend.auth import UserAccount
from backend.storage.db import DatabaseManager


class ReconciliationRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def save_import_batch(
        self,
        batch: ImportBatch,
        records: List[Invoice | Payment],
        errors: List[ImportRowError],
    ) -> None:
        """Atomic insert of import batch header, valid records, and error rows."""
        with self.db.get_connection() as conn:
            # Insert Batch
            conn.execute(
                """
                INSERT INTO import_batches 
                (batch_id, file_name, file_type, row_count, valid_count, error_count, warning_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch.batch_id,
                    batch.file_name,
                    batch.file_type,
                    batch.row_count,
                    batch.valid_count,
                    batch.error_count,
                    batch.warning_count,
                    batch.created_at.isoformat(),
                ),
            )

            # Insert Errors
            for err in errors:
                conn.execute(
                    """
                    INSERT INTO import_errors 
                    (batch_id, row_index, field_name, error_type, message, raw_data, is_warning)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        err.batch_id,
                        err.row_index,
                        err.field_name,
                        err.error_type,
                        err.message,
                        json.dumps(err.raw_data),
                        1 if err.is_warning else 0,
                    ),
                )

            # Insert Valid Records
            if batch.file_type == "INVOICE":
                for inv in records:  # type: ignore
                    conn.execute(
                        """
                        INSERT INTO invoices 
                        (invoice_id, batch_id, row_index, customer_id, customer_name, customer_name_normalized,
                         amount, issue_date, due_date, reference, note, raw_data, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            inv.invoice_id,
                            inv.batch_id,
                            inv.row_index,
                            inv.customer_id,
                            inv.customer_name,
                            inv.customer_name_normalized,
                            str(inv.amount),
                            inv.issue_date.isoformat(),
                            inv.due_date.isoformat() if inv.due_date else None,
                            inv.reference,
                            inv.note,
                            json.dumps(inv.raw_data),
                            inv.created_at.isoformat(),
                        ),
                    )
            elif batch.file_type == "PAYMENT":
                for pay in records:  # type: ignore
                    conn.execute(
                        """
                        INSERT INTO payments 
                        (payment_id, batch_id, row_index, customer_id, customer_name, customer_name_normalized,
                         amount, payment_date, reference, payment_method, note, raw_data, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            pay.payment_id,
                            pay.batch_id,
                            pay.row_index,
                            pay.customer_id,
                            pay.customer_name,
                            pay.customer_name_normalized,
                            str(pay.amount),
                            pay.payment_date.isoformat(),
                            pay.reference,
                            pay.payment_method,
                            pay.note,
                            json.dumps(pay.raw_data),
                            pay.created_at.isoformat(),
                        ),
                    )

            conn.commit()

    def get_existing_invoice_ids(self) -> Set[str]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT invoice_id FROM invoices;")
            return {row["invoice_id"] for row in cursor.fetchall()}

    def get_existing_payment_ids(self) -> Set[str]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT payment_id FROM payments;")
            return {row["payment_id"] for row in cursor.fetchall()}

    def get_invoices(self) -> List[Invoice]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM invoices ORDER BY issue_date ASC, invoice_id ASC;")
            rows = cursor.fetchall()
            return [
                Invoice(
                    invoice_id=row["invoice_id"],
                    batch_id=row["batch_id"],
                    row_index=row["row_index"],
                    customer_id=row["customer_id"],
                    customer_name=row["customer_name"],
                    customer_name_normalized=row["customer_name_normalized"],
                    amount=Decimal(row["amount"]),
                    issue_date=date.fromisoformat(row["issue_date"]),
                    due_date=date.fromisoformat(row["due_date"]) if row["due_date"] else None,
                    reference=row["reference"],
                    note=row["note"],
                    raw_data=json.loads(row["raw_data"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]

    def get_invoice_by_id(self, invoice_id: str) -> Optional[Invoice]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM invoices WHERE invoice_id = ?;", (invoice_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return Invoice(
                invoice_id=row["invoice_id"],
                batch_id=row["batch_id"],
                row_index=row["row_index"],
                customer_id=row["customer_id"],
                customer_name=row["customer_name"],
                customer_name_normalized=row["customer_name_normalized"],
                amount=Decimal(row["amount"]),
                issue_date=date.fromisoformat(row["issue_date"]),
                due_date=date.fromisoformat(row["due_date"]) if row["due_date"] else None,
                reference=row["reference"],
                note=row["note"],
                raw_data=json.loads(row["raw_data"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def get_payments(self) -> List[Payment]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM payments ORDER BY payment_date ASC, payment_id ASC;")
            rows = cursor.fetchall()
            return [
                Payment(
                    payment_id=row["payment_id"],
                    batch_id=row["batch_id"],
                    row_index=row["row_index"],
                    customer_id=row["customer_id"],
                    customer_name=row["customer_name"],
                    customer_name_normalized=row["customer_name_normalized"],
                    amount=Decimal(row["amount"]),
                    payment_date=date.fromisoformat(row["payment_date"]),
                    reference=row["reference"],
                    payment_method=row["payment_method"],
                    note=row["note"],
                    raw_data=json.loads(row["raw_data"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]

    def get_payment_by_id(self, payment_id: str) -> Optional[Payment]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM payments WHERE payment_id = ?;", (payment_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return Payment(
                payment_id=row["payment_id"],
                batch_id=row["batch_id"],
                row_index=row["row_index"],
                customer_id=row["customer_id"],
                customer_name=row["customer_name"],
                customer_name_normalized=row["customer_name_normalized"],
                amount=Decimal(row["amount"]),
                payment_date=date.fromisoformat(row["payment_date"]),
                reference=row["reference"],
                payment_method=row["payment_method"],
                note=row["note"],
                raw_data=json.loads(row["raw_data"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def get_import_batches(self) -> List[ImportBatch]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM import_batches ORDER BY created_at DESC;")
            return [
                ImportBatch(
                    batch_id=r["batch_id"],
                    file_name=r["file_name"],
                    file_type=r["file_type"],
                    row_count=r["row_count"],
                    valid_count=r["valid_count"],
                    error_count=r["error_count"],
                    warning_count=r["warning_count"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
                for r in cursor.fetchall()
            ]

    def get_import_errors(self, batch_id: Optional[str] = None) -> List[ImportRowError]:
        with self.db.get_connection() as conn:
            query = "SELECT * FROM import_errors"
            params = ()
            if batch_id:
                query += " WHERE batch_id = ?"
                params = (batch_id,)
            query += " ORDER BY batch_id, row_index ASC;"
            cursor = conn.execute(query, params)
            return [
                ImportRowError(
                    error_id=r["error_id"],
                    batch_id=r["batch_id"],
                    row_index=r["row_index"],
                    field_name=r["field_name"],
                    error_type=r["error_type"],
                    message=r["message"],
                    raw_data=json.loads(r["raw_data"]),
                    is_warning=bool(r["is_warning"]),
                )
                for r in cursor.fetchall()
            ]

    def save_suggestions(self, suggestions: List[MatchSuggestion]) -> None:
        with self.db.get_connection() as conn:
            for s in suggestions:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO match_suggestions
                    (suggestion_id, invoice_id, payment_id, score, confidence_tier, is_ambiguous,
                     amount_mismatch, explanation, evidence_json, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        s.suggestion_id,
                        s.invoice_id,
                        s.payment_id,
                        s.score,
                        s.confidence_tier,
                        1 if s.is_ambiguous else 0,
                        1 if s.amount_mismatch else 0,
                        s.explanation,
                        s.evidence_json(),
                        s.status,
                        s.created_at.isoformat(),
                    ),
                )
            conn.commit()

    def get_suggestions(
        self, status: Optional[str] = None, tier: Optional[str] = None
    ) -> List[MatchSuggestion]:
        with self.db.get_connection() as conn:
            query = "SELECT * FROM match_suggestions WHERE 1=1"
            params = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if tier:
                query += " AND confidence_tier = ?"
                params.append(tier)
            query += " ORDER BY score DESC, created_at DESC;"

            cursor = conn.execute(query, tuple(params))
            results: List[MatchSuggestion] = []
            for r in cursor.fetchall():
                ev_list = [
                    EvidenceItem(
                        rule_name=e["rule_name"],
                        score=e["score"],
                        max_score=e["max_score"],
                        description=e["description"],
                        details=e.get("details", {}),
                    )
                    for e in json.loads(r["evidence_json"])
                ]
                results.append(
                    MatchSuggestion(
                        suggestion_id=r["suggestion_id"],
                        invoice_id=r["invoice_id"],
                        payment_id=r["payment_id"],
                        score=r["score"],
                        confidence_tier=r["confidence_tier"],
                        is_ambiguous=bool(r["is_ambiguous"]),
                        amount_mismatch=bool(r["amount_mismatch"]),
                        explanation=r["explanation"],
                        evidence=ev_list,
                        status=r["status"],
                        created_at=datetime.fromisoformat(r["created_at"]),
                    )
                )
            return results

    def get_suggestion_by_id(self, suggestion_id: str) -> Optional[MatchSuggestion]:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM match_suggestions WHERE suggestion_id = ?;", (suggestion_id,)
            )
            r = cursor.fetchone()
            if not r:
                return None
            ev_list = [
                EvidenceItem(
                    rule_name=e["rule_name"],
                    score=e["score"],
                    max_score=e["max_score"],
                    description=e["description"],
                    details=e.get("details", {}),
                )
                for e in json.loads(r["evidence_json"])
            ]
            return MatchSuggestion(
                suggestion_id=r["suggestion_id"],
                invoice_id=r["invoice_id"],
                payment_id=r["payment_id"],
                score=r["score"],
                confidence_tier=r["confidence_tier"],
                is_ambiguous=bool(r["is_ambiguous"]),
                amount_mismatch=bool(r["amount_mismatch"]),
                explanation=r["explanation"],
                evidence=ev_list,
                status=r["status"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )

    def update_suggestion_status(self, suggestion_id: str, status: str) -> None:
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE match_suggestions SET status = ? WHERE suggestion_id = ?;",
                (status, suggestion_id),
            )
            conn.commit()

    def save_review_decision(self, decision: ReviewDecision) -> None:
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO review_decisions
                (decision_id, suggestion_id, invoice_id, payment_id, action, amount, reviewer, notes, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.decision_id,
                    decision.suggestion_id,
                    decision.invoice_id,
                    decision.payment_id,
                    decision.action,
                    str(decision.amount) if decision.amount is not None else None,
                    decision.reviewer,
                    decision.notes,
                    decision.timestamp.isoformat(),
                ),
            )
            conn.commit()

    def get_review_decisions(
        self, invoice_id: Optional[str] = None, payment_id: Optional[str] = None
    ) -> List[ReviewDecision]:
        with self.db.get_connection() as conn:
            query = "SELECT * FROM review_decisions WHERE 1=1"
            params = []
            if invoice_id:
                query += " AND invoice_id = ?"
                params.append(invoice_id)
            if payment_id:
                query += " AND payment_id = ?"
                params.append(payment_id)
            query += " ORDER BY timestamp ASC;"
            cursor = conn.execute(query, tuple(params))
            return [
                ReviewDecision(
                    decision_id=r["decision_id"],
                    suggestion_id=r["suggestion_id"],
                    invoice_id=r["invoice_id"],
                    payment_id=r["payment_id"],
                    action=r["action"],
                    amount=Decimal(r["amount"]) if r["amount"] is not None else None,
                    reviewer=r["reviewer"],
                    notes=r["notes"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                )
                for r in cursor.fetchall()
            ]

    def save_allocation(self, allocation: ConfirmedAllocation) -> None:
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO confirmed_allocations
                (allocation_id, invoice_id, payment_id, allocated_amount, confirmed_at, reviewer, decision_id, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    allocation.allocation_id,
                    allocation.invoice_id,
                    allocation.payment_id,
                    str(allocation.allocated_amount),
                    allocation.confirmed_at.isoformat(),
                    allocation.reviewer,
                    allocation.decision_id,
                    allocation.notes,
                ),
            )
            conn.commit()

    def delete_allocation(self, allocation_id: str) -> None:
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM confirmed_allocations WHERE allocation_id = ?;", (allocation_id,)
            )
            conn.commit()

    def get_all_allocations(self) -> List[ConfirmedAllocation]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM confirmed_allocations ORDER BY confirmed_at ASC;")
            return [
                ConfirmedAllocation(
                    allocation_id=r["allocation_id"],
                    invoice_id=r["invoice_id"],
                    payment_id=r["payment_id"],
                    allocated_amount=Decimal(r["allocated_amount"]),
                    confirmed_at=datetime.fromisoformat(r["confirmed_at"]),
                    reviewer=r["reviewer"],
                    decision_id=r["decision_id"],
                    notes=r["notes"],
                )
                for r in cursor.fetchall()
            ]

    def get_allocations_for_payment(self, payment_id: str) -> List[ConfirmedAllocation]:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM confirmed_allocations WHERE payment_id = ? ORDER BY confirmed_at ASC;",
                (payment_id,),
            )
            return [
                ConfirmedAllocation(
                    allocation_id=r["allocation_id"],
                    invoice_id=r["invoice_id"],
                    payment_id=r["payment_id"],
                    allocated_amount=Decimal(r["allocated_amount"]),
                    confirmed_at=datetime.fromisoformat(r["confirmed_at"]),
                    reviewer=r["reviewer"],
                    decision_id=r["decision_id"],
                    notes=r["notes"],
                )
                for r in cursor.fetchall()
            ]

    def get_allocations_for_invoice(self, invoice_id: str) -> List[ConfirmedAllocation]:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM confirmed_allocations WHERE invoice_id = ? ORDER BY confirmed_at ASC;",
                (invoice_id,),
            )
            return [
                ConfirmedAllocation(
                    allocation_id=r["allocation_id"],
                    invoice_id=r["invoice_id"],
                    payment_id=r["payment_id"],
                    allocated_amount=Decimal(r["allocated_amount"]),
                    confirmed_at=datetime.fromisoformat(r["confirmed_at"]),
                    reviewer=r["reviewer"],
                    decision_id=r["decision_id"],
                    notes=r["notes"],
                )
                for r in cursor.fetchall()
            ]

    # -------------------------------------------------------------
    # User and Business Authentication Repository Methods
    # -------------------------------------------------------------

    def create_user(self, user: UserAccount) -> None:
        """Insert a newly registered user account into the database."""
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users 
                (user_id, email, mobile, business_name, owner_name, password_hash, password_salt, role, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.user_id,
                    user.email,
                    user.mobile,
                    user.business_name,
                    user.owner_name,
                    user.password_hash,
                    user.password_salt,
                    user.role,
                    user.status,
                    user.created_at.isoformat(),
                ),
            )
            conn.commit()

    def get_user_by_email(self, email: str) -> Optional[UserAccount]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?);", (email.strip(),))
            r = cursor.fetchone()
            if not r:
                return None
            return UserAccount(
                user_id=r["user_id"],
                email=r["email"],
                mobile=r["mobile"],
                business_name=r["business_name"],
                owner_name=r["owner_name"],
                password_hash=r["password_hash"],
                password_salt=r["password_salt"],
                role=r["role"],
                status=r["status"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )

    def get_user_by_mobile(self, mobile: str) -> Optional[UserAccount]:
        clean_mobile = mobile.strip().replace(" ", "").replace("-", "")
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE mobile = ?;", (clean_mobile,))
            r = cursor.fetchone()
            if not r:
                return None
            return UserAccount(
                user_id=r["user_id"],
                email=r["email"],
                mobile=r["mobile"],
                business_name=r["business_name"],
                owner_name=r["owner_name"],
                password_hash=r["password_hash"],
                password_salt=r["password_salt"],
                role=r["role"],
                status=r["status"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )

    def get_user_by_id(self, user_id: str) -> Optional[UserAccount]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE user_id = ?;", (user_id,))
            r = cursor.fetchone()
            if not r:
                return None
            return UserAccount(
                user_id=r["user_id"],
                email=r["email"],
                mobile=r["mobile"],
                business_name=r["business_name"],
                owner_name=r["owner_name"],
                password_hash=r["password_hash"],
                password_salt=r["password_salt"],
                role=r["role"],
                status=r["status"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )

    def get_all_users(self, role: Optional[str] = None) -> List[UserAccount]:
        with self.db.get_connection() as conn:
            query = "SELECT * FROM users"
            params = []
            if role:
                query += " WHERE role = ?"
                params.append(role.lower())
            query += " ORDER BY created_at DESC;"
            cursor = conn.execute(query, tuple(params))
            return [
                UserAccount(
                    user_id=r["user_id"],
                    email=r["email"],
                    mobile=r["mobile"],
                    business_name=r["business_name"],
                    owner_name=r["owner_name"],
                    password_hash=r["password_hash"],
                    password_salt=r["password_salt"],
                    role=r["role"],
                    status=r["status"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
                for r in cursor.fetchall()
            ]

    def update_user_status(self, user_id: str, status: str) -> None:
        with self.db.get_connection() as conn:
            conn.execute("UPDATE users SET status = ? WHERE user_id = ?;", (status, user_id))
            conn.commit()
