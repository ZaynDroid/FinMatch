"""
End-to-end integration tests using full sample datasets.
"""

from decimal import Decimal
import pytest

from backend.service import ReconciliationService


def test_full_reconciliation_workflow(sample_data_paths):
    # 1. Initialize service with clean in-memory database
    service = ReconciliationService(db_path=":memory:")

    # 2. Ingest Invoices
    inv_batch, valid_invoices, inv_errors = service.import_invoices_csv(
        sample_data_paths["invoices"], file_name="sample_invoices.csv"
    )
    assert inv_batch.valid_count == 12
    assert inv_batch.error_count == 3  # The 3 invalid rows in sample_invoices.csv
    assert len(inv_errors) == 3

    # 3. Ingest Payments
    pay_batch, valid_payments, pay_errors = service.import_payments_csv(
        sample_data_paths["payments"], file_name="sample_payments.csv"
    )
    assert pay_batch.valid_count == 11
    assert pay_batch.error_count == 2  # The 2 invalid rows in sample_payments.csv
    assert len(pay_errors) == 2

    # 4. Generate Explainable Match Suggestions
    suggestions = service.generate_suggestions()
    assert len(suggestions) > 0

    # Ensure suggestions did not alter balances yet
    pre_balances = service.get_balances()
    assert pre_balances["invoices"]["total_settled"] == "0.00"
    assert pre_balances["payments"]["total_allocated"] == "0.00"

    # 5. Review & Confirm High-Confidence Match
    # Find INV-101 and PAY-501 suggestion
    inv101_sug = next(
        s for s in suggestions if s.invoice_id == "INV-101" and s.payment_id == "PAY-501"
    )
    assert inv101_sug.confidence_tier == "HIGH"
    alloc = service.confirm_match(
        inv101_sug.suggestion_id,
        reviewer="SENIOR_ACCOUNTANT",
        notes="Verified against bank statement",
    )
    assert alloc.allocated_amount == Decimal("12500.00")

    # 6. Verify Balances Updated Correctly
    post_balances = service.get_balances()
    assert post_balances["invoices"]["total_settled"] == "12500.00"
    assert post_balances["payments"]["total_allocated"] == "12500.00"

    # Check INV-101 is PAID
    inv101_status = next(
        d for d in post_balances["invoices"]["details"] if d["invoice_id"] == "INV-101"
    )
    assert inv101_status["status"] == "PAID"
    assert inv101_status["outstanding_balance"] == "0.00"

    # 7. Reject an Ambiguous Suggestion
    # Find suggestion involving PAY-510 (from Ramesh, ambiguous 6800)
    ambiguous_sug = next((s for s in suggestions if s.payment_id == "PAY-510"), None)
    if ambiguous_sug:
        assert ambiguous_sug.is_ambiguous is True
        dec = service.reject_match(
            ambiguous_sug.suggestion_id,
            reviewer="SENIOR_ACCOUNTANT",
            notes="Third party payer cannot be verified without customer receipt",
        )
        assert dec.action == "REJECT"

    # 8. Check Unresolved Work
    unresolved = service.get_unresolved_work()
    assert unresolved["unmatched_invoices_count"] >= 1
    assert unresolved["unallocated_payments_count"] >= 1
    assert unresolved["import_errors_count"] == 5  # 3 invoice + 2 payment errors

    # 9. Export Reconciliation Report
    report_csv = service.export_reconciliation_report()
    assert "INV-101" in report_csv
    assert "PAY-501" in report_csv
    assert "CONFIRMED_MATCH" in report_csv

    # 10. Dataset-Level Evaluation
    metrics = service.evaluate_dataset(sample_data_paths["ground_truth"], min_score_threshold=50.0)
    assert metrics["matching_precision"] >= 0.70
    assert metrics["proportion_receiving_correct_suggestions_recall"] >= 0.70
    assert metrics["unresolved_cases_count"] > 0
