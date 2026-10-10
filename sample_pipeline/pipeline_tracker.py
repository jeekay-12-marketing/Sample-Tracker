"""
Pipeline Tracker — view and update active pipeline entries.
Shows full stage history and allows advancing to next stage.
"""
import html
import streamlit as st
import pandas as pd
from datetime import date, datetime
from samples_new.sample_constants import SAMPLE_CSS
from sample_pipeline.sample_pipeline_firestore import (
    load_pipeline_entries, update_pipeline_stage,
    get_pipeline_entry, STAGES, STAGE_ORDER
)
from sample_pipeline.sample_pipeline_sync import silent_pipeline_sync


# ─────────────────────────────────────────
# CSS
# ─────────────────────────────────────────
TRACKER_CSS = """
<style>
.pipeline-card {
    background: #FFFFFF;
    border: 1.5px solid #DDD5C5;
    border-radius: 14px;
    padding: 1.2rem 1.6rem;
    margin-bottom: 1rem;
    position: relative;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(27,42,74,0.05);
    transition: box-shadow 0.15s ease;
}
.pipeline-card:hover {
    box-shadow: 0 4px 16px rgba(27,42,74,0.1);
}
.pipeline-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
}
.pipeline-card.enquiry::before          { background: #6B7A99; }
.pipeline-card.supplier_enquiry::before { background: #F57F17; }
.pipeline-card.shipped::before          { background: #1565C0; }
.pipeline-card.stock_received::before   { background: #6A1B9A; }
.pipeline-card.handed_over::before      { background: #2E7D32; }

.pipeline-customer {
    font-family: 'Cormorant Garamond', serif;
    font-size: 1.5rem; font-weight: 700;
    color: #1B2A4A; margin-bottom: 2px;
    text-transform: uppercase;
}
.pipeline-product {
    font-family: 'Outfit', sans-serif;
    font-size: 1.15rem; color: #C9A84C;
    font-weight: 600; margin-bottom: 8px;
}
.pipeline-meta {
    font-family: 'Outfit', sans-serif;
    font-size: 0.98rem; color: #6B7A99;
    display: flex; flex-wrap: wrap; gap: 12px;
}
.stage-badge {
    display: inline-flex; align-items: center; gap: 5px;
    border-radius: 20px; padding: 4px 12px;
    font-size: 0.98rem; font-weight: 700;
    font-family: 'Outfit', sans-serif;
}
.stage-enquiry          { background:#F0F4FF; color:#3949AB; border:1.5px solid #9FA8DA; }
.stage-supplier_enquiry { background:#FFF8E1; color:#F57F17; border:1.5px solid #FFD54F; }
.stage-shipped          { background:#E3F2FD; color:#1565C0; border:1.5px solid #90CAF9; }
.stage-stock_received   { background:#F3E5F5; color:#6A1B9A; border:1.5px solid #CE93D8; }
.stage-handed_over      { background:#E8F5E9; color:#2E7D32; border:1.5px solid #A5D6A7; }

.timeline {
    border-left: 2px solid #DDD5C5;
    margin-left: 10px;
    padding-left: 16px;
    margin-top: 8px;
}
.timeline-item {
    position: relative;
    margin-bottom: 10px;
    font-family: 'Outfit', sans-serif;
    font-size: 0.95rem;
    color: #1B2A4A;
}
.timeline-item::before {
    content: '';
    position: absolute;
    left: -22px; top: 5px;
    width: 10px; height: 10px;
    border-radius: 50%;
    background: #C9A84C;
    border: 2px solid #FFFFFF;
    box-shadow: 0 0 0 2px #C9A84C;
}
.timeline-item.pending::before {
    background: #DDD5C5;
    box-shadow: 0 0 0 2px #DDD5C5;
}
.timeline-date {
    font-size: 0.95rem; color: #6B7A99; margin-bottom: 1px;
}
.update-form {
    background: #FAF7F2;
    border: 1.5px solid #DDD5C5;
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    margin-top: 0.8rem;
}
</style>
"""


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def fmt_date(val) -> str:
    if val is None or (hasattr(val, '__class__') and
                       val.__class__.__name__ == 'NaTType'):
        return "—"
    try:
        if pd.isna(val):
            return "—"
    except:
        pass
    if hasattr(val, 'strftime'):
        return val.strftime("%d %b %Y")
    return str(val)[:10] if val else "—"


def stage_badge(stage: str) -> str:
    info = STAGES.get(stage, {"label": stage, "icon": ""})
    return (f'<span class="stage-badge stage-{stage}">'
            f'{info["icon"]} {info["label"]}</span>')



def next_stage(current: str, in_stock: str) -> str | None:
    """Return next stage given current stage and in_stock value."""
    if current == "enquiry":
        return "handed_over" if in_stock == "Yes" else "supplier_enquiry"
    idx = STAGE_ORDER.index(current) if current in STAGE_ORDER else -1
    if idx == -1 or idx >= len(STAGE_ORDER) - 1:
        return None
    return STAGE_ORDER[idx + 1]


# ─────────────────────────────────────────
# STAGE UPDATE FORMS
# ─────────────────────────────────────────
def render_update_form(row: pd.Series, doc_id: str):
    stage    = row.get("stage", "enquiry")
    in_stock = row.get("in_stock", "No")
    nxt      = next_stage(stage, in_stock)

    if nxt is None:
        st.success("✅ This sample has been handed over. Track feedback in Detailed Info.")
        return

    nxt_info   = STAGES.get(nxt, {})
    confirm_key = f"confirm_{doc_id}"
    success_key = f"success_{doc_id}"
    success_label_key = f"success_label_{doc_id}"

    # ── Global lock: if a DIFFERENT card has an undismissed success
    # message, block updates here. This is the direct fix for "the next
    # card opens and the user accidentally updates it too" — it makes
    # that physically impossible until the pending confirmation is
    # dismissed, instead of relying on the user noticing in time.
    pinned_other = st.session_state.get("_pt_pinned", set()) - {doc_id}
    if pinned_other and not st.session_state.get(success_key):
        st.warning(
            "⚠️ Dismiss the update confirmation above first "
            "before updating this card."
        )
        return

    # ── Show success message if just updated ──
    # IMPORTANT: nxt_info above is recomputed from this row's CURRENT
    # stage on every rerun. Once the update lands, the row's stage has
    # already advanced, so nxt would now point to the stage AFTER the
    # one that was just confirmed. That mismatch was why the banner
    # could show the wrong label (e.g. "Supplier Shipped" right after
    # confirming "Supplier Contacted"). We store the label at the
    # moment of confirmation instead, so this banner is never computed
    # from a stage that's already moved on.
    if st.session_state.get(success_key):
        confirmed_label = st.session_state.get(success_label_key, "the next stage")
        st.markdown(
            f"<div style='background:#E8F5E9;border:2px solid #2E7D32;"
            f"border-radius:8px;padding:14px 18px;font-family:Outfit,sans-serif;"
            f"font-size:0.95rem;color:#2E7D32;box-shadow:0 2px 8px rgba(46,125,50,0.15);'>"
            f"✅ <b>Updated to {confirmed_label}!</b><br>"
            f"<span style='font-size:0.8rem;color:#2E7D32;'>"
            f"This card stays open until you dismiss this message — "
            f"click Dismiss below before updating another card.</span></div>",
            unsafe_allow_html=True
        )
        if st.button("↩ Dismiss", key=f"dismiss_{doc_id}",
                    width='content', type="primary"):
            st.session_state.pop(success_key, None)
            st.session_state.pop(success_label_key, None)
            st.session_state.setdefault("_pt_pinned", set()).discard(doc_id)
            st.rerun()
        return  # ← don't show update form again

    st.markdown(
        f'<div class="update-form"><b style="font-family:Outfit,sans-serif;'
        f'color:#1B2A4A;">Next: {nxt_info.get("icon","")} '
        f'{nxt_info.get("label","")}</b></div>',
        unsafe_allow_html=True
    )
    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

    key_prefix = f"upd_{doc_id}"
    updates    = {}
    valid      = True

    if nxt == "supplier_enquiry":
        sup_enq_date = st.date_input(
            "Enquiry Sent to Supplier Date *",
            value=date.today(), key=f"{key_prefix}_sup_enq"
        )
        updates["supplier_enquiry_date"] = str(sup_enq_date)

    elif nxt == "shipped":
        ship_date = st.date_input(
            "Supplier Shipment Date *",
            value=date.today(), key=f"{key_prefix}_ship"
        )
        updates["supplier_shipment_date"] = str(ship_date)

    elif nxt == "stock_received":
        recv_date = st.date_input(
            "Stock Received Date *",
            value=date.today(), key=f"{key_prefix}_recv"
        )
        updates["stock_received_date"] = str(recv_date)

    elif nxt == "handed_over":
        col1, col2, col3 = st.columns(3)
        with col1:
            ho_date = st.date_input(
                "Handover Date *",
                value=date.today(), key=f"{key_prefix}_ho"
            )
        with col2:
            ho_by = st.text_input(
                "Handed Over By *",
                placeholder="e.g. Mr. Rajan",
                key=f"{key_prefix}_ho_by"
            )
        with col3:
            ho_to = st.text_input(
                "Handed Over To *",
                placeholder="e.g. Ms. Priya",
                key=f"{key_prefix}_ho_to"
            )
        if not ho_by.strip() or not ho_to.strip():
            valid = False
        updates["handover_date"]  = str(ho_date)
        updates["handed_over_by"] = ho_by.strip()
        updates["handed_over_to"] = ho_to.strip()

    # ── Two step confirm ──
    if not st.session_state.get(confirm_key):
        # Step 1 — show update button
        if st.button(
            f"📋 Mark as {nxt_info.get('label','')}",
            key=f"{key_prefix}_request",
            width='content'
        ):
            if not valid:
                st.error("⚠️ Please fill all required fields.")
            else:
                st.session_state[confirm_key] = updates
                st.rerun()
    else:
        # Step 2 — confirm or cancel
        st.markdown(
            "<div style='background:#FFF8E1;border:1.5px solid #FFD54F;"
            "border-radius:8px;padding:10px 14px;font-family:Outfit,sans-serif;"
            "font-size:0.90rem;color:#F57F17;margin-bottom:8px;'>"
            f"⚠️ Confirm: Mark as <b>{nxt_info.get('label','')}</b>? "
            "This cannot be undone.</div>",
            unsafe_allow_html=True
        )
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("✅ Yes, Confirm", key=f"{key_prefix}_confirm",
                        type="primary", width='content'):
                confirmed_updates = st.session_state.pop(confirm_key, {})

                update_pipeline_stage(doc_id, confirmed_updates, nxt)
                if nxt == "handed_over":

                    # Get full doc to write to main sheet
                    from sample_pipeline.sample_pipeline_firestore import get_pipeline_entry
                    from sample_pipeline.sample_pipeline_sync import move_to_main_sheet
                    full_doc = get_pipeline_entry(doc_id)
                    full_doc.update(confirmed_updates)  # include latest handover fields
                    move_to_main_sheet(full_doc)

                    # Handover is terminal — the doc is gone from the
                    # pipeline collection, there's nothing left to keep
                    # tracking here. Instead of faking a card in place,
                    # switch the whole page to a dedicated success view.
                    st.session_state["pt_view"] = "handover_success"
                    st.session_state["pt_handover_customer"] = row.get("customer", "—")
                    st.session_state["pt_handover_product"] = row.get("sample_product", "—")
                    st.rerun()
                else:
                    silent_pipeline_sync()
                    load_pipeline_entries.clear()
                    st.session_state[success_key] = True
                    st.session_state[success_label_key] = nxt_info.get("label", nxt)
                    pinned = st.session_state.setdefault("_pt_pinned", set())
                    pinned.add(doc_id)
                    st.rerun()

        with col_no:
            if st.button("✕ Cancel", key=f"{key_prefix}_cancel",
                        width='content'):
                st.session_state.pop(confirm_key, None)
                st.rerun()

# ─────────────────────────────────────────
# TIMELINE DISPLAY
# ─────────────────────────────────────────
def render_timeline(row: pd.Series):
    in_stock = row.get("in_stock", "No")
    stage    = row.get("stage", "enquiry")

    # Define timeline steps based on in_stock
    if in_stock == "Yes":
        steps = [
            ("enquiry",    "Enquiry Received",   row.get("enquiry_date")),
            ("handed_over","Handed Over",         row.get("handover_date")),
        ]
    else:
        steps = [
            ("enquiry",          "Enquiry Received",        row.get("enquiry_date")),
            ("supplier_enquiry", "Supplier Contacted",      row.get("supplier_enquiry_date")),
            ("shipped",          "Supplier Shipped",        row.get("supplier_shipment_date")),
            ("stock_received",   "Stock Received",          row.get("stock_received_date")),
            ("handed_over",      "Handed Over",             row.get("handover_date")),
        ]

    stage_order_idx = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else 0

    # One markdown call for the whole timeline instead of 3 + N (open div,
    # close div, and one call per step) — each call is a separate
    # frontend round-trip. Each fragment is .strip()'d before joining so
    # no blank line survives at the seams (a blank line followed by
    # indented HTML gets treated as a Markdown code block instead of
    # being rendered — bit us on notifications.py, avoiding it here).
    html_parts = ['<div class="timeline">']
    for step_stage, step_label, step_date in steps:
        step_idx = STAGE_ORDER.index(step_stage) if step_stage in STAGE_ORDER else 0
        done     = step_idx <= stage_order_idx
        cls      = "" if done else "pending"
        date_str = fmt_date(step_date) if done else "Pending"
        icon     = STAGES.get(step_stage, {}).get("icon", "")
        handover_details = ""
        if step_stage == "handed_over" and done:
            handed_over_by = html.escape(str(row.get("handed_over_by") or "—"))
            handed_over_to = html.escape(str(row.get("handed_over_to") or "—"))
            handover_details = (
                f'<div class="timeline-date">By: {handed_over_by} · '
                f'To: {handed_over_to}</div>'
            )
        html_parts.append(f"""
        <div class="timeline-item {cls}">
            <div class="timeline-date">{date_str}</div>
            {icon} {step_label}
            {handover_details}
        </div>
        """.strip())
    html_parts.append("</div>")

    st.markdown("".join(html_parts), unsafe_allow_html=True)


# ─────────────────────────────────────────
# HANDOVER SUCCESS PAGE
# ─────────────────────────────────────────
def _show_handover_success():
    """
    Dedicated full-page success view shown right after a sample is
    handed over. Handover is terminal — the doc is deleted from the
    pipeline collection — so there's no card left to keep tracking
    here. A clean separate page avoids reshuffling/scrolling games
    trying to keep a "ghost" card alive in the list below.
    """
    customer = st.session_state.get("pt_handover_customer", "—")
    product  = st.session_state.get("pt_handover_product", "—")

    st.markdown("""
    <div class="sd-hero">
        <div class="sd-eyebrow">Sample Pipeline</div>
        <div class="sd-title">Handover <em>Complete</em></div>
        <div class="sd-divider"></div>
    </div>""", unsafe_allow_html=True)

    st.markdown(
        f"<div style='background:#E8F5E9;border:2px solid #2E7D32;"
        f"border-radius:12px;padding:20px 24px;font-family:Outfit,sans-serif;"
        f"box-shadow:0 2px 8px rgba(46,125,50,0.15);margin-bottom:1.5rem;'>"
        f"<div style='font-size:1.05rem;color:#2E7D32;font-weight:700;'>"
        f"✅ Sample handed over to {customer}</div>"
        f"<div style='font-size:0.88rem;color:#2E7D32;margin-top:4px;'>"
        f"📦 {product} has been moved out of the pipeline and into the main sheet.</div>"
        f"<div style='font-size:0.82rem;color:#1B2A4A;margin-top:10px;'>"
        f"Track feedback for this sample from the <b>Detailed Info</b> page from now on.</div>"
        f"</div>",
        unsafe_allow_html=True
    )

    if st.button("← Back to Pipeline Tracker", type="primary", width='content'):
        st.session_state.pop("pt_view", None)
        st.session_state.pop("pt_handover_customer", None)
        st.session_state.pop("pt_handover_product", None)
        st.rerun()


# ─────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────
def show_pipeline_tracker():
    # ── Gate: show the handover success page instead of the tracker ──
    if st.session_state.get("pt_view") == "handover_success":
        _show_handover_success()
        return

    st.markdown(SAMPLE_CSS, unsafe_allow_html=True)
    st.markdown(TRACKER_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="sd-hero">
        <div class="sd-eyebrow">Sample Pipeline</div>
        <div class="sd-title">Pipeline <em>Tracker</em></div>
        <div class="sd-sub">Track active sample enquiries through each stage — from enquiry to handover.</div>
        <div class="sd-divider"></div>
    </div>""", unsafe_allow_html=True)

    with st.spinner("Loading pipeline..."):
        df = load_pipeline_entries()

    if df.empty:
        st.info("No pipeline entries yet. Use **New Enquiry** to add one.")
        return

    def _reset_pt_filters():
        st.session_state["pt_branch"] = "-Select-"
        st.session_state["pt_area"]   = "-Select-"
        st.session_state["pt_cust"]   = "-Select-"
        st.session_state["pt_stage"]  = "-Select-"
        st.session_state["pt_stock"]  = "-Select-"

    # ── Filters ──
    col1, col2, col3, col4, col5, col6  = st.columns(6)
    with col1:
        branches   = ["-Select-"] + sorted(df["branch"].dropna().unique().tolist())
        sel_branch = st.selectbox("Branch", branches, key="pt_branch")
    with col2:
        areas = ["-Select-"] + sorted(df["area"].dropna().unique().tolist())
        sel_area = st.selectbox("Area", areas, key="pt_area")
    with col3:
        customers = ["-Select-"] + sorted(df["customer"].dropna().unique().tolist())
        sel_cust  = st.selectbox("Customer", customers, key="pt_cust") 
    with col4:
        stage_opts = ["-Select-"] + [STAGES[s]["label"] for s in STAGE_ORDER]
        sel_stage  = st.selectbox("Stage", stage_opts, key="pt_stage")          
    with col5:
        stock_opts = ["-Select-", "Yes", "No"]
        sel_stock  = st.selectbox("In Stock?", stock_opts, key="pt_stock")
    with col6:
        st.markdown("<div style='height:1.85rem;'></div>", unsafe_allow_html=True)
        st.button(" 🚫 Clear Selection", key="pt_reset_filters", width='stretch', on_click=_reset_pt_filters)
        

    any_filter_active = (
        sel_branch != "-Select-" or
        sel_cust != "-Select-" or 
        sel_area != "-Select-" or
        sel_stage != "-Select-" or 
        sel_stock != "-Select-"
    )

    # ── Apply filters ──
    fdf = df.copy()
    # Exclude completed (handed_over) by default unless selected
    #if sel_stage == "-Select-":
     #   fdf = fdf[fdf["stage"] != "handed_over"]
    if sel_branch != "-Select-":
        fdf = fdf[fdf["branch"] == sel_branch]
    if sel_area != "-Select-":
        fdf = fdf[fdf["area"] == sel_area]  
    if sel_cust != "-Select-":
        fdf = fdf[fdf["customer"] == sel_cust]              
    if sel_stage != "-Select-":
        sel_stage_key = next(
            (k for k, v in STAGES.items() if v["label"] == sel_stage), None
        )
        if sel_stage_key:
            fdf = fdf[fdf["stage"] == sel_stage_key]
    if sel_stock != "-Select-":
        fdf = fdf[fdf["in_stock"] == sel_stock]

    total = len(fdf)
    pipeline_len = fdf[fdf["stage"] != "handed_over"]

    if not any_filter_active:
        st.info("👆 Please select a **Branch**, **Area**, **Customer**, **Stage**, or **In Stock** filter to view pipeline cards.")
        st.markdown(
            f"<div style='font-family:Outfit,sans-serif;font-size:0.85rem;color:#6B7A99;margin:1rem 0;'>"
            f"<b>Total {len(pipeline_len)}</b> entries in pipeline that have <b> not been handed over yet </b>!</div>",
            unsafe_allow_html=True
        )
        return   # ← Don't show cards
    
    st.markdown(
        f"<div style='font-family:Outfit,sans-serif;font-size:0.85rem;"
        f"color:#6B7A99;margin-bottom:1.5rem;'>"
        f"<b>{total}</b> matching entries"
        f"{'  ·  All active stages' if sel_stage == '-Select-' else ''}</div>",
        unsafe_allow_html=True
    )

    if fdf.empty:
        st.info("No entries match the current filters.")
        return

    # ── Pagination ──
    ITEMS_PER_PAGE = 10
    total_pages    = max(1, (total - 1) // ITEMS_PER_PAGE + 1)
    page_num       = st.session_state.get("pt_page", 0)

    filter_sig = f"{total}_{sel_branch}_{sel_stage}_{sel_stock}"
    if st.session_state.get("_pt_sig") != filter_sig:
        st.session_state["pt_page"] = 0
        st.session_state["_pt_sig"] = filter_sig
        page_num = 0

    start   = page_num * ITEMS_PER_PAGE
    end     = start + ITEMS_PER_PAGE
    page_df = fdf.iloc[start:end]

    pinned_ids = {
        doc_id for doc_id in st.session_state.get("_pt_pinned", set())
    }
    if pinned_ids:
        missing_pinned = df[df["_doc_id"].isin(pinned_ids)
                            & ~df["_doc_id"].isin(page_df["_doc_id"])]
        if not missing_pinned.empty:
            # Merge by df's original row order so pinned rows land back
            # near where they used to sit relative to the other cards
            # on this page, instead of jumping to position 1.
            combined = pd.concat([page_df, missing_pinned])
            # df.index reflects original load order — sort by that.
            combined = combined.loc[
                combined.index.isin(df.index)
            ].reindex(df.index.intersection(combined.index))
            page_df = combined

    # ── Cards ──
    for _, row in page_df.iterrows():
        doc_id   = row.get("_doc_id", "")
        stage    = row.get("stage", "enquiry")
        customer = str(row.get("customer", "—"))
        product  = str(row.get("sample_product", "—"))
        branch   = str(row.get("branch", "—"))
        area     = str(row.get("area", "—"))
        supplier = str(row.get("supplier", "—"))
        qty      = str(row.get("standard_qty", "—"))
        units    = str(row.get("standard_unit", "-"))
        in_stock = str(row.get("in_stock", "No"))
    
        enq_date = fmt_date(row.get("enquiry_date"))

        with st.container():
            st.markdown(f"""
            <div class="pipeline-card {stage}">
                <div style="display:flex;justify-content:space-between;
                            align-items:flex-start;flex-wrap:wrap;gap:8px;">
                    <div>
                        <div class="pipeline-customer">{customer}</div>
                        <div class="pipeline-product">📦 {product}</div>
                    </div>
                    <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
                        {stage_badge(stage)}
                    </div>
                </div>
                <div class="pipeline-meta">
                    <span>📍 {branch} — {area}</span>
                    <span>🏭 Supplier: {supplier}</span>
                    <span>🧪 Qty: {qty}{units}</span>
                    <span>📅 Enquiry: {enq_date}</span>
                    <span>📦 In Stock: <b>{in_stock}</b></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            should_expand = bool(
                st.session_state.get(f"success_{doc_id}")
                or st.session_state.get(f"confirm_{doc_id}")
                or doc_id in st.session_state.get("_pt_pinned", set())
            )

            with st.expander("📋 View Details & Update Stage", expanded=should_expand):
                col_timeline, col_update = st.columns([1, 1], gap="large")

                with col_timeline:
                    st.markdown(
                        "<div style='font-family:Outfit,sans-serif;font-size:0.78rem;"
                        "font-weight:700;letter-spacing:0.1em;text-transform:uppercase;"
                        "color:#C9A84C;margin-bottom:8px;'>Stage Timeline</div>",
                        unsafe_allow_html=True
                    )
                    render_timeline(row)

                with col_update:
                    st.markdown(
                        "<div style='font-family:Outfit,sans-serif;font-size:0.78rem;"
                        "font-weight:700;letter-spacing:0.1em;text-transform:uppercase;"
                        "color:#C9A84C;margin-bottom:8px;'>Update Stage</div>",
                        unsafe_allow_html=True
                    )
                    render_update_form(row, doc_id)

    # ── Pagination controls ──
    st.divider()
    col_prev, col_info, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("← Prev", disabled=(page_num == 0),
                    key="pt_prev", width='content'):
            st.session_state["pt_page"] = page_num - 1
            st.rerun()
    with col_info:
        st.markdown(
            f"<div style='text-align:center;font-family:Outfit,sans-serif;"
            f"font-size:0.85rem;color:#6B7A99;padding-top:6px;'>"
            f"Page {page_num+1} of {total_pages}</div>",
            unsafe_allow_html=True
        )
    with col_next:
        if st.button("Next →", disabled=(page_num >= total_pages - 1),
                    key="pt_next", width='content'):
            st.session_state["pt_page"] = page_num + 1
            st.rerun()