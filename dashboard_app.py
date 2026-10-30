"""
Streamlit interactive reconciliation dashboard for FinMatch.
Connects directly to ReconciliationService.
"""

from __future__ import annotations
import os
from decimal import Decimal
import pandas as pd
import streamlit as st

from backend.matcher import MatchingConfig
from backend.service import ReconciliationService

# Page configuration
st.set_page_config(
    page_title="FinMatch Reconciliation Engine",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for clean UI styling
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .badge-high {
        background-color: #dcfce7;
        color: #166534;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-med {
        background-color: #fef9c3;
        color: #854d0e;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-low {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .explanation-box {
        background-color: #f1f5f9;
        border-left: 4px solid #3b82f6;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 0.9rem;
        margin-top: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_service(db_file: str = "finmatch_app.db") -> ReconciliationService:
    return ReconciliationService(db_path=db_file)


service = get_service()

# Session State for Authentication
if "auth_user" not in st.session_state:
    # Auto-login default user for demo convenience if desired, or keep as None
    st.session_state["auth_user"] = {
        "user_id": "USR-DEMO01",
        "business_name": "Sharma Traders",
        "owner_name": "Rajesh Sharma",
        "email": "user@finmatch.demo",
        "mobile": "9876543210",
        "role": "user",
        "status": "Active",
    }

current_user = st.session_state["auth_user"]

# Sidebar controls
st.sidebar.title("⚖️ FinMatch Engine")
st.sidebar.markdown("**Auditable Invoice-to-Payment Reconciliation**")
st.sidebar.divider()

# Auth Panel in Sidebar
if current_user:
    st.sidebar.markdown(f"### 👤 Logged in as:")
    st.sidebar.markdown(f"**{current_user['business_name']}**")
    role_color = "#166534" if current_user["role"] == "admin" else "#1e40af"
    st.sidebar.markdown(
        f"<span style='background-color:#dcfce7; color:{role_color}; padding:2px 8px; border-radius:10px; font-size:0.8rem; font-weight:bold;'>{current_user['role'].upper()}</span> &nbsp; <b>{current_user['owner_name']}</b>",
        unsafe_allow_html=True,
    )
    st.sidebar.caption(f"📱 {current_user['mobile']} | ✉️ {current_user['email']}")
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state["auth_user"] = None
        st.rerun()
else:
    st.sidebar.warning("⚠️ Not logged in. Please sign in below.")
    with st.sidebar.expander("🔑 Sign In to Business / Admin", expanded=True):
        login_id_in = st.text_input("Mobile Number or Email", key="sb_login_id")
        password_in = st.text_input("Password", type="password", key="sb_login_pw")
        role_select = st.selectbox("Role", ["user", "admin"], key="sb_login_role")
        
        if st.button("Sign In"):
            try:
                auth_res = service.login(login_id=login_id_in, password=password_in, role=role_select)
                st.session_state["auth_user"] = auth_res.to_dict()
                st.sidebar.success("Logged in successfully!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(str(e))
        
        st.markdown("---")
        st.caption("Quick Demo Logins:")
        c_dem1, c_dem2 = st.columns(2)
        if c_dem1.button("Demo User"):
            res = service.login("user@finmatch.demo", "demo123")
            st.session_state["auth_user"] = res.to_dict()
            st.rerun()
        if c_dem2.button("Demo Admin"):
            res = service.login("admin@finmatch.demo", "admin123")
            st.session_state["auth_user"] = res.to_dict()
            st.rerun()

st.sidebar.divider()
reviewer_name = st.sidebar.text_input(
    "Reviewer Identity",
    value=current_user["owner_name"] if current_user else "FINANCE_OPERATOR",
)

if st.sidebar.button("🔄 Reset / Clear All Data"):
    service.db_manager.reset_db()
    st.sidebar.success("Database reset successfully.")
    st.rerun()

st.sidebar.divider()
st.sidebar.info(
    "💡 **Key Rule:** Matches are never confirmed solely by amount equality. "
    "All monetary balances are computed using exact Decimal arithmetic without floats."
)

# Tabs
tabs = st.tabs([
    "📥 Ingestion & Validation",
    "🎯 Match Suggestions & Review",
    "📊 Balances & Unresolved Work",
    "🏢 Accounts & Businesses",
    "📑 Reconciliation Report",
    "📈 Dataset Evaluation Metrics",
])

# -------------------------------------------------------------
# TAB 1: Ingestion & Validation
# -------------------------------------------------------------
with tabs[0]:
    st.header("1. CSV Ingestion & Row Validation")
    st.markdown(
        "Import invoice and payment CSV files. Row errors and warnings are recorded without silently dropping records."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Invoices CSV")
        inv_file = st.file_uploader("Upload Invoices CSV", type=["csv"], key="inv_upload")
        if inv_file is not None:
            if st.button("Process Invoices File"):
                batch, valids, errors = service.import_invoices_csv(
                    inv_file.getvalue(), file_name=inv_file.name
                )
                st.success(
                    f"Processed {batch.row_count} rows: {batch.valid_count} valid, {batch.error_count} errors, {batch.warning_count} warnings."
                )
                st.rerun()

    with col2:
        st.subheader("Payments CSV")
        pay_file = st.file_uploader("Upload Payments CSV", type=["csv"], key="pay_upload")
        if pay_file is not None:
            if st.button("Process Payments File"):
                batch, valids, errors = service.import_payments_csv(
                    pay_file.getvalue(), file_name=pay_file.name
                )
                st.success(
                    f"Processed {batch.row_count} rows: {batch.valid_count} valid, {batch.error_count} errors, {batch.warning_count} warnings."
                )
                st.rerun()

    st.markdown("---")
    st.markdown("#### Quick Load Demo Dataset")
    if st.button("🚀 Load Supplied Labeled Sample Dataset"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        inv_path = os.path.join(base_dir, "data", "sample_invoices.csv")
        pay_path = os.path.join(base_dir, "data", "sample_payments.csv")
        
        if os.path.exists(inv_path) and os.path.exists(pay_path):
            with open(inv_path, "rb") as f:
                service.import_invoices_csv(f.read(), file_name="sample_invoices.csv")
            with open(pay_path, "rb") as f:
                service.import_payments_csv(f.read(), file_name="sample_payments.csv")
            st.success("Successfully loaded sample invoices and payments datasets!")
            st.rerun()
        else:
            st.error("Sample dataset files not found in data/ directory.")

    # Show batches and errors
    summary = service.get_import_summary()
    if summary["total_batches"] > 0:
        st.markdown("### Imported Batches")
        st.dataframe(pd.DataFrame(summary["batches"]), use_container_width=True)

        errors = service.get_import_errors()
        if errors:
            st.markdown("### Row-Level Validation Errors & Warnings")
            err_data = [
                {
                    "Batch ID": e.batch_id[:8] + "...",
                    "Row #": e.row_index,
                    "Severity": "Warning" if e.is_warning else "Error",
                    "Field": e.field_name or "General",
                    "Error Type": e.error_type,
                    "Message": e.message,
                    "Raw Row Data": str(e.raw_data),
                }
                for e in errors
            ]
            st.dataframe(pd.DataFrame(err_data), use_container_width=True)

# -------------------------------------------------------------
# TAB 2: Match Suggestions & Review
# -------------------------------------------------------------
with tabs[1]:
    st.header("2. Explainable Match Suggestions & Review Decisions")
    st.markdown(
        "Candidate matches ranked by transparent evidence scores. "
        "Suggestions **do not** modify account balances until confirmed."
    )

    col_btn1, col_btn2 = st.columns([2, 4])
    with col_btn1:
        if st.button("⚡ Generate Match Suggestions", type="primary"):
            sugs = service.generate_suggestions()
            st.success(f"Generated {len(sugs)} explainable match suggestions.")
            st.rerun()

    suggestions = service.get_suggestions()

    if suggestions:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            tier_filter = st.selectbox("Filter by Confidence Tier", ["ALL", "HIGH", "MEDIUM", "LOW"])
        with col_f2:
            status_filter = st.selectbox("Filter by Status", ["ALL", "PENDING", "CONFIRMED", "REJECTED"])

        filtered = suggestions
        if tier_filter != "ALL":
            filtered = [s for s in filtered if s.confidence_tier == tier_filter]
        if status_filter != "ALL":
            filtered = [s for s in filtered if s.status == status_filter]

        st.caption(f"Showing {len(filtered)} suggestions")

        for idx, s in enumerate(filtered):
            inv = service.repo.get_invoice_by_id(s.invoice_id)
            pay = service.repo.get_payment_by_id(s.payment_id)

            badge_class = (
                "badge-high"
                if s.confidence_tier == "HIGH"
                else ("badge-med" if s.confidence_tier == "MEDIUM" else "badge-low")
            )

            with st.container():
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <h4>Suggestion #{idx + 1}: Invoice <code>{s.invoice_id}</code> ↔ Payment <code>{s.payment_id}</code></h4>
                            <div>
                                <span class="{badge_class}">{s.confidence_tier} ({s.score:.1f} pts)</span>
                                &nbsp;<b>Status:</b> {s.status}
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                c1, c2, c3 = st.columns([3, 3, 4])
                with c1:
                    st.markdown(
                        f"""
                        **Invoice Details:**
                        - Customer: **{inv.customer_name if inv else 'N/A'}**
                        - Total Amount: **₹{inv.amount if inv else '0'}**
                        - Issue Date: {inv.issue_date if inv else 'N/A'}
                        - Reference: {inv.reference or 'None'}
                        """
                    )
                with c2:
                    st.markdown(
                        f"""
                        **Payment Details:**
                        - Payer: **{pay.customer_name if pay else 'N/A'}**
                        - Received Amount: **₹{pay.amount if pay else '0'}**
                        - Payment Date: {pay.payment_date if pay else 'N/A'}
                        - Reference / UTR: {pay.reference or 'None'}
                        """
                    )
                with c3:
                    st.markdown("**Evidence & Plain-Language Explanation:**")
                    st.markdown(f"<div class='explanation-box'>{s.explanation}</div>", unsafe_allow_html=True)
                    if s.is_ambiguous:
                        st.warning("⚠️ Ambiguous candidate: Similar competing candidates exist.")
                    if s.amount_mismatch:
                        st.info("ℹ️ Amount mismatch: Partial payment or overpayment.")

                # Review actions
                if s.status == "PENDING":
                    act_col1, act_col2, act_col3 = st.columns([2, 2, 4])
                    with act_col1:
                        if st.button("✅ Confirm Match", key=f"conf_{s.suggestion_id}"):
                            try:
                                service.confirm_match(
                                    s.suggestion_id,
                                    reviewer=reviewer_name,
                                    notes="Confirmed via Streamlit dashboard",
                                )
                                st.success("Confirmed!")
                                st.rerun()
                            except Exception as ex:
                                st.error(str(ex))
                    with act_col2:
                        if st.button("❌ Reject", key=f"rej_{s.suggestion_id}"):
                            service.reject_match(
                                s.suggestion_id,
                                reviewer=reviewer_name,
                                notes="Rejected via Streamlit dashboard",
                            )
                            st.warning("Rejected.")
                            st.rerun()
                    with act_col3:
                        custom_amt = st.text_input(
                            "Custom Allocation Amount",
                            value=str(min(inv.amount, pay.amount)) if inv and pay else "0.00",
                            key=f"amt_{s.suggestion_id}",
                        )
                        if st.button("✍️ Confirm with Custom Amount", key=f"custom_conf_{s.suggestion_id}"):
                            try:
                                service.confirm_match(
                                    s.suggestion_id,
                                    reviewer=reviewer_name,
                                    allocation_amount=Decimal(custom_amt),
                                    notes=f"Custom partial allocation by {reviewer_name}",
                                )
                                st.success("Allocated custom amount!")
                                st.rerun()
                            except Exception as ex:
                                st.error(str(ex))

                st.divider()
    else:
        st.info("No suggestions generated yet. Click 'Generate Match Suggestions' above.")

# -------------------------------------------------------------
# TAB 3: Balances & Unresolved Work
# -------------------------------------------------------------
with tabs[2]:
    st.header("3. Balances & Categorized Unresolved Work")
    st.markdown("All balances reflect **only confirmed allocations**. Never double-counted.")

    bal = service.get_balances()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Invoiced", f"₹{bal['invoices']['total_invoiced']}")
    m2.metric("Total Confirmed Settled", f"₹{bal['invoices']['total_settled']}")
    m3.metric("Outstanding Unpaid", f"₹{bal['invoices']['total_outstanding']}")
    m4.metric("Unallocated Payments", f"₹{bal['payments']['total_unallocated']}")

    st.markdown("---")
    st.subheader("Unresolved Review Buckets")
    unres = service.get_unresolved_work()

    b_col1, b_col2, b_col3, b_col4 = st.columns(4)
    b_col1.metric("Unmatched Invoices", unres["unmatched_invoices_count"])
    b_col2.metric("Unallocated Payments", unres["unallocated_payments_count"])
    b_col3.metric("Ambiguous Candidates", unres["ambiguous_suggestions_count"])
    b_col4.metric("Amount Mismatches", unres["amount_mismatches_count"])

    subtab1, subtab2, subtab3, subtab4 = st.tabs([
        "Unmatched Invoices",
        "Unallocated Payments",
        "Ambiguous Suggestions",
        "Manual Allocation Form",
    ])

    with subtab1:
        if unres["unmatched_invoices"]:
            st.dataframe(pd.DataFrame(unres["unmatched_invoices"]), use_container_width=True)
        else:
            st.success("All invoices are fully settled!")

    with subtab2:
        if unres["unallocated_payments"]:
            st.dataframe(pd.DataFrame(unres["unallocated_payments"]), use_container_width=True)
        else:
            st.success("All payments are fully allocated!")

    with subtab3:
        if unres["ambiguous_suggestions"]:
            st.dataframe(pd.DataFrame(unres["ambiguous_suggestions"]), use_container_width=True)
        else:
            st.success("No ambiguous candidates pending.")

    with subtab4:
        st.markdown("#### Manually Assign Payment to Invoice")
        m_inv = st.text_input("Invoice ID (e.g. INV-102)")
        m_pay = st.text_input("Payment ID (e.g. PAY-502)")
        m_amt = st.text_input("Allocation Amount (e.g. 30000.00)")
        if st.button("Submit Manual Allocation"):
            try:
                alloc = service.manual_assign(
                    invoice_id=m_inv,
                    payment_id=m_pay,
                    amount=Decimal(m_amt),
                    reviewer=reviewer_name,
                    notes="Direct manual assignment",
                )
                st.success(f"Successfully allocated ₹{alloc.allocated_amount} from {m_pay} to {m_inv}")
                st.rerun()
            except Exception as e:
                st.error(str(e))

# -------------------------------------------------------------
# TAB 4: Accounts & Businesses (User & Admin Auth)
# -------------------------------------------------------------
with tabs[3]:
    st.header("4. User & Admin Accounts / Business Management")
    st.markdown("Manage registered businesses, administrator logins, credentials, and access statuses.")

    sec_col1, sec_col2 = st.columns([6, 4])

    with sec_col1:
        st.subheader("📋 Registered Businesses & Admin Users")
        users_list = service.list_businesses()
        if users_list:
            u_df = pd.DataFrame([
                {
                    "User ID": u.user_id,
                    "Business Name": u.business_name,
                    "Owner": u.owner_name,
                    "Email": u.email,
                    "Mobile": u.mobile,
                    "Role": u.role.upper(),
                    "Status": u.status,
                    "Created At": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "-",
                }
                for u in users_list
            ])
            st.dataframe(u_df, use_container_width=True)
        else:
            st.info("No accounts registered yet.")

        # Status toggle
        st.markdown("#### Account Status Toggle")
        t_col1, t_col2, t_col3 = st.columns([4, 3, 3])
        with t_col1:
            target_uid = st.selectbox(
                "Select User Account",
                options=[u.user_id for u in users_list],
                format_func=lambda x: f"{x} - {next((u.business_name for u in users_list if u.user_id == x), '')}",
            )
        with t_col2:
            new_status = st.selectbox("Set Status", ["Active", "Disabled"])
        with t_col3:
            st.write("")
            st.write("")
            if st.button("Update Status"):
                try:
                    service.set_business_status(user_id=target_uid, status=new_status)
                    st.success(f"Updated status of {target_uid} to {new_status}!")
                    st.rerun()
                except Exception as ex:
                    st.error(str(ex))

    with sec_col2:
        st.subheader("➕ Register New Business")
        with st.form("new_biz_form"):
            nb_bname = st.text_input("Business Name", placeholder="e.g. Apex Hardware")
            nb_oname = st.text_input("Owner Name", placeholder="e.g. Vikram Mehta")
            nb_mobile = st.text_input("Mobile Number (10 digits)", placeholder="e.g. 9822001122")
            nb_email = st.text_input("Email Address", placeholder="e.g. vikram@apex.com")
            nb_pw = st.text_input("Password", type="password", placeholder="Min 4 characters")
            nb_role = st.selectbox("Role", ["user", "admin"])

            submitted = st.form_submit_button("Register Account in Database")
            if submitted:
                try:
                    new_acc = service.register_business(
                        business_name=nb_bname,
                        owner_name=nb_oname,
                        email=nb_email,
                        mobile=nb_mobile,
                        password=nb_pw,
                        role=nb_role,
                    )
                    st.success(f"Successfully registered '{new_acc.business_name}' ({new_acc.user_id})!")
                    st.rerun()
                except Exception as ex:
                    st.error(str(ex))

# -------------------------------------------------------------
# TAB 5: Reconciliation Report
# -------------------------------------------------------------
with tabs[4]:
    st.header("5. Reconciliation Report & Export")
    st.markdown(
        "Traceable report detailing confirmed matches, allocation amounts, audit users, and unresolved records."
    )

    report_df = service.reporter.generate_report_dataframe()
    if not report_df.empty:
        st.dataframe(report_df, use_container_width=True)
        csv_data = report_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Reconciliation Report (CSV)",
            data=csv_data,
            file_name="finmatch_reconciliation_report.csv",
            mime="text/csv",
        )
    else:
        st.info("No records loaded to generate report.")

# -------------------------------------------------------------
# TAB 6: Dataset Evaluation Metrics
# -------------------------------------------------------------
with tabs[5]:
    st.header("6. Labeled Dataset Evaluation Metrics")
    st.markdown("Evaluate suggestion precision and recall against verified ground-truth labels.")

    gt_file = st.file_uploader("Upload Custom Ground Truth Labels (CSV)", type=["csv"], key="gt_upload")
    min_score = st.slider("Minimum Suggestion Score Threshold", min_value=30.0, max_value=90.0, value=60.0, step=5.0)

    eval_btn = st.button("Run Evaluation Benchmark")
    if eval_btn:
        gt_source = None
        if gt_file is not None:
            gt_source = pd.read_csv(gt_file, dtype=str)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            default_gt = os.path.join(base_dir, "data", "ground_truth_labels.csv")
            if os.path.exists(default_gt):
                gt_source = default_gt

        if gt_source is not None:
            results = service.evaluate_dataset(gt_source, min_score_threshold=min_score)

            e1, e2, e3, e4 = st.columns(4)
            e1.metric("Matching Precision", f"{results['matching_precision'] * 100:.1f}%")
            e2.metric("Accuracy / Recall", f"{results['proportion_receiving_correct_suggestions_recall'] * 100:.1f}%")
            e3.metric("F1-Score", f"{results['f1_score']:.4f}")
            e4.metric("Unresolved Cases Count", results["unresolved_cases_count"])

            st.markdown("### Confusion Matrix Breakdown")
            c_mat = pd.DataFrame([
                {"Metric": "True Positives (TP)", "Count": results["true_positives"], "Description": "Correct suggested matches"},
                {"Metric": "False Positives (FP)", "Count": results["false_positives"], "Description": "Incorrect suggested matches"},
                {"Metric": "False Negatives (FN)", "Count": results["false_negatives"], "Description": "True matches missed below threshold"},
                {"Metric": "Total Ground Truth Matches", "Count": results["total_ground_truth_matches"], "Description": "Target matches in ground truth"},
            ])
            st.table(c_mat)

            st.markdown("### Metric Definitions & Exclusion Rules")
            for k, v in results["metric_definitions"].items():
                st.markdown(f"- **{k.capitalize()}:** {v}")
        else:
            st.error("Ground truth file not available.")
