"""
Detailed Info page — uses global sidebar filters from router.
Cards: sample details + inline-editable feedback history.
PDF generation respecting all active filters.
"""
import html
import io
import streamlit as st
import pandas as pd
from datetime import datetime, date

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, KeepTogether
)

from samples_new.sample_constants import (
    SAMPLE_CSS, COL_BRANCH, COL_AREA, COL_CUSTOMER,
    COL_SAMPLE_PROD, COL_HO_DATE, COL_HO_BY, COL_HO_TO,
    COL_CONTACT, COL_QTY, COL_FEEDBACK
)
from samples_new.sample_firestore import (
    load_feedback_for_sample, add_feedback,
    classify_feedback, get_urgency, build_sample_key,
    add_feedback_with_status, delete_feedback, is_admin
)
from samples_new.sample_firestore import get_db, delete_entire_card


def esc(val) -> str:
    if pd.isna(val) or val is None:
        return "—"
    return html.escape(str(val))


# ─────────────────────────────────────────
# FIRESTORE EDIT
# ─────────────────────────────────────────
def update_feedback_entry(customer, product, ho_date, entry_id, new_text, new_date, new_status="Pending", purchased="Purchase Data Not Available"):
    db  = get_db()
    key = build_sample_key(customer, product, ho_date)
    db.collection("sample_feedback").document(key)\
      .collection("entries").document(entry_id).update({
          "feedback":      new_text.strip(),
          "feedback_date": str(new_date),
          "fb_status":     new_status, 
          "purchased":     purchased,
          "edited_at":     datetime.now().isoformat(),
          "edited_by":     st.session_state.get("email", ""),
      })
    print(f"[update_feedback_entry] Firestore write done, now calling sync_latest_feedback_to_sheet...")
    # ← sync latest to sheet
    from samples_new.sample_firestore import sync_latest_feedback_to_sheet
    sync_latest_feedback_to_sheet(customer, product, ho_date)
    load_feedback_for_sample.clear()
    from samples_new.sample_firestore import load_all_latest_feedback
    load_all_latest_feedback.clear()


# ─────────────────────────────────────────
# PDF GENERATOR
# ─────────────────────────────────────────
def generate_sample_pdf(grouped_data: dict, filters_desc: str) -> bytes:
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors as rl_colors

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=20*mm, bottomMargin=20*mm
    )

    W = A4[0] - 36*mm  # usable width

    NAVY  = colors.HexColor("#1B2A4A")
    GOLD  = colors.HexColor("#C9A84C")
    MUTED = colors.HexColor("#8A9BBB")
    CREAM = colors.HexColor("#F5F1EA")
    WHITE = colors.HexColor("#FFFFFF")
    LGREY = colors.HexColor("#DDD5C5")

    def safe(text):
        return (str(text) or "—")            .replace("&","&amp;")            .replace("<","&lt;")            .replace(">","&gt;")

    S_title = ParagraphStyle("t", fontSize=22, fontName="Times-Bold",
        textColor=NAVY, alignment=TA_CENTER, spaceAfter=2)
    S_sub   = ParagraphStyle("sub", fontSize=9, fontName="Times-Roman",
        textColor=MUTED, alignment=TA_CENTER, spaceAfter=0)
    S_cust  = ParagraphStyle("c", fontSize=14, fontName="Times-Bold",
        textColor=WHITE, spaceBefore=0, spaceAfter=0, leading=18)
    S_prod  = ParagraphStyle("p", fontSize=11, fontName="Times-Bold",
        textColor=GOLD, spaceBefore=10, spaceAfter=2)
    S_meta  = ParagraphStyle("m", fontSize=9, fontName="Times-Roman",
        textColor=MUTED, spaceAfter=6, leading=13)
    S_fblbl = ParagraphStyle("fl", fontSize=8, fontName="Times-Bold",
        textColor=MUTED, spaceBefore=6, spaceAfter=1, leading=11)
    S_fbtext= ParagraphStyle("ft", fontSize=10, fontName="Times-Roman",
        textColor=NAVY, spaceAfter=4, leading=14,
        leftIndent=0, rightIndent=0)
    S_nofb  = ParagraphStyle("nf", fontSize=9, fontName="Times-Italic",
        textColor=MUTED, spaceAfter=6)

    story = []

    # ── Title block ──
    story.append(Paragraph("Samples' Feedback Report", S_title))
    story.append(Spacer(1, 3*mm))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d %b %Y')}  &nbsp;·&nbsp;  {safe(filters_desc)}",
        S_sub
    ))
    story.append(Spacer(1, 3*mm))
    story.append(HRFlowable(width="100%", thickness=2.5, color=GOLD,
                            spaceBefore=0, spaceAfter=10))

    for customer_name, samples in grouped_data.items():
        # ── Customer header — navy band ──
        cust_para = Paragraph(safe(customer_name), S_cust)
        cust_table = Table([[cust_para]], colWidths=[W])
        cust_table.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,-1), NAVY),
            ("TOPPADDING",   (0,0), (-1,-1), 8),
            ("BOTTOMPADDING",(0,0), (-1,-1), 8),
            ("LEFTPADDING",  (0,0), (-1,-1), 10),
            ("RIGHTPADDING", (0,0), (-1,-1), 10),
            ("ROUNDEDCORNERS", [4]),
        ]))
        story.append(cust_table)
        story.append(Spacer(1, 3*mm))

        for si, sample in enumerate(samples, 1):
            product   = safe(sample["product"])
            ho_date   = safe(sample["ho_date"])
            ho_by     = safe(sample["ho_by"])
            ho_to     = safe(sample.get("ho_to", "—"))
            contact   = safe(sample["contact"])
            qty       = safe(sample["qty"])
            feedbacks = sample["feedbacks"]

            story.append(Paragraph(f"Sample {si}: {product}", S_prod))
            story.append(Paragraph(
                f"Handed over: <b>{ho_date}</b> &nbsp;·&nbsp; "
                f"By: <b>{ho_by}</b> &nbsp;·&nbsp; "
                f"To: <b>{ho_to}</b> &nbsp;·&nbsp; "
                f"Contact: <b>{contact}</b> &nbsp;·&nbsp; "
                f"Qty: <b>{qty}</b>",
                S_meta
            ))

            if not feedbacks:
                story.append(Paragraph("No feedback recorded yet.", S_nofb))
            else:
                for fb in feedbacks:
                    label   = safe(fb["label"])
                    fb_date = safe(fb["date"])
                    fb_by   = safe(fb["by"])
                    fb_text = safe(fb["text"]) or "—"

                    story.append(Paragraph(
                        f"{label} &nbsp;·&nbsp; {fb_date} &nbsp;·&nbsp; {fb_by}",
                        S_fblbl
                    ))

                    # Feedback text in cream box via Table
                    fb_para = Paragraph(fb_text, S_fbtext)
                    fb_table = Table([[fb_para]], colWidths=[W - 4*mm])
                    fb_table.setStyle(TableStyle([
                        ("BACKGROUND",   (0,0), (-1,-1), CREAM),
                        ("TOPPADDING",   (0,0), (-1,-1), 7),
                        ("BOTTOMPADDING",(0,0), (-1,-1), 7),
                        ("LEFTPADDING",  (0,0), (-1,-1), 10),
                        ("RIGHTPADDING", (0,0), (-1,-1), 10),
                        ("LINEBELOW",    (0,0), (-1,-1), 0.5, LGREY),
                        ("LINEABOVE",    (0,0), (0,0),   0.5, LGREY),
                        ("LINEBEFORE",   (0,0), (-1,-1), 2,   GOLD),
                    ]))
                    story.append(fb_table)
                    story.append(Spacer(1, 1.5*mm))

            if si < len(samples):
                story.append(Spacer(1, 2*mm))
                story.append(HRFlowable(width="40%", thickness=0.5,
                                        color=LGREY, spaceBefore=2, spaceAfter=2))

        story.append(Spacer(1, 6*mm))
        story.append(HRFlowable(width="100%", thickness=1,
                                color=LGREY, spaceBefore=0, spaceAfter=8))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ─────────────────────────────────────────
# ADD FEEDBACK DIALOG
# ─────────────────────────────────────────
@st.dialog("Add Feedback")
def add_feedback_dialog(customer, product, ho_date):
    st.markdown(f"**{esc(customer)}** · {esc(product)}")
    fb_date   = st.date_input("Feedback Date *", value=date.today(), key="dlg_fb_date")
    fb_status = st.selectbox(                          
        "Classify Feedback *",
        ["Positive", "Negative", "Pending", "Hold"],
        key="dlg_fb_status"
    )
    fb_text = st.text_area(
        "Feedback Text *", placeholder="Enter feedback...",
        height=120, key="dlg_fb_text"
    )

    if fb_status =="Positive":
        purchased = st.selectbox(
        "Purchased?",
        ["Yes", "Not Yet", "No"],
        key="dlg_purchased"
    )
    elif fb_status == "Negative":
        purchased = "No"
        st.selectbox("Purchased?", ["No"], disabled=True, key="dlg_purchased_dis")
    else:
        purchased = "Purchase Data Not Available"
        st.selectbox("Purchased?", ["Purchase Data Not Available"],
                    disabled=True, key="dlg_purchased_na")
        
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save", type="primary",
                    width='stretch', key="dlg_save"):
            if not fb_text.strip():
                st.error("Please enter feedback text.")
            else:
                add_feedback_with_status(          
                    customer, product, ho_date,
                    fb_text, fb_date, fb_status, purchased
                )
                st.session_state["dlg_saved"] = True
                st.rerun()

# ─────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────
def show_detailed_info(fdf: pd.DataFrame):
    """
    fdf: already-filtered dataframe passed from router
         (global filters already applied)
    """
    st.markdown(SAMPLE_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="sd-hero">
        <div class="sd-eyebrow">Sample Intelligence</div>
        <div class="sd-title">Detailed <em>Info</em></div>
        <div class="sd-sub">Full feedback history per company.</div>
        <div class="sd-divider"></div>
    </div>""", unsafe_allow_html=True)
    sheet_sync_error = st.session_state.pop("feedback_sheet_sync_error", None)
    if sheet_sync_error:
        st.warning(
            "Feedback was saved in Firebase, but the main sheet could not be "
            f"updated: {sheet_sync_error}"
        )

    if st.session_state.pop("_card_deleted", False):
        st.rerun() 

    if fdf.empty:
        st.warning("No samples match the current filters.")
        return

    from samples_new.sample_constants import urgency_badge, feedback_badge

    fdf = fdf.copy()

    def _reset_di_top_filters():
        st.session_state["di_top_branch"]   = "-Select-"
        st.session_state["di_top_area"]     = "-Select-"
        st.session_state["di_top_customer"] = "-Select-"
        st.session_state["di_top_product"]  = "-Select-"
        st.session_state["di_top_urgency"]  = "-Select-"

    col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1, 1, 1, 0.7])

    with col1:
        branches = ["-Select-"] + sorted(fdf[COL_BRANCH].dropna().unique().tolist())
        sel_branch = st.selectbox("Branch", branches, key="di_top_branch")

    with col2:
        # Area depends on branch
        area_pool = fdf if sel_branch == "-Select-" else fdf[fdf[COL_BRANCH] == sel_branch]
        areas = ["-Select-"] + sorted(area_pool[COL_AREA].dropna().unique().tolist())
        sel_area = st.selectbox("Area", areas, key="di_top_area")

    with col3:
        cust_pool = area_pool if sel_area == "-Select-" else area_pool[area_pool[COL_AREA] == sel_area]
        customers = ["-Select-"] + sorted(cust_pool[COL_CUSTOMER].dropna().unique().tolist())
        sel_customer = st.selectbox("Customer", customers, key="di_top_customer")

    with col4:
        products = ["-Select-"] + sorted(fdf[COL_SAMPLE_PROD].dropna().unique().tolist())
        sel_product = st.selectbox("Product", products, key="di_top_product")

    with col5:
        urg_opts = ["-Select-", "Critical", "Push Required", "Initial Follow-up", 
                   "Freshly Handed", "Responded", "Hold"]
        sel_urgency = st.selectbox("Urgency", urg_opts, key="di_top_urgency")

    with col6:
        st.markdown("<div style='height:1.85rem;'></div>", unsafe_allow_html=True)
        st.button(" 🚫 Clear Selection", key="di_top_clear", width='stretch', on_click=_reset_di_top_filters)

    # ── Check if any top filter is active ──
    any_top_filter_active = (
        sel_branch != "-Select-" or
        sel_area != "-Select-" or
        sel_customer != "-Select-" or
        sel_product != "-Select-" or
        sel_urgency != "-Select-"
    )

    filtered_df = fdf.copy()

    if sel_branch != "-Select-":
        filtered_df = filtered_df[filtered_df[COL_BRANCH] == sel_branch]
    if sel_area != "-Select-":
        filtered_df = filtered_df[filtered_df[COL_AREA] == sel_area]
    if sel_customer != "-Select-":
        filtered_df = filtered_df[filtered_df[COL_CUSTOMER] == sel_customer]
    if sel_product != "-Select-":
        filtered_df = filtered_df[filtered_df[COL_SAMPLE_PROD] == sel_product]
    if sel_urgency != "-Select-":
        filtered_df = filtered_df[filtered_df["Urgency"] == sel_urgency]

    if not any_top_filter_active:
        st.info("👆 Please select at least one filter above (Branch, Area, Customer, Product, or Urgency) to view detailed cards.")
        return
    
    # Continue with non-empty filtered data
    if filtered_df.empty:
        st.info("No samples match the selected filters.")
        return

    fdf = filtered_df  # Use the top-filtered data from here

    fdf = fdf.copy()

    fdf["ho_date_str"] = fdf[COL_HO_DATE].apply(
        lambda x: str(x.date()) if pd.notna(x) else ""
    )
    fdf = fdf.sort_values(COL_CUSTOMER)

    total_items = len(fdf)

    # ── Pagination setup ──
    ITEMS_PER_PAGE = 15
    total_pages    = max(1, (total_items - 1) // ITEMS_PER_PAGE + 1)
    page_num       = st.session_state.get("di_page", 0)

    filter_sig = f"{total_items}_{fdf[COL_CUSTOMER].iloc[0] if total_items > 0 else ''}"
    if st.session_state.get("_di_filter_sig") != filter_sig:
        st.session_state["di_page"]        = 0
        st.session_state["_di_filter_sig"] = filter_sig
        page_num = 0

    start    = page_num * ITEMS_PER_PAGE
    end      = start + ITEMS_PER_PAGE
    page_fdf = fdf.iloc[start:end]

    st.markdown(
        f"<div style='font-family:Outfit,sans-serif;font-size:0.85rem;"
        f"color:#6B7A99;margin-bottom:1rem;'>"
        f"Showing <b>{start+1}–{min(end,total_items)}</b> of <b>{total_items}</b> samples</div>",
        unsafe_allow_html=True
    )

    # ══════════════════════════════════════
    # LOOP 2 — Render UI cards (current page only)
    # ══════════════════════════════════════
    for idx, (_, row) in enumerate(page_fdf.iterrows()):
        customer = str(row.get(COL_CUSTOMER, "—"))
        product  = str(row.get(COL_SAMPLE_PROD, "—"))
        ho_date  = row[COL_HO_DATE]
        ho_str   = row["ho_date_str"]
        ho_disp  = ho_date.strftime("%d %b %Y") if pd.notna(ho_date) else "—"
        ho_by    = str(row.get(COL_HO_BY, "—"))
        ho_to    = str(row.get(COL_HO_TO, "—"))
        contact  = str(row.get(COL_CONTACT, "—"))
        qty      = str(row.get(COL_QTY, "—"))
        days_ago = int((pd.Timestamp.now() - ho_date).days) if pd.notna(ho_date) else 0
        branch = str(row.get(COL_BRANCH, "-"))
        area = str(row.get(COL_AREA, "-"))

        # ── Combined feedback ──
        sheet_fb_raw = row.get(COL_FEEDBACK, "")
        sheet_fb     = "" if pd.isna(sheet_fb_raw) or \
                       str(sheet_fb_raw).strip() in ("", "nan", "None", "-", "_") \
                       else str(sheet_fb_raw).strip()

        firestore_entries = load_feedback_for_sample(customer, product, ho_str)

        all_fb = []
        if sheet_fb:
            all_fb.append({
                "id":            "__sheet__",
                "feedback":      sheet_fb,
                "feedback_date": ho_str,
                "added_by":      "Original (Sheet)",
                "source":        "sheet"
            })
        for fb in firestore_entries:
            all_fb.append({**fb, "source": "firestore"})

        has_fb           = len(all_fb) > 0
        latest_fb        = all_fb[-1]["feedback"] if has_fb else ""
        latest_fb_status = all_fb[-1].get("fb_status") if has_fb else None
        fb_status        = classify_feedback(latest_fb, latest_fb_status)
        urgency          = get_urgency(days_ago, has_fb, fb_status)

        # ── Sample card ──
        with st.container():
            # ── Admin delete card button — rendered BEFORE the HTML card ──
            if is_admin():
                card_key         = build_sample_key(customer, product, ho_str)
                del_card_key     = f"del_card_{card_key}_{idx}"
                confirm_card_key = f"confirm_del_card_{card_key}_{idx}"

                # Put button top-right using columns
                _spacer, _del_col = st.columns([6, 1])
                with _del_col:
                    if st.button("🗑️ Delete Card",
                                key=del_card_key,
                                width='stretch'):
                        st.session_state[confirm_card_key] = True
                        st.rerun()

                if st.session_state.get(confirm_card_key):
                    st.error(
                        f"⚠️ Permanently delete **{customer} / {product}** "
                        f"from Firestore AND Spreadsheet? This cannot be undone."
                    )
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("🗑️ Yes, delete",
                                    key=f"yes_{del_card_key}",
                                    width='stretch', type="primary"):
                            with st.spinner("Deleting..."):
                                delete_entire_card(customer, product, ho_str)
                                from samples_new.sample_constants import load_sample_data  # ← add this
                                load_sample_data.clear()
                                st.session_state["_card_deleted"] = True
                                st.rerun()                                    # ← add this
                            st.session_state.pop(confirm_card_key, None)
                            st.rerun()
                    with cc2:
                        if st.button("✕ Cancel",
                                    key=f"no_{del_card_key}",
                                    width='stretch'):
                            st.session_state.pop(confirm_card_key, None)
                            st.rerun()

            st.markdown(f"""
            <div class="sample-card">
                <div style="display:flex;justify-content:space-between;
                            align-items:flex-start;flex-wrap:wrap;gap:8px;">
                    <div>
                        <div class="sample-card-title">{esc(customer)}</div>
                        <div class="sample-card-product">📦 {esc(product)}</div>
                    </div>
                    <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
                        {urgency_badge(urgency)}
                        {feedback_badge(fb_status)}
                    </div>
                </div>
                <div class="sample-card-meta">
                    <span>📅 Handed over: <b>{ho_disp}</b> ({days_ago}d ago)</span>
                    <span>🤝 By: <b>{esc(ho_by)}</b></span>
                    <span>➡️ To: <b>{esc(ho_to)}</b></span>
                    <span>👤 Contact: <b>{esc(contact)}</b></span>
                    <span>🧪 Qty: <b>{esc(qty)}</b></span>
                    <span> 🏢 Branch: <b>{esc(branch)}</b></span>
                    <span> 📍Area: <b>{esc(area)}</b></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            fb_count = len(all_fb)
            with st.expander(
                f"💬 Feedback History ({fb_count} {'entry' if fb_count == 1 else 'entries'})",
                expanded=False
            ):
                if not all_fb:
                    st.markdown(
                        "<div style='font-family:Outfit,sans-serif;font-size:0.90rem;"
                        "color:#6B7A99;padding:8px 0;'>No feedback recorded yet.</div>",
                        unsafe_allow_html=True
                    )
                else:
                    for i, fb in enumerate(all_fb):
                        label    = "Initial Feedback" if i == 0 else f"Follow-up {i}"
                        fb_date  = str(fb.get("feedback_date", ""))[:10]
                        added_by = fb.get("added_by", "")
                        fb_text  = fb.get("feedback", "")
                        is_sheet = fb.get("source") == "sheet"
                        entry_id = fb.get("id", "")

                        # ← idx added to make keys unique across duplicate rows
                        edit_key = f"editing_{build_sample_key(customer,product,ho_str)}_{entry_id}_{idx}"

                        sheet_tag = "&nbsp;·&nbsp;<span style='font-size:0.65rem;color:#DDD5C5;'>sheet</span>" if is_sheet else ""
                        st.markdown(
                            f"<div style='font-family:Outfit,sans-serif;font-size:0.90rem;"
                            f"font-weight:700;letter-spacing:0.1em;text-transform:uppercase;"
                            f"color:#6B7A99;margin-top:8px;margin-bottom:2px;'>{label}</div>"
                            f"<div style='font-family:Outfit,sans-serif;font-size:0.90rem;"
                            f"color:#6B7A99;margin-bottom:4px;'>"
                            f"📅 {fb_date} &nbsp;·&nbsp; 👤 {esc(added_by)}{sheet_tag}</div>",
                            unsafe_allow_html=True
                        )

                        if st.session_state.get(edit_key):
                            # ── Edit mode ──
                            new_text = st.text_area(
                                "Edit feedback", value=fb_text, height=80,
                                key=f"edit_text_{edit_key}",
                                label_visibility="collapsed"
                            )
                            new_date = st.date_input(
                                "Edit date",
                                value=pd.to_datetime(fb_date).date() if fb_date else date.today(),
                                key=f"edit_date_{edit_key}",
                                label_visibility="collapsed"
                            )
                            new_status = st.selectbox(
                                "Classify Feedback",
                                ["Positive", "Negative", "Pending", "Hold"],
                                index=["Positive","Negative","Pending","Hold"].index(
                                    fb.get("fb_status","Pending")
                                ) if fb.get("fb_status") in ["Positive","Negative","Pending","Hold"] else 2,
                                key=f"edit_status_{edit_key}"
                            )

                            if new_status == "Positive":
                                new_purchased = st.selectbox(
                                    "Purchased?",
                                    ["Yes", "Not Yet", "No"],
                                    index=["Yes","Not Yet","No"].index(fb.get("purchased","Not Yet"))
                                        if fb.get("purchased") in ["Yes","Not Yet","No"] else 1,
                                    key=f"edit_purchased_{edit_key}"
                                )
                            elif new_status == "Negative":
                                new_purchased = "No"
                                st.selectbox("Purchased?", ["No"], disabled=True,
                                            key=f"edit_purchased_dis_{edit_key}")
                            else:
                                new_purchased = "Purchase Data Not Available"


                            col_save, col_cancel = st.columns(2)
                            with col_save:
                                if st.button("💾 Save", key=f"save_{edit_key}",
                                            width='stretch', type="primary"):
                                    if new_text.strip():
                                        update_feedback_entry(
                                            customer, product, ho_str,
                                            entry_id, new_text, new_date, new_status, new_purchased
                                        )
                                        st.session_state.pop(edit_key, None)
                                        st.rerun()
                            with col_cancel:
                                if st.button("✕ Cancel", key=f"cancel_{edit_key}",
                                            width='stretch'):
                                    st.session_state.pop(edit_key, None)
                                    st.rerun()
                        else:
                            # ── Display mode ──
                            st.markdown(
                                f"<div style='font-family:Outfit,sans-serif;"
                                f"font-size:0.9rem;color:#1B2A4A;"
                                f"background:#F0EBE1;border-radius:6px;"
                                f"padding:8px 12px;margin-bottom:4px;"
                                f"line-height:1.5;'>{esc(fb_text)}</div>",
                                unsafe_allow_html=True
                            )


                            purchased_val = fb.get("purchased", "Purchase Data Not Available")
                            purchased_color = {
                                "Yes":                          "#2E7D32",
                                "Not Yet":                      "#E65100",
                                "No":                           "#B71C1C",
                                "Purchase Data Not Available":  "#6B7A99"
                            }.get(purchased_val, "#6B7A99")
                            st.markdown(
                                f"<div style='font-family:Outfit,sans-serif;font-size:1.05rem;"
                                f"color:{purchased_color};font-weight:600;"
                                f"margin-top:2px;margin-bottom:4px;'>"
                                f"🛒 Purchased: {purchased_val}</div>",
                                unsafe_allow_html=True
                            )
                            if not is_sheet:
                                if st.button("✏️ Edit",
                                            key=f"edit_btn_{edit_key}",
                                            width='content'):
                                    st.session_state[edit_key] = True
                                    st.rerun()

                        if i < len(all_fb) - 1:
                            st.markdown(
                                "<hr style='border-color:#F0EBE1;margin:6px 0;'>",
                                unsafe_allow_html=True
                            )

                # ── Add Feedback button ──
                st.markdown("<div style='margin-top:0.6rem;'></div>", unsafe_allow_html=True)
                if st.button(
                    "➕ Add Feedback",
                    key=f"add_fb_{build_sample_key(customer,product,ho_str)}_{idx}",
                ):
                    st.session_state["dlg_customer"] = customer
                    st.session_state["dlg_product"]  = product
                    st.session_state["dlg_ho_date"]  = ho_str
                    st.session_state["show_fb_dlg"]  = True

            # ── Separator ──
            st.markdown(
                "<div style='height:8px;border-bottom:2px solid #DDD5C5;"
                "margin-bottom:16px;'></div>",
                unsafe_allow_html=True
            )

        # ── Show dialog for this row ──
        if (st.session_state.get("show_fb_dlg") and
            st.session_state.get("dlg_customer") == customer and
            st.session_state.get("dlg_product")  == product and
            st.session_state.get("dlg_ho_date")  == ho_str):
            add_feedback_dialog(customer, product, ho_str)
            st.session_state.pop("show_fb_dlg", None)

        if st.session_state.get("dlg_saved"):
            st.session_state.pop("dlg_saved", None)
            st.success("✅ Feedback saved!")
            st.rerun()

    # ── Pagination controls ──
    st.divider()
    col_prev, col_info, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("← Prev", disabled=(page_num == 0),
                    key="di_prev", width='stretch'):
            st.session_state["di_page"] = page_num - 1
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
                    key="di_next", width='stretch'):
            st.session_state["di_page"] = page_num + 1
            st.rerun()

    # ── PDF Download ──
    st.divider()

    filters_parts = []
    for label, val in [
        ("Branch",   sel_branch),
        ("Area",     sel_area),
        ("Customer", sel_customer),
        ("Product",  sel_product),
        ("Urgency",  sel_urgency),
    ]:
        if val and val != "-Select-":
            filters_parts.append(f"{label}: {val}")
    filters_desc = " · ".join(filters_parts) if filters_parts else "All Samples"

    # ── PDF Download ──

    if st.button("📄 Generate PDF", type="primary",
                width='content', key="di_pdf_btn"):
        
        # ← Build PDF data HERE, only on click
        with st.spinner("Preparing report..."):
            pdf_grouped = {}
            for _, row in fdf.iterrows():
                customer = str(row.get(COL_CUSTOMER, "—"))
                product  = str(row.get(COL_SAMPLE_PROD, "—"))
                ho_date  = row[COL_HO_DATE]
                ho_str   = row["ho_date_str"]
                ho_disp  = ho_date.strftime("%d %b %Y") if pd.notna(ho_date) else "—"

                sheet_fb_raw = row.get(COL_FEEDBACK, "")
                sheet_fb     = "" if pd.isna(sheet_fb_raw) or \
                            str(sheet_fb_raw).strip() in ("","nan","None","-","_") \
                            else str(sheet_fb_raw).strip()

                firestore_entries = load_feedback_for_sample(
                    customer, product, ho_str
                )

                all_fb = []
                if sheet_fb:
                    all_fb.append({
                        "id":            "__sheet__",
                        "feedback":      sheet_fb,
                        "feedback_date": ho_str,
                        "added_by":      "Original (Sheet)",
                        "source":        "sheet"
                    })
                for fb in firestore_entries:
                    all_fb.append({**fb, "source": "firestore"})

                pdf_grouped.setdefault(customer, []).append({
                    "product":  product,
                    "ho_date":  ho_disp,
                    "ho_by":    str(row.get(COL_HO_BY, "—")),
                    "ho_to":    str(row.get(COL_HO_TO, "—")),
                    "contact":  str(row.get(COL_CONTACT, "—")),
                    "qty":      str(row.get(COL_QTY, "—")),
                    "feedbacks": [
                        {
                            "label": "Initial Feedback" if i == 0 else f"Follow-up {i}",
                            "date":  str(fb.get("feedback_date",""))[:10],
                            "by":    fb.get("added_by",""),
                            "text":  fb.get("feedback",""),
                        }
                        for i, fb in enumerate(all_fb)
                    ]
                })

            pdf_bytes = generate_sample_pdf(pdf_grouped, filters_desc)

        # filters_desc is meant for display (colons, middots) — build a
        # filesystem-safe version separately for the actual filename.
        import re as _re
        safe_filters = _re.sub(r"[^A-Za-z0-9]+", "_", filters_desc).strip("_")
        filename = f"SampleReport_{safe_filters}_{datetime.now().strftime('%d%b%Y')}.pdf"
        st.download_button(
            label="⬇️ Download PDF",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            key="di_pdf_download"
        )
