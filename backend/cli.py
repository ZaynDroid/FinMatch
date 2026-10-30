"""
Command-Line Interface for FinMatch reconciliation backend.
Provides quick commands for import, suggestions, human review, reporting, and evaluation.
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from decimal import Decimal

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.service import ReconciliationService


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="finmatch",
        description="FinMatch: Transparent Invoice-to-Payment Reconciliation Engine",
    )
    parser.add_argument("--db", default="finmatch.db", help="Path to SQLite database file")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: import-invoices
    p_inv = subparsers.add_parser("import-invoices", help="Import invoices CSV file")
    p_inv.add_argument("file", help="Path to invoices CSV")

    # Command: import-payments
    p_pay = subparsers.add_parser("import-payments", help="Import payments CSV file")
    p_pay.add_argument("file", help="Path to payments CSV")

    # Command: suggest
    p_sug = subparsers.add_parser("suggest", help="Generate explainable match suggestions")

    # Command: list-suggestions
    p_ls = subparsers.add_parser("list-suggestions", help="List match suggestions")
    p_ls.add_argument("--status", choices=["PENDING", "CONFIRMED", "REJECTED"], help="Filter by status")
    p_ls.add_argument("--tier", choices=["HIGH", "MEDIUM", "LOW"], help="Filter by confidence tier")

    # Command: confirm
    p_conf = subparsers.add_parser("confirm", help="Confirm a match suggestion")
    p_conf.add_argument("suggestion_id", help="UUID of suggestion to confirm")
    p_conf.add_argument("--reviewer", default="CLI_USER", help="Reviewer username")
    p_conf.add_argument("--amount", type=str, help="Explicit allocation amount (optional)")
    p_conf.add_argument("--notes", help="Optional review notes")

    # Command: reject
    p_rej = subparsers.add_parser("reject", help="Reject a match suggestion")
    p_rej.add_argument("suggestion_id", help="UUID of suggestion to reject")
    p_rej.add_argument("--reviewer", default="CLI_USER", help="Reviewer username")
    p_rej.add_argument("--notes", help="Optional review notes")

    # Command: manual-allocate
    p_man = subparsers.add_parser("manual-allocate", help="Manually allocate payment to invoice")
    p_man.add_argument("invoice_id", help="Target invoice ID")
    p_man.add_argument("payment_id", help="Source payment ID")
    p_man.add_argument("amount", help="Amount to allocate (Decimal string)")
    p_man.add_argument("--reviewer", default="CLI_USER", help="Reviewer username")
    p_man.add_argument("--notes", help="Optional review notes")

    # Command: balances
    subparsers.add_parser("balances", help="Display confirmed balances and summary")

    # Command: unresolved
    subparsers.add_parser("unresolved", help="Display categorized unresolved review buckets")

    # Command: export-report
    p_exp = subparsers.add_parser("export-report", help="Export reconciliation report CSV")
    p_exp.add_argument("--output", "-o", default="reconciliation_report.csv", help="Destination CSV path")

    # Command: evaluate
    p_ev = subparsers.add_parser("evaluate", help="Evaluate matching accuracy against ground truth labels")
    p_ev.add_argument("ground_truth", help="Path to ground truth labels CSV")
    p_ev.add_argument("--min-score", type=float, default=60.0, help="Minimum score threshold (default: 60)")

    # Command: register-user
    p_reg = subparsers.add_parser("register-user", help="Register a new business account or admin")
    p_reg.add_argument("--business", required=True, help="Business Name")
    p_reg.add_argument("--owner", required=True, help="Owner Name")
    p_reg.add_argument("--email", required=True, help="Email address")
    p_reg.add_argument("--mobile", required=True, help="10-digit mobile number")
    p_reg.add_argument("--password", required=True, help="Password")
    p_reg.add_argument("--role", default="user", choices=["user", "admin"], help="Account role")

    # Command: list-users
    p_lu = subparsers.add_parser("list-users", help="List all registered user/admin accounts")
    p_lu.add_argument("--role", choices=["user", "admin"], help="Filter by role")

    # Command: login-test
    p_log = subparsers.add_parser("login-test", help="Test authenticating a user by email/mobile and password")
    p_log.add_argument("id", help="Email address or 10-digit mobile number")
    p_log.add_argument("password", help="Password")
    p_log.add_argument("--role", choices=["user", "admin"], help="Expected role (optional)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    service = ReconciliationService(db_path=args.db)

    try:
        if args.command == "import-invoices":
            batch, valids, errors = service.import_invoices_csv(args.file, file_name=args.file)
            print(f"=== Imported Invoices from '{args.file}' ===")
            print(f"Batch ID: {batch.batch_id}")
            print(f"Total Rows: {batch.row_count} | Valid Records: {batch.valid_count} | Error Rows: {batch.error_count} | Warnings: {batch.warning_count}")
            if errors:
                print("\n[!] Import Errors / Warnings:")
                for e in errors:
                    tag = "WARNING" if e.is_warning else "ERROR"
                    print(f"  - Row {e.row_index} [{tag}]: {e.field_name or 'file'} -> {e.message}")

        elif args.command == "import-payments":
            batch, valids, errors = service.import_payments_csv(args.file, file_name=args.file)
            print(f"=== Imported Payments from '{args.file}' ===")
            print(f"Batch ID: {batch.batch_id}")
            print(f"Total Rows: {batch.row_count} | Valid Records: {batch.valid_count} | Error Rows: {batch.error_count} | Warnings: {batch.warning_count}")
            if errors:
                print("\n[!] Import Errors / Warnings:")
                for e in errors:
                    tag = "WARNING" if e.is_warning else "ERROR"
                    print(f"  - Row {e.row_index} [{tag}]: {e.field_name or 'file'} -> {e.message}")

        elif args.command == "suggest":
            suggestions = service.generate_suggestions()
            print(f"Generated {len(suggestions)} explainable match suggestions.")
            for s in suggestions[:10]:
                print(f"[{s.confidence_tier}] Inv: {s.invoice_id} <-> Pay: {s.payment_id} | Score: {s.score:.1f} | ID: {s.suggestion_id}")
                print(f"    Reason: {s.explanation}")

        elif args.command == "list-suggestions":
            suggestions = service.get_suggestions(status=args.status, tier=args.tier)
            print(f"Found {len(suggestions)} suggestions matching filters:")
            for s in suggestions:
                print(f"ID: {s.suggestion_id} | {s.invoice_id} <-> {s.payment_id} | Score: {s.score:.1f} ({s.confidence_tier}) | Status: {s.status}")
                print(f"    Explanation: {s.explanation}")

        elif args.command == "confirm":
            alloc_amt = Decimal(args.amount) if args.amount else None
            alloc = service.confirm_match(
                suggestion_id=args.suggestion_id,
                reviewer=args.reviewer,
                allocation_amount=alloc_amt,
                notes=args.notes,
            )
            print(f"[SUCCESS] Confirmed allocation {alloc.allocation_id}")
            print(f"    Invoice: {alloc.invoice_id} | Payment: {alloc.payment_id} | Allocated Amount: {alloc.allocated_amount}")

        elif args.command == "reject":
            dec = service.reject_match(
                suggestion_id=args.suggestion_id,
                reviewer=args.reviewer,
                notes=args.notes,
            )
            print(f"[SUCCESS] Rejected suggestion {dec.suggestion_id} (Audit Decision: {dec.decision_id})")

        elif args.command == "manual-allocate":
            amt = Decimal(args.amount)
            alloc = service.manual_assign(
                invoice_id=args.invoice_id,
                payment_id=args.payment_id,
                amount=amt,
                reviewer=args.reviewer,
                notes=args.notes,
            )
            print(f"[SUCCESS] Created manual allocation {alloc.allocation_id}")
            print(f"    Invoice: {alloc.invoice_id} | Payment: {alloc.payment_id} | Amount: {alloc.allocated_amount}")

        elif args.command == "balances":
            b = service.get_balances()
            print("\n=== FINMATCH BALANCES ===")
            print(f"Invoices Total:    {b['invoices']['total_invoiced']}")
            print(f"Invoices Settled:  {b['invoices']['total_settled']}")
            print(f"Invoices Unpaid:   {b['invoices']['total_outstanding']}")
            print("-" * 35)
            print(f"Payments Total:    {b['payments']['total_received']}")
            print(f"Payments Allocated:{b['payments']['total_allocated']}")
            print(f"Payments Unalloc:  {b['payments']['total_unallocated']}")

        elif args.command == "unresolved":
            u = service.get_unresolved_work()
            print("\n=== UNRESOLVED WORK SUMMARY ===")
            print(f"Unmatched Invoices:    {u['unmatched_invoices_count']}")
            print(f"Unallocated Payments:  {u['unallocated_payments_count']}")
            print(f"Ambiguous Candidates:  {u['ambiguous_suggestions_count']}")
            print(f"Amount Mismatches:     {u['amount_mismatches_count']}")
            print(f"Import Row Errors:     {u['import_errors_count']}")

        elif args.command == "export-report":
            csv_str = service.export_reconciliation_report(output_path=args.output)
            print(f"[SUCCESS] Exported reconciliation report to '{args.output}'.")

        elif args.command == "evaluate":
            metrics = service.evaluate_dataset(args.ground_truth, min_score_threshold=args.min_score)
            print("\n=== DATASET EVALUATION METRICS ===")
            print(f"Threshold Used:        {metrics['threshold_used']}")
            print(f"Ground Truth Matches:  {metrics['total_ground_truth_matches']}")
            print(f"System Suggested:      {metrics['system_suggestions_count']}")
            print(f"True Positives (TP):   {metrics['true_positives']}")
            print(f"False Positives (FP):  {metrics['false_positives']}")
            print(f"False Negatives (FN):  {metrics['false_negatives']}")
            print(f"Precision:             {metrics['matching_precision'] * 100:.2f}%")
            print(f"Recall (Accuracy):     {metrics['proportion_receiving_correct_suggestions_recall'] * 100:.2f}%")
            print(f"F1-Score:              {metrics['f1_score']:.4f}")
            print(f"Unresolved Cases Count:{metrics['unresolved_cases_count']}")
            print("\nDefinitions & Notes:")
            for k, v in metrics["metric_definitions"].items():
                print(f"  [{k}]: {v}")

        elif args.command == "register-user":
            user = service.register_business(
                business_name=args.business,
                owner_name=args.owner,
                email=args.email,
                mobile=args.mobile,
                password=args.password,
                role=args.role,
            )
            print(f"[SUCCESS] Registered new {user.role.upper()} account:")
            print(f"  User ID:       {user.user_id}")
            print(f"  Business Name: {user.business_name}")
            print(f"  Owner:         {user.owner_name}")
            print(f"  Email:         {user.email}")
            print(f"  Mobile:        {user.mobile}")
            print(f"  Role:          {user.role}")
            print(f"  Status:        {user.status}")

        elif args.command == "list-users":
            users = service.list_businesses(role=args.role)
            print(f"\n=== REGISTERED ACCOUNTS ({len(users)}) ===")
            for u in users:
                print(f"[{u.role.upper():5}] {u.user_id:12} | {u.business_name:24} | Owner: {u.owner_name:18} | Email: {u.email:22} | Mob: {u.mobile:10} | Status: {u.status}")

        elif args.command == "login-test":
            user = service.login(login_id=args.id, password=args.password, role=args.role)
            print(f"[AUTH SUCCESS] Logged in successfully:")
            print(f"  User ID:       {user.user_id}")
            print(f"  Business Name: {user.business_name}")
            print(f"  Role:          {user.role}")
            print(f"  Email:         {user.email}")
            print(f"  Mobile:        {user.mobile}")

    except Exception as exc:
        print(f"[ERROR] {str(exc)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
