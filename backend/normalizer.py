"""
Data normalization, string sanitization, and strict Decimal & Date parsing.
Never converts monetary amounts through float.
"""

from __future__ import annotations
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional, Set

# Common business suffixes and honorifics that vary between bank statements and invoices
BUSINESS_SUFFIXES = {
    "pvt", "ltd", "limited", "private", "traders", "trading", "store", "stores",
    "co", "corp", "corporation", "company", "enterprises", "enterprise", "hall",
    "centre", "center", "clinic", "dr", "mr", "mrs", "ms", "tuition", "wholesale",
    "electricals", "hardware", "medical", "sweets", "dairy", "auto", "parts", "kirana"
}

PUNCT_RE = re.compile(r"[^\w\s]")
MULTI_SPACE_RE = re.compile(r"\s+")
INVOICE_PATTERN = re.compile(r"\b(INV[-_]?\d+|B[-_]?\d+|BILL[-_]?\d+)\b", re.IGNORECASE)


def normalize_whitespace(text: Optional[Any]) -> str:
    """Strip leading/trailing whitespace and collapse internal consecutive spaces."""
    if text is None:
        return ""
    s = str(text).strip()
    return MULTI_SPACE_RE.sub(" ", s)


def normalize_customer_name(name: Optional[Any]) -> str:
    """
    Produce a canonical version of a customer name for matching:
    1. Lowercase
    2. Remove punctuation
    3. Remove common business entity descriptors (e.g. Pvt Ltd, Store, etc.)
    4. Collapse spaces
    """
    if name is None:
        return ""
    text = str(name).lower()
    # Remove punctuation
    text = PUNCT_RE.sub(" ", text)
    tokens = [t for t in text.split() if t]
    
    # Filter out common stop-words/suffixes if length > 1 token
    filtered = [t for t in tokens if t not in BUSINESS_SUFFIXES]
    # If filtering removed everything, keep the tokens
    final_tokens = filtered if filtered else tokens
    return " ".join(final_tokens)


def parse_decimal_amount(value: Any, field_name: str = "amount", allow_negative: bool = False) -> Decimal:
    """
    Safely parse monetary amounts into Decimal with exactly 2 decimal places.
    Never passes through float.
    Accepts strings with currency signs (₹, $, €, £), thousands separators (,),
    and accounting negatives (100.00).
    """
    if value is None:
        raise ValueError(f"Missing required monetary amount for {field_name}")
    
    val_str = str(value).strip()
    if not val_str or val_str.lower() in ("nan", "null", "none"):
        raise ValueError(f"Empty monetary amount for {field_name}")

    # Remove currency signs and spaces
    for symbol in ["₹", "$", "€", "£", "rs.", "rs", "inr", "usd", "eur"]:
        val_str = re.sub(re.escape(symbol), "", val_str, flags=re.IGNORECASE)
    val_str = val_str.strip()

    # Check for accounting negative in parentheses: (123.45) -> -123.45
    is_paren_neg = False
    if val_str.startswith("(") and val_str.endswith(")"):
        is_paren_neg = True
        val_str = val_str[1:-1].strip()

    # Remove commas
    val_str = val_str.replace(",", "")

    if is_paren_neg:
        val_str = "-" + val_str

    try:
        dec = Decimal(val_str)
    except InvalidOperation:
        raise ValueError(f"Invalid monetary amount format '{value}' for {field_name}")

    if not allow_negative and dec <= Decimal("0"):
        raise ValueError(f"Monetary amount must be strictly positive (> 0), got '{dec}' for {field_name}")

    # Quantize to 2 decimal places
    return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_date(value: Any, field_name: str = "date") -> date:
    """
    Parse a date string or object into a python datetime.date.
    Supported string formats:
    - YYYY-MM-DD
    - DD/MM/YYYY
    - MM/DD/YYYY
    - DD-MM-YYYY
    - YYYY/MM/DD
    """
    if value is None:
        raise ValueError(f"Missing date for {field_name}")
    
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    val_str = str(value).strip()
    if not val_str or val_str.lower() in ("nan", "null", "none"):
        raise ValueError(f"Empty date for {field_name}")

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d %b %Y",
        "%d %B %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Unable to parse date '{val_str}' for {field_name}. Expected format: YYYY-MM-DD or DD/MM/YYYY")


def extract_reference_tokens(text: Optional[str]) -> Set[str]:
    """
    Extract invoice reference tokens like 'INV-101' or 'B-2201' from payment notes or references.
    """
    if not text:
        return set()
    matches = INVOICE_PATTERN.findall(text)
    # Standardize hyphens: e.g. INV_101 -> INV-101
    normalized = set()
    for m in matches:
        canon = m.upper().replace("_", "-")
        normalized.add(canon)
        # Also include without hyphen e.g. INV101
        normalized.add(canon.replace("-", ""))
    return normalized
