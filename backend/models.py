"""
Domain models and dataclasses for FinMatch reconciliation system.
Strictly uses Decimal for all monetary values.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
import json


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ImportBatch:
    batch_id: str
    file_name: str
    file_type: str  # "INVOICE" or "PAYMENT"
    row_count: int
    valid_count: int
    error_count: int
    warning_count: int
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class ImportRowError:
    error_id: Optional[int]
    batch_id: str
    row_index: int  # 1-based index in the CSV
    field_name: Optional[str]
    error_type: str  # MISSING_FIELD, INVALID_AMOUNT, INVALID_DATE, DUPLICATE_ID, etc.
    message: str
    raw_data: Dict[str, Any] = field(default_factory=dict)
    is_warning: bool = False


@dataclass
class Invoice:
    invoice_id: str
    batch_id: str
    row_index: int
    customer_id: Optional[str]
    customer_name: str
    customer_name_normalized: str
    amount: Decimal
    issue_date: date
    due_date: Optional[date] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invoice_id": self.invoice_id,
            "batch_id": self.batch_id,
            "row_index": self.row_index,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "customer_name_normalized": self.customer_name_normalized,
            "amount": str(self.amount),
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "reference": self.reference,
            "note": self.note,
        }


@dataclass
class Payment:
    payment_id: str
    batch_id: str
    row_index: int
    customer_id: Optional[str]
    customer_name: Optional[str]
    customer_name_normalized: Optional[str]
    amount: Decimal
    payment_date: date
    reference: Optional[str] = None
    payment_method: Optional[str] = None
    note: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "payment_id": self.payment_id,
            "batch_id": self.batch_id,
            "row_index": self.row_index,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "customer_name_normalized": self.customer_name_normalized,
            "amount": str(self.amount),
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "reference": self.reference,
            "payment_method": self.payment_method,
            "note": self.note,
        }


@dataclass
class EvidenceItem:
    rule_name: str
    score: float
    max_score: float
    description: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "score": self.score,
            "max_score": self.max_score,
            "description": self.description,
            "details": self.details,
        }


@dataclass
class MatchSuggestion:
    suggestion_id: str
    invoice_id: str
    payment_id: str
    score: float
    confidence_tier: str  # HIGH, MEDIUM, LOW
    is_ambiguous: bool
    amount_mismatch: bool
    explanation: str
    evidence: List[EvidenceItem] = field(default_factory=list)
    status: str = "PENDING"  # PENDING, CONFIRMED, REJECTED
    created_at: datetime = field(default_factory=_utc_now)

    def evidence_json(self) -> str:
        return json.dumps([e.to_dict() for e in self.evidence])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "invoice_id": self.invoice_id,
            "payment_id": self.payment_id,
            "score": self.score,
            "confidence_tier": self.confidence_tier,
            "is_ambiguous": self.is_ambiguous,
            "amount_mismatch": self.amount_mismatch,
            "explanation": self.explanation,
            "status": self.status,
            "evidence": [e.to_dict() for e in self.evidence],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class ConfirmedAllocation:
    allocation_id: str
    invoice_id: str
    payment_id: str
    allocated_amount: Decimal
    confirmed_at: datetime = field(default_factory=_utc_now)
    reviewer: str = "SYSTEM"
    decision_id: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allocation_id": self.allocation_id,
            "invoice_id": self.invoice_id,
            "payment_id": self.payment_id,
            "allocated_amount": str(self.allocated_amount),
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "reviewer": self.reviewer,
            "decision_id": self.decision_id,
            "notes": self.notes,
        }


@dataclass
class ReviewDecision:
    decision_id: str
    suggestion_id: Optional[str]
    invoice_id: str
    payment_id: str
    action: str  # CONFIRM, REJECT, MANUAL_ALLOCATION, UNALLOCATE
    amount: Optional[Decimal]
    reviewer: str
    notes: Optional[str]
    timestamp: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "suggestion_id": self.suggestion_id,
            "invoice_id": self.invoice_id,
            "payment_id": self.payment_id,
            "action": self.action,
            "amount": str(self.amount) if self.amount is not None else None,
            "reviewer": self.reviewer,
            "notes": self.notes,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class InvoiceBalance:
    invoice: Invoice
    total_amount: Decimal
    allocated_amount: Decimal
    outstanding_balance: Decimal
    status: str  # UNPAID, PARTIALLY_PAID, PAID, OVERPAID
    allocations: List[ConfirmedAllocation] = field(default_factory=list)


@dataclass
class PaymentBalance:
    payment: Payment
    total_amount: Decimal
    allocated_amount: Decimal
    unallocated_amount: Decimal
    status: str  # UNALLOCATED, PARTIALLY_ALLOCATED, FULLY_ALLOCATED
    allocations: List[ConfirmedAllocation] = field(default_factory=list)


@dataclass
class UnresolvedWorkSummary:
    unmatched_invoices: List[InvoiceBalance]
    unallocated_payments: List[PaymentBalance]
    ambiguous_suggestions: List[MatchSuggestion]
    amount_mismatches: List[MatchSuggestion]
    import_errors: List[ImportRowError]
