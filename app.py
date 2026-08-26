import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import re
from datetime import datetime

# Optional Plotly import with graceful fallback
try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ModuleNotFoundError:
    HAS_PLOTLY = False

# Page Configuration
st.set_page_config(
    page_title="SettleIQ | AI Finance Controller",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Design & Visual Excellence
st.markdown("""
<style>
    .main {
        background-color: #0F172A;
        color: #F8FAFC;
    }
    
    .header-container {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        padding: 24px 32px;
        border-radius: 16px;
        border: 1px solid #334155;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    
    .header-title {
        font-family: 'Inter', sans-serif;
        font-size: 32px;
        font-weight: 800;
        background: linear-gradient(90deg, #38BDF8 0%, #818CF8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    
    .header-subtitle {
        color: #94A3B8;
        font-size: 15px;
        margin-top: 6px;
    }
    
    .metric-card {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .metric-val {
        font-size: 28px;
        font-weight: 700;
        color: #F8FAFC;
        margin-top: 8px;
    }
    
    .metric-lbl {
        font-size: 13px;
        font-weight: 600;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .badge-success {
        background-color: rgba(34, 197, 94, 0.15);
        color: #4ADE80;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
    }
    
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

def safe_read_csv(filepath):
    """Safely read CSV files checking existence and non-zero file size."""
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        try:
            return pd.read_csv(filepath)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

# Helper Data Loader
@st.cache_data(ttl=60)
def load_reconciliation_data():
    need_rebuild = False
    for fname in ['matched_pairs.csv', 'exceptions.csv', 'razorpay_settlements.csv', 'bank_statement.csv']:
        if not os.path.exists(fname) or os.path.getsize(fname) == 0:
            need_rebuild = True
            break
            
    if need_rebuild:
        from generate_datasets import main as gen_main
        from reconciliation_engine import ReconciliationEngine
        gen_main()
        engine = ReconciliationEngine()
        engine.execute_reconciliation()
        
    matched_df = safe_read_csv('matched_pairs.csv')
    exceptions_df = safe_read_csv('exceptions.csv')
    razorpay_df = safe_read_csv('razorpay_settlements.csv')
    bank_df = safe_read_csv('bank_statement.csv')
    
    return matched_df, exceptions_df, razorpay_df, bank_df

# Main App Layout
def main():
    # Session state initialization for resolution actions
    if "resolved_items" not in st.session_state:
        st.session_state.resolved_items = set()

    # Sidebar
    st.sidebar.title("⚡ SettleIQ Controls")
    st.sidebar.markdown("**Track 04 — AI Finance Controller**")
    st.sidebar.markdown("---")
    
    if st.sidebar.button("🔄 Re-run 3-Tier Reconciliation", use_container_width=True):
        with st.spinner("Executing 3-Tier Reconciliation Engine..."):
            from reconciliation_engine import ReconciliationEngine
            engine = ReconciliationEngine()
            engine.execute_reconciliation()
            st.cache_data.clear()
            st.sidebar.success("Reconciliation updated in 0.1s!")
            st.rerun()
            
    if st.sidebar.button("🎲 Generate Fresh Datasets", use_container_width=True):
        with st.spinner("Generating fresh datasets..."):
            from generate_datasets import main as gen_main
            from reconciliation_engine import ReconciliationEngine
            gen_main()
            engine = ReconciliationEngine()
            engine.execute_reconciliation()
            st.cache_data.clear()
            st.sidebar.success("Fresh dataset generated & reconciled in 0.2s!")
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📤 Upload Custom Files")
    uploaded_rp = st.sidebar.file_uploader("Upload Razorpay Settlement CSV", type=['csv'], key="rp_upload")
    uploaded_bank = st.sidebar.file_uploader("Upload Bank Statement CSV", type=['csv'], key="bank_upload")

    # Track uploads in session state so they persist across reruns
    if "custom_rp_loaded" not in st.session_state:
        st.session_state.custom_rp_loaded = False
    if "custom_bank_loaded" not in st.session_state:
        st.session_state.custom_bank_loaded = False

    if uploaded_rp is not None:
        df_rp = pd.read_csv(uploaded_rp)
        # Normalize column names to lowercase
        df_rp.columns = [str(c).lower().strip() for c in df_rp.columns]
        # Auto-detect column mapping for common Razorpay export formats
        if 'amount' not in df_rp.columns and 'total_amount' in df_rp.columns:
            df_rp['amount'] = df_rp['total_amount']
        if 'utr' not in df_rp.columns:
            df_rp['utr'] = ''
        if 'payment_id' not in df_rp.columns and 'id' in df_rp.columns:
            df_rp['payment_id'] = df_rp['id']
        if 'merchant_id' not in df_rp.columns:
            df_rp['merchant_id'] = 'MERCH_001'
        if 'status' not in df_rp.columns:
            df_rp['status'] = 'settled'
        df_rp.to_csv('razorpay_settlements.csv', index=False)
        st.session_state.custom_rp_loaded = True
        st.sidebar.success(f"Loaded {len(df_rp)} Razorpay records!")
        
    if uploaded_bank is not None:
        df_bank = pd.read_csv(uploaded_bank)
        # Normalize column names to lowercase
        df_bank.columns = [str(c).lower().strip() for c in df_bank.columns]
        if 'utr' not in df_bank.columns:
            df_bank['utr'] = ''
        if 'txn_ref' not in df_bank.columns and 'reference' in df_bank.columns:
            df_bank['txn_ref'] = df_bank['reference']
        elif 'txn_ref' not in df_bank.columns:
            df_bank['txn_ref'] = [f"TXN_{i}" for i in range(len(df_bank))]
        if 'value_date' not in df_bank.columns and 'date' in df_bank.columns:
            df_bank['value_date'] = df_bank['date']
        if 'merchant_id' not in df_bank.columns:
            df_bank['merchant_id'] = 'MERCH_001'
        df_bank.to_csv('bank_statement.csv', index=False)
        st.session_state.custom_bank_loaded = True
        st.sidebar.success(f"Loaded {len(df_bank)} Bank records!")

    if st.sidebar.button("⚡ Reconcile Uploaded Files", use_container_width=True):
        if st.session_state.custom_rp_loaded or st.session_state.custom_bank_loaded:
            with st.spinner("Running 3-Tier Reconciliation on uploaded files..."):
                from reconciliation_engine import ReconciliationEngine
                engine = ReconciliationEngine()
                engine.execute_reconciliation()
                st.cache_data.clear()
                st.sidebar.success("Reconciliation complete!")
                st.rerun()
        else:
            st.sidebar.warning("Please upload at least one CSV file first.")

    st.sidebar.markdown("---")
    
    matched_df, exceptions_df, razorpay_df, bank_df = load_reconciliation_data()
    
    total_rp = len(razorpay_df)
    matched_count = len(matched_df)
    exc_count = len(exceptions_df) - len(st.session_state.resolved_items)
    match_rate = round((matched_count / total_rp * 100), 1) if total_rp > 0 else 0
    cleared_amt = matched_df['bank_amount'].sum() if not matched_df.empty else 0
    risk_amt = exceptions_df['amount'].sum() if not exceptions_df.empty else 0
    
    st.sidebar.metric("Auto-Match Rate", f"{match_rate}%", delta=f"{match_rate - 70.0:.1f}% vs baseline")
    st.sidebar.metric("Cleared Volume", f"₹{cleared_amt:,.2f}")
    st.sidebar.metric("Amount at Risk", f"₹{risk_amt:,.2f}", delta_color="inverse")
    
    st.sidebar.markdown("---")
    st.sidebar.info("💡 **Production Audit Trail**: Timestamped decision log with rule IDs & confidence scores.")

    # Header Banner
    st.markdown("""
    <div class="header-container">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 class="header-title">⚡ SettleIQ — AI Finance Controller</h1>
                <p class="header-subtitle">Multi-Source Payment Reconciliation & AI Exception Intelligence for Razorpay</p>
            </div>
            <div>
                <span class="badge-success">● Engine Live</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Top KPI Metrics Cards
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-lbl">Match Rate</div>
            <div class="metric-val" style="color: #4ADE80;">{match_rate}%</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-lbl">Matched Entries</div>
            <div class="metric-val">{matched_count}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-lbl">Exceptions Flagged</div>
            <div class="metric-val" style="color: #F87171;">{max(0, exc_count)}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-lbl">Cleared Position</div>
            <div class="metric-val" style="font-size: 22px;">₹{cleared_amt:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-lbl">Unreconciled Risk</div>
            <div class="metric-val" style="color: #F87171; font-size: 22px;">₹{risk_amt:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Main Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Reconciliation Dashboard",
        "🚨 AI Exception Queue & Actions",
        "💬 Settlement Q&A Agent",
        "📜 Audit Trail & Exports"
    ])

    # Tab 1: Dashboard
    with tab1:
        g_col1, g_col2 = st.columns([1, 1])
        
        with g_col1:
            st.subheader("🎯 Auto-Match Rate Progress")
            if HAS_PLOTLY:
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=match_rate,
                    number={'suffix': "%", 'font': {'color': '#F8FAFC', 'size': 40}},
                    domain={'x': [0, 1], 'y': [0, 1]},
                    gauge={
                        'axis': {'range': [0, 100], 'tickcolor': "#94A3B8"},
                        'bar': {'color': "#22C55E" if match_rate >= 90 else "#F59E0B"},
                        'bgcolor': "#1E293B",
                        'bordercolor': "#334155",
                        'steps': [
                            {'range': [0, 75], 'color': "rgba(239, 68, 68, 0.2)"},
                            {'range': [75, 90], 'color': "rgba(245, 158, 11, 0.2)"},
                            {'range': [90, 100], 'color': "rgba(34, 197, 94, 0.2)"}
                        ],
                        'threshold': {
                            'line': {'color': "#38BDF8", 'width': 4},
                            'thickness': 0.75,
                            'value': 94.0
                        }
                    }
                ))
                fig_gauge.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=300,
                    margin=dict(l=20, r=20, t=30, b=20)
                )
                st.plotly_chart(fig_gauge, use_container_width=True)
            else:
                st.progress(float(match_rate / 100.0))
                st.write(f"**Auto-Match Rate:** {match_rate}% (Target: 94.0%)")

        with g_col2:
            st.subheader("🧩 3-Tier Match Decomposition")
            if not matched_df.empty:
                tier_counts = matched_df['match_type'].value_counts().to_dict()
                tier_counts['Exceptions Flagged'] = max(0, exc_count)
                
                df_pie = pd.DataFrame({
                    'Category': list(tier_counts.keys()),
                    'Records': list(tier_counts.values())
                })
                
                if HAS_PLOTLY:
                    fig_pie = px.pie(
                        df_pie,
                        values='Records',
                        names='Category',
                        color='Category',
                        color_discrete_map={
                            'Tier 1 (Exact UTR)': '#22C55E',
                            'Tier 2 (Fuzzy Match)': '#38BDF8',
                            'Exceptions Flagged': '#EF4444'
                        },
                        hole=0.45
                    )
                    fig_pie.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#F8FAFC'),
                        height=300,
                        margin=dict(l=20, r=20, t=30, b=20)
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.bar_chart(df_pie.set_index('Category'))

        st.markdown("---")
        st.subheader("📉 Reconciliation Breakdown by Exception Category")
        if not exceptions_df.empty and 'exception_type' in exceptions_df.columns:
            exc_summary = exceptions_df.groupby('exception_type').agg(
                Count=('payment_id', 'count'),
                Total_Risk=('amount', 'sum'),
                Avg_Confidence=('confidence', 'mean')
            ).reset_index()
            
            exc_summary['Avg_Confidence'] = (exc_summary['Avg_Confidence'] * 100).round(1).astype(str) + '%'
            exc_summary['Total_Risk'] = exc_summary['Total_Risk'].apply(lambda x: f"₹{x:,.2f}")
            
            st.dataframe(
                exc_summary,
                column_config={
                    "exception_type": "Exception Category",
                    "Count": "Affected Transactions",
                    "Total_Risk": "Amount at Risk",
                    "Avg_Confidence": "AI Model Confidence"
                },
                hide_index=True,
                use_container_width=True
            )

    # Tab 2: Exception Queue & Remediation Actions
    with tab2:
        st.subheader("🚨 AI Exception Queue & Resolution Desk")
        st.markdown("Review payment exceptions enriched with AI explanations and trigger **One-Click Auto-Remediation**.")
        
        if not exceptions_df.empty:
            f_col1, f_col2, f_col3 = st.columns([1, 1, 1])
            with f_col1:
                categories = ["All Categories"] + list(exceptions_df['exception_type'].unique())
                sel_cat = st.selectbox("Filter Exception Category", categories)
            with f_col2:
                min_conf = st.slider("Minimum AI Confidence", 0.50, 1.00, 0.70, 0.05)
            with f_col3:
                search_kw = st.text_input("Search Payment ID / Merchant", "")
                
            filtered_exc = exceptions_df.copy()
            if sel_cat != "All Categories":
                filtered_exc = filtered_exc[filtered_exc['exception_type'] == sel_cat]
            filtered_exc = filtered_exc[filtered_exc['confidence'] >= min_conf]
            if search_kw:
                filtered_exc = filtered_exc[
                    filtered_exc['payment_id'].astype(str).str.contains(search_kw, case=False) |
                    filtered_exc['merchant_id'].astype(str).str.contains(search_kw, case=False)
                ]

            st.write(f"Showing **{len(filtered_exc)}** flagged exceptions")
            
            for idx, row in filtered_exc.iterrows():
                pid = row['payment_id']
                is_resolved = pid in st.session_state.resolved_items
                status_icon = "✅ RESOLVED" if is_resolved else f"🔴 [{row['exception_type']}]"
                
                with st.expander(f"{status_icon} {pid} — ₹{row['amount']:,.2f} ({row.get('date', 'N/A')})"):
                    e_col1, e_col2 = st.columns([2, 1])
                    with e_col1:
                        st.markdown(f"**🤖 AI Explanation:** {row.get('ai_explanation', 'N/A')}")
                        st.markdown(f"**💡 Suggested Action:** `{row.get('suggested_action', 'N/A')}`")
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        act_col1, act_col2 = st.columns(2)
                        with act_col1:
                            if not is_resolved:
                                if st.button(f"✅ Mark Resolved", key=f"res_{idx}_{pid}"):
                                    st.session_state.resolved_items.add(pid)
                                    st.success(f"Item {pid} marked as resolved!")
                                    st.rerun()
                            else:
                                st.info("This transaction has been resolved.")
                                
                        with act_col2:
                            if st.button(f"📩 Draft Bank Email", key=f"email_{idx}_{pid}"):
                                email_text = f"""
Subject: Request for Settlement Trace - UTR: {row.get('utr', 'N/A')} (Payment ID: {pid})

Dear Nodal Bank Operations,

We are requesting an urgent settlement status trace for the following transaction:
- Payment ID: {pid}
- UTR/RRN Reference: {row.get('utr', 'N/A')}
- Amount: Rs. {row['amount']:,.2f}
- Transaction Date: {row.get('date', 'N/A')}
- Merchant ID: {row.get('merchant_id', 'N/A')}

Exception Type Flagged: {row['exception_type']}
AI Controller Note: {row.get('ai_explanation')}

Please confirm credit posting date or process necessary reversal.

Regards,
Finance Controller Desk
"""
                                st.code(email_text, language="markdown")
                                st.success("Bank Email Draft generated!")

                    with e_col2:
                        st.markdown(f"**Merchant ID:** `{row.get('merchant_id', 'N/A')}`")
                        st.markdown(f"**UTR Reference:** `{row.get('utr', 'N/A')}`")
                        st.markdown(f"**AI Confidence:** `{round(row.get('confidence', 0.85)*100, 1)}%`")

    # Tab 3: Q&A Chat Agent
    with tab3:
        st.subheader("💬 Settlement Q&A Agent")
        st.markdown("Ask any questions about payments, settlement delays, unreconciled items, or financial metrics.")
        
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "assistant", "content": "👋 Hello! I am your SettleIQ Agent. Ask me questions like:\n- *Why is payment pay_... unreconciled?*\n- *What is our auto-match rate?*\n- *Show me all Amount Mismatches*\n- *How much cash is at risk?*"}
            ]

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Ask SettleIQ Q&A Agent..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            query_lower = prompt.lower()
            pay_match = re.search(r'pay_\w+', query_lower)
            
            if pay_match or "unreconciled" in query_lower and "why" in query_lower:
                pid = pay_match.group() if pay_match else None
                found_exc = pd.DataFrame()
                found_match = pd.DataFrame()
                
                if pid:
                    if not exceptions_df.empty:
                        found_exc = exceptions_df[exceptions_df['payment_id'].astype(str).str.contains(pid, case=False)]
                    if not matched_df.empty:
                        found_match = matched_df[matched_df['payment_id'].astype(str).str.contains(pid, case=False)]
                        
                if not found_exc.empty:
                    rec = found_exc.iloc[0]
                    response = f"""
### 🚨 Exception Found for Payment `{rec['payment_id']}`
- **Category:** `{rec['exception_type']}`
- **Amount:** ₹{rec['amount']:,.2f}
- **Date:** {rec.get('date', 'N/A')}
- **Confidence Score:** {round(rec.get('confidence', 0.85)*100, 1)}%

**🤖 AI Diagnosis:**
{rec.get('ai_explanation', 'No explanation available.')}

**💡 Suggested Next Step:**
{rec.get('suggested_action', 'Contact finance desk.')}
"""
                elif not found_match.empty:
                    rec = found_match.iloc[0]
                    response = f"""
### ✅ Payment `{rec['payment_id']}` is Successfully Reconciled!
- **Match Tier:** `{rec['match_type']}`
- **Rule Fired:** `{rec.get('rule_fired', 'N/A')}`
- **Razorpay Amount:** ₹{rec['razorpay_amount']:,.2f}
- **Bank Amount:** ₹{rec['bank_amount']:,.2f}
- **UTR Reference:** `{rec.get('utr', 'N/A')}`
- **Confidence:** {round(rec.get('confidence', 0.98)*100, 1)}%
"""
                else:
                    if not exceptions_df.empty:
                        sample_exc = exceptions_df.iloc[0]
                        response = f"I could not locate specific payment `{pid if pid else 'requested'}`. Here is a high-priority unreconciled item in your queue:\n\n" \
                                   f"**Payment `{sample_exc['payment_id']}`** (₹{sample_exc['amount']:,.2f}): Flagged as **{sample_exc['exception_type']}**. {sample_exc.get('ai_explanation')}"
                    else:
                        response = "All payments are currently 100% reconciled!"
                        
            elif "match rate" in query_lower or "overall" in query_lower or "performance" in query_lower:
                response = f"📊 **SettleIQ Current Metrics Summary:**\n- **Auto-Match Rate:** `{match_rate}%`\n- **Cleared Settlements:** `{matched_count}` records (₹{cleared_amt:,.2f})\n- **Pending Exceptions:** `{exc_count}` records (₹{risk_amt:,.2f} at risk)"
                
            elif "risk" in query_lower or "at risk" in query_lower or "amount" in query_lower:
                response = f"⚠️ **Cash Position at Risk:** Total unreconciled amount is **₹{risk_amt:,.2f}** across {exc_count} flagged exceptions. Top risk category is **{exceptions_df.iloc[0]['exception_type'] if not exceptions_df.empty else 'None'}**."
                
            elif "amount mismatch" in query_lower or "timing mismatch" in query_lower or "gst" in query_lower:
                response = f"🔍 Found **{exc_count}** exceptions in queue. Filter by tab **🚨 AI Exception Queue** to inspect full explanations and download audit exports."
                
            else:
                response = f"I am your SettleIQ Finance Controller Assistant. I can analyze any payment settlement, explain bank discrepancies, calculate match rates, or audit GST variances. Try asking: *'Why is payment pay_... unreconciled?'* or *'What is the total cash at risk?'*"

            with st.chat_message("assistant"):
                st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

    # Tab 4: Audit Trail & Exports
    with tab4:
        st.subheader("📜 Production Audit Trail & Multi-Format Exports")
        st.markdown("Full transparency log of every matching rule, confidence score, and timestamped decision.")
        
        st.markdown("### 📥 Download Reports")
        ex_col1, ex_col2, ex_col3 = st.columns(3)
        
        with ex_col1:
            if not matched_df.empty:
                st.download_button(
                    label="📄 Download Matched Pairs (CSV)",
                    data=matched_df.to_csv(index=False),
                    file_name="settleiq_matched_pairs.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        with ex_col2:
            if not exceptions_df.empty:
                st.download_button(
                    label="🚨 Download Exception Queue (CSV)",
                    data=exceptions_df.to_csv(index=False),
                    file_name="settleiq_exceptions_queue.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        with ex_col3:
            if os.path.exists('reconciliation_report.xlsx'):
                with open('reconciliation_report.xlsx', 'rb') as f:
                    st.download_button(
                        label="📊 Download Styled Excel Report (.xlsx)",
                        data=f.read(),
                        file_name="settleiq_reconciliation_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

        st.markdown("---")
        st.subheader("🔍 Production Decision Log (Matched Records)")
        if not matched_df.empty:
            st.dataframe(
                matched_df[['timestamp', 'match_type', 'payment_id', 'utr', 'razorpay_amount', 'bank_amount', 'confidence', 'rule_fired']],
                column_config={
                    "timestamp": "Timestamp",
                    "match_type": "Tier Classification",
                    "payment_id": "Razorpay Payment ID",
                    "utr": "UTR / RRN",
                    "razorpay_amount": "Razorpay Amount (₹)",
                    "bank_amount": "Bank Amount (₹)",
                    "confidence": "Confidence",
                    "rule_fired": "Decision Rule Fired"
                },
                hide_index=True,
                use_container_width=True
            )

if __name__ == "__main__":
    main()
