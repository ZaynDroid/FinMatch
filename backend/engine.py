"""
Financial reconciliation engine enforcing auditable business logic.
Strictly relies on Confirmed Allocations for balance calculations.
Guarantees Decimal arithmetic and prevents duplicate or over-allocation.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Set, Tuple

from backend.models import (
    ConfirmedAllocation,
    Invoice,
    InvoiceBalance,
    MatchSuggestion,
    Payment,
    PaymentBalance,
    ReviewDecision,
    UnresolvedWorkSummary,
)
from backend.storage.repository import ReconciliationRepository


class ReconciliationEngine:
    def __init__(self, repo: ReconciliationRepository):
        self.repo = repo

    def confirm_suggestion(
        self,
        suggestion_id: str,
        reviewer: str = "SYSTEM",
        allocation_amount: Optional[Decimal] = None,
        notes: Optional[str] = None,
    ) -> ConfirmedAllocation:
        """
        Confirm a match suggestion and record allocation + audit trail.
        Safely rejects duplicate confirmation or over-allocation attempts.
        """
        suggestion = self.repo.get_suggestion_by_id(suggestion_id)
        if not suggestion:
            raise ValueError(f"Suggestion with ID '{suggestion_id}' not found.")

        if suggestion.status == "CONFIRMED":
            raise ValueError(f"Suggestion '{suggestion_id}' is already confirmed.")

        invoice = self.repo.get_invoice_by_id(suggestion.invoice_id)
        if not invoice:
            raise ValueError(f"Invoice '{suggestion.invoice_id}' not found.")

        payment = self.repo.get_payment_by_id(suggestion.payment_id)
        if not payment:
            raise ValueError(f"Payment '{suggestion.payment_id}' not found.")

        # Compute current unallocated payment & unpaid invoice
        pay_allocs = self.repo.get_allocations_for_payment(payment.payment_id)
        total_pay_allocated = sum((a.allocated_amount for a in pay_allocs), Decimal("0.00"))
        available_payment = payment.amount - total_pay_allocated

        if available_payment <= Decimal("0.00"):
            raise ValueError(
                f"Payment '{payment.payment_id}' is already fully allocated ({total_pay_allocated} / {payment.amount})."
            )

        inv_allocs = self.repo.get_allocations_for_invoice(invoice.invoice_id)
        total_inv_allocated = sum((a.allocated_amount for a in inv_allocs), Decimal("0.00"))
        remaining_invoice = invoice.amount - total_inv_allocated

        if remaining_invoice <= Decimal("0.00"):
            raise ValueError(
                f"Invoice '{invoice.invoice_id}' is already fully settled ({total_inv_allocated} / {invoice.amount})."
            )

        # Determine exact allocation amount
        if allocation_amount is not None:
            if not isinstance(allocation_amount, Decimal):
                raise TypeError("Allocation amount must be a Decimal instance.")
            if allocation_amount <= Decimal("0.00"):
                raise ValueError("Allocation amount must be strictly greater than 0.")
            if allocation_amount > available_payment:
                raise ValueError(
                    f"Requested allocation ({allocation_amount}) exceeds available payment balance ({available_payment})."
                )
            if allocation_amount > remaining_invoice:
                raise ValueError(
                    f"Requested allocation ({allocation_amount}) exceeds outstanding invoice balance ({remaining_invoice})."
                )
            actual_amount = allocation_amount
        else:
            # Allocate up to the minimum of available payment and unpaid balance
            actual_amount = min(available_payment, remaining_invoice)

        # 1. Record Audit Decision
        decision_id = str(uuid.uuid4())
        decision = ReviewDecision(
            decision_id=decision_id,
            suggestion_id=suggestion.suggestion_id,
            invoice_id=invoice.invoice_id,
            payment_id=payment.payment_id,
            action="CONFIRM",
            amount=actual_amount,
            reviewer=reviewer,
            notes=notes or suggestion.explanation,
            timestamp=datetime.now(timezone.utc),
        )
        self.repo.save_review_decision(decision)

        # 2. Record Confirmed Allocation
        allocation_id = str(uuid.uuid4())
        allocation = ConfirmedAllocation(
            allocation_id=allocation_id,
            invoice_id=invoice.invoice_id,
            payment_id=payment.payment_id,
            allocated_amount=actual_amount,
            confirmed_at=datetime.now(timezone.utc),
            reviewer=reviewer,
            decision_id=decision_id,
            notes=notes,
        )
        self.repo.save_allocation(allocation)

        # 3. Update Suggestion Status
        self.repo.update_suggestion_status(suggestion.suggestion_id, "CONFIRMED")

        return allocation

    def reject_suggestion(
        self,
        suggestion_id: str,
        reviewer: str = "SYSTEM",
        notes: Optional[str] = None,
    ) -> ReviewDecision:
        """
        Reject a match suggestion without allocating funds.
        """
        suggestion = self.repo.get_suggestion_by_id(suggestion_id)
        if not suggestion:
            raise ValueError(f"Suggestion with ID '{suggestion_id}' not found.")

        decision_id = str(uuid.uuid4())
        decision = ReviewDecision(
            decision_id=decision_id,
            suggestion_id=suggestion.suggestion_id,
            invoice_id=suggestion.invoice_id,
            payment_id=suggestion.payment_id,
            action="REJECT",
            amount=None,
            reviewer=reviewer,
            notes=notes or "Suggestion rejected by reviewer.",
            timestamp=datetime.now(timezone.utc),
        )
        self.repo.save_review_decision(decision)
        self.repo.update_suggestion_status(suggestion.suggestion_id, "REJECTED")
        return decision

    def manual_allocate(
        self,
        invoice_id: str,
        payment_id: str,
        amount: Decimal,
        reviewer: str = "SYSTEM",
        notes: Optional[str] = None,
    ) -> ConfirmedAllocation:
        """
        Manually assign a payment to an invoice with explicit amount.
        Enforces balance and duplicate safeguards.
        """
        if not isinstance(amount, Decimal):
            raise TypeError("Manual allocation amount must be a Decimal.")
        if amount <= Decimal("0.00"):
            raise ValueError("Allocation amount must be strictly greater than 0.")

        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice '{invoice_id}' not found.")

        payment = self.repo.get_payment_by_id(payment_id)
        if not payment:
            raise ValueError(f"Payment '{payment_id}' not found.")

        # Payment unallocated check
        pay_allocs = self.repo.get_allocations_for_payment(payment_id)
        total_pay_allocated = sum((a.allocated_amount for a in pay_allocs), Decimal("0.00"))
        available_payment = payment.amount - total_pay_allocated
        if amount > available_payment:
            raise ValueError(
                f"Requested allocation ({amount}) exceeds available payment balance ({available_payment})."
            )

        # Invoice unpaid balance check
        inv_allocs = self.repo.get_allocations_for_invoice(invoice_id)
        total_inv_allocated = sum((a.allocated_amount for a in inv_allocs), Decimal("0.00"))
        remaining_invoice = invoice.amount - total_inv_allocated
        if amount > remaining_invoice:
            raise ValueError(
                f"Requested allocation ({amount}) exceeds outstanding invoice balance ({remaining_invoice})."
            )

        # Create decision
        decision_id = str(uuid.uuid4())
        decision = ReviewDecision(
            decision_id=decision_id,
            suggestion_id=None,
            invoice_id=invoice_id,
            payment_id=payment_id,
            action="MANUAL_ALLOCATION",
            amount=amount,
            reviewer=reviewer,
            notes=notes or f"Manual allocation by {reviewer}",
            timestamp=datetime.now(timezone.utc),
        )
        self.repo.save_review_decision(decision)

        # Create allocation
        allocation_id = str(uuid.uuid4())
        allocation = ConfirmedAllocation(
            allocation_id=allocation_id,
            invoice_id=invoice_id,
            payment_id=payment_id,
            allocated_amount=amount,
            confirmed_at=datetime.now(timezone.utc),
            reviewer=reviewer,
            decision_id=decision_id,
            notes=notes,
        )
        self.repo.save_allocation(allocation)

        # If a pending suggestion existed between them, mark confirmed
        suggestions = self.repo.get_suggestions(status="PENDING")
        for s in suggestions:
            if s.invoice_id == invoice_id and s.payment_id == payment_id:
                self.repo.update_suggestion_status(s.suggestion_id, "CONFIRMED")

        return allocation

    def unallocate(
        self,
        allocation_id: str,
        reviewer: str = "SYSTEM",
        notes: Optional[str] = None,
    ) -> ReviewDecision:
        """
        Reverse a confirmed allocation while preserving complete audit history.
        """
        allocations = self.repo.get_all_allocations()
        target = next((a for a in allocations if a.allocation_id == allocation_id), None)
        if not target:
            raise ValueError(f"Allocation '{allocation_id}' not found.")

        # Record UNALLOCATE audit event
        decision_id = str(uuid.uuid4())
        decision = ReviewDecision(
            decision_id=decision_id,
            suggestion_id=None,
            invoice_id=target.invoice_id,
            payment_id=target.payment_id,
            action="UNALLOCATE",
            amount=target.allocated_amount,
            reviewer=reviewer,
            notes=notes or f"Reversed allocation {allocation_id}",
            timestamp=datetime.now(timezone.utc),
        )
        self.repo.save_review_decision(decision)

        # Delete allocation
        self.repo.delete_allocation(allocation_id)
        return decision

    def calculate_invoice_balance(self, invoice: Invoice) -> InvoiceBalance:
        allocs = self.repo.get_allocations_for_invoice(invoice.invoice_id)
        allocated = sum((a.allocated_amount for a in allocs), Decimal("0.00"))
        outstanding = invoice.amount - allocated

        if allocated == Decimal("0.00"):
            status = "UNPAID"
        elif allocated < invoice.amount:
            status = "PARTIALLY_PAID"
        elif allocated == invoice.amount:
            status = "PAID"
        else:
            status = "OVERPAID"

        return InvoiceBalance(
            invoice=invoice,
            total_amount=invoice.amount,
            allocated_amount=allocated,
            outstanding_balance=outstanding,
            status=status,
            allocations=allocs,
        )

    def calculate_payment_balance(self, payment: Payment) -> PaymentBalance:
        allocs = self.repo.get_allocations_for_payment(payment.payment_id)
        allocated = sum((a.allocated_amount for a in allocs), Decimal("0.00"))
        unallocated = payment.amount - allocated

        if allocated == Decimal("0.00"):
            status = "UNALLOCATED"
        elif allocated < payment.amount:
            status = "PARTIALLY_ALLOCATED"
        else:
            status = "FULLY_ALLOCATED"

        return PaymentBalance(
            payment=payment,
            total_amount=payment.amount,
            allocated_amount=allocated,
            unallocated_amount=unallocated,
            status=status,
            allocations=allocs,
        )

    def get_all_balances(self) -> Tuple[List[InvoiceBalance], List[PaymentBalance]]:
        invoices = self.repo.get_invoices()
        payments = self.repo.get_payments()
        inv_balances = [self.calculate_invoice_balance(inv) for inv in invoices]
        pay_balances = [self.calculate_payment_balance(pay) for pay in payments]
        return inv_balances, pay_balances

    def get_unresolved_work(self) -> UnresolvedWorkSummary:
        """
        Categorize outstanding review items into distinct actionable buckets.
        """
        inv_balances, pay_balances = self.get_all_balances()
        unmatched_invoices = [ib for ib in inv_balances if ib.outstanding_balance > Decimal("0.00")]
        unallocated_payments = [pb for pb in pay_balances if pb.unallocated_amount > Decimal("0.00")]

        pending_suggestions = self.repo.get_suggestions(status="PENDING")
        ambiguous = [s for s in pending_suggestions if s.is_ambiguous]
        mismatches = [s for s in pending_suggestions if s.amount_mismatch]
        errors = self.repo.get_import_errors()

        return UnresolvedWorkSummary(
            unmatched_invoices=unmatched_invoices,
            unallocated_payments=unallocated_payments,
            ambiguous_suggestions=ambiguous,
            amount_mismatches=mismatches,
            import_errors=errors,
        )
