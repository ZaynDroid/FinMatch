"""
Tests for reconciliation reporting, CSV exports, and evaluation metrics against ground truth.
"""

from decimal import Decimal
import pandas as pd
import pytest

from backend.service import ReconciliationService


def test_reconciliation_report_export(sample_data_paths):
    svc = ReconciliationService(db_path=":memory:")
    # Import sample data
    svc.import_invoices_csv(sample_data_paths["invoices"])
    svc.import_payments_csv(sample_data_paths["payments"])

    # Suggest and confirm one match
    suggestions = svc.generate_suggestions()
    high_tier = [s for s in suggestions if s.confidence_tier == "HIGH"]
    assert len(high_tier) > 0
    svc.confirm_match(high_tier[0].suggestion_id, reviewer="TESTER")

    report_csv = svc.export_reconciliation_report()
    assert "record_type" in report_csv
    assert "invoice_id" in report_csv
    assert "payment_id" in report_csv
    assert "allocated_amount" in report_csv
    assert "CONFIRMED_MATCH" in report_csv
    assert "UNMATCHED_INVOICE" in report_csv
    assert "UNALLOCATED_PAYMENT" in report_csv


def test_evaluate_dataset_metrics(sample_data_paths):
    svc = ReconciliationService(db_path=":memory:")
    svc.import_invoices_csv(sample_data_paths["invoices"])
    svc.import_payments_csv(sample_data_paths["payments"])
    svc.generate_suggestions()

    metrics = svc.evaluate_dataset(sample_data_paths["ground_truth"], min_score_threshold=50.0)

    assert metrics["total_ground_truth_matches"] > 0
    assert metrics["true_positives"] > 0
    assert 0.0 <= metrics["matching_precision"] <= 1.0
    assert 0.0 <= metrics["proportion_receiving_correct_suggestions_recall"] <= 1.0
    assert 0.0 <= metrics["f1_score"] <= 1.0
    assert metrics["unresolved_cases_count"] >= 0
    assert "metric_definitions" in metrics
    assert "precision" in metrics["metric_definitions"]
    assert "recall" in metrics["metric_definitions"]
