"""
Tests for normalization, string sanitization, and strict Decimal & date parsing.
"""

from datetime import date
from decimal import Decimal
import pytest

from backend.normalizer import (
    extract_reference_tokens,
    normalize_customer_name,
    normalize_whitespace,
    parse_date,
    parse_decimal_amount,
)


def test_normalize_whitespace():
    assert normalize_whitespace("  hello   world  ") == "hello world"
    assert normalize_whitespace(None) == ""
    assert normalize_whitespace("\n\t  Sharma   Traders \r\n") == "Sharma Traders"


def test_normalize_customer_name():
    # Removal of suffixes and punctuation
    assert normalize_customer_name("Sharma Kirana Store") == "sharma"
    assert normalize_customer_name("Gupta Hardware Pvt. Ltd.") == "gupta"
    assert normalize_customer_name("Dr. Bisht Clinic") == "bisht"
    assert normalize_customer_name("Verma Medical Hall") == "verma"
    # Case insensitivity
    assert normalize_customer_name("NEGI ELECTRICALS") == "negi"


def test_parse_decimal_amount_valid():
    assert parse_decimal_amount("12500") == Decimal("12500.00")
    assert parse_decimal_amount("12,500.50") == Decimal("12500.50")
    assert parse_decimal_amount(" ₹ 48,000.00 ") == Decimal("48000.00")
    assert parse_decimal_amount("$1,234.56") == Decimal("1234.56")
    assert parse_decimal_amount("Rs. 7800") == Decimal("7800.00")
    assert parse_decimal_amount(15000) == Decimal("15000.00")


def test_parse_decimal_amount_invalid():
    # Negative values rejected
    with pytest.raises(ValueError, match="strictly positive"):
        parse_decimal_amount("-500.00")

    with pytest.raises(ValueError, match="strictly positive"):
        parse_decimal_amount("(500.00)")

    # Zero rejected
    with pytest.raises(ValueError, match="strictly positive"):
        parse_decimal_amount("0.00")

    # Non numeric
    with pytest.raises(ValueError, match="Invalid monetary amount"):
        parse_decimal_amount("abc_dollars")

    # Empty
    with pytest.raises(ValueError, match="Empty monetary amount"):
        parse_decimal_amount("  ")

    with pytest.raises(ValueError, match="Missing required"):
        parse_decimal_amount(None)


def test_parse_date_valid():
    assert parse_date("2026-10-05") == date(2026, 10, 5)
    assert parse_date("05/10/2026") == date(2026, 10, 5)
    assert parse_date("2026/10/05") == date(2026, 10, 5)
    assert parse_date("05-10-2026") == date(2026, 10, 5)


def test_parse_date_invalid():
    with pytest.raises(ValueError, match="Unable to parse date"):
        parse_date("2026-99-99")

    with pytest.raises(ValueError, match="Empty date"):
        parse_date("")

    with pytest.raises(ValueError, match="Missing date"):
        parse_date(None)


def test_extract_reference_tokens():
    tokens = extract_reference_tokens("Payment for INV-101 and B-2201")
    assert "INV-101" in tokens
    assert "INV101" in tokens
    assert "B-2201" in tokens
    assert "B2201" in tokens

    empty_tokens = extract_reference_tokens("Regular transfer without invoice number")
    assert len(empty_tokens) == 0
