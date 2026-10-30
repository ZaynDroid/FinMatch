"""
Tests for deterministic explainable match suggestions and scoring logic.
"""

from datetime import date
from decimal import Decimal
import pytest

from backend.matcher import MatchingConfig, MatchingEngine
from backend.models import Invoice, Payment


@pytest.fixture
def sample_invoice():
    return Invoice(
        invoice_id="INV-101",
        batch_id="b1",
        row_index=2,
        customer_id="CUST-1",
        customer_name="Sharma Kirana Store",
        customer_name_normalized="sharma",
        amount=Decimal("12500.00"),
        issue_date=date(2026, 10, 5),
        reference="B-2201",
        note="Monthly groceries",
    )


def test_exact_reference_high_confidence(sample_invoice):
    payment = Payment(
        payment_id="PAY-501",
        batch_id="b2",
        row_index=2,
        customer_id="CUST-1",
        customer_name="Sharma Kirana",
        customer_name_normalized="sharma",
        amount=Decimal("12500.00"),
        payment_date=date(2026, 10, 7),
        reference="UPI4382910",
        note="Payment for INV-101",
    )
    engine = MatchingEngine()
    suggestions = engine.generate_suggestions([sample_invoice], [payment])
    assert len(suggestions) == 1
    sug = suggestions[0]
    assert sug.score >= 90.0
    assert sug.confidence_tier == "HIGH"
    assert not sug.is_ambiguous
    assert not sug.amount_mismatch
    assert "EXACT_INVOICE_ID_REFERENCE" in [e.rule_name for e in sug.evidence]
    assert "HIGH CONFIDENCE" in sug.explanation


def test_amount_only_equality_is_not_high_confidence():
    """
    Critical requirement: Do not claim a match is certain solely because amounts are equal!
    """
    invoice = Invoice(
        invoice_id="INV-200",
        batch_id="b1",
        row_index=2,
        customer_id=None,
        customer_name="Alpha Enterprises",
        customer_name_normalized="alpha",
        amount=Decimal("5000.00"),
        issue_date=date(2026, 10, 1),
    )
    payment = Payment(
        payment_id="PAY-200",
        batch_id="b2",
        row_index=2,
        customer_id=None,
        customer_name="Omega Logistics",
        customer_name_normalized="omega",
        amount=Decimal("5000.00"),
        payment_date=date(2026, 10, 5),
        note="Generic transfer",
    )
    engine = MatchingEngine()
    suggestions = engine.generate_suggestions([invoice], [payment])
    assert len(suggestions) == 1
    sug = suggestions[0]
    # Amount is equal (+20) + date is proximate (+5) = 25 pts.
    assert sug.score <= 35.0
    assert sug.confidence_tier == "LOW"
    assert sug.is_ambiguous is True
    assert "LOW CONFIDENCE" in sug.explanation


def test_partial_payment_amount_mismatch(sample_invoice):
    payment = Payment(
        payment_id="PAY-PARTIAL",
        batch_id="b2",
        row_index=2,
        customer_id="CUST-1",
        customer_name="Sharma Kirana Store",
        customer_name_normalized="sharma",
        amount=Decimal("5000.00"),  # Partial
        payment_date=date(2026, 10, 8),
        reference="B-2201",
        note="Advance payment",
    )
    engine = MatchingEngine()
    suggestions = engine.generate_suggestions([sample_invoice], [payment])
    assert len(suggestions) == 1
    sug = suggestions[0]
    assert sug.amount_mismatch is True
    # Because of amount mismatch, confidence cannot be HIGH
    assert sug.confidence_tier != "HIGH"
    assert any(e.rule_name == "PARTIAL_AMOUNT_MATCH" for e in sug.evidence)


def test_fuzzy_name_matching():
    invoice = Invoice(
        invoice_id="INV-CLINIC",
        batch_id="b1",
        row_index=2,
        customer_id=None,
        customer_name="Bisht Medical Clinic",
        customer_name_normalized="bisht",
        amount=Decimal("9600.00"),
        issue_date=date(2026, 10, 3),
    )
    payment = Payment(
        payment_id="PAY-DOCTOR",
        batch_id="b2",
        row_index=2,
        customer_id=None,
        customer_name="Dr. Bisht Clinic",
        customer_name_normalized="bisht",
        amount=Decimal("9600.00"),
        payment_date=date(2026, 10, 10),
    )
    engine = MatchingEngine()
    suggestions = engine.generate_suggestions([invoice], [payment])
    assert len(suggestions) == 1
    sug = suggestions[0]
    assert sug.score >= 40.0
    # Customer normalized names match exactly or fuzzy
    assert any(e.rule_name in ["EXACT_CUSTOMER_NAME", "FUZZY_CUSTOMER_NAME"] for e in sug.evidence)


def test_ambiguity_when_multiple_invoices_compete():
    # Two invoices with identical amounts and no distinctive references
    inv1 = Invoice(
        invoice_id="INV-A",
        batch_id="b1",
        row_index=2,
        customer_id=None,
        customer_name="Dairy Farm 1",
        customer_name_normalized="dairy 1",
        amount=Decimal("6800.00"),
        issue_date=date(2026, 10, 10),
    )
    inv2 = Invoice(
        invoice_id="INV-B",
        batch_id="b1",
        row_index=3,
        customer_id=None,
        customer_name="Dairy Farm 2",
        customer_name_normalized="dairy 2",
        amount=Decimal("6800.00"),
        issue_date=date(2026, 10, 10),
    )
    pay = Payment(
        payment_id="PAY-UNKNOWN",
        batch_id="b2",
        row_index=2,
        customer_id=None,
        customer_name="Third Party Remitter",
        customer_name_normalized="third party",
        amount=Decimal("6800.00"),
        payment_date=date(2026, 10, 15),
    )
    engine = MatchingEngine()
    suggestions = engine.generate_suggestions([inv1, inv2], [pay])
    assert len(suggestions) == 2
    # Both suggestions must be flagged as ambiguous
    assert suggestions[0].is_ambiguous is True
    assert suggestions[1].is_ambiguous is True
