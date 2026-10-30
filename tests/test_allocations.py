"""
Tests for allocations, confirmation, rejection, manual assignments, and safety constraints.
"""

from datetime import date
from decimal import Decimal
import pytest

from backend.models import ImportBatch, Invoice, Payment
from backend.service import ReconciliationService


@pytest.fixture
def service_with_records(in_memory_service: ReconciliationService):
    svc = in_memory_service
    batch_inv = ImportBatch("b_inv", "inv.csv", "INVOICE", 1, 1, 0, 0)
    inv = Invoice(
        invoice_id="INV-001",
        batch_id="b_inv",
        row_index=2,
        customer_id="C1",
        customer_name="Alpha Traders",
        customer_name_normalized="alpha",
        amount=Decimal("1000.00"),
        issue_date=date(2026, 10, 1),
    )
    svc.repo.save_import_batch(batch_inv, [inv], [])

    batch_pay = ImportBatch("b_pay", "pay.csv", "PAYMENT", 1, 1, 0, 0)
    pay = Payment(
        payment_id="PAY-001",
        batch_id="b_pay",
        row_index=2,
        customer_id="C1",
        customer_name="Alpha Traders",
        customer_name_normalized="alpha",
        amount=Decimal("1000.00"),
        payment_date=date(2026, 10, 3),
        note="Payment for INV-001",
    )
    svc.repo.save_import_batch(batch_pay, [pay], [])
    return svc


def test_confirm_suggestion(service_with_records: ReconciliationService):
    svc = service_with_records
    suggestions = svc.generate_suggestions()
    assert len(suggestions) == 1
    sug_id = suggestions[0].suggestion_id

    # Confirm suggestion
    alloc = svc.confirm_match(sug_id, reviewer="ALICE", notes="Verified by invoice ref")
    assert alloc.invoice_id == "INV-001"
    assert alloc.payment_id == "PAY-001"
    assert alloc.allocated_amount == Decimal("1000.00")
    assert alloc.reviewer == "ALICE"

    # Verify suggestion is now CONFIRMED
    updated_sug = svc.repo.get_suggestion_by_id(sug_id)
    assert updated_sug.status == "CONFIRMED"

    # Verify audit decision was logged
    decisions = svc.repo.get_review_decisions(invoice_id="INV-001")
    assert len(decisions) == 1
    assert decisions[0].action == "CONFIRM"
    assert decisions[0].amount == Decimal("1000.00")


def test_duplicate_confirmation_safely_rejected(service_with_records: ReconciliationService):
    svc = service_with_records
    suggestions = svc.generate_suggestions()
    sug_id = suggestions[0].suggestion_id

    svc.confirm_match(sug_id)

    # Re-confirming same suggestion must fail safely
    with pytest.raises(ValueError, match="already confirmed"):
        svc.confirm_match(sug_id)


def test_payment_cannot_be_allocated_more_than_its_amount(service_with_records: ReconciliationService):
    svc = service_with_records
    # Add a second invoice
    batch_inv2 = ImportBatch("b_inv2", "inv2.csv", "INVOICE", 1, 1, 0, 0)
    inv2 = Invoice(
        invoice_id="INV-002",
        batch_id="b_inv2",
        row_index=3,
        customer_id="C1",
        customer_name="Alpha Traders",
        customer_name_normalized="alpha",
        amount=Decimal("500.00"),
        issue_date=date(2026, 10, 2),
    )
    svc.repo.save_import_batch(batch_inv2, [inv2], [])

    # First allocate PAY-001 (1000.00) fully to INV-001
    svc.manual_assign("INV-001", "PAY-001", Decimal("1000.00"))

    # Attempt to allocate PAY-001 to INV-002 must fail because PAY-001 has 0 unallocated balance
    with pytest.raises(ValueError, match="exceeds available payment balance"):
        svc.manual_assign("INV-002", "PAY-001", Decimal("500.00"))


def test_over_allocation_of_invoice_prevented(service_with_records: ReconciliationService):
    svc = service_with_records
    # Invoice is 1000.00. Attempting to allocate 1500.00 must fail
    with pytest.raises(ValueError, match="exceeds available payment balance|exceeds outstanding invoice balance"):
        svc.manual_assign("INV-001", "PAY-001", Decimal("1500.00"))


def test_partial_allocation_and_remaining_balance(service_with_records: ReconciliationService):
    svc = service_with_records
    # Allocate partial amount 400.00
    alloc1 = svc.manual_assign("INV-001", "PAY-001", Decimal("400.00"))
    assert alloc1.allocated_amount == Decimal("400.00")

    balances = svc.get_balances()
    assert balances["invoices"]["details"][0]["allocated_amount"] == "400.00"
    assert balances["invoices"]["details"][0]["outstanding_balance"] == "600.00"
    assert balances["invoices"]["details"][0]["status"] == "PARTIALLY_PAID"

    assert balances["payments"]["details"][0]["allocated_amount"] == "400.00"
    assert balances["payments"]["details"][0]["unallocated_amount"] == "600.00"
    assert balances["payments"]["details"][0]["status"] == "PARTIALLY_ALLOCATED"

    # Allocate remaining 600.00
    alloc2 = svc.manual_assign("INV-001", "PAY-001", Decimal("600.00"))
    assert alloc2.allocated_amount == Decimal("600.00")

    balances_after = svc.get_balances()
    assert balances_after["invoices"]["details"][0]["status"] == "PAID"
    assert balances_after["invoices"]["details"][0]["outstanding_balance"] == "0.00"
    assert balances_after["payments"]["details"][0]["status"] == "FULLY_ALLOCATED"
    assert balances_after["payments"]["details"][0]["unallocated_amount"] == "0.00"


def test_reject_suggestion(service_with_records: ReconciliationService):
    svc = service_with_records
    suggestions = svc.generate_suggestions()
    sug_id = suggestions[0].suggestion_id

    dec = svc.reject_match(sug_id, reviewer="BOB", notes="Customer names do not match reality")
    assert dec.action == "REJECT"

    # Balances must remain completely unchanged (suggestions and rejections don't allocate)
    balances = svc.get_balances()
    assert balances["invoices"]["details"][0]["allocated_amount"] == "0.00"
    assert balances["payments"]["details"][0]["allocated_amount"] == "0.00"

    # Status of suggestion updated
    sug = svc.repo.get_suggestion_by_id(sug_id)
    assert sug.status == "REJECTED"


def test_unallocate_reversal_audit_trail(service_with_records: ReconciliationService):
    svc = service_with_records
    alloc = svc.manual_assign("INV-001", "PAY-001", Decimal("500.00"))
    
    # Reverse / unallocate
    dec = svc.engine.unallocate(alloc.allocation_id, reviewer="ADMIN", notes="Allocated by mistake")
    assert dec.action == "UNALLOCATE"
    assert dec.amount == Decimal("500.00")

    # Balances reset to 0 allocated
    balances = svc.get_balances()
    assert balances["invoices"]["details"][0]["allocated_amount"] == "0.00"

    # Complete audit trail preserved
    history = svc.repo.get_review_decisions(invoice_id="INV-001")
    actions = [h.action for h in history]
    assert "MANUAL_ALLOCATION" in actions
    assert "UNALLOCATE" in actions
