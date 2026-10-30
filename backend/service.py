"""
Unified Reconciliation Service facade.
Provides a clean, documented, high-level API for Python scripts, CLI, or UI dashboards (e.g. Streamlit).
"""

from __future__ import annotations
import os
from decimal import Decimal
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd

from backend.engine import ReconciliationEngine
from backend.importer import CSVImporter
from backend.matcher import MatchingConfig, MatchingEngine
from backend.models import (
    ConfirmedAllocation,
    ImportBatch,
    ImportRowError,
    Invoice,
    InvoiceBalance,
    MatchSuggestion,
    Payment,
    PaymentBalance,
    ReviewDecision,
    UnresolvedWorkSummary,
)
from backend.reporting import ReconciliationReporter
from backend.storage.db import DatabaseManager
from backend.storage.repository import ReconciliationRepository
from backend.auth import AuthManager, UserAccount, verify_password


class ReconciliationService:
    """
    Main entry point for all reconciliation workflows.
    Encapsulates ingestion, deterministic matching, human review, allocation,
    audit history, balance tracking, and reporting.
    """

    def __init__(self, db_path: str = "finmatch.db"):
        self.db_manager = DatabaseManager(db_path)
        self.repo = ReconciliationRepository(self.db_manager)
        self.engine = ReconciliationEngine(self.repo)
        self.reporter = ReconciliationReporter(self.repo, self.engine)

    def import_invoices_csv(
        self,
        source: Union[str, StringIO, bytes],
        file_name: str = "invoices.csv",
    ) -> Tuple[ImportBatch, List[Invoice], List[ImportRowError]]:
        """
        Import and validate an invoices CSV file.
        Persists batch information, valid invoices, and row errors into SQLite.
        """
        existing_ids = self.repo.get_existing_invoice_ids()
        batch, valid_records, errors = CSVImporter.import_invoices(
            source=source,
            file_name=file_name,
            existing_invoice_ids=existing_ids,
        )
        self.repo.save_import_batch(batch, valid_records, errors)
        return batch, valid_records, errors

    def import_payments_csv(
        self,
        source: Union[str, StringIO, bytes],
        file_name: str = "payments.csv",
    ) -> Tuple[ImportBatch, List[Payment], List[ImportRowError]]:
        """
        Import and validate a payments CSV file.
        Persists batch information, valid payments, and row errors into SQLite.
        """
        existing_ids = self.repo.get_existing_payment_ids()
        batch, valid_records, errors = CSVImporter.import_payments(
            source=source,
            file_name=file_name,
            existing_payment_ids=existing_ids,
        )
        self.repo.save_import_batch(batch, valid_records, errors)
        return batch, valid_records, errors

    def get_import_summary(self) -> Dict[str, Any]:
        """
        Retrieve a summary of all imported batches, total records, and errors.
        """
        batches = self.repo.get_import_batches()
        errors = self.repo.get_import_errors()
        return {
            "batches": [
                {
                    "batch_id": b.batch_id,
                    "file_name": b.file_name,
                    "file_type": b.file_type,
                    "row_count": b.row_count,
                    "valid_count": b.valid_count,
                    "error_count": b.error_count,
                    "warning_count": b.warning_count,
                    "created_at": b.created_at.isoformat(),
                }
                for b in batches
            ],
            "total_batches": len(batches),
            "total_errors": len([e for e in errors if not e.is_warning]),
            "total_warnings": len([e for e in errors if e.is_warning]),
        }

    def get_import_errors(self, batch_id: Optional[str] = None) -> List[ImportRowError]:
        """Retrieve row-level import errors and warnings."""
        return self.repo.get_import_errors(batch_id=batch_id)

    def generate_suggestions(
        self, config: Optional[MatchingConfig] = None
    ) -> List[MatchSuggestion]:
        """
        Run the deterministic evidence engine across all active invoices and payments.
        Saves suggestions into database and returns them.
        """
        matcher = MatchingEngine(config=config)
        invoices = self.repo.get_invoices()
        payments = self.repo.get_payments()

        # Retrieve already fully allocated items to avoid generating redundant suggestions
        allocations = self.repo.get_all_allocations()
        
        # Payment allocation sums
        pay_sums: Dict[str, Decimal] = {}
        for a in allocations:
            pay_sums[a.payment_id] = pay_sums.get(a.payment_id, Decimal("0.00")) + a.allocated_amount
        
        fully_allocated_payments = {
            p.payment_id for p in payments if pay_sums.get(p.payment_id, Decimal("0.00")) >= p.amount
        }

        # Invoice allocation sums
        inv_sums: Dict[str, Decimal] = {}
        for a in allocations:
            inv_sums[a.invoice_id] = inv_sums.get(a.invoice_id, Decimal("0.00")) + a.allocated_amount
        
        fully_paid_invoices = {
            i.invoice_id for i in invoices if inv_sums.get(i.invoice_id, Decimal("0.00")) >= i.amount
        }

        suggestions = matcher.generate_suggestions(
            invoices=invoices,
            payments=payments,
            confirmed_allocated_payment_ids=fully_allocated_payments,
            confirmed_allocated_invoice_ids=fully_paid_invoices,
        )
        self.repo.save_suggestions(suggestions)
        return suggestions

    def get_suggestions(
        self, status: Optional[str] = None, tier: Optional[str] = None
    ) -> List[MatchSuggestion]:
        """Retrieve match suggestions filtered by status or confidence tier."""
        return self.repo.get_suggestions(status=status, tier=tier)

    def confirm_match(
        self,
        suggestion_id: str,
        reviewer: str = "FINANCE_USER",
        allocation_amount: Optional[Decimal] = None,
        notes: Optional[str] = None,
    ) -> ConfirmedAllocation:
        """
        Confirm a match suggestion, creating an allocation and immutable audit entry.
        """
        return self.engine.confirm_suggestion(
            suggestion_id=suggestion_id,
            reviewer=reviewer,
            allocation_amount=allocation_amount,
            notes=notes,
        )

    def reject_match(
        self,
        suggestion_id: str,
        reviewer: str = "FINANCE_USER",
        notes: Optional[str] = None,
    ) -> ReviewDecision:
        """
        Reject a match suggestion without allocating funds.
        """
        return self.engine.reject_suggestion(
            suggestion_id=suggestion_id,
            reviewer=reviewer,
            notes=notes,
        )

    def manual_assign(
        self,
        invoice_id: str,
        payment_id: str,
        amount: Decimal,
        reviewer: str = "FINANCE_USER",
        notes: Optional[str] = None,
    ) -> ConfirmedAllocation:
        """
        Manually assign funds from a payment to an invoice with explicit amount.
        """
        return self.engine.manual_allocate(
            invoice_id=invoice_id,
            payment_id=payment_id,
            amount=amount,
            reviewer=reviewer,
            notes=notes,
        )

    def get_balances(self) -> Dict[str, Any]:
        """
        Calculate total invoice amounts, total payments, confirmed paid amounts,
        outstanding unpaid invoice balances, and unallocated payment balances.
        """
        inv_balances, pay_balances = self.engine.get_all_balances()
        total_invoiced = sum((b.total_amount for b in inv_balances), Decimal("0.00"))
        total_allocated_inv = sum((b.allocated_amount for b in inv_balances), Decimal("0.00"))
        total_outstanding_inv = sum((b.outstanding_balance for b in inv_balances), Decimal("0.00"))

        total_received = sum((b.total_amount for b in pay_balances), Decimal("0.00"))
        total_allocated_pay = sum((b.allocated_amount for b in pay_balances), Decimal("0.00"))
        total_unallocated_pay = sum((b.unallocated_amount for b in pay_balances), Decimal("0.00"))

        return {
            "invoices": {
                "total_invoiced": str(total_invoiced),
                "total_settled": str(total_allocated_inv),
                "total_outstanding": str(total_outstanding_inv),
                "count": len(inv_balances),
                "details": [
                    {
                        "invoice_id": b.invoice.invoice_id,
                        "customer_name": b.invoice.customer_name,
                        "total_amount": str(b.total_amount),
                        "allocated_amount": str(b.allocated_amount),
                        "outstanding_balance": str(b.outstanding_balance),
                        "status": b.status,
                    }
                    for b in inv_balances
                ],
            },
            "payments": {
                "total_received": str(total_received),
                "total_allocated": str(total_allocated_pay),
                "total_unallocated": str(total_unallocated_pay),
                "count": len(pay_balances),
                "details": [
                    {
                        "payment_id": b.payment.payment_id,
                        "customer_name": b.payment.customer_name,
                        "total_amount": str(b.total_amount),
                        "allocated_amount": str(b.allocated_amount),
                        "unallocated_amount": str(b.unallocated_amount),
                        "status": b.status,
                    }
                    for b in pay_balances
                ],
            },
        }

    def get_unresolved_work(self) -> Dict[str, Any]:
        """
        Retrieve structured buckets of unresolved items:
        - Unmatched invoices
        - Unallocated payments
        - Ambiguous candidates
        - Amount mismatches
        - Row-level import errors
        """
        summary = self.engine.get_unresolved_work()
        return {
            "unmatched_invoices_count": len(summary.unmatched_invoices),
            "unallocated_payments_count": len(summary.unallocated_payments),
            "ambiguous_suggestions_count": len(summary.ambiguous_suggestions),
            "amount_mismatches_count": len(summary.amount_mismatches),
            "import_errors_count": len(summary.import_errors),
            "unmatched_invoices": [
                {
                    "invoice_id": ib.invoice.invoice_id,
                    "customer_name": ib.invoice.customer_name,
                    "amount": str(ib.total_amount),
                    "outstanding_balance": str(ib.outstanding_balance),
                    "issue_date": ib.invoice.issue_date.isoformat(),
                }
                for ib in summary.unmatched_invoices
            ],
            "unallocated_payments": [
                {
                    "payment_id": pb.payment.payment_id,
                    "customer_name": pb.payment.customer_name,
                    "amount": str(pb.total_amount),
                    "unallocated_amount": str(pb.unallocated_amount),
                    "payment_date": pb.payment.payment_date.isoformat(),
                }
                for pb in summary.unallocated_payments
            ],
            "ambiguous_suggestions": [s.to_dict() for s in summary.ambiguous_suggestions],
            "amount_mismatches": [s.to_dict() for s in summary.amount_mismatches],
            "import_errors": [
                {
                    "row_index": e.row_index,
                    "field_name": e.field_name,
                    "error_type": e.error_type,
                    "message": e.message,
                    "is_warning": e.is_warning,
                }
                for e in summary.import_errors
            ],
        }

    def export_reconciliation_report(self, output_path: Optional[str] = None) -> str:
        """Export reconciliation report to CSV string or file."""
        return self.reporter.export_report_csv(output_path=output_path)

    def evaluate_dataset(
        self, ground_truth: Union[str, pd.DataFrame], min_score_threshold: float = 60.0
    ) -> Dict[str, Any]:
        """
        Evaluate precision, recall, and unresolved work metrics against ground truth.
        """
        return self.reporter.evaluate_dataset(
            ground_truth=ground_truth, min_score_threshold=min_score_threshold
        )

    # -------------------------------------------------------------
    # User and Business Authentication Service APIs
    # -------------------------------------------------------------

    def register_business(
        self,
        business_name: str,
        owner_name: str,
        email: str,
        mobile: str,
        password: str,
        role: str = "user",
    ) -> UserAccount:
        """
        Register a new business account or admin with password hashing and uniqueness checks.
        """
        clean_email = email.strip().lower()
        clean_mobile = mobile.strip().replace(" ", "").replace("-", "")

        # Check existing email
        if self.repo.get_user_by_email(clean_email):
            raise ValueError(f"Email address '{email}' is already registered.")

        # Check existing mobile
        if self.repo.get_user_by_mobile(clean_mobile):
            raise ValueError(f"Mobile number '{mobile}' is already registered.")

        user = AuthManager.create_user_account(
            business_name=business_name,
            owner_name=owner_name,
            email=clean_email,
            mobile=clean_mobile,
            password=password,
            role=role,
        )
        self.repo.create_user(user)
        return user

    def login(
        self,
        login_id: str,
        password: str,
        role: Optional[str] = None,
    ) -> UserAccount:
        """
        Authenticate a user by email or 10-digit mobile number.
        Returns the UserAccount if successful, or raises a ValueError.
        """
        if not login_id or not login_id.strip():
            raise ValueError("Mobile number or Email is required for login.")
        if not password:
            raise ValueError("Password is required.")

        raw_id = login_id.strip()
        user: Optional[UserAccount] = None

        if "@" in raw_id:
            user = self.repo.get_user_by_email(raw_id)
        else:
            clean_mobile = raw_id.replace(" ", "").replace("-", "")
            user = self.repo.get_user_by_mobile(clean_mobile)

        if not user:
            raise ValueError("Account not found with provided email or mobile number.")

        if user.status != "Active":
            raise ValueError(f"This account is {user.status.lower()}. Please contact administrator.")

        if role and user.role.lower() != role.lower():
            raise ValueError(f"This account is not authorized as '{role}'.")

        if not verify_password(password, user.password_hash, user.password_salt):
            raise ValueError("Incorrect password.")

        return user

    def list_businesses(self, role: Optional[str] = None) -> List[UserAccount]:
        """List registered business accounts or admins."""
        return self.repo.get_all_users(role=role)

    def set_business_status(self, user_id: str, status: str) -> None:
        """Enable or disable a registered business account."""
        valid_statuses = ["Active", "Disabled"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Must be one of {valid_statuses}")
        self.repo.update_user_status(user_id=user_id, status=status)
