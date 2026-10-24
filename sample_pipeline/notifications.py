"""
In-app notifications page for sample pipeline alerts.
Shows alerts for stuck pipeline entries based on thresholds.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from samples_new.sample_constants import SAMPLE_CSS
from sample_pipeline.sample_pipeline_firestore import load_pipeline_entries, get_pipeline_alerts, STAGES


NOTIF_CSS = """
<style>
.notif-card {
    background: #FFFFFF;
    border: 1.5px solid #DDD5C5;
    border-radius: 12px;
    padding: 1rem 1.4rem;
    margin-bottom: 0.8rem;
    display: flex;
    align-items: flex-start;
    gap: 14px;
    font-family: 'Outfit', sans-serif;
    transition: box-shadow 0.15s ease;
}
.notif-card:hover {
    box-shadow: 0 4px 16px rgba(27,42,74,0.08);
}
.notif-card.high {
    border-left: 5px solid #B71C1C;
    background: #FFFAFA;
}
.notif-card.medium {
    border-left: 5px solid #E65100;
    background: #FFFDF7;
}
.notif-icon {
    font-size: 2.2rem;
    min-width: 36px;
    text-align: center;
    padding-top: 2px;
}
.notif-body { flex: 1; }
.notif-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: #1B2A4A;
    margin-bottom: 3px;
}
.notif-detail {
    font-size: 1.05rem;
    color: #6B7A99;
    margin-bottom: 4px;
}
.notif-days-high {
    display: inline-block;
    background: #FFEBEE;
    border: 1px solid #EF9A9A;
    color: #B71C1C;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.9rem;
    font-weight: 700;
}
.notif-days-medium {
    display: inline-block;
    background: #FFF3E0;
    border: 1px solid #FFAB40;
    color: #E65100;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.9rem;
    font-weight: 700;
}
.notif-empty {
    background: #E8F5E9;
    border: 1.5px solid #A5D6A7;
    border-radius: 12px;
    padding: 2rem;
    text-align: center;
    font-family: 'Outfit', sans-serif;
    color: #2E7D32;
}

.notif-section-divider {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 1.6rem 0 0.7rem 0;
}
.notif-section-divider:first-of-type { margin-top: 0.2rem; }
.notif-section-label {
    font-family: 'Outfit', sans-serif;
    font-size: 0.90rem;
    font-weight: 900;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: #6B7A99;
    white-space: nowrap;
}
.notif-section-line {
    flex: 1;
    height: 1px;
    background: #DDD5C5;
}
</style>
"""


def show_notifications():
    st.markdown(SAMPLE_CSS, unsafe_allow_html=True)
    st.markdown(NOTIF_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="sd-hero">
        <div class="sd-eyebrow">Sample Pipeline</div>
        <div class="sd-title">🔔 <em>Notifications</em></div>
        <div class="sd-sub">Pipeline entries that need your attention — check these regularly.</div>
        <div class="sd-divider"></div>
    </div>""", unsafe_allow_html=True)

    with st.spinner("Checking pipeline for alerts..."):
        # Pipeline data may have changed in another session or app worker.
        # Alerts are derived from each entry's current stage, so refresh the
        # source before calculating them; this also drops alerts for stages
        # an entry has already left.
        load_pipeline_entries.clear()
        df     = load_pipeline_entries()
        alerts = get_pipeline_alerts(df) if not df.empty else []

    # ── Summary bar ──
    high_count   = len([a for a in alerts if a["severity"] == "high"])
    medium_count = len([a for a in alerts if a["severity"] == "medium"])

    col1, col2  = st.columns(2)
    with col1:
        st.markdown(f"""
        <div class="kpi-card red">
            <div class="kpi-label">High Priority</div>
            <div class="kpi-value red">{high_count}</div>
            <div class="kpi-sub">needs immediate action</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="kpi-card amber">
            <div class="kpi-label">Medium Priority</div>
            <div class="kpi-value amber">{medium_count}</div>
            <div class="kpi-sub">follow up soon</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)

    # ── Filters: type, branch, area ──
    alert_types = {
        "All":                  "All Alerts",
        "supplier_no_response": "📤 Supplier Not Responding",
        "not_received":         "🚚 Stock Not Received",
        "not_handed_over":      "📦 Not Handed Over",
    }

    # Build branch/area option lists from the underlying pipeline data,
    # so the dropdowns always reflect what's actually in Firestore.
    branch_options = ["All Branches"]
    if not df.empty and "branch" in df.columns:
        branch_options += sorted(df["branch"].dropna().unique().tolist())

    col_type, col_branch, col_area = st.columns(3)

    with col_type:
        sel_type = st.selectbox(
            "Filter by alert type",
            list(alert_types.keys()),
            format_func=lambda x: alert_types[x],
            key="notif_type",
            label_visibility="collapsed"
        )

    with col_branch:
        sel_branch = st.selectbox(
            "Filter by branch",
            branch_options,
            key="notif_branch",
            label_visibility="collapsed"
        )

    # Area options narrow down based on the selected branch
    area_options = ["All Areas"]
    if not df.empty and "area" in df.columns:
        area_df = df if sel_branch == "All Branches" else df[df["branch"] == sel_branch]
        area_options += sorted(area_df["area"].dropna().unique().tolist())

    # If branch changed since last run, the previously selected area may no
    # longer be valid — reset it before the widget renders to avoid a
    # StreamlitAPIException.
    prev_branch = st.session_state.get("_prev_notif_branch")
    if prev_branch != sel_branch:
        st.session_state["_prev_notif_branch"] = sel_branch
        st.session_state["notif_area"] = "All Areas"

    with col_area:
        sel_area = st.selectbox(
            "Filter by area",
            area_options,
            key="notif_area",
            label_visibility="collapsed"
        )

    filtered_alerts = alerts
    if sel_type != "All":
        filtered_alerts = [a for a in filtered_alerts if a["type"] == sel_type]
    if sel_branch != "All Branches":
        filtered_alerts = [a for a in filtered_alerts if a.get("branch") == sel_branch]
    if sel_area != "All Areas":
        filtered_alerts = [a for a in filtered_alerts if a.get("area") == sel_area]

    # Group cards by type so each category renders as one contiguous block,
    # instead of interleaving (alerts may arrive sorted by days/severity,
    # not by type). Within each group, original relative order is preserved.
    if sel_type == "All":
        seen_order = []
        for a in filtered_alerts:
            if a["type"] not in seen_order:
                seen_order.append(a["type"])
        filtered_alerts = sorted(
            filtered_alerts,
            key=lambda a: seen_order.index(a["type"])
        )

    st.caption(f"{len(filtered_alerts)} alerts")
    st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)

    # ── Alert cards ──
    if not filtered_alerts:
        st.markdown("""
        <div class="notif-empty">
            ✅ <b>All clear!</b><br>
            <span style="font-size:1.25rem;color:#2E7D32;">
            No pipeline alerts at this time.
            </span>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Build one big HTML string for the whole section instead of calling
        # st.markdown() once per card (and once per divider) — each call is
        # a separate round-trip to the frontend, which adds up fast on a
        # page with dozens of alerts, especially on every filter rerun.
        html_parts = []
        last_type  = None
        for alert in filtered_alerts:
            if alert["type"] != last_type:
                html_parts.append(f"""
                <div class="notif-section-divider">
                    <span class="notif-section-label">{alert_types.get(alert["type"], alert["type"])}</span>
                    <div class="notif-section-line"></div>
                </div>
                """.strip())
                last_type = alert["type"]

            severity = alert["severity"]
            days_cls = f"notif-days-{severity}"

            html_parts.append(f"""
            <div class="notif-card {severity}">
                <div class="notif-icon">{alert["icon"]}</div>
                <div class="notif-body">
                    <div class="notif-title">{alert["title"]}</div>
                    <div class="notif-detail">{alert["loc_details"]}</div>
                    <div class="notif-detail">{alert["detail"]}</div>
                    <span class="{days_cls}">
                        {alert["days"]} days overdue
                    </span>
                </div>
            </div>
            """.strip())

        st.markdown("".join(html_parts), unsafe_allow_html=True)

    # ── Download as Excel ──
    if filtered_alerts:
        export_df = pd.DataFrame([
            {
                "Alert Type":  alert_types.get(a["type"], a["type"]),
                "Severity":    a["severity"].capitalize(),
                "Title":       a["title"],
                "Detail":      a["detail"],
                "Location":    a.get("loc_details", ""),
                "Days Overdue": a["days"],
            }
            for a in filtered_alerts
        ])

        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            export_df.to_excel(writer, index=False, sheet_name="Notifications")
            ws_xl = writer.sheets["Notifications"]
            ws_xl.set_column(0, len(export_df.columns) - 1, 26)

        st.download_button(
            "📥 Download as Excel",
            data=buf.getvalue(),
            file_name=f"PipelineNotifications_{datetime.now().strftime('%d%b%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="notif_download"
        )

    st.divider()
