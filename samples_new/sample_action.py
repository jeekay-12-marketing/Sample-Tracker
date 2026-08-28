"""
Action Required page — pending samples sorted by urgency with latest feedback.
All Samples page — full searchable table.
"""
import html
import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from samples_new.sample_constants import (
    load_sample_data, SAMPLE_CSS, urgency_badge, feedback_badge,
    COL_BRANCH, COL_AREA, COL_CUSTOMER, COL_SAMPLE_PROD,
    COL_HO_DATE, COL_HO_BY, COL_CONTACT, COL_FEEDBACK, COL_PURCHASED
)
from samples_new.sample_firestore import (
    load_all_latest_feedback, classify_feedback,
    get_urgency, build_sample_key
)
from samples_new.sample_detailed import generate_sample_pdf


def esc(val) -> str:
    if pd.isna(val) or val is None:
        return "—"
    return html.escape(str(val))


def _build_grouped_data(df: pd.DataFrame) -> dict:
    """
    Reshape a purchase-status dataframe into the {customer: [samples...]}
    structure expected by generate_sample_pdf(). Each sample carries its
    latest feedback as a single-entry history (that's all we track here —
    full feedback history lives in Firestore's per-sample subcollection,
    not in this enriched dataframe).
    """
    grouped: dict = {}
    for _, row in df.iterrows():
        customer = str(row.get(COL_CUSTOMER, "—")).strip() or "—"
        ho_date  = row[COL_HO_DATE].strftime("%d %b %Y") if pd.notna(row.get(COL_HO_DATE)) else "—"
        ho_by    = str(row.get(COL_HO_BY, "—")).strip() or "—"
        contact  = str(row.get(COL_CONTACT, "—")).strip() or "—"
        qty      = str(row.get("Sample Quantity", "—")).strip() or "—"
        latest   = str(row.get("Latest Feedback", "")).strip()

        feedbacks = []
        if latest:
            feedbacks.append({
                "label": "Latest Feedback",
                "date":  ho_date,
                "by":    ho_by,
                "text":  latest,
            })

        sample = {
            "product":   str(row.get(COL_SAMPLE_PROD, "—")).strip() or "—",
            "ho_date":   ho_date,
            "ho_by":     ho_by,
            "contact":   contact,
            "qty":       qty,
            "feedbacks": feedbacks,
        }
        grouped.setdefault(customer, []).append(sample)
    return grouped


def _enrich(df: pd.DataFrame, history: dict) -> pd.DataFrame:
    """Add Latest Feedback, Feedback Status, Urgency, Days, Purchased columns."""
    df = df.copy()

    def get_latest(row):
        ho = row[COL_HO_DATE]
        ho_str = str(ho.date()) if pd.notna(ho) else ""
        key = (str(row.get(COL_CUSTOMER,"")).strip(),
               str(row.get(COL_SAMPLE_PROD,"")).strip(), ho_str)
        entry = history.get(key)
        if entry:
            return entry.get("feedback","")
        fb = row.get(COL_FEEDBACK,"")
        return "" if pd.isna(fb) else str(fb)

    def get_purchased(row):
        ho = row[COL_HO_DATE]
        ho_str = str(ho.date()) if pd.notna(ho) else ""
        key = (str(row.get(COL_CUSTOMER,"")).strip(),
               str(row.get(COL_SAMPLE_PROD,"")).strip(), ho_str)
        entry = history.get(key)
        if entry and entry.get("purchased"):
            return entry.get("purchased")
        # Fall back to sheet column if Firestore history has no edit yet
        sheet_val = row.get("Purchased?", "")
        sheet_val = "" if pd.isna(sheet_val) else str(sheet_val).strip()
        return sheet_val if sheet_val else "Purchase Data Not Available"

    df["Latest Feedback"]  = df.apply(get_latest, axis=1)
    df["Feedback Status"]  = df["Latest Feedback"].apply(classify_feedback)
    df["Purchased?"]        = df.apply(get_purchased, axis=1)
    print(f"[_enrich] 'Purchased?' in df.columns: {'Purchased?' in df.columns}")
    print(f"[_enrich] Purchased value_counts: {df['Purchased?'].value_counts().to_dict()}")
    print(f"[_enrich] Sample of first 5 Purchased values: {df['Purchased?'].head(5).tolist()}")
    df["Days Since HO"]    = (pd.Timestamp.now() - df[COL_HO_DATE]).dt.days.fillna(0).astype(int)
    df["Has Feedback"]     = df["Feedback Status"] != "Pending"
    df["Urgency"]          = df.apply(
        lambda r: get_urgency(r["Days Since HO"], r["Has Feedback"], r["Latest Feedback"]), axis=1
    )
    df["ho_date_str"]      = df[COL_HO_DATE].apply(
        lambda x: str(x.date()) if pd.notna(x) else ""
    )
    return df


def _show_needs_attention(fdf):
    # ── Only non-responded ──
    pending_df = fdf[fdf["Urgency"] != "Responded"].copy()

    if pending_df.empty:
        st.success("Responded samples require no further action 🎉!")
        return

    # ── Sort by urgency priority ──
    urg_order = {"Critical": 4, "Push Required": 3,
                 "Initial Follow-up": 2, "Freshly Handed": 1, "Hold": 0}
    pending_df["_sort"] = pending_df["Urgency"].map(urg_order).fillna(0)
    pending_df = pending_df.sort_values(
        ["_sort", "Days Since HO"], ascending=[False, False]
    ).drop(columns=["_sort"])

    # ── Urgency counts ──
    counts = pending_df["Urgency"].value_counts().to_dict()
    critical_n  = counts.get("Critical", 0)
    push_n      = counts.get("Push Required", 0)
    initial_n   = counts.get("Initial Follow-up", 0)
    fresh_n     = counts.get("Freshly Handed", 0)

    # ── Active urgency filter from session ──
    active_urg = st.session_state.get("ar_urg_filter", None)

    # ── Clickable urgency badge buttons ──
    st.markdown(
        "<div style='font-family:Outfit,sans-serif;font-size:0.9rem;"
        "font-weight:600;color:#6B7A99;margin-bottom:8px;'>Filter by Urgency:</div>",
        unsafe_allow_html=True
    )

    hold_n = counts.get("Hold", 0)

    b1, b2, b3, b4, b5, b6 = st.columns(6)

    with b1:
        if st.button(f"🟢 Freshly Handed ({fresh_n})", key="ar_btn_fresh",
                    width='stretch'):
            st.session_state["ar_urg_filter"] = None if active_urg == "Freshly Handed" else "Freshly Handed"
            st.session_state["ar_page"] = 0
            st.rerun()
        
    with b2:
        if st.button(f"🟡 Initial Follow-up ({initial_n})", key="ar_btn_initial",
                    width='stretch'):
            st.session_state["ar_urg_filter"] = None if active_urg == "Initial Follow-up" else "Initial Follow-up"
            st.session_state["ar_page"] = 0
            st.rerun()
        
    with b3:
        if st.button(f"🟠 Push Required ({push_n})", key="ar_btn_push",
                    width='stretch'):
            st.session_state["ar_urg_filter"] = None if active_urg == "Push Required" else "Push Required"
            st.session_state["ar_page"] = 0
            st.rerun()
        
    with b4:
        if st.button(f"🔴 Critical ({critical_n})", key="ar_btn_critical",
                    width='stretch'):
            st.session_state["ar_urg_filter"] = None if active_urg == "Critical" else "Critical"
            st.session_state["ar_page"] = 0
            st.rerun()
        
    with b5:
        if st.button(f"⏸ Hold ({hold_n})", key="ar_btn_hold",
                    width='stretch'):
            st.session_state["ar_urg_filter"] = None if active_urg == "Hold" else "Hold"
            st.session_state["ar_page"] = 0
            st.rerun()
        
    with b6:
        if active_urg:
            if st.button("✕ Clear", key="ar_btn_clear", width='stretch'):
                st.session_state.pop("ar_urg_filter", None)
                st.session_state["ar_page"] = 0
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom:1rem;'></div>", unsafe_allow_html=True)

    # ── Apply urgency button filter ──
    # pending_df is the FULL dataset for Excel download
    display_df = pending_df.copy()
    if active_urg:
        display_df = display_df[display_df["Urgency"] == active_urg]

    total_items = len(display_df)
    st.caption(
        f"{total_items} samples need attention"
        + (f" · filtered by **{active_urg}**" if active_urg else "")
    )

    if display_df.empty:
        st.info(f"No {active_urg} samples found.")
    else:
        # ── Pagination ──
        ITEMS_PER_PAGE = 15
        total_pages    = max(1, (total_items - 1) // ITEMS_PER_PAGE + 1)
        page_num       = st.session_state.get("ar_page", 0)

        # Reset page if filter changed
        filter_sig = f"{total_items}_{active_urg}"
        if st.session_state.get("_ar_filter_sig") != filter_sig:
            st.session_state["ar_page"]         = 0
            st.session_state["_ar_filter_sig"]  = filter_sig
            page_num = 0

        start    = page_num * ITEMS_PER_PAGE
        end      = start + ITEMS_PER_PAGE
        page_df  = display_df.iloc[start:end]

        st.markdown(
            f"<div style='font-family:Outfit,sans-serif;font-size:0.82rem;"
            f"color:#6B7A99;margin-bottom:1rem;'>"
            f"Showing <b>{start+1}–{min(end,total_items)}</b> "
            f"of <b>{total_items}</b></div>",
            unsafe_allow_html=True
        )

        # ── Cards ──
        for _, row in page_df.iterrows():
            urg     = row["Urgency"]
            css_cls = {
                "Critical":          "critical",
                "Push Required":     "push",
                "Initial Follow-up": "initial",
                "Freshly Handed":    "fresh",
                "Hold":              "hold",
            }.get(urg, "fresh")

            customer = esc(row.get(COL_CUSTOMER))
            product  = esc(row.get(COL_SAMPLE_PROD))
            ho_disp  = row[COL_HO_DATE].strftime("%d %b %Y") \
                       if pd.notna(row.get(COL_HO_DATE)) else "—"
            ho_by    = esc(row.get(COL_HO_BY))
            contact  = esc(row.get(COL_CONTACT))
            days_ago = int(row["Days Since HO"])
            latest   = str(row.get("Latest Feedback", "")) or ""
            latest   = esc(latest)

            fb_html = (
                f'<div class="action-card-fb">💬 Last: {latest[:120]}'
                f'{"..." if len(latest) > 120 else ""}</div>'
            ) if latest and latest != "—" else (
                '<div class="action-card-fb" style="color:#6B7A99;">'
                'No feedback yet</div>'
            )

            st.markdown(f"""
            <div class="action-card {css_cls}">
                <div class="action-card-top">
                    <div>
                        <div class="action-card-name">{customer}</div>
                        <div class="action-card-meta">
                            📦 {product} &nbsp;·&nbsp;
                            📍 {esc(row.get(COL_AREA))} &nbsp;·&nbsp;
                            📅 {ho_disp} (<b>{days_ago}d ago</b>) &nbsp;·&nbsp;
                            🤝 {ho_by} &nbsp;·&nbsp; 👤 {contact}
                        </div>
                    </div>
                    {urgency_badge(urg)}
                </div>
                {fb_html}
            </div>
            """, unsafe_allow_html=True)

        # ── Pagination controls ───
        st.divider()
        col_prev, col_info, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.button("← Prev", disabled=(page_num == 0),
                        key="ar_prev", width='stretch'):
                st.session_state["ar_page"] = page_num - 1
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
                        key="ar_next", width='stretch'):
                st.session_state["ar_page"] = page_num + 1
                st.rerun()

    # ── Excel download — always uses FULL pending_df (all filters, all pages) ──
    st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
    dl_cols = [COL_BRANCH, COL_AREA, COL_CUSTOMER, COL_SAMPLE_PROD,
               COL_HO_DATE, COL_HO_BY, COL_CONTACT, COL_PURCHASED,
               "Days Since HO", "Urgency", "Latest Feedback", "Feedback Status"]
    dl_cols = [c for c in dl_cols if c in pending_df.columns]
    dl_df   = display_df[dl_cols].copy()  # ← full pending_df not display_df
    if COL_HO_DATE in dl_df.columns:
        dl_df[COL_HO_DATE] = dl_df[COL_HO_DATE].dt.strftime("%d %b %Y")

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        dl_df.to_excel(writer, index=False, sheet_name="Action Required")
        ws = writer.sheets["Action Required"]
        ws.set_column(0, len(dl_df.columns) - 1, 22)

    st.download_button(
        "📥 Download All Action Items",
        data=buf.getvalue(),
        file_name=f"ActionRequired_{datetime.now().strftime('%d%b%Y')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="ar_download"
    )

    # ── PDF generation (two-step: Generate → Download) ──
    # Only builds the PDF when the user explicitly clicks Generate, so we
    # don't pay the PDF-rendering cost on every rerun (urgency filter click,
    # pagination, etc.) — only when they actually want the file.
    filters_desc = f"Needs Attention · {active_urg}" if active_urg else "Needs Attention — All"

    col_gen, col_dl = st.columns(2)
    with col_gen:
        if st.button("📄 Generate PDF", key="ar_gen_pdf", width='content'):
            grouped_data = _build_grouped_data(display_df)
            st.session_state["ar_pdf_bytes"] = generate_sample_pdf(grouped_data, filters_desc)
            st.rerun()
    with col_dl:
        if st.session_state.get("ar_pdf_bytes"):
            st.download_button(
                "📥 Download PDF",
                data=st.session_state["ar_pdf_bytes"],
                file_name=f"ActionRequired_{datetime.now().strftime('%d%b%Y')}.pdf",
                mime="application/pdf",
                key="ar_download_pdf"
            )


def _show_purchase_status(fdf):
    """
    Purchase analysis split by feedback type:
      - Positive feedback: full breakdown into Yes / Not Yet / No / NA
      - Negative feedback: simplified breakdown — Didn't Purchase / No Data only,
        since a negative response is never followed by a "Yes"/"Not Yet" purchase.
    """
    responded_df = fdf[fdf["Urgency"] == "Responded"].copy()

    if responded_df.empty:
        st.info("No responded samples yet.")
        return

    COL_PUR = "Purchased?"

    fb_view = st.radio(
        "Feedback type",
        ["✅ Positive Feedback", "❌ Negative Feedback"],
        key="ps_fb_view",
        horizontal=True,
        label_visibility="collapsed"
    )
    st.markdown("<div style='margin-bottom:0.8rem;'></div>", unsafe_allow_html=True)

    if fb_view.startswith("✅"):
        _render_positive_purchase_status(responded_df, COL_PUR)
    else:
        _render_negative_purchase_status(responded_df, COL_PUR)


def _render_positive_purchase_status(responded_df, COL_PUR):
    """
    Purchase analysis for Positive-feedback samples only,
    grouped by purchase outcome: Yes / Not Yet / No+NA.
    Filter buttons at top, grouped sections below.
    """
    positive_df  = responded_df[responded_df["Feedback Status"] == "Positive"].copy()

    if positive_df.empty:
        st.info("No positively-responded samples yet.")
        return

    # NOTE: "Purchased?" column (with question mark) from Sheet1 / Firestore
    # from Firestore history (key "purchased") or sheet col "Purchased?"

    total_n   = len(positive_df)
    yes_n     = (positive_df[COL_PUR] == "Yes").sum()
    notyet_n  = (positive_df[COL_PUR] == "Not Yet").sum()
    no_n      = (positive_df[COL_PUR] == "No").sum()
    na_n      = (~positive_df[COL_PUR].isin(["Yes", "Not Yet", "No"])).sum()
    conv_rate = f"{(yes_n / total_n * 100):.0f}%" if total_n else "—"

    # ── Stats bar ──
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Positive Feedback</div>
            <div class="kpi-value">{total_n}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="kpi-card green">
            <div class="kpi-label">Purchased</div>
            <div class="kpi-value green">{yes_n}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="kpi-card amber">
            <div class="kpi-label">Not Yet</div>
            <div class="kpi-value amber">{notyet_n}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="kpi-card red">
            <div class="kpi-label">Didn't Purchase</div>
            <div class="kpi-value red">{no_n}</div>
        </div>""", unsafe_allow_html=True)
    with c5:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">No Data</div>
            <div class="kpi-value">{na_n}</div>
        </div>""", unsafe_allow_html=True)
    with c6:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Conversion Rate</div>
            <div class="kpi-value">{conv_rate}</div>
            <div class="kpi-sub">of positive feedbacks</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin:1.5rem 0 0.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Filter buttons ──
    active_pur = st.session_state.get("ps_pur_filter", None)
    st.markdown(
        "<div style='font-family:Outfit,sans-serif;font-size:0.88rem;"
        "font-weight:600;color:#6B7A99;margin-bottom:8px;'>Filter by Purchase Outcome:</div>",
        unsafe_allow_html=True
    )

    b1, b2, b3, b4, b5 = st.columns(5)
    with b1:
        if st.button(f"✅ Purchased ({yes_n})", key="ps_btn_yes", width='stretch'):
            st.session_state["ps_pur_filter"] = None if active_pur == "Yes" else "Yes"
            st.rerun()
    with b2:
        if st.button(f"⏳ Not Yet ({notyet_n})", key="ps_btn_notyet", width='stretch'):
            st.session_state["ps_pur_filter"] = None if active_pur == "Not Yet" else "Not Yet"
            st.rerun()
    with b3:
        if st.button(f"❌ Didn't Purchase ({no_n})", key="ps_btn_no", width='stretch'):
            st.session_state["ps_pur_filter"] = None if active_pur == "No" else "No"
            st.rerun()
    with b4:
        if st.button(f"❔ No Data ({na_n})", key="ps_btn_na", width='stretch'):
            st.session_state["ps_pur_filter"] = None if active_pur == "__NA__" else "__NA__"
            st.rerun()
    with b5:
        if active_pur:
            if st.button("✕ Clear Filter", key="ps_btn_clear", width='stretch'):
                st.session_state.pop("ps_pur_filter", None)
                st.rerun()

    st.markdown("<div style='margin-bottom:1.2rem;'></div>", unsafe_allow_html=True)

    # ── Apply filter ──
    if active_pur == "Yes":
        base_df = positive_df[positive_df[COL_PUR] == "Yes"]
    elif active_pur == "Not Yet":
        base_df = positive_df[positive_df[COL_PUR] == "Not Yet"]
    elif active_pur == "No":
        base_df = positive_df[positive_df[COL_PUR] == "No"]
    elif active_pur == "__NA__":
        base_df = positive_df[~positive_df[COL_PUR].isin(["Yes", "Not Yet", "No"])]
    else:
        base_df = positive_df

    if active_pur:
        label = {"Yes": "Purchased", "Not Yet": "Not Yet", "No": "Didn't Purchase", "__NA__": "No Data"}.get(active_pur, "")
        filters_desc = f"Positive Feedback · {label}"
        st.caption(f"{len(base_df)} samples · filtered by **{label}**")
    else:
        filters_desc = "Positive Feedback — All"
        st.caption(f"{total_n} positive feedback samples")

    st.markdown("<div style='margin-bottom:0.5rem;'></div>", unsafe_allow_html=True)

    # ── Groups ──
    GROUPS = [
        ("yes",    "Yes",    "✅ Purchased",            "Successful 😎✌️",                   "#2E7D32", "#E8F5E9", "#A5D6A7"),
        ("notyet", "Not Yet","⏳ Not Yet",               "Reconnect with the Customer 👨‍💻", "#E65100", "#FFF3E0", "#FFAB40"),
        ("no",     "No",     "❌ Didn't Purchase",       "Liked it but didn't buy 🤨",        "#B71C1C", "#FFEBEE", "#EF9A9A"),
        ("na",     "__NA__", "❔ Purchase Data Not Available", "Update purchase status",       "#4527A0", "#EDE7F6", "#B39DDB"),
    ]

    for key, filter_val, label, scenario, fg, bg, border in GROUPS:
        if active_pur and active_pur != filter_val:
            continue

        if filter_val == "__NA__":
            group_df = base_df[~base_df[COL_PUR].isin(["Yes", "Not Yet", "No"])].copy()
        else:
            group_df = base_df[base_df[COL_PUR] == filter_val].copy()

        group_df = group_df.sort_values("Days Since HO", ascending=False)
        count = len(group_df)

        # Section divider with blinking label + scenario inline
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;margin:1.4rem 0 0.8rem 0;">
            <span class="ps-section-{key}"
                  style="border:1.5px solid {border};border-radius:20px;
                         padding:3px 14px;font-size:0.9rem;font-weight:700;
                         color:{fg};font-family:Outfit,sans-serif;white-space:nowrap;">
                {label} ({count})
            </span>
            <span style="font-family:Outfit,sans-serif;font-size:0.9rem;
                         font-weight:700;color:{fg};">— {scenario}</span>
            <div style="flex:1;height:1px;background:#DDD5C5;"></div>
        </div>
        """, unsafe_allow_html=True)

        if group_df.empty:
            st.markdown(
                "<div style='font-family:Outfit,sans-serif;font-size:0.9rem;"
                "color:#6B7A99;padding:0.3rem 0 1rem 0;'>No samples here.</div>",
                unsafe_allow_html=True
            )
        else:
            for _, row in group_df.iterrows():
                customer = esc(row.get(COL_CUSTOMER))
                product  = esc(row.get(COL_SAMPLE_PROD))
                ho_disp  = row[COL_HO_DATE].strftime("%d %b %Y") \
                           if pd.notna(row.get(COL_HO_DATE)) else "—"
                ho_by    = esc(row.get(COL_HO_BY))
                contact  = esc(row.get(COL_CONTACT))
                days_ago = int(row["Days Since HO"])
                latest   = esc(str(row.get("Latest Feedback", "")) or "")

                fb_html = (
                    f'<div class="action-card-fb">💬 {latest[:140]}'
                    f'{"..." if len(latest) > 140 else ""}</div>'
                ) if latest else ""

                st.markdown(f"""
                <div class="action-card fresh" style="border-left:4px solid {border};">
                    <div class="action-card-top">
                        <div>
                            <div class="action-card-name">{customer}</div>
                            <div class="action-card-meta">
                                📦 {product} &nbsp;·&nbsp;
                                📍 {esc(row.get(COL_AREA))} &nbsp;·&nbsp;
                                📅 {ho_disp} (<b>{days_ago}d ago</b>) &nbsp;·&nbsp;
                                🤝 {ho_by} &nbsp;·&nbsp; 👤 {contact}
                            </div>
                        </div>
                    </div>
                    {fb_html}
                </div>
                """, unsafe_allow_html=True)

    # ── Excel download ──
    st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
    dl_cols = [COL_BRANCH, COL_AREA, COL_CUSTOMER, COL_SAMPLE_PROD,
               COL_HO_DATE, COL_HO_BY, COL_CONTACT,
               "Days Since HO", "Latest Feedback", COL_PUR]
    dl_cols = [c for c in dl_cols if c in base_df.columns]
    dl_df   = base_df[dl_cols].copy()
    if COL_HO_DATE in dl_df.columns:
        dl_df[COL_HO_DATE] = dl_df[COL_HO_DATE].dt.strftime("%d %b %Y")

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        dl_df.to_excel(writer, index=False, sheet_name="Purchase Status")
        ws_xl = writer.sheets["Purchase Status"]
        ws_xl.set_column(0, len(dl_df.columns) - 1, 22)

    st.download_button(
        "📥 Download Purchase Analysis",
        data=buf.getvalue(),
        file_name=f"PurchaseAnalysis_{datetime.now().strftime('%d%b%Y')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="ps_download"
    )

    # ── PDF generation (two-step: Generate → Download) ──
    col_gen, col_dl = st.columns(2)
    with col_gen:
        if st.button("📄 Generate PDF", key="ps_gen_pdf_pos", width='content'):
            grouped_data = _build_grouped_data(base_df)
            st.session_state["ps_pdf_bytes_pos"] = generate_sample_pdf(grouped_data, filters_desc)
            st.rerun()
    with col_dl:
        if st.session_state.get("ps_pdf_bytes_pos"):
            st.download_button(
                "📥 Download PDF",
                data=st.session_state["ps_pdf_bytes_pos"],
                file_name=f"PurchaseAnalysis_{datetime.now().strftime('%d%b%Y')}.pdf",
                mime="application/pdf",
                key="ps_download_pdf_pos"
            )


def _render_negative_purchase_status(responded_df, COL_PUR):
    """
    Purchase analysis for Negative-feedback samples.
    Purchase outcome here is only ever "No" or missing/unset — a customer
    who gave negative feedback isn't expected to have purchased, so we skip
    the Yes / Not Yet buckets entirely and just show Didn't Purchase / No Data.
    """
    negative_df = responded_df[responded_df["Feedback Status"] == "Negative"].copy()

    if negative_df.empty:
        st.info("No negatively-responded samples yet.")
        return

    total_n = len(negative_df)
    no_n    = (negative_df[COL_PUR] == "No").sum()
    na_n    = (~negative_df[COL_PUR].isin(["No"])).sum()

    # ── Stats bar ──
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Negative Feedback</div>
            <div class="kpi-value">{total_n}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="kpi-card red">
            <div class="kpi-label">Didn't Purchase</div>
            <div class="kpi-value red">{no_n}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">No Data</div>
            <div class="kpi-value">{na_n}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin:1.5rem 0 0.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Filter buttons ──
    active_pur = st.session_state.get("ps_pur_filter_neg", None)
    st.markdown(
        "<div style='font-family:Outfit,sans-serif;font-size:0.88rem;"
        "font-weight:600;color:#6B7A99;margin-bottom:8px;'>Filter by Purchase Outcome:</div>",
        unsafe_allow_html=True
    )

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button(f"❌ Didn't Purchase ({no_n})", key="ps_btn_no_neg", width='stretch'):
            st.session_state["ps_pur_filter_neg"] = None if active_pur == "No" else "No"
            st.rerun()
    with b2:
        if st.button(f"❔ No Data ({na_n})", key="ps_btn_na_neg", width='stretch'):
            st.session_state["ps_pur_filter_neg"] = None if active_pur == "__NA__" else "__NA__"
            st.rerun()
    with b3:
        if active_pur:
            if st.button("✕ Clear Filter", key="ps_btn_clear_neg", width='stretch'):
                st.session_state.pop("ps_pur_filter_neg", None)
                st.rerun()

    st.markdown("<div style='margin-bottom:1.2rem;'></div>", unsafe_allow_html=True)

    # ── Apply filter ──
    if active_pur == "No":
        base_df = negative_df[negative_df[COL_PUR] == "No"]
    elif active_pur == "__NA__":
        base_df = negative_df[~negative_df[COL_PUR].isin(["No"])]
    else:
        base_df = negative_df

    if active_pur:
        label = {"No": "Didn't Purchase", "__NA__": "No Data"}.get(active_pur, "")
        filters_desc = f"Negative Feedback · {label}"
        st.caption(f"{len(base_df)} samples · filtered by **{label}**")
    else:
        filters_desc = "Negative Feedback — All"
        st.caption(f"{total_n} negative feedback samples")

    st.markdown("<div style='margin-bottom:0.5rem;'></div>", unsafe_allow_html=True)

    # ── Groups ──
    GROUPS = [
        ("no_neg", "No",     "❌ Didn't Purchase",             "As expected — sample was disliked", "#B71C1C", "#FFEBEE", "#EF9A9A"),
        ("na_neg", "__NA__", "❔ Purchase Data Not Available", "Update purchase status",            "#4527A0", "#EDE7F6", "#B39DDB"),
    ]

    for key, filter_val, label, scenario, fg, bg, border in GROUPS:
        if active_pur and active_pur != filter_val:
            continue

        if filter_val == "__NA__":
            group_df = base_df[~base_df[COL_PUR].isin(["No"])].copy()
        else:
            group_df = base_df[base_df[COL_PUR] == filter_val].copy()

        group_df = group_df.sort_values("Days Since HO", ascending=False)
        count = len(group_df)

        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;margin:1.4rem 0 0.8rem 0;">
            <span class="ps-section-{key}"
                  style="border:1.5px solid {border};border-radius:20px;
                         padding:3px 14px;font-size:0.9rem;font-weight:700;
                         color:{fg};font-family:Outfit,sans-serif;white-space:nowrap;">
                {label} ({count})
            </span>
            <span style="font-family:Outfit,sans-serif;font-size:0.9rem;
                         font-weight:700;color:{fg};">— {scenario}</span>
            <div style="flex:1;height:1px;background:#DDD5C5;"></div>
        </div>
        """, unsafe_allow_html=True)

        if group_df.empty:
            st.markdown(
                "<div style='font-family:Outfit,sans-serif;font-size:0.85rem;"
                "color:#6B7A99;padding:0.3rem 0 1rem 0;'>No samples here.</div>",
                unsafe_allow_html=True
            )
        else:
            for _, row in group_df.iterrows():
                customer = esc(row.get(COL_CUSTOMER))
                product  = esc(row.get(COL_SAMPLE_PROD))
                ho_disp  = row[COL_HO_DATE].strftime("%d %b %Y") \
                           if pd.notna(row.get(COL_HO_DATE)) else "—"
                ho_by    = esc(row.get(COL_HO_BY))
                contact  = esc(row.get(COL_CONTACT))
                days_ago = int(row["Days Since HO"])
                latest   = esc(str(row.get("Latest Feedback", "")) or "")

                fb_html = (
                    f'<div class="action-card-fb">💬 {latest[:140]}'
                    f'{"..." if len(latest) > 140 else ""}</div>'
                ) if latest else ""

                st.markdown(f"""
                <div class="action-card fresh" style="border-left:4px solid {border};">
                    <div class="action-card-top">
                        <div>
                            <div class="action-card-name">{customer}</div>
                            <div class="action-card-meta">
                                📦 {product} &nbsp;·&nbsp;
                                📍 {esc(row.get(COL_AREA))} &nbsp;·&nbsp;
                                📅 {ho_disp} (<b>{days_ago}d ago</b>) &nbsp;·&nbsp;
                                🤝 {ho_by} &nbsp;·&nbsp; 👤 {contact}
                            </div>
                        </div>
                    </div>
                    {fb_html}
                </div>
                """, unsafe_allow_html=True)

    # ── Excel download ──
    st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
    dl_cols = [COL_BRANCH, COL_AREA, COL_CUSTOMER, COL_SAMPLE_PROD,
               COL_HO_DATE, COL_HO_BY, COL_CONTACT,
               "Days Since HO", "Latest Feedback", COL_PUR]
    dl_cols = [c for c in dl_cols if c in base_df.columns]
    dl_df   = base_df[dl_cols].copy()
    if COL_HO_DATE in dl_df.columns:
        dl_df[COL_HO_DATE] = dl_df[COL_HO_DATE].dt.strftime("%d %b %Y")

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        dl_df.to_excel(writer, index=False, sheet_name="Negative Purchase Status")
        ws_xl = writer.sheets["Negative Purchase Status"]
        ws_xl.set_column(0, len(dl_df.columns) - 1, 22)

    st.download_button(
        "📥 Download Negative Feedback Analysis",
        data=buf.getvalue(),
        file_name=f"NegativePurchaseAnalysis_{datetime.now().strftime('%d%b%Y')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="ps_download_neg"
    )

    # ── PDF generation (two-step: Generate → Download) ──
    col_gen, col_dl = st.columns(2)
    with col_gen:
        if st.button("📄Generate PDF", key="ps_gen_pdf_neg", width='content'):
            grouped_data = _build_grouped_data(base_df)
            st.session_state["ps_pdf_bytes_neg"] = generate_sample_pdf(grouped_data, filters_desc)
            st.rerun()
    with col_dl:
        if st.session_state.get("ps_pdf_bytes_neg"):
            st.download_button(
                "📥 Download PDF",
                data=st.session_state["ps_pdf_bytes_neg"],
                file_name=f"NegativePurchaseAnalysis_{datetime.now().strftime('%d%b%Y')}.pdf",
                mime="application/pdf",
                key="ps_download_pdf_neg"
            )


def show_action_required(fdf=None):
    st.markdown(SAMPLE_CSS, unsafe_allow_html=True)

    # ── All button CSS injected once here, targeted by st-key-{button_key} ──
    st.markdown("""
    <style>
    @keyframes blink-green  { 0%,100%{background:#C8E6C9!important;} 50%{background:#A5D6A7!important;} }
    @keyframes blink-yellow { 0%,100%{background:#FFF9C4!important;} 50%{background:#FFF176!important;} }
    @keyframes blink-orange { 0%,100%{background:#FFE0B2!important;} 50%{background:#FFCC80!important;} }
    @keyframes blink-red    { 0%,100%{background:#FFCDD2!important;} 50%{background:#EF9A9A!important;} }
    @keyframes blink-purple { 0%,100%{background:#E1BEE7!important;} 50%{background:#CE93D8!important;} }

    /* ── Needs Attention buttons ── */
    .st-key-ar_btn_fresh button   { background:#C8E6C9!important; border:1.5px solid #66BB6A!important; color:#1B5E20!important; font-weight:700!important; animation:blink-green  1.4s ease-in-out infinite!important; }
    .st-key-ar_btn_initial button { background:#FFF9C4!important; border:1.5px solid #FDD835!important; color:#F57F17!important; font-weight:700!important; animation:blink-yellow 1.4s ease-in-out infinite!important; }
    .st-key-ar_btn_push button    { background:#FFE0B2!important; border:1.5px solid #FF9800!important; color:#E65100!important; font-weight:700!important; animation:blink-orange 1.4s ease-in-out infinite!important; }
    .st-key-ar_btn_critical button{ background:#FFCDD2!important; border:1.5px solid #EF5350!important; color:#B71C1C!important; font-weight:700!important; animation:blink-red    1.4s ease-in-out infinite!important; }
    .st-key-ar_btn_hold button    { background:#E1BEE7!important; border:1.5px solid #CE93D8!important; color:#4527A0!important; font-weight:700!important; animation:blink-purple 1.4s ease-in-out infinite!important; }
    .st-key-ar_btn_clear button   { background:#FFFFFF!important; border:1.5px solid #DDD5C5!important; color:#1B2A4A!important; font-weight:600!important; animation:none!important; }

    /* ── Purchase Status buttons (Positive feedback) ── */
    .st-key-ps_btn_yes button    { background:#C8E6C9!important; border:1.5px solid #66BB6A!important; color:#1B5E20!important; font-weight:700!important; animation:blink-green  1.4s ease-in-out infinite!important; }
    .st-key-ps_btn_notyet button { background:#FFF9C4!important; border:1.5px solid #FDD835!important; color:#F57F17!important; font-weight:700!important; animation:blink-yellow 1.4s ease-in-out infinite!important; }
    .st-key-ps_btn_no button     { background:#FFCDD2!important; border:1.5px solid #EF5350!important; color:#B71C1C!important; font-weight:700!important; animation:blink-red    1.4s ease-in-out infinite!important; }
    .st-key-ps_btn_na button     { background:#E1BEE7!important; border:1.5px solid #CE93D8!important; color:#4527A0!important; font-weight:700!important; animation:blink-purple 1.4s ease-in-out infinite!important; }
    .st-key-ps_btn_clear button  { background:#FFFFFF!important; border:1.5px solid #DDD5C5!important; color:#1B2A4A!important; font-weight:600!important; animation:none!important; }

    /* ── Purchase Status buttons (Negative feedback) ── */
    .st-key-ps_btn_no_neg button    { background:#FFCDD2!important; border:1.5px solid #EF5350!important; color:#B71C1C!important; font-weight:700!important; animation:blink-red    1.4s ease-in-out infinite!important; }
    .st-key-ps_btn_na_neg button    { background:#E1BEE7!important; border:1.5px solid #CE93D8!important; color:#4527A0!important; font-weight:700!important; animation:blink-purple 1.4s ease-in-out infinite!important; }
    .st-key-ps_btn_clear_neg button { background:#FFFFFF!important; border:1.5px solid #DDD5C5!important; color:#1B2A4A!important; font-weight:600!important; animation:none!important; }

    /* ── Purchase section header blinking spans ── */
    .ps-section-yes    { animation:blink-green  1.4s ease-in-out infinite; }
    .ps-section-notyet { animation:blink-yellow 1.4s ease-in-out infinite; }
    .ps-section-no     { animation:blink-red    1.4s ease-in-out infinite; }
    .ps-section-na     { animation:blink-purple 1.4s ease-in-out infinite; }
    .ps-section-no_neg  { animation:blink-red    1.4s ease-in-out infinite; }
    .ps-section-na_neg  { animation:blink-purple 1.4s ease-in-out infinite; }

    /* ── Generate PDF buttons — match the Download button styling ── */
    .st-key-ps_gen_pdf_pos button,
    .st-key-ps_gen_pdf_neg button,
    .st-key-ar_gen_pdf button {
        background: #1B2A4A !important;
        color: #E8C97A !important;
        border: 2px solid #C9A84C !important;
        border-radius: 8px !important;
        font-family: 'Libre Baskerville', serif !important;
        font-size: 15px !important;
        font-weight: 700 !important;
        padding: 10px 28px !important;
        letter-spacing: 0.5px !important;
        transition: all 0.2s ease !important;
    }
    .st-key-ps_gen_pdf_pos button:hover,
    .st-key-ps_gen_pdf_neg button:hover,
    .st-key-ar_gen_pdf button:hover {
        background: #C9A84C !important;
        color: #1B2A4A !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="sd-hero">
        <div class="sd-eyebrow">Sample Intelligence</div>
        <div class="sd-title">Action <em>Required</em></div>
        <div class="sd-sub">Samples awaiting feedback — sorted by urgency. Act on critical ones first.</div>
        <div class="sd-divider"></div>
    </div>""", unsafe_allow_html=True)

    if fdf is None or fdf.empty:
        st.warning("No samples match the current filters.")
        return

    tab1, tab2 = st.tabs(["🔔 Needs Attention", "💰 Purchase Status"])

    with tab1:
        _show_needs_attention(fdf)

    with tab2:
        _show_purchase_status(fdf)


def show_all_samples(fdf=None):
    st.markdown(SAMPLE_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="sd-hero">
        <div class="sd-eyebrow">Sample Intelligence</div>
        <div class="sd-title">All <em>Samples</em></div>
        <div class="sd-sub">Complete searchable record of all samples with latest feedback.</div>
        <div class="sd-divider"></div>
    </div>""", unsafe_allow_html=True)

    if fdf is None or fdf.empty:
        st.warning("No samples match the current filters.")
        return

    COL_HO_DATE = "Hand over to customer date"

    # === DATE PROCESSING (Do this FIRST) ===
    if COL_HO_DATE in fdf.columns:
        # Convert to datetime
        fdf[COL_HO_DATE] = pd.to_datetime(fdf[COL_HO_DATE], errors='coerce', dayfirst=True)
        
        # Create display column
        fdf[COL_HO_DATE + "_display"] = fdf[COL_HO_DATE].dt.strftime("%d %b %Y").fillna("—")
    # ====================== SEARCH ======================
    search = st.text_input(
        "🔍 Search", placeholder="Search customer, product, area...",
        key="as_search", label_visibility="collapsed"
    )
    
    if search:
        s = search.lower()
        mask = (
            fdf[COL_CUSTOMER].fillna("").str.lower().str.contains(s) |
            fdf[COL_SAMPLE_PROD].fillna("").str.lower().str.contains(s) |
            fdf[COL_AREA].fillna("").str.lower().str.contains(s)
        )
        fdf = fdf[mask].copy()

    st.caption(f"{len(fdf)} records")

    # ====================== PREPARE DISPLAY DF ======================
    show_df = fdf.copy()

    show_cols = [
        COL_BRANCH, 
        COL_AREA, 
        COL_HO_DATE,      
        COL_CUSTOMER, 
        COL_SAMPLE_PROD,
        "Supplier Name",
        "Sample Quantity",
        "Sample Unit",  
        COL_HO_BY,
        "Latest Feedback", 
        "Feedback Status", 
        "Urgency", 
        "Days Since HO",
        COL_PURCHASED
    ]
    show_cols = [c for c in show_cols if c in show_df.columns]


    # ====================== DISPLAY ======================
    st.dataframe(
        show_df[show_cols].reset_index(drop=True),
        width='stretch', 
        height=520,
        use_container_width=True,
        hide_index=True
    )
    

    # ========================= EXCEL DOWNLOAD ======================== 
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        excel_df = show_df[show_cols].copy()
        # Optional: Put real datetime in Excel too
        if COL_HO_DATE in excel_df.columns and COL_HO_DATE in fdf.columns:
            excel_df[COL_HO_DATE] = fdf[COL_HO_DATE].iloc[:len(excel_df)]  # align lengths
        
        excel_df.to_excel(writer, index=False, sheet_name="All Samples")
        ws = writer.sheets["All Samples"]
        ws.set_column(0, len(show_cols) - 1, 22)
    
    st.download_button(
        "📥 Download All Records", 
        data=buf.getvalue(),
        file_name=f"AllSamples_{datetime.now().strftime('%d%b%Y')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )