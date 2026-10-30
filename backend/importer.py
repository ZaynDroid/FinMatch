"""
CSV Importer and Validator for Invoices and Payments.
Uses pandas with strict string dtypes to prevent float conversions.
Captures row-level errors and warnings without silently dropping invalid rows.
"""

from __future__ import annotations
import os
import uuid
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd

from backend.models import ImportBatch, ImportRowError, Invoice, Payment
from backend.normalizer import (
    normalize_whitespace,
    normalize_customer_name,
    parse_decimal_amount,
    parse_date,
)

# Column mapping aliases
INVOICE_COLUMN_ALIASES = {
    "invoice_id": ["invoice_id", "inv_id", "id", "invoice_number", "invoiceno", "bill_no"],
    "customer_name": ["customer_name", "customer", "cust", "client_name", "client", "buyer"],
    "customer_id": ["customer_id", "cust_id", "client_id"],
    "amount": ["amount", "amt", "total", "invoice_amount", "gross_amount", "billed_amount"],
    "issue_date": ["issue_date", "invoice_date", "date", "inv_date", "billed_date"],
    "due_date": ["due_date", "due", "payment_due_date"],
    "reference": ["reference", "ref", "ref_no", "invoice_ref", "bill_ref"],
    "note": ["note", "notes", "description", "memo", "remarks"],
}

PAYMENT_COLUMN_ALIASES = {
    "payment_id": ["payment_id", "pay_id", "id", "transaction_id", "txn_id", "receipt_no"],
    "customer_name": ["customer_name", "customer", "from", "payer", "remitter", "sender"],
    "customer_id": ["customer_id", "cust_id", "client_id"],
    "amount": ["amount", "amt", "paid_amount", "received_amount", "credit"],
    "payment_date": ["payment_date", "date", "pay_date", "transaction_date", "txn_date"],
    "reference": ["reference", "ref", "utr", "txn_ref", "reference_no", "cheque_no"],
    "payment_method": ["payment_method", "mode", "method", "channel", "type"],
    "note": ["note", "notes", "description", "memo", "remarks"],
}


def _resolve_column_map(df_columns: List[str], alias_map: Dict[str, List[str]]) -> Dict[str, str]:
    """
    Map standardized internal attribute names to actual dataframe column names.
    Returns {internal_name: csv_column_name}
    """
    col_lookup = {str(col).strip().lower(): col for col in df_columns}
    resolved = {}
    for canonical_name, aliases in alias_map.items():
        for alias in aliases:
            cleaned_alias = alias.lower()
            if cleaned_alias in col_lookup:
                resolved[canonical_name] = col_lookup[cleaned_alias]
                break
    return resolved


def load_csv_dataframe(source: Union[str, StringIO, bytes]) -> pd.DataFrame:
    """
    Read CSV into pandas ensuring all columns are loaded as object/strings
    to strictly prevent float parsing or precision truncation.
    """
    if isinstance(source, bytes):
        source = StringIO(source.decode("utf-8-sig", errors="replace"))
    
    # dtype=str and keep_default_na=False avoids converting "NA" or empty strings to float NaN
    df = pd.read_csv(source, dtype=str, keep_default_na=False, skipinitialspace=True)
    # Strip whitespace from column headers
    df.columns = [str(c).strip() for c in df.columns]
    return df


class CSVImporter:
    """
    Validates, normalizes, and packages invoice and payment CSV data into domain entities.
    """

    @staticmethod
    def import_invoices(
        source: Union[str, StringIO, bytes],
        file_name: str = "invoices.csv",
        existing_invoice_ids: Optional[set[str]] = None,
    ) -> Tuple[ImportBatch, List[Invoice], List[ImportRowError]]:
        """
        Import and validate an invoices CSV.
        """
        batch_id = str(uuid.uuid4())
        try:
            df = load_csv_dataframe(source)
        except Exception as e:
            batch = ImportBatch(
                batch_id=batch_id,
                file_name=file_name,
                file_type="INVOICE",
                row_count=0,
                valid_count=0,
                error_count=1,
                warning_count=0,
            )
            err = ImportRowError(
                error_id=None,
                batch_id=batch_id,
                row_index=0,
                field_name=None,
                error_type="FILE_READ_ERROR",
                message=f"Failed to read CSV: {str(e)}",
                raw_data={},
            )
            return batch, [], [err]

        col_map = _resolve_column_map(df.columns.tolist(), INVOICE_COLUMN_ALIASES)
        errors: List[ImportRowError] = []
        valid_invoices: List[Invoice] = []
        seen_in_file: set[str] = set()
        existing_ids = existing_invoice_ids or set()
        warnings_count = 0

        # Validate mandatory column presence
        mandatory = ["invoice_id", "customer_name", "amount", "issue_date"]
        missing_mandatory = [col for col in mandatory if col not in col_map]
        if missing_mandatory:
            batch = ImportBatch(
                batch_id=batch_id,
                file_name=file_name,
                file_type="INVOICE",
                row_count=len(df),
                valid_count=0,
                error_count=len(missing_mandatory),
                warning_count=0,
            )
            for m in missing_mandatory:
                errors.append(
                    ImportRowError(
                        error_id=None,
                        batch_id=batch_id,
                        row_index=0,
                        field_name=m,
                        error_type="MISSING_COLUMN",
                        message=f"Required column '{m}' (or alias) is missing from file.",
                        raw_data={"headers": df.columns.tolist()},
                    )
                )
            return batch, [], errors

        for idx, row in df.iterrows():
            row_idx = int(idx) + 2  # 1-based index (header is line 1)
            raw_dict = row.to_dict()
            row_errors: List[ImportRowError] = []

            # 1. Invoice ID
            raw_id = normalize_whitespace(row.get(col_map["invoice_id"]))
            if not raw_id:
                row_errors.append(
                    ImportRowError(
                        error_id=None,
                        batch_id=batch_id,
                        row_index=row_idx,
                        field_name="invoice_id",
                        error_type="MISSING_FIELD",
                        message="Invoice ID cannot be empty.",
                        raw_data=raw_dict,
                    )
                )
            elif raw_id in seen_in_file:
                row_errors.append(
                    ImportRowError(
                        error_id=None,
                        batch_id=batch_id,
                        row_index=row_idx,
                        field_name="invoice_id",
                        error_type="DUPLICATE_ID",
                        message=f"Duplicate invoice ID '{raw_id}' in current batch.",
                        raw_data=raw_dict,
                    )
                )
            elif raw_id in existing_ids:
                row_errors.append(
                    ImportRowError(
                        error_id=None,
                        batch_id=batch_id,
                        row_index=row_idx,
                        field_name="invoice_id",
                        error_type="DUPLICATE_ID",
                        message=f"Invoice ID '{raw_id}' already exists in system.",
                        raw_data=raw_dict,
                    )
                )
            else:
                seen_in_file.add(raw_id)

            # 2. Customer Name
            raw_customer = normalize_whitespace(row.get(col_map["customer_name"]))
            if not raw_customer:
                row_errors.append(
                    ImportRowError(
                        error_id=None,
                        batch_id=batch_id,
                        row_index=row_idx,
                        field_name="customer_name",
                        error_type="MISSING_FIELD",
                        message="Customer name cannot be empty.",
                        raw_data=raw_dict,
                    )
                )

            # 3. Amount (Strict Decimal)
            raw_amount = row.get(col_map["amount"])
            parsed_amount = None
            try:
                parsed_amount = parse_decimal_amount(raw_amount, field_name="invoice amount")
            except ValueError as ve:
                row_errors.append(
                    ImportRowError(
                        error_id=None,
                        batch_id=batch_id,
                        row_index=row_idx,
                        field_name="amount",
                        error_type="INVALID_AMOUNT",
                        message=str(ve),
                        raw_data=raw_dict,
                    )
                )

            # 4. Issue Date
            raw_issue_date = row.get(col_map["issue_date"])
            parsed_issue_date = None
            try:
                parsed_issue_date = parse_date(raw_issue_date, field_name="issue date")
            except ValueError as ve:
                row_errors.append(
                    ImportRowError(
                        error_id=None,
                        batch_id=batch_id,
                        row_index=row_idx,
                        field_name="issue_date",
                        error_type="INVALID_DATE",
                        message=str(ve),
                        raw_data=raw_dict,
                    )
                )

            # 5. Optional Due Date
            parsed_due_date = None
            if "due_date" in col_map:
                raw_due_date = normalize_whitespace(row.get(col_map["due_date"]))
                if raw_due_date:
                    try:
                        parsed_due_date = parse_date(raw_due_date, field_name="due date")
                        if parsed_issue_date and parsed_due_date < parsed_issue_date:
                            warnings_count += 1
                            errors.append(
                                ImportRowError(
                                    error_id=None,
                                    batch_id=batch_id,
                                    row_index=row_idx,
                                    field_name="due_date",
                                    error_type="DATE_WARNING",
                                    message=f"Due date ({parsed_due_date}) is earlier than issue date ({parsed_issue_date}).",
                                    raw_data=raw_dict,
                                    is_warning=True,
                                )
                            )
                    except ValueError as ve:
                        row_errors.append(
                            ImportRowError(
                                error_id=None,
                                batch_id=batch_id,
                                row_index=row_idx,
                                field_name="due_date",
                                error_type="INVALID_DATE",
                                message=str(ve),
                                raw_data=raw_dict,
                            )
                        )

            # Optional reference & note & customer_id
            customer_id = (
                normalize_whitespace(row.get(col_map["customer_id"]))
                if "customer_id" in col_map
                else None
            ) or None
            reference = (
                normalize_whitespace(row.get(col_map["reference"]))
                if "reference" in col_map
                else None
            ) or None
            note = (
                normalize_whitespace(row.get(col_map["note"]))
                if "note" in col_map
                else None
            ) or None

            if row_errors:
                errors.extend(row_errors)
            else:
                # Valid Invoice record
                inv_obj = Invoice(
                    invoice_id=raw_id,
                    batch_id=batch_id,
                    row_index=row_idx,
                    customer_id=customer_id,
                    customer_name=raw_customer,
                    customer_name_normalized=normalize_customer_name(raw_customer),
                    amount=parsed_amount,  # Guaranteed Decimal
                    issue_date=parsed_issue_date,
                    due_date=parsed_due_date,
                    reference=reference,
                    note=note,
                    raw_data=raw_dict,
                )
                valid_invoices.append(inv_obj)

        error_rows_count = len({e.row_index for e in errors if not e.is_warning})
        batch = ImportBatch(
            batch_id=batch_id,
            file_name=file_name,
            file_type="INVOICE",
            row_count=len(df),
            valid_count=len(valid_invoices),
            error_count=error_rows_count,
            warning_count=warnings_count,
        )
        return batch, valid_invoices, errors

    @staticmethod
    def import_payments(
        source: Union[str, StringIO, bytes],
        file_name: str = "payments.csv",
        existing_payment_ids: Optional[set[str]] = None,
    ) -> Tuple[ImportBatch, List[Payment], List[ImportRowError]]:
        """
        Import and validate a payments CSV.
        """
        batch_id = str(uuid.uuid4())
        try:
            df = load_csv_dataframe(source)
        except Exception as e:
            batch = ImportBatch(
                batch_id=batch_id,
                file_name=file_name,
                file_type="PAYMENT",
                row_count=0,
                valid_count=0,
                error_count=1,
                warning_count=0,
            )
            err = ImportRowError(
                error_id=None,
                batch_id=batch_id,
                row_index=0,
                field_name=None,
                error_type="FILE_READ_ERROR",
                message=f"Failed to read CSV: {str(e)}",
                raw_data={},
            )
            return batch, [], [err]

        col_map = _resolve_column_map(df.columns.tolist(), PAYMENT_COLUMN_ALIASES)
        errors: List[ImportRowError] = []
        valid_payments: List[Payment] = []
        seen_in_file: set[str] = set()
        existing_ids = existing_payment_ids or set()
        warnings_count = 0

        # Validate mandatory columns
        mandatory = ["payment_id", "amount", "payment_date"]
        missing_mandatory = [col for col in mandatory if col not in col_map]
        if missing_mandatory:
            batch = ImportBatch(
                batch_id=batch_id,
                file_name=file_name,
                file_type="PAYMENT",
                row_count=len(df),
                valid_count=0,
                error_count=len(missing_mandatory),
                warning_count=0,
            )
            for m in missing_mandatory:
                errors.append(
                    ImportRowError(
                        error_id=None,
                        batch_id=batch_id,
                        row_index=0,
                        field_name=m,
                        error_type="MISSING_COLUMN",
                        message=f"Required column '{m}' (or alias) is missing from file.",
                        raw_data={"headers": df.columns.tolist()},
                    )
                )
            return batch, [], errors

        for idx, row in df.iterrows():
            row_idx = int(idx) + 2
            raw_dict = row.to_dict()
            row_errors: List[ImportRowError] = []

            # 1. Payment ID
            raw_id = normalize_whitespace(row.get(col_map["payment_id"]))
            if not raw_id:
                row_errors.append(
                    ImportRowError(
                        error_id=None,
                        batch_id=batch_id,
                        row_index=row_idx,
                        field_name="payment_id",
                        error_type="MISSING_FIELD",
                        message="Payment ID cannot be empty.",
                        raw_data=raw_dict,
                    )
                )
            elif raw_id in seen_in_file:
                row_errors.append(
                    ImportRowError(
                        error_id=None,
                        batch_id=batch_id,
                        row_index=row_idx,
                        field_name="payment_id",
                        error_type="DUPLICATE_ID",
                        message=f"Duplicate payment ID '{raw_id}' in current batch.",
                        raw_data=raw_dict,
                    )
                )
            elif raw_id in existing_ids:
                row_errors.append(
                    ImportRowError(
                        error_id=None,
                        batch_id=batch_id,
                        row_index=row_idx,
                        field_name="payment_id",
                        error_type="DUPLICATE_ID",
                        message=f"Payment ID '{raw_id}' already exists in system.",
                        raw_data=raw_dict,
                    )
                )
            else:
                seen_in_file.add(raw_id)

            # 2. Amount
            raw_amount = row.get(col_map["amount"])
            parsed_amount = None
            try:
                parsed_amount = parse_decimal_amount(raw_amount, field_name="payment amount")
            except ValueError as ve:
                row_errors.append(
                    ImportRowError(
                        error_id=None,
                        batch_id=batch_id,
                        row_index=row_idx,
                        field_name="amount",
                        error_type="INVALID_AMOUNT",
                        message=str(ve),
                        raw_data=raw_dict,
                    )
                )

            # 3. Payment Date
            raw_date = row.get(col_map["payment_date"])
            parsed_date = None
            try:
                parsed_date = parse_date(raw_date, field_name="payment date")
            except ValueError as ve:
                row_errors.append(
                    ImportRowError(
                        error_id=None,
                        batch_id=batch_id,
                        row_index=row_idx,
                        field_name="payment_date",
                        error_type="INVALID_DATE",
                        message=str(ve),
                        raw_data=raw_dict,
                    )
                )

            # Optional fields
            customer_name = (
                normalize_whitespace(row.get(col_map["customer_name"]))
                if "customer_name" in col_map
                else None
            ) or None
            customer_id = (
                normalize_whitespace(row.get(col_map["customer_id"]))
                if "customer_id" in col_map
                else None
            ) or None
            reference = (
                normalize_whitespace(row.get(col_map["reference"]))
                if "reference" in col_map
                else None
            ) or None
            payment_method = (
                normalize_whitespace(row.get(col_map["payment_method"]))
                if "payment_method" in col_map
                else None
            ) or None
            note = (
                normalize_whitespace(row.get(col_map["note"]))
                if "note" in col_map
                else None
            ) or None

            if row_errors:
                errors.extend(row_errors)
            else:
                pay_obj = Payment(
                    payment_id=raw_id,
                    batch_id=batch_id,
                    row_index=row_idx,
                    customer_id=customer_id,
                    customer_name=customer_name,
                    customer_name_normalized=normalize_customer_name(customer_name) if customer_name else None,
                    amount=parsed_amount,
                    payment_date=parsed_date,
                    reference=reference,
                    payment_method=payment_method,
                    note=note,
                    raw_data=raw_dict,
                )
                valid_payments.append(pay_obj)

        error_rows_count = len({e.row_index for e in errors if not e.is_warning})
        batch = ImportBatch(
            batch_id=batch_id,
            file_name=file_name,
            file_type="PAYMENT",
            row_count=len(df),
            valid_count=len(valid_payments),
            error_count=error_rows_count,
            warning_count=warnings_count,
        )
        return batch, valid_payments, errors
