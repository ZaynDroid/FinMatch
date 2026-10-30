"""
Deterministic, explainable rule and evidence-based matching engine.
Uses RapidFuzz for fuzzy string similarity.
Never uses float for financial balance logic; uses float only for 0-100 heuristic scoring.
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple
from rapidfuzz import fuzz

from backend.models import EvidenceItem, Invoice, MatchSuggestion, Payment
from backend.normalizer import extract_reference_tokens


@dataclass
class MatchingConfig:
    # Rule weight maximums (sums to 100)
    weight_exact_ref: float = 40.0
    weight_customer_id: float = 30.0
    weight_customer_name_exact: float = 28.0
    weight_customer_name_fuzzy: float = 22.0
    weight_amount_exact: float = 25.0
    weight_amount_partial: float = 12.0
    weight_amount_over: float = 2.0
    weight_date_proximate: float = 7.0

    # Thresholds
    min_suggestion_score: float = 25.0
    high_confidence_threshold: float = 85.0
    medium_confidence_threshold: float = 60.0
    min_fuzzy_name_threshold: float = 70.0
    ambiguity_delta: float = 5.0
    max_proximity_days: int = 45


class MatchingEngine:
    """
    Evaluates invoice-payment pairs against explicit, explainable evidence dimensions.
    """

    def __init__(self, config: Optional[MatchingConfig] = None):
        self.config = config or MatchingConfig()

    def evaluate_pair(self, invoice: Invoice, payment: Payment) -> Tuple[float, List[EvidenceItem], bool]:
        """
        Evaluate a single (invoice, payment) candidate pair.
        Returns (total_score, evidence_items, amount_mismatch_flag).
        """
        evidence: List[EvidenceItem] = []
        total_score = 0.0
        amount_mismatch = False

        # -------------------------------------------------------------
        # 1. Exact Reference Evidence (Max 50 pts)
        # -------------------------------------------------------------
        ref_matched = False
        payment_text = f"{payment.reference or ''} {payment.note or ''}"
        ref_tokens = extract_reference_tokens(payment_text)

        inv_canonical_id = invoice.invoice_id.upper().replace("_", "-")
        inv_id_no_hyphen = inv_canonical_id.replace("-", "")

        inv_ref_canonical = (invoice.reference or "").upper().replace("_", "-")
        inv_ref_no_hyphen = inv_ref_canonical.replace("-", "")

        # Check invoice_id tokens
        if inv_canonical_id in ref_tokens or inv_id_no_hyphen in ref_tokens or inv_canonical_id in payment_text.upper():
            ref_matched = True
            evidence.append(
                EvidenceItem(
                    rule_name="EXACT_INVOICE_ID_REFERENCE",
                    score=self.config.weight_exact_ref,
                    max_score=self.config.weight_exact_ref,
                    description=f"Payment reference/note explicitly references Invoice ID '{invoice.invoice_id}'",
                    details={"matched_token": invoice.invoice_id, "source_field": "reference/note"},
                )
            )
            total_score += self.config.weight_exact_ref
        elif inv_ref_canonical and (inv_ref_canonical in ref_tokens or inv_ref_no_hyphen in ref_tokens or inv_ref_canonical in payment_text.upper()):
            ref_matched = True
            evidence.append(
                EvidenceItem(
                    rule_name="EXACT_INVOICE_REFERENCE_CODE",
                    score=self.config.weight_exact_ref,
                    max_score=self.config.weight_exact_ref,
                    description=f"Payment references bill/quote reference code '{invoice.reference}'",
                    details={"matched_token": invoice.reference, "source_field": "reference/note"},
                )
            )
            total_score += self.config.weight_exact_ref
        elif payment.reference and invoice.reference and payment.reference.strip().upper() == invoice.reference.strip().upper():
            ref_matched = True
            evidence.append(
                EvidenceItem(
                    rule_name="MATCHING_REFERENCE_FIELDS",
                    score=self.config.weight_exact_ref,
                    max_score=self.config.weight_exact_ref,
                    description=f"Both invoice and payment share reference code '{invoice.reference}'",
                    details={"reference": invoice.reference},
                )
            )
            total_score += self.config.weight_exact_ref

        # -------------------------------------------------------------
        # 2. Customer Identity Evidence (Max 25 pts)
        # -------------------------------------------------------------
        cust_id_matched = False
        if invoice.customer_id and payment.customer_id:
            if invoice.customer_id.strip().lower() == payment.customer_id.strip().lower():
                cust_id_matched = True
                evidence.append(
                    EvidenceItem(
                        rule_name="EXACT_CUSTOMER_ID",
                        score=self.config.weight_customer_id,
                        max_score=self.config.weight_customer_id,
                        description=f"Customer IDs match exactly ('{invoice.customer_id}')",
                        details={"customer_id": invoice.customer_id},
                    )
                )
                total_score += self.config.weight_customer_id

        if not cust_id_matched and payment.customer_name_normalized and invoice.customer_name_normalized:
            inv_norm = invoice.customer_name_normalized
            pay_norm = payment.customer_name_normalized

            if inv_norm == pay_norm:
                evidence.append(
                    EvidenceItem(
                        rule_name="EXACT_CUSTOMER_NAME",
                        score=self.config.weight_customer_name_exact,
                        max_score=self.config.weight_customer_name_exact,
                        description=f"Normalized customer names match exactly ('{invoice.customer_name}')",
                        details={"normalized_name": inv_norm},
                    )
                )
                total_score += self.config.weight_customer_name_exact
            else:
                # Fuzzy similarity with RapidFuzz
                ratio = fuzz.token_sort_ratio(inv_norm, pay_norm)
                if ratio >= self.config.min_fuzzy_name_threshold:
                    # Scale score linearly based on ratio
                    scaled_score = round((ratio / 100.0) * self.config.weight_customer_name_fuzzy, 1)
                    evidence.append(
                        EvidenceItem(
                            rule_name="FUZZY_CUSTOMER_NAME",
                            score=scaled_score,
                            max_score=self.config.weight_customer_name_fuzzy,
                            description=f"Customer name fuzzy similarity {ratio:.0f}% ('{payment.customer_name}' vs '{invoice.customer_name}')",
                            details={"similarity_ratio": ratio, "invoice_name": invoice.customer_name, "payment_name": payment.customer_name},
                        )
                    )
                    total_score += scaled_score
                else:
                    evidence.append(
                        EvidenceItem(
                            rule_name="LOW_CUSTOMER_SIMILARITY",
                            score=0.0,
                            max_score=self.config.weight_customer_name_fuzzy,
                            description=f"Customer names differ significantly ({ratio:.0f}% similarity)",
                            details={"similarity_ratio": ratio},
                        )
                    )

        # -------------------------------------------------------------
        # 3. Amount Evidence (Max 20 pts)
        # -------------------------------------------------------------
        if payment.amount == invoice.amount:
            evidence.append(
                EvidenceItem(
                    rule_name="EXACT_AMOUNT_MATCH",
                    score=self.config.weight_amount_exact,
                    max_score=self.config.weight_amount_exact,
                    description=f"Exact monetary amount match ({payment.amount})",
                    details={"amount": str(payment.amount)},
                )
            )
            total_score += self.config.weight_amount_exact
        elif payment.amount < invoice.amount:
            amount_mismatch = True
            diff = invoice.amount - payment.amount
            evidence.append(
                EvidenceItem(
                    rule_name="PARTIAL_AMOUNT_MATCH",
                    score=self.config.weight_amount_partial,
                    max_score=self.config.weight_amount_exact,
                    description=f"Payment ({payment.amount}) is less than invoice ({invoice.amount}); remaining: {diff}",
                    details={"invoice_amount": str(invoice.amount), "payment_amount": str(payment.amount), "diff": str(diff)},
                )
            )
            total_score += self.config.weight_amount_partial
        else:
            # Overpayment / excess payment
            amount_mismatch = True
            diff = payment.amount - invoice.amount
            evidence.append(
                EvidenceItem(
                    rule_name="OVERPAYMENT_AMOUNT_MISMATCH",
                    score=self.config.weight_amount_over,
                    max_score=self.config.weight_amount_exact,
                    description=f"Payment ({payment.amount}) exceeds invoice ({invoice.amount}) by {diff}",
                    details={"invoice_amount": str(invoice.amount), "payment_amount": str(payment.amount), "diff": str(diff)},
                )
            )
            total_score += self.config.weight_amount_over

        # -------------------------------------------------------------
        # 4. Date Proximity Evidence (Max 5 pts)
        # -------------------------------------------------------------
        if payment.payment_date >= invoice.issue_date:
            days_diff = (payment.payment_date - invoice.issue_date).days
            if days_diff <= 30:
                evidence.append(
                    EvidenceItem(
                        rule_name="DATE_PROXIMITY_OPTIMAL",
                        score=self.config.weight_date_proximate,
                        max_score=self.config.weight_date_proximate,
                        description=f"Payment received {days_diff} days after invoice date",
                        details={"days_diff": days_diff},
                    )
                )
                total_score += self.config.weight_date_proximate
            elif days_diff <= self.config.max_proximity_days:
                score = round(self.config.weight_date_proximate * 0.6, 1)
                evidence.append(
                    EvidenceItem(
                        rule_name="DATE_PROXIMITY_ACCEPTABLE",
                        score=score,
                        max_score=self.config.weight_date_proximate,
                        description=f"Payment received {days_diff} days after invoice date (within {self.config.max_proximity_days} days)",
                        details={"days_diff": days_diff},
                    )
                )
                total_score += score
            else:
                score = round(self.config.weight_date_proximate * 0.2, 1)
                evidence.append(
                    EvidenceItem(
                        rule_name="DATE_PROXIMITY_DELAYED",
                        score=score,
                        max_score=self.config.weight_date_proximate,
                        description=f"Payment received {days_diff} days after invoice date (delayed)",
                        details={"days_diff": days_diff},
                    )
                )
                total_score += score
        else:
            days_early = (invoice.issue_date - payment.payment_date).days
            evidence.append(
                EvidenceItem(
                    rule_name="DATE_ANOMALY_PAYMENT_BEFORE_INVOICE",
                    score=0.0,
                    max_score=self.config.weight_date_proximate,
                    description=f"Payment date ({payment.payment_date}) is {days_early} days BEFORE invoice date ({invoice.issue_date})",
                    details={"days_before": days_early},
                )
            )

        return min(round(total_score, 1), 100.0), evidence, amount_mismatch

    def generate_suggestions(
        self,
        invoices: List[Invoice],
        payments: List[Payment],
        confirmed_allocated_payment_ids: Optional[Set[str]] = None,
        confirmed_allocated_invoice_ids: Optional[Set[str]] = None,
    ) -> List[MatchSuggestion]:
        """
        Evaluate all candidate pairs between unallocated payments and unpaid invoices.
        Applies ambiguity detection and assigns confidence tiers.
        """
        allocated_payments = confirmed_allocated_payment_ids or set()
        allocated_invoices = confirmed_allocated_invoice_ids or set()

        candidate_invoices = [inv for inv in invoices if inv.invoice_id not in allocated_invoices]
        candidate_payments = [pay for pay in payments if pay.payment_id not in allocated_payments]

        # payment_id -> list of (score, invoice, evidence, amount_mismatch)
        payment_candidates: Dict[str, List[Tuple[float, Invoice, List[EvidenceItem], bool]]] = {
            p.payment_id: [] for p in candidate_payments
        }
        # invoice_id -> list of payment_ids that scored above threshold
        invoice_candidates: Dict[str, List[Tuple[float, str]]] = {
            inv.invoice_id: [] for inv in candidate_invoices
        }

        for payment in candidate_payments:
            for invoice in candidate_invoices:
                score, evidence, amount_mismatch = self.evaluate_pair(invoice, payment)
                if score >= self.config.min_suggestion_score:
                    payment_candidates[payment.payment_id].append((score, invoice, evidence, amount_mismatch))
                    invoice_candidates[invoice.invoice_id].append((score, payment.payment_id))

        suggestions: List[MatchSuggestion] = []

        # Evaluate ambiguity across both directions
        for payment in candidate_payments:
            candidates = payment_candidates[payment.payment_id]
            if not candidates:
                continue

            # Sort descending by score
            candidates.sort(key=lambda x: x[0], reverse=True)
            top_score = candidates[0][0]

            for score, invoice, evidence, amount_mismatch in candidates:
                is_ambiguous = False

                # 1. Check if multiple invoices compete for this payment closely
                competing_invoices = [c for c in candidates if (top_score - c[0]) <= self.config.ambiguity_delta]
                if len(competing_invoices) > 1 and score in [c[0] for c in competing_invoices]:
                    is_ambiguous = True

                # 2. Check if multiple payments compete for this invoice closely
                inv_competing_payments = [
                    p for p in invoice_candidates[invoice.invoice_id]
                    if abs(p[0] - score) <= self.config.ambiguity_delta
                ]
                if len(inv_competing_payments) > 1:
                    is_ambiguous = True

                # 3. Check for pure amount-only match without identity
                has_identity_evidence = any(
                    e.rule_name in ["EXACT_INVOICE_ID_REFERENCE", "EXACT_INVOICE_REFERENCE_CODE", "MATCHING_REFERENCE_FIELDS", "EXACT_CUSTOMER_ID", "EXACT_CUSTOMER_NAME"]
                    for e in evidence
                )
                if not has_identity_evidence and not any(e.rule_name == "FUZZY_CUSTOMER_NAME" and e.score >= 12.0 for e in evidence):
                    # Pure amount match or weak fuzzy match without reference or name must be flagged ambiguous
                    is_ambiguous = True

                # Confidence tier determination
                # Rule: Do not claim a match is certain solely because amounts are equal!
                confidence_tier = "LOW"
                if score >= self.config.high_confidence_threshold and not is_ambiguous and not amount_mismatch and has_identity_evidence:
                    confidence_tier = "HIGH"
                elif score >= self.config.medium_confidence_threshold:
                    confidence_tier = "MEDIUM"
                else:
                    confidence_tier = "LOW"

                # Construct plain-language explanation
                explanation = self._build_plain_language_explanation(
                    score, confidence_tier, is_ambiguous, amount_mismatch, evidence, invoice, payment
                )

                sug = MatchSuggestion(
                    suggestion_id=str(uuid.uuid4()),
                    invoice_id=invoice.invoice_id,
                    payment_id=payment.payment_id,
                    score=score,
                    confidence_tier=confidence_tier,
                    is_ambiguous=is_ambiguous,
                    amount_mismatch=amount_mismatch,
                    explanation=explanation,
                    evidence=evidence,
                    status="PENDING",
                )
                suggestions.append(sug)

        # Sort suggestions by score descending
        suggestions.sort(key=lambda s: s.score, reverse=True)
        return suggestions

    def _build_plain_language_explanation(
        self,
        score: float,
        tier: str,
        is_ambiguous: bool,
        amount_mismatch: bool,
        evidence: List[EvidenceItem],
        invoice: Invoice,
        payment: Payment,
    ) -> str:
        parts = []
        for e in evidence:
            if e.score > 0:
                parts.append(f"{e.description} (+{e.score:g} pts)")
            else:
                parts.append(f"{e.description} (+0 pts)")

        notes = []
        if is_ambiguous:
            notes.append("AMBIGUOUS: Multiple candidates with similar signals detected")
        if amount_mismatch:
            notes.append("AMOUNT MISMATCH: Payment amount does not equal invoice total")
        if tier == "HIGH":
            notes.append("HIGH CONFIDENCE: Strong identity & reference corroboration")
        elif tier == "LOW":
            notes.append("LOW CONFIDENCE: Requires manual verification")

        summary = "; ".join(parts)
        flags = f" [{', '.join(notes)}]" if notes else ""
        return f"Score {score:.1f}/100 ({tier}){flags}: {summary}"
