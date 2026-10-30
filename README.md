# FinMatch: Transparent Invoice-to-Payment Reconciliation Engine

FinMatch is a production-grade, transparent, and auditable financial reconciliation backend written in Python. It ingests invoice and payment CSV files, normalizes business names and transaction identifiers, scores candidate matches using an explainable, deterministic evidence engine, provides human-in-the-loop review actions with an immutable audit trail, computes precise financial balances using strict `Decimal` arithmetic, and generates comprehensive reconciliation reports with benchmark evaluation metrics.

---

## 1. Project Architecture & Directory Structure

```text
FInMatch(original)/
├── backend/
│   ├── __init__.py               # Top-level exports
│   ├── auth.py                   # User/Admin registration, salted PBKDF2 hashing, and authentication
│   ├── models.py                 # Domain models (Invoice, Payment, Suggestion, Allocation, AuditEvent)
│   ├── normalizer.py             # Normalization, string sanitization, and strict Decimal & date parsing
│   ├── importer.py               # CSV ingestion, column aliasing, and row-level error validation
│   ├── matcher.py                # Deterministic, explainable rule-based evidence matching engine
│   ├── engine.py                 # Allocation business logic, balance calculators, duplicate/over-allocation safeguards
│   ├── reporting.py              # Reconciliation report generator and dataset evaluation metrics against ground truth
│   ├── service.py                # Unified ReconciliationService facade API (includes login & business registration)
│   ├── cli.py                    # Command-line interface for reconciliation, user management, and auth
│   └── storage/
│       ├── __init__.py
│       ├── db.py                 # SQLite database connection, schema DDL, user seeding, and migrations
│       └── repository.py         # Type-safe SQLite CRUD repository and user account queries
├── data/
│   ├── sample_invoices.csv       # Benchmark sample invoice CSV with valid, edge-case, and invalid rows
│   ├── sample_payments.csv       # Benchmark sample payment CSV with exact, partial, fuzzy, and ambiguous payments
│   ├── ground_truth_labels.csv   # Ground-truth match labels with rationale annotations
│   └── data_dictionary.md        # Complete data dictionary for all entities and columns
├── tests/
│   ├── conftest.py               # Shared test fixtures and in-memory test databases
│   ├── test_auth.py              # User/Admin login, registration, password hashing, and role restriction tests
│   ├── test_api_server.py        # REST API tests for /api/login, /api/register, and /api/businesses
│   ├── test_normalizer.py        # String cleaning, regex, and Decimal parsing unit tests
│   ├── test_importer.py          # Schema validation, alias resolution, and row error unit tests
│   ├── test_matcher.py           # Rule weights, evidence scoring, and ambiguity detection unit tests
│   ├── test_allocations.py       # Allocation safeguards, over-allocation prevention, and audit logging tests
│   ├── test_audit_and_balances.py# Decimal balance calculations and unresolved work categorization tests
│   ├── test_reporting_metrics.py # CSV export and precision/recall evaluation tests
│   └── test_service_end_to_end.py# Complete end-to-end integration test suite
├── server.py                     # Starlette/Uvicorn REST API server and static frontend host
├── dashboard_app.py              # Streamlit interactive web dashboard connected to ReconciliationService
├── requirements.txt              # Production and test dependencies
└── README.md                     # System documentation and operational runbook
```

---

## 2. SQLite Database Schema & Setup

FinMatch uses SQLite with foreign key enforcement (`PRAGMA foreign_keys = ON;`) and stores all monetary values as canonical `TEXT` representations (e.g. `'12500.00'`) to guarantee that floating-point rounding errors never corrupt financial amounts.

### Schema DDL

```sql
PRAGMA foreign_keys = ON;

-- 1. Import Batches
CREATE TABLE IF NOT EXISTS import_batches (
    batch_id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL, -- 'INVOICE' or 'PAYMENT'
    row_count INTEGER NOT NULL,
    valid_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    warning_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

-- 2. Row-Level Validation Errors (Traceability)
CREATE TABLE IF NOT EXISTS import_errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL REFERENCES import_batches(batch_id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    field_name TEXT,
    error_type TEXT NOT NULL,
    message TEXT NOT NULL,
    raw_data TEXT NOT NULL,
    is_warning INTEGER NOT NULL DEFAULT 0
);

-- 3. Invoices
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES import_batches(batch_id),
    row_index INTEGER NOT NULL,
    customer_id TEXT,
    customer_name TEXT NOT NULL,
    customer_name_normalized TEXT NOT NULL,
    amount TEXT NOT NULL, -- Exact Decimal string e.g. '12500.00'
    issue_date TEXT NOT NULL, -- 'YYYY-MM-DD'
    due_date TEXT,
    reference TEXT,
    note TEXT,
    raw_data TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 4. Payments
CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES import_batches(batch_id),
    row_index INTEGER NOT NULL,
    customer_id TEXT,
    customer_name TEXT,
    customer_name_normalized TEXT,
    amount TEXT NOT NULL, -- Exact Decimal string e.g. '12500.00'
    payment_date TEXT NOT NULL, -- 'YYYY-MM-DD'
    reference TEXT,
    payment_method TEXT,
    note TEXT,
    raw_data TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 5. Match Suggestions
CREATE TABLE IF NOT EXISTS match_suggestions (
    suggestion_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(invoice_id),
    payment_id TEXT NOT NULL REFERENCES payments(payment_id),
    score REAL NOT NULL,
    confidence_tier TEXT NOT NULL, -- 'HIGH', 'MEDIUM', 'LOW'
    is_ambiguous INTEGER NOT NULL,
    amount_mismatch INTEGER NOT NULL,
    explanation TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'CONFIRMED', 'REJECTED'
    created_at TEXT NOT NULL
);

-- 6. Review Decisions (Immutable Audit Trail)
CREATE TABLE IF NOT EXISTS review_decisions (
    decision_id TEXT PRIMARY KEY,
    suggestion_id TEXT,
    invoice_id TEXT NOT NULL REFERENCES invoices(invoice_id),
    payment_id TEXT NOT NULL REFERENCES payments(payment_id),
    action TEXT NOT NULL, -- 'CONFIRM', 'REJECT', 'MANUAL_ALLOCATION', 'UNALLOCATE'
    amount TEXT,
    reviewer TEXT NOT NULL,
    notes TEXT,
    timestamp TEXT NOT NULL
);

-- 7. Confirmed Allocations (Strict Balances Foundation)
CREATE TABLE IF NOT EXISTS confirmed_allocations (
    allocation_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(invoice_id),
    payment_id TEXT NOT NULL REFERENCES payments(payment_id),
    allocated_amount TEXT NOT NULL,
    confirmed_at TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    decision_id TEXT REFERENCES review_decisions(decision_id),
    notes TEXT
);

-- 8. Users & Registered Businesses (Authentication & RBAC)
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    mobile TEXT UNIQUE NOT NULL,
    business_name TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user', -- 'user' or 'admin'
    status TEXT NOT NULL DEFAULT 'Active', -- 'Active' or 'Disabled'
    created_at TEXT NOT NULL
);

-- Indexes for rapid lookup, auth, and balance calculations
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_mobile ON users(mobile);
CREATE INDEX IF NOT EXISTS idx_invoices_batch ON invoices(batch_id);
CREATE INDEX IF NOT EXISTS idx_payments_batch ON payments(batch_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_inv ON match_suggestions(invoice_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_pay ON match_suggestions(payment_id);
CREATE INDEX IF NOT EXISTS idx_allocations_inv ON confirmed_allocations(invoice_id);
CREATE INDEX IF NOT EXISTS idx_allocations_pay ON confirmed_allocations(payment_id);
```

### Database Initialization
The database schema initializes automatically on first connection through `DatabaseManager("finmatch.db")`. No external migrations or manual setup commands are required.

---

## 3. Setup and Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.15)
- Standard virtual environment or pip

### Install Dependencies
```bash
pip install -r requirements.txt
```

*Direct dependencies installed:*
- `pandas>=2.0.0`
- `RapidFuzz>=3.0.0`
- `pytest>=7.0.0`
- `streamlit>=1.30.0`

---

## 4. Running Automated Tests

Run the full pytest suite with verbose output:

```bash
python -m pytest -v -o pythonpath=.
```

### Coverage Highlights
- **`test_normalizer.py`**: Validates decimal parsing against negative inputs, currency prefixes (`₹`, `$`, `Rs.`), accounting parentheses, date formats, and suffix removal.
- **`test_importer.py`**: Verifies CSV ingestion, column alias fallback, missing required fields, row-level error reporting, duplicate ID detection, and due-date warnings.
- **`test_matcher.py`**: Tests exact reference prioritization, fuzzy name similarity, partial payment amount handling, date proximity scoring, and the crucial rule: *equal amounts alone are never high confidence*.
- **`test_allocations.py`**: Proves that suggestions never alter balances until confirmed, prevents double allocation of the same payment, enforces available balance bounds, rejects duplicate confirmations, and preserves the decision audit trail.
- **`test_audit_and_balances.py`**: Demonstrates zero float rounding error across multiple micro-allocations, and categorizes unresolved items.
- **`test_reporting_metrics.py`**: Confirms CSV export schema and benchmark precision/recall evaluation.
- **`test_service_end_to_end.py`**: Exercises the complete end-to-end workflow on the sample dataset.

---

## 5. End-to-End Workflow & Example Output

### Option A: Interactive Streamlit Dashboard

Run the Streamlit application:
```bash
streamlit run dashboard_app.py
```

The web dashboard provides:
1. **Ingestion & Validation**: Upload CSVs or click **"Load Supplied Labeled Sample Dataset"** to load the benchmark data.
2. **Match Suggestions & Review**: Inspect explainable candidate cards, view breakdown scores, and one-click confirm, reject, or assign custom amounts.
3. **Balances & Unresolved Work**: Real-time KPI tiles for Total Invoiced, Confirmed Settled, Outstanding Unpaid, and Unallocated Payments, plus drill-downs for unmatched invoices, ambiguous candidates, and import errors.
4. **Reconciliation Report**: View and download the auditable CSV report.
5. **Dataset Evaluation Metrics**: Compute precision, recall, F1-score, and review definitions against `data/ground_truth_labels.csv`.

---

### Option B: Command-Line Interface (CLI)

The CLI supports scripting and headless automation:

```bash
# User Management & Authentication
python backend/cli.py list-users
python backend/cli.py register-user --business "Apex Traders" --owner "Vikram" --email "vikram@apex.com" --mobile "9822334455" --password "secret123" --role "user"
python backend/cli.py login-test 9822334455 secret123

# Ingestion & Reconciliation
python backend/cli.py import-invoices data/sample_invoices.csv
python backend/cli.py import-payments data/sample_payments.csv
python backend/cli.py suggest
python backend/cli.py balances
python backend/cli.py unresolved
python backend/cli.py export-report -o reconciliation_report.csv
python backend/cli.py evaluate data/ground_truth_labels.csv --min-score 60.0
```

---

### Option C: REST API Server & Web Frontend

Run the unified API server to host the HTML/JS frontend and serve live REST endpoints:

```bash
python server.py
```
- **Web Frontend**: `http://localhost:8000/index.html` (or `http://localhost:8000/`)
- **Login API**: `POST http://localhost:8000/api/login` (Body: `{"id": "...", "pw": "...", "role": "user"}`)
- **Register Business API**: `POST http://localhost:8000/api/register` (Body: `{"business_name": "...", "owner_name": "...", "email": "...", "mobile": "...", "password": "..."}`)
- **List Businesses API**: `GET http://localhost:8000/api/businesses`
- **Health Check**: `GET http://localhost:8000/api/health`

### Sample CLI Run Output

```text
=== Imported Invoices from 'data/sample_invoices.csv' ===
Batch ID: 8520561f-e7c3-43dc-b2d3-5541f3f906fe
Total Rows: 15 | Valid Records: 12 | Error Rows: 3 | Warnings: 0

[!] Import Errors / Warnings:
  - Row 14 [ERROR]: amount -> Monetary amount must be strictly positive (> 0), got '-5000.00' for invoice amount
  - Row 15 [ERROR]: invoice_id -> Invoice ID cannot be empty.
  - Row 16 [ERROR]: issue_date -> Unable to parse date 'invalid-date' for issue date.

Generated 13 explainable match suggestions.
[HIGH] Inv: INV-101 <-> Pay: PAY-501 | Score: 100.0 | ID: 32f7cb1a-9d95-40e1-97e3-a9a6cf34ef5c
    Reason: Score 100.0/100 (HIGH) [HIGH CONFIDENCE: Strong identity & reference corroboration]: Payment reference/note explicitly references Invoice ID 'INV-101' (+40 pts); Normalized customer names match exactly ('Sharma Kirana Store') (+28 pts); Exact monetary amount match (12500.00) (+25 pts); Payment received 2 days after invoice date (+7 pts)

=== FINMATCH BALANCES ===
Invoices Total:    345400.00
Invoices Settled:  12500.00
Invoices Unpaid:   332900.00
-----------------------------------
Payments Total:    188000.00
Payments Allocated:12500.00
Payments Unalloc:  175500.00

=== DATASET EVALUATION METRICS ===
Threshold Used:        60.0
Ground Truth Matches:  9
System Suggested:      8
True Positives (TP):   8
False Positives (FP):  0
False Negatives (FN):  1
Precision:             100.00%
Recall (Accuracy):     88.89%
F1-Score:              0.9412
Unresolved Cases Count:31
```

### Sample Reconciliation Report CSV (`reconciliation_report.csv`)

| record_type | invoice_id | customer_name | invoice_amount | payment_id | payment_customer | payment_amount | allocated_amount | invoice_outstanding_balance | allocation_status | reviewer | explanation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `CONFIRMED_MATCH` | `INV-101` | Sharma Kirana Store | `12500.00` | `PAY-501` | Sharma Kirana | `12500.00` | `12500.00` | `0.00` | `PAID` | SENIOR_ACCOUNTANT | Score 100.0/100 (HIGH): Payment references 'INV-101' |
| `UNMATCHED_INVOICE` | `INV-109` | Pant Cloth House | `56000.00` | | | | `0.00` | `56000.00` | `UNPAID` | | No confirmed payment allocated. |
| `UNALLOCATED_PAYMENT` | | | | `PAY-511` | Unrelated Advance Payer | `25000.00` | `0.00` | | `UNALLOCATED` | | Unsolicited deposit with no invoice. |

---

## 6. Business Logic, Weights, and Metric Definitions

### A. Matching Weights and Evidence Dimensions
Total possible score is 100.0:

1. **Exact Reference Match (Max 40.0 pts)**
   - Payment note or reference code explicitly cites the Invoice ID (e.g. `INV-101`) or quotation number (`B-2201`).
   - Strongest individual signal in financial matching.
2. **Customer Identity Match (Max 30.0 pts)**
   - Exact Customer ID match: 30.0 pts.
   - Exact normalized customer name match: 28.0 pts.
   - Fuzzy customer name match (RapidFuzz ratio $\ge 70\%$): Scaled linearly up to 22.0 pts.
   - Unrecognized / unmatched payer: 0.0 pts.
3. **Monetary Amount Match (Max 25.0 pts)**
   - Exact match (`payment.amount == invoice.amount`): 25.0 pts.
   - Partial payment (`payment.amount < invoice.amount`): 12.0 pts (flagged: `amount_mismatch = True`).
   - Overpayment (`payment.amount > invoice.amount`): 2.0 pts (flagged: `amount_mismatch = True`).
4. **Date Sequence & Proximity (Max 7.0 pts)**
   - Paid within 30 days after invoice issue: 7.0 pts.
   - Paid between 31 and 45 days after invoice issue: 4.2 pts.
   - Paid after 45 days: 1.4 pts.
   - Paid before invoice issue date: 0.0 pts (and logged as an anomaly).

### B. Confidence Interpretation & Safeguards
- **HIGH Confidence (Score $\ge 85.0$)**:
  - Requires **either** an exact reference match **or** an exact customer name match corroborating an exact amount.
  - Must not be ambiguous and must have zero amount mismatch.
- **MEDIUM Confidence (Score 60.0 to 84.9)**:
  - Strong partial payments or valid matches lacking an explicit invoice reference code.
- **LOW Confidence (Score 25.0 to 59.9)**:
  - Requires manual human verification.
- **Ambiguity Safeguard**:
  - If a payment matches two or more invoices within 5.0 points of each other (e.g. equal amounts with no customer identity signal), the candidates are strictly flagged as `is_ambiguous = True` and downgraded from HIGH confidence.
  - **Core Financial Law:** Equal monetary amounts alone **never** justify an automated or high-confidence match.

### C. Metric Definitions & Formulas
1. **Precision**:
   $$\text{Precision} = \frac{\text{True Positives}}{\text{True Positives} + \text{False Positives}}$$
   *Proportion of generated match suggestions above threshold that represent authorized, valid reconciliation pairs.*
2. **Recall (Suggestion Accuracy)**:
   $$\text{Recall} = \frac{\text{True Positives}}{\text{True Positives} + \text{False Negatives}}$$
   *Proportion of actual ground-truth matching pairs that successfully received a suggestion above threshold.*
3. **Unresolved Cases**:
   $$\text{Unresolved Count} = \text{Unmatched Invoices} + \text{Unallocated Payments} + \text{Ambiguous Candidates} + \text{Amount Mismatches}$$
4. **Exclusions**:
   - Rows failing CSV schema validation (e.g. negative amounts, malformed dates) are quarantined in `import_errors` and excluded from precision/recall denominators.

### D. Known Limitations & Prototype Boundaries
1. **Single Currency**: Currently optimized for single-currency operations (e.g. INR/USD); FX rate conversion spreads are out of prototype scope.
2. **Many-to-Many Aggregation**: The engine supports one-to-one matches and sequential partial allocations (many payments toward one invoice, or one payment split across invoices via explicit amounts). Automatic combinatorial subset-sum optimization (e.g. 3 small payments together settling 1 invoice) requires manual assignment in this 24-hour prototype.
