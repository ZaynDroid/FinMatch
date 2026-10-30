"""
Tests for balance calculations, unresolved work categorization, and Decimal precision.
"""

from datetime import date
from decimal import Decimal
import pytest

from backend.models import ImportBatch, Invoice, Payment
from backend.service import ReconciliationService


def test_decimal_precision_multi_item():
    """Verify that multiple decimal additions do not suffer floating-point inaccuracy."""
    svc = ReconciliationService(db_path=":memory:")

    # 3 decimal amounts that would suffer float precision issues (0.1 + 0.2 != 0.3 in float)
    batch_inv = ImportBatch("b1", "inv.csv", "INVOICE", 1, 1, 0, 0)
    inv = Invoice(
        invoice_id="INV-DEC",
        batch_id="b1",
        row_index=2,
        customer_id=None,
        customer_name="Tech Solutions",
        customer_name_normalized="tech",
        amount=Decimal("0.30"),
        issue_date=date(2026, 10, 1),
    )
    svc.repo.save_import_batch(batch_inv, [inv], [])

    batch_pay = ImportBatch("b2", "pay.csv", "PAYMENT", 2, 2, 0, 0)
    p1 = Payment(
        payment_id="PAY-P1",
        batch_id="b2",
        row_index=2,
        customer_id=None,
        customer_name="Tech Solutions",
        customer_name_normalized="tech",
        amount=Decimal("0.10"),
        payment_date=date(2026, 10, 2),
    )
    p2 = Payment(
        payment_id="PAY-P2",
        batch_id="b2",
        row_index=3,
        customer_id=None,
        customer_name="Tech Solutions",
        customer_name_normalized="tech",
        amount=Decimal("0.20"),
        payment_date=date(2026, 10, 3),
    )
    svc.repo.save_import_batch(batch_pay, [p1, p2], [])

    # Allocate both
    svc.manual_assign("INV-DEC", "PAY-P1", Decimal("0.10"))
    svc.manual_assign("INV-DEC", "PAY-P2", Decimal("0.20"))

    balances = svc.get_balances()
    inv_stat = balances["invoices"]["details"][0]
    assert inv_stat["allocated_amount"] == "0.30"
    assert inv_stat["outstanding_balance"] == "0.00"
    assert inv_stat["status"] == "PAID"


def test_suggestions_do_not_change_balances():
    svc = ReconciliationService(db_path=":memory:")
    batch_inv = ImportBatch("b1", "inv.csv", "INVOICE", 1, 1, 0, 0)
    inv = Invoice(
        invoice_id="INV-1",
        batch_id="b1",
        row_index=2,
        customer_id=None,
        customer_name="Alpha",
        customer_name_normalized="alpha",
        amount=Decimal("500.00"),
        issue_date=date(2026, 10, 1),
    )
    svc.repo.save_import_batch(batch_inv, [inv], [])

    batch_pay = ImportBatch("b2", "pay.csv", "PAYMENT", 1, 1, 0, 0)
    pay = Payment(
        payment_id="PAY-1",
        batch_id="b2",
        row_index=2,
        customer_id=None,
        customer_name="Alpha",
        customer_name_normalized="alpha",
        amount=Decimal("500.00"),
        payment_date=date(2026, 10, 2),
    )
    svc.repo.save_import_batch(batch_pay, [pay], [])

    # Generate suggestions
    svc.generate_suggestions()

    # Balances must still show 0.00 allocated
    balances = svc.get_balances()
    assert balances["invoices"]["details"][0]["allocated_amount"] == "0.00"
    assert balances["invoices"]["details"][0]["outstanding_balance"] == "500.00"
    assert balances["invoices"]["details"][0]["status"] == "UNPAID"
    assert balances["payments"]["details"][0]["allocated_amount"] == "0.00"
    assert balances["payments"]["details"][0]["unallocated_amount"] == "500.00"
    assert balances["payments"]["details"][0]["status"] == "UNALLOCATED"


def test_unresolved_work_categorization():
    svc = ReconciliationService(db_path=":memory:")
    # Invoice 1
    batch_inv = ImportBatch("b1", "inv.csv", "INVOICE", 1, 1, 0, 0)
    inv = Invoice(
        invoice_id="INV-1",
        batch_id="b1",
        row_index=2,
        customer_id=None,
        customer_name="Beta Corp",
        customer_name_normalized="beta",
        amount=Decimal("1000.00"),
        issue_date=date(2026, 10, 1),
    )
    svc.repo.save_import_batch(batch_inv, [inv], [])

    # Payment 1 (unallocated)
    batch_pay = ImportBatch("b2", "pay.csv", "PAYMENT", 1, 1, 0, 0)
    pay = Payment(
        payment_id="PAY-1",
        batch_id="b2",
        row_index=2,
        customer_id=None,
        customer_name="Gamma LLC",
        customer_name_normalized="gamma",
        amount=Decimal("800.00"),
        payment_date=date(2026, 10, 3),
    )
    svc.repo.save_import_batch(batch_pay, [pay], [])

    unresolved = svc.get_unresolved_work()
    assert unresolved["unmatched_invoices_count"] == 1
    assert unresolved["unallocated_payments_count"] == 1
    assert unresolved["unmatched_invoices"][0]["invoice_id"] == "INV-1"
    assert unresolved["unallocated_payments"][0]["payment_id"] == "PAY-1"
