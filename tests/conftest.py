"""
Pytest configuration and reusable fixtures.
"""

import os
from decimal import Decimal
import pytest

from backend.service import ReconciliationService


@pytest.fixture
def in_memory_service():
    """Provides a clean in-memory ReconciliationService for each test."""
    service = ReconciliationService(db_path=":memory:")
    return service


@pytest.fixture
def sample_data_paths():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return {
        "invoices": os.path.join(base_dir, "data", "sample_invoices.csv"),
        "payments": os.path.join(base_dir, "data", "sample_payments.csv"),
        "ground_truth": os.path.join(base_dir, "data", "ground_truth_labels.csv"),
    }
