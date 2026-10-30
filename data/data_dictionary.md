# FinMatch Data Dictionary

This document details the schema definitions, field validation rules, data types, and ground truth definitions used in FinMatch reconciliation.

---

## 1. Invoices Dataset (`sample_invoices.csv`)

| Field Name | Type | Required | Description / Constraints | Example |
| :--- | :--- | :--- | :--- | :--- |
| `invoice_id` | String | **Yes** | Unique primary identifier of the invoice. Cannot be empty or duplicated within the dataset. | `INV-101` |
| `customer_name` | String | **Yes** | Legal or trading name of the billed customer. Normalized internally for fuzzy matching. | `Sharma Kirana Store` |
| `amount` | Decimal | **Yes** | Total invoiced amount. Parsed strictly as `Decimal('0.01')`. Must be strictly positive (`> 0.00`). | `12500.00` |
| `issue_date` | Date | **Yes** | Date invoice was generated. Supported formats: `YYYY-MM-DD`, `DD/MM/YYYY`. | `2026-10-05` |
| `due_date` | Date | No | Expected payment due date. If present and `< issue_date`, flagged as a non-fatal warning. | `2026-10-20` |
| `reference` | String | No | Secondary reference code or bill number (e.g., quotation number, order number). | `B-2201` |
| `note` | String | No | Item line summary or remarks. | `Grocery supplies invoice` |

---

## 2. Payments Dataset (`sample_payments.csv`)

| Field Name | Type | Required | Description / Constraints | Example |
| :--- | :--- | :--- | :--- | :--- |
| `payment_id` | String | **Yes** | Unique transaction identifier. Cannot be empty or duplicated. | `PAY-501` |
| `customer_name` | String | No | Payer/Remitter name from the bank statement or receipt. | `Sharma Kirana` |
| `amount` | Decimal | **Yes** | Total received amount. Parsed strictly as `Decimal('0.01')`. Must be strictly positive (`> 0.00`). | `12500.00` |
| `payment_date` | Date | **Yes** | Date funds were received/cleared. Supported formats: `YYYY-MM-DD`, `DD/MM/YYYY`. | `2026-10-07` |
| `reference` | String | No | Bank UTR, cheque number, or payment reference. | `UPI4382910` |
| `payment_method` | String | No | Channel used (`UPI`, `NEFT`, `Cash`, `Cheque`, `Card`). | `UPI` |
| `note` | String | No | Narrative or description from bank feed, often containing invoice reference tokens. | `Settlement for INV-101` |

---

## 3. Ground Truth Labels (`ground_truth_labels.csv`)

| Column | Type | Description |
| :--- | :--- | :--- |
| `invoice_id` | String | Foreign key to `invoices.invoice_id`. |
| `payment_id` | String | Foreign key to `payments.payment_id`. |
| `is_match` | Integer (0 or 1) | `1` indicates an authorized, valid reconciliation pair; `0` indicates a non-match or ambiguous pairing. |
| `match_type` | String | Categorization of match rationale (`EXACT_REFERENCE`, `PARTIAL_REFERENCE`, `FUZZY_CUSTOMER`, `AMBIGUOUS_AMOUNT_ONLY`, `NO_MATCH`). |
| `notes` | String | Ground-truth explanation. |

### Labeling Methodology & Principles
1. **Traceable References**: When payment narration contains explicit invoice identifiers (e.g. `INV-101` or `B-2201`), it is labeled `is_match = 1`.
2. **Partial Payments**: Payments matching the customer name and referencing the invoice but for less than the total invoice amount are true matches (`is_match = 1`, `PARTIAL_REFERENCE`).
3. **Ambiguous Amount-Only Collisions**: Payments where the amount happens to match one or more invoices but the payer name is unrelated (e.g. `PAY-510` of ₹6,800 from "Ramesh" vs `INV-106` Joshi Dairy and `INV-112` Sharma Kirana) are labeled `is_match = 0`. Financial reconciliation engines must **never** assume a match is true solely based on equal monetary amounts.
4. **Invalid Records Exclusion**: Rows with missing IDs, negative amounts, or unparseable dates are logged as row-level errors and excluded from suggestion evaluation.
