"""
Tests for CSV ingestion, validation, row-level error capturing, and alias mapping.
"""

from io import StringIO
from decimal import Decimal
import pytest

from backend.importer import CSVImporter


def test_import_valid_invoices():
    csv_data = """invoice_id,customer_name,amount,issue_date,due_date,reference,note
INV-001,Sharma Store,1500.50,2026-10-01,2026-10-15,REF-1,Test note
INV-002,Gupta Traders,3200.00,2026-10-02,2026-10-20,REF-2,Another note
"""
    batch, valids, errors = CSVImporter.import_invoices(StringIO(csv_data), "test_inv.csv")
    assert batch.row_count == 2
    assert batch.valid_count == 2
    assert batch.error_count == 0
    assert len(valids) == 2
    assert valids[0].invoice_id == "INV-001"
    assert valids[0].amount == Decimal("1500.50")
    assert valids[0].customer_name == "Sharma Store"


def test_import_invoices_with_column_aliases():
    # Uses 'id', 'cust', 'amt', 'date'
    csv_data = """id,cust,amt,date
INV-003,Verma Hall,750.00,2026-10-03
"""
    batch, valids, errors = CSVImporter.import_invoices(StringIO(csv_data), "alias_inv.csv")
    assert batch.valid_count == 1
    assert valids[0].invoice_id == "INV-003"
    assert valids[0].customer_name == "Verma Hall"
    assert valids[0].amount == Decimal("750.00")


def test_import_invoices_row_level_errors():
    csv_data = """invoice_id,customer_name,amount,issue_date,due_date
INV-OK,Good Customer,1000.00,2026-10-01,2026-10-15
,Missing ID,2000.00,2026-10-02,2026-10-16
INV-BAD-AMT,Bad Amount,not_a_number,2026-10-03,2026-10-17
INV-NEG-AMT,Negative Amount,-500.00,2026-10-04,2026-10-18
INV-BAD-DATE,Bad Date,3000.00,2026-13-45,2026-10-19
INV-DUP,Dup Customer 1,4000.00,2026-10-05,2026-10-20
INV-DUP,Dup Customer 2,5000.00,2026-10-06,2026-10-21
"""
    batch, valids, errors = CSVImporter.import_invoices(StringIO(csv_data), "errors_inv.csv")
    assert len(valids) == 2  # INV-OK and the first INV-DUP
    assert batch.error_count >= 5  # 5 invalid rows

    # Errors should record row index and field name
    err_fields = [e.field_name for e in errors if not e.is_warning]
    assert "invoice_id" in err_fields
    assert "amount" in err_fields
    assert "issue_date" in err_fields


def test_import_due_date_warning():
    # Due date earlier than issue date should be a non-fatal warning
    csv_data = """invoice_id,customer_name,amount,issue_date,due_date
INV-WARN,Warning Customer,1000.00,2026-10-15,2026-10-05
"""
    batch, valids, errors = CSVImporter.import_invoices(StringIO(csv_data), "warn.csv")
    assert batch.valid_count == 1
    assert batch.warning_count == 1
    warnings = [e for e in errors if e.is_warning]
    assert len(warnings) == 1
    assert "earlier than issue date" in warnings[0].message


def test_import_duplicate_against_existing_ids():
    csv_data = """invoice_id,customer_name,amount,issue_date
INV-EXIST,Customer A,1000.00,2026-10-01
"""
    batch, valids, errors = CSVImporter.import_invoices(
        StringIO(csv_data), "dup.csv", existing_invoice_ids={"INV-EXIST"}
    )
    assert batch.valid_count == 0
    assert batch.error_count == 1
    assert "already exists in system" in errors[0].message


def test_import_payments_valid():
    csv_data = """payment_id,customer_name,amount,payment_date,reference,payment_method,note
PAY-001,Sharma Store,1500.50,2026-10-02,UPI123,UPI,INV-001 payment
"""
    batch, valids, errors = CSVImporter.import_payments(StringIO(csv_data), "pay.csv")
    assert batch.valid_count == 1
    assert valids[0].payment_id == "PAY-001"
    assert valids[0].amount == Decimal("1500.50")
    assert valids[0].payment_method == "UPI"
