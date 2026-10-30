"""
Reconciliation report generation and dataset evaluation metrics against ground-truth labels.
"""

from __future__ import annotations
import csv
from decimal import Decimal
from io import StringIO
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import pandas as pd

from backend.engine import ReconciliationEngine
from backend.models import ConfirmedAllocation, Invoice, Payment
from backend.storage.repository import ReconciliationRepository


class ReconciliationReporter:
    def __init__(self, repo: ReconciliationRepository, engine: ReconciliationEngine):
        self.repo = repo
        self.engine = engine

    def generate_report_dataframe(self) -> pd.DataFrame:
        """
        Produce a comprehensive reconciliation report dataframe containing:
        - Confirmed allocations with full audit and trace IDs
        - Unmatched invoices and outstanding balances
        - Unallocated payments
        """
        rows: List[Dict[str, Any]] = []

        # 1. Confirmed allocations
        allocations = self.repo.get_all_allocations()
        allocated_inv_ids: Set[str] = set()
        allocated_pay_ids: Set[str] = set()

        decisions = {d.decision_id: d for d in self.repo.get_review_decisions()}
        suggestions = {f"{s.invoice_id}_{s.payment_id}": s for s in self.repo.get_suggestions()}

        for a in allocations:
            inv = self.repo.get_invoice_by_id(a.invoice_id)
            pay = self.repo.get_payment_by_id(a.payment_id)
            inv_bal = self.engine.calculate_invoice_balance(inv) if inv else None
            pay_bal = self.engine.calculate_payment_balance(pay) if pay else None
            dec = decisions.get(a.decision_id) if a.decision_id else None
            sug = suggestions.get(f"{a.invoice_id}_{a.payment_id}")

            allocated_inv_ids.add(a.invoice_id)
            allocated_pay_ids.add(a.payment_id)

            rows.append({
                "record_type": "CONFIRMED_MATCH",
                "invoice_id": a.invoice_id,
                "invoice_batch_id": inv.batch_id if inv else "",
                "customer_name": inv.customer_name if inv else "",
                "invoice_amount": str(inv.amount) if inv else "",
                "invoice_date": inv.issue_date.isoformat() if inv else "",
                "payment_id": a.payment_id,
                "payment_batch_id": pay.batch_id if pay else "",
                "payment_customer": pay.customer_name if pay else "",
                "payment_amount": str(pay.amount) if pay else "",
                "payment_date": pay.payment_date.isoformat() if pay else "",
                "allocated_amount": str(a.allocated_amount),
                "invoice_outstanding_balance": str(inv_bal.outstanding_balance) if inv_bal else "",
                "payment_unallocated_amount": str(pay_bal.unallocated_amount) if pay_bal else "",
                "allocation_status": inv_bal.status if inv_bal else "ALLOCATED",
                "reviewer": a.reviewer,
                "confirmed_at": a.confirmed_at.isoformat(),
                "suggestion_score": f"{sug.score:.1f}" if sug else "N/A",
                "explanation": sug.explanation if sug else (a.notes or "Manual Allocation"),
            })

        # 2. Unmatched Invoices
        invoices = self.repo.get_invoices()
        for inv in invoices:
            inv_bal = self.engine.calculate_invoice_balance(inv)
            if inv_bal.outstanding_balance > Decimal("0.00") and inv.invoice_id not in allocated_inv_ids:
                rows.append({
                    "record_type": "UNMATCHED_INVOICE",
                    "invoice_id": inv.invoice_id,
                    "invoice_batch_id": inv.batch_id,
                    "customer_name": inv.customer_name,
                    "invoice_amount": str(inv.amount),
                    "invoice_date": inv.issue_date.isoformat(),
                    "payment_id": "",
                    "payment_batch_id": "",
                    "payment_customer": "",
                    "payment_amount": "",
                    "payment_date": "",
                    "allocated_amount": "0.00",
                    "invoice_outstanding_balance": str(inv_bal.outstanding_balance),
                    "payment_unallocated_amount": "",
                    "allocation_status": "UNPAID",
                    "reviewer": "",
                    "confirmed_at": "",
                    "suggestion_score": "",
                    "explanation": "No confirmed payment allocated to this invoice.",
                })

        # 3. Unallocated Payments
        payments = self.repo.get_payments()
        for pay in payments:
            pay_bal = self.engine.calculate_payment_balance(pay)
            if pay_bal.unallocated_amount > Decimal("0.00") and pay.payment_id not in allocated_pay_ids:
                rows.append({
                    "record_type": "UNALLOCATED_PAYMENT",
                    "invoice_id": "",
                    "invoice_batch_id": "",
                    "customer_name": "",
                    "invoice_amount": "",
                    "invoice_date": "",
                    "payment_id": pay.payment_id,
                    "payment_batch_id": pay.batch_id,
                    "payment_customer": pay.customer_name or "",
                    "payment_amount": str(pay.amount),
                    "payment_date": pay.payment_date.isoformat(),
                    "allocated_amount": "0.00",
                    "invoice_outstanding_balance": "",
                    "payment_unallocated_amount": str(pay_bal.unallocated_amount),
                    "allocation_status": "UNALLOCATED",
                    "reviewer": "",
                    "confirmed_at": "",
                    "suggestion_score": "",
                    "explanation": "Payment funds remain unallocated.",
                })

        return pd.DataFrame(rows)

    def export_report_csv(self, output_path: Optional[str] = None) -> str:
        """Export report to CSV file or string."""
        df = self.generate_report_dataframe()
        if output_path:
            df.to_csv(output_path, index=False)
        return df.to_csv(index=False)

    def evaluate_dataset(
        self,
        ground_truth: Union[str, pd.DataFrame],
        min_score_threshold: float = 60.0,
    ) -> Dict[str, Any]:
        """
        Evaluate match suggestions against ground truth labels.
        Ground truth CSV / DataFrame must have columns:
        - invoice_id
        - payment_id
        - is_match (1 / True or 0 / False)
        """
        if isinstance(ground_truth, str):
            gt_df = pd.read_csv(ground_truth, dtype=str)
        else:
            gt_df = ground_truth.copy()

        gt_df.columns = [c.strip().lower() for c in gt_df.columns]
        if "invoice_id" not in gt_df or "payment_id" not in gt_df:
            raise ValueError("Ground truth file must contain 'invoice_id' and 'payment_id' columns.")

        # Normalize ground truth matches
        true_pairs: Set[Tuple[str, str]] = set()
        false_pairs: Set[Tuple[str, str]] = set()

        match_col = next((c for c in ["is_match", "match", "target", "label"] if c in gt_df), None)
        if match_col:
            for _, r in gt_df.iterrows():
                pair = (str(r["invoice_id"]).strip(), str(r["payment_id"]).strip())
                val = str(r[match_col]).strip().lower()
                if val in ["1", "true", "yes", "match"]:
                    true_pairs.add(pair)
                else:
                    false_pairs.add(pair)
        else:
            # All rows in ground truth are considered positive matches
            for _, r in gt_df.iterrows():
                true_pairs.add((str(r["invoice_id"]).strip(), str(r["payment_id"]).strip()))

        # Retrieve system suggestions above threshold
        suggestions = self.repo.get_suggestions()
        system_suggested_pairs: Set[Tuple[str, str]] = {
            (s.invoice_id, s.payment_id) for s in suggestions if s.score >= min_score_threshold
        }

        # Calculate confusion matrix components
        tp_set = system_suggested_pairs.intersection(true_pairs)
        tp = len(tp_set)

        fp_set = system_suggested_pairs.intersection(false_pairs)
        # Also any suggested pair that was evaluated in GT but not in true_pairs
        if false_pairs:
            fp = len(fp_set)
        else:
            # If false pairs weren't explicitly labeled, any suggestion not in true_pairs is FP
            all_gt_invoices = {p[0] for p in true_pairs}
            all_gt_payments = {p[1] for p in true_pairs}
            fp = len([
                p for p in system_suggested_pairs
                if p[0] in all_gt_invoices and p[1] in all_gt_payments and p not in true_pairs
            ])

        fn_set = true_pairs - system_suggested_pairs
        fn = len(fn_set)

        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        unresolved = self.engine.get_unresolved_work()
        unresolved_count = (
            len(unresolved.unmatched_invoices)
            + len(unresolved.unallocated_payments)
            + len(unresolved.ambiguous_suggestions)
            + len(unresolved.amount_mismatches)
        )

        return {
            "threshold_used": min_score_threshold,
            "total_ground_truth_matches": len(true_pairs),
            "system_suggestions_count": len(system_suggested_pairs),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "matching_precision": round(precision, 4),
            "proportion_receiving_correct_suggestions_recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "unresolved_cases_count": unresolved_count,
            "metric_definitions": {
                "precision": "True Positives / (True Positives + False Positives): proportion of suggested matches that are correct.",
                "recall": "True Positives / (True Positives + False Negatives): proportion of actual matching pairs that received suggestions above threshold.",
                "unresolved_cases": "Sum of outstanding unpaid invoices, unallocated payments, ambiguous candidate suggestions, and amount mismatches.",
                "exclusions": "Invalid CSV rows (which fail schema validation upon import) and unlabeled experimental records are excluded from matching precision/recall denominators."
            },
        }
