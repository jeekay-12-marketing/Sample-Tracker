"""
Sample Router - As per the landing page. Each page will have its own sidebar + filters
"""

import streamlit as st
import pandas as pd
from samples_new.sample_constants import (
    SAMPLE_CSS, load_sample_data,
    COL_BRANCH, COL_AREA, COL_CUSTOMER,
    COL_SAMPLE_PROD
)
from samples_new.sample_firestore import load_all_latest_feedback, classify_feedback, get_urgency

INTELLIGENCE_PAGES = {
    "sample_overview":  "📊  Overview",
    "sample_detailed":  "🔍  Detailed Info",
    "sample_action":    "🚨  Action Required",
    "sample_all":       "📋  All Samples"
}

PIPELINE_PAGES = {
    "sample_entry":     "➕  Fill Enquiry form",
    "pipeline_tracker": "╰┈➤ Pipeline Tracker",
    "notifications":    "🔔 Notifications",
    "pipeline_kpi":     "🧐 Pipeline Analytics"
}

# Pages that show sidebar filters
INTEL_SIDEBAR_PAGES    = {"sample_overview", "sample_action", "sample_all"}
PIPELINE_SIDEBAR_PAGES = {"pipeline_kpi"}

# ─────────────────────────────────────────
# SIDEBAR COLOR CODING
# "Back to Home" = amber (leaving this section)
# Nav buttons     = outlined navy/gold by default, filled gold when ACTIVE
# Reset Filters   = muted/neutral (already visually distinct via icon+label)
# ─────────────────────────────────────────
ROUTER_NAV_CSS = """
<style>
/* "Back to Home" — Color 2 (utility action): translucent indigo, matching
   Admin Hub / Home / Logout in app.py */
section[data-testid="stSidebar"] .st-key-snav_home .stButton > button,
section[data-testid="stSidebar"] .st-key-pnav_home .stButton > button {
    background: rgba(147, 112, 219, 0.16) !important;
    border: 1.5px solid rgba(147, 112, 219, 0.55) !important;
    color: #D8CFFA !important;
    font-weight: 700 !important;
}
section[data-testid="stSidebar"] .st-key-snav_home .stButton > button:hover,
section[data-testid="stSidebar"] .st-key-pnav_home .stButton > button:hover {
    background: rgba(147, 112, 219, 0.30) !important;
    border-color: rgba(147, 112, 219, 0.8) !important;
    color: #FFFFFF !important;
}

/* Reset Filters — neutral, translucent, clearly a utility action not a nav item */
section[data-testid="stSidebar"] .st-key-g_reset .stButton > button,
section[data-testid="stSidebar"] .st-key-gp_reset .stButton > button {
    background: rgba(90, 106, 133, 0.14) !important;
    border: 1px solid rgba(90, 106, 133, 0.5) !important;
    color: #9AA5BD !important;
    font-weight: 500 !important;
}
section[data-testid="stSidebar"] .st-key-g_reset .stButton > button:hover,
section[data-testid="stSidebar"] .st-key-gp_reset .stButton > button:hover {
    background: rgba(90, 106, 133, 0.24) !important;
    border-color: #C9A84C !important;
    color: #E8C97A !important;
}

/* Nav buttons (Overview/Detailed Info/etc, Pipeline Tracker/Notifications/etc)
   — Color 3: translucent blue. The active one is overridden to a translucent
   gold overlay below by _highlight_active_nav(). */
section[data-testid="stSidebar"] .st-key-snav_sample_overview .stButton > button,
section[data-testid="stSidebar"] .st-key-snav_sample_detailed .stButton > button,
section[data-testid="stSidebar"] .st-key-snav_sample_action .stButton > button,
section[data-testid="stSidebar"] .st-key-snav_sample_all .stButton > button,
section[data-testid="stSidebar"] .st-key-snav_sample_entry .stButton > button,
section[data-testid="stSidebar"] .st-key-snav_pipeline_tracker .stButton > button,
section[data-testid="stSidebar"] .st-key-snav_notifications .stButton > button,
section[data-testid="stSidebar"] .st-key-snav_pipeline_kpi .stButton > button {
    background: rgba(90, 140, 220, 0.14) !important;
    border: 1.5px solid rgba(90, 140, 220, 0.45) !important;
    color: #C9D8F0 !important;
}
section[data-testid="stSidebar"] .st-key-snav_sample_overview .stButton > button:hover,
section[data-testid="stSidebar"] .st-key-snav_sample_detailed .stButton > button:hover,
section[data-testid="stSidebar"] .st-key-snav_sample_action .stButton > button:hover,
section[data-testid="stSidebar"] .st-key-snav_sample_all .stButton > button:hover,
section[data-testid="stSidebar"] .st-key-snav_sample_entry .stButton > button:hover,
section[data-testid="stSidebar"] .st-key-snav_pipeline_tracker .stButton > button:hover,
section[data-testid="stSidebar"] .st-key-snav_notifications .stButton > button:hover,
section[data-testid="stSidebar"] .st-key-snav_pipeline_kpi .stButton > button:hover {
    background: rgba(90, 140, 220, 0.24) !important;
    border-color: rgba(90, 140, 220, 0.7) !important;
    color: #FFFFFF !important;
}
</style>
"""


def _highlight_active_nav(active_key: str):
    """Overlay the current page's sidebar nav button with a translucent gold
    fill + bold gold border, so it's obviously the active page — while
    staying translucent like every other button, not a solid block."""
    st.markdown(f"""
    <style>
    section[data-testid="stSidebar"] .st-key-{active_key} .stButton > button {{
        background: rgba(201, 168, 76, 0.35) !important;
        color: #FFF6E0 !important;
        border: 2px solid #E8C96A !important;
        font-weight: 800 !important;
        box-shadow: 0 0 0 1px rgba(201, 168, 76, 0.25) inset;
    }}
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# ENRICH
# ─────────────────────────────────────────
def enrich(df: pd.DataFrame, history: dict) -> pd.DataFrame:
    df = df.copy()
    COL_HO_DATE = "Hand over to customer date"

    def normalize_date(value):
        if value is None or pd.isna(value) or not str(value).strip():
            return ""
        parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
        return "" if pd.isna(parsed) else parsed.date().isoformat()

    def normalize_text(value):
        if value is None or pd.isna(value):
            return ""
        return " ".join(str(value).split()).casefold()

    # Older Firebase entries may differ from the sheet in capitalization or
    # whitespace. Normalize both sides so their explicit status is still used.
    history_by_sample = {
        (normalize_text(customer), normalize_text(product), normalize_date(ho_date)): entry
        for (customer, product, ho_date), entry in history.items()
    }

    def get_latest(row):
        ho     = row[COL_HO_DATE] if COL_HO_DATE in row.index else None
        ho_str = normalize_date(ho)
        key = (
            normalize_text(row.get(COL_CUSTOMER, "")),
            normalize_text(row.get(COL_SAMPLE_PROD, "")),
            ho_str
        )
        entry = history_by_sample.get(key)
        if entry:
            return (
                entry.get("feedback", ""),
                entry.get("fb_status", None),
                entry.get("purchased", None),
            )
        fb = row.get("Feedback", "")
        return ("" if pd.isna(fb) else str(fb)), None, None

    df[["Latest Feedback", "Latest FB Status", "Latest FB Purchased"]] = df.apply(
        get_latest, axis=1, result_type="expand"
    )
    df["Feedback Status"] = df.apply(
        lambda r: classify_feedback(r["Latest Feedback"], r["Latest FB Status"]),
        axis=1
    )
    if "Purchased?" not in df.columns:
        df["Purchased?"] = "Purchase Data Not Available"

    def get_purchased(row):
        value = row.get("Latest FB Purchased")
        if value is None or pd.isna(value) or not str(value).strip():
            value = row.get("Purchased?", "")
        if value is None or pd.isna(value):
            return "Purchase Data Not Available"
        cleaned = " ".join(str(value).split()).casefold()
        return {
            "yes": "Yes",
            "not yet": "Not Yet",
            "no": "No",
            "purchase data not available": "Purchase Data Not Available",
        }.get(cleaned, str(value).strip() or "Purchase Data Not Available")

    df["Purchased?"] = df.apply(get_purchased, axis=1)
    df["Days Since HO"] = (
        pd.Timestamp.now() - df[COL_HO_DATE]
    ).dt.days.fillna(0).astype(int)

    df["Has Feedback"] = df["Latest Feedback"].str.strip().ne("")
    df["Urgency"] = df.apply(
        lambda r: get_urgency(
            r["Days Since HO"],
            r["Has Feedback"],
            r["Latest FB Status"],
            r["Latest Feedback"]
        ),
        axis=1
    )
    return df


# ─────────────────────────────────────────
# INTELLIGENCE SIDEBAR FILTERS
# Branch, Area, Customer, Product, Urgency, Feedback Status
# ─────────────────────────────────────────
def render_intelligence_filters(df: pd.DataFrame):
    if st.session_state.get("_reset_intel_filters"):
        st.session_state.pop("_reset_intel_filters", None)
        for k in ["g_branch","g_area","g_customer","g_product","g_urgency","g_fb"]:
            st.session_state[k] = "All"

    with st.sidebar:
        st.markdown(
            "<div style='font-size:0.68rem;font-weight:700;letter-spacing:0.18em;"
            "text-transform:uppercase;color:#C9A84C;margin:0.8rem 0 8px 0;'>"
            "Filters</div>",
            unsafe_allow_html=True
        )

        branches = ["All"] + sorted(df[COL_BRANCH].dropna().unique().tolist())
        sel_branch = st.selectbox("Branch", branches, key="g_branch")

        area_pool = df[df[COL_BRANCH] == sel_branch] if sel_branch != "All" else df
        areas = ["All"] + sorted(area_pool[COL_AREA].dropna().unique().tolist())
        if st.session_state.get("g_area","All") not in areas:
            st.session_state["g_area"] = "All"
        sel_area = st.selectbox("Area", areas, key="g_area")

        cust_pool = area_pool if sel_area == "All" \
                    else area_pool[area_pool[COL_AREA] == sel_area]
        customers = ["All"] + sorted(cust_pool[COL_CUSTOMER].dropna().unique().tolist())
        if st.session_state.get("g_customer","All") not in customers:
            st.session_state["g_customer"] = "All"
        sel_cust = st.selectbox("Customer", customers, key="g_customer")

        products = ["All"] + sorted(df[COL_SAMPLE_PROD].dropna().unique().tolist())
        sel_prod = st.selectbox("Product", products, key="g_product")

        urg_opts = ["All","Critical","Push Required",
                    "Initial Follow-up","Freshly Handed","Responded","Hold"]
        sel_urg = st.selectbox("Urgency", urg_opts, key="g_urgency")

        fb_opts = ["All","Positive","Negative","Pending","Hold"]
        sel_fb  = st.selectbox("Feedback Status", fb_opts, key="g_fb")

        if st.button("🔄 Reset Filters", key="g_reset", width='stretch'):
            st.session_state["_reset_intel_filters"] = True
            st.rerun()

    fdf = df.copy()
    if sel_branch != "All": fdf = fdf[fdf[COL_BRANCH]        == sel_branch]
    if sel_area   != "All": fdf = fdf[fdf[COL_AREA]          == sel_area]
    if sel_cust   != "All": fdf = fdf[fdf[COL_CUSTOMER]      == sel_cust]
    if sel_prod   != "All": fdf = fdf[fdf[COL_SAMPLE_PROD]   == sel_prod]
    if sel_urg    != "All": fdf = fdf[fdf["Urgency"]         == sel_urg]
    if sel_fb     != "All": fdf = fdf[fdf["Feedback Status"] == sel_fb]

    return fdf, sel_prod


# ─────────────────────────────────────────
# PIPELINE SIDEBAR FILTERS (Analytics only)
# Branch, Area, Customer, Supplier, Stage, Product
# ─────────────────────────────────────────
def render_pipeline_filters(df: pd.DataFrame):
    if df.empty:
        return df

    if st.session_state.get("_reset_pipe_filters"):
        st.session_state.pop("_reset_pipe_filters", None)
        for k in ["gp_branch","gp_area","gp_customer","gp_supplier","gp_stage","gp_product"]:
            st.session_state[k] = "All"

    with st.sidebar:
        st.markdown(
            "<div style='font-size:0.68rem;font-weight:700;letter-spacing:0.18em;"
            "text-transform:uppercase;color:#C9A84C;margin:0.8rem 0 8px 0;'>"
            "Filters</div>",
            unsafe_allow_html=True
        )

        # Branch
        b_col = next((c for c in ["branch","Branch",COL_BRANCH] if c in df.columns), None)
        if b_col:
            branches = ["All"] + sorted(df[b_col].dropna().unique().tolist())
            sel_branch = st.selectbox("Branch", branches, key="gp_branch")
            area_pool = df[df[b_col] == sel_branch] if sel_branch != "All" else df
        else:
            sel_branch, area_pool = "All", df

        # Area
        a_col = next((c for c in ["area","Area",COL_AREA] if c in df.columns), None)
        if a_col:
            areas = ["All"] + sorted(area_pool[a_col].dropna().unique().tolist())
            if st.session_state.get("gp_area","All") not in areas:
                st.session_state["gp_area"] = "All"
            sel_area = st.selectbox("Area", areas, key="gp_area")
            cust_pool = area_pool if sel_area == "All" else area_pool[area_pool[a_col] == sel_area]
        else:
            sel_area, cust_pool = "All", area_pool

        # Customer
        c_col = next((c for c in ["customer","Customer",COL_CUSTOMER] if c in df.columns), None)
        if c_col:
            customers = ["All"] + sorted(cust_pool[c_col].dropna().unique().tolist())
            if st.session_state.get("gp_customer","All") not in customers:
                st.session_state["gp_customer"] = "All"
            sel_cust = st.selectbox("Customer", customers, key="gp_customer")
        else:
            sel_cust = "All"

        # Supplier
        s_col = next((c for c in ["supplier","Supplier"] if c in df.columns), None)
        if s_col:
            suppliers = ["All"] + sorted(df[s_col].dropna().unique().tolist())
            sel_supplier = st.selectbox("Supplier", suppliers, key="gp_supplier")
        else:
            sel_supplier = "All"

        # Stage
        stage_col = next((c for c in ["stage","Stage"] if c in df.columns), None)
        if stage_col:
            stages = ["All"] + sorted(df[stage_col].dropna().unique().tolist())
            sel_stage = st.selectbox("Stage", stages, key="gp_stage")
        else:
            sel_stage = "All"

        # Product
        p_col = next((c for c in ["sample_product","product","Product",COL_SAMPLE_PROD] if c in df.columns), None)
        if p_col:
            products = ["All"] + sorted(df[p_col].dropna().unique().tolist())
            sel_prod = st.selectbox("Product", products, key="gp_product")
        else:
            sel_prod = "All"

        if st.button("🔄 Reset Filters", key="gp_reset", width='stretch'):
            st.session_state["_reset_pipe_filters"] = True
            st.rerun()

    fdf = df.copy()
    if sel_branch   != "All" and b_col:     fdf = fdf[fdf[b_col]     == sel_branch]
    if sel_area     != "All" and a_col:     fdf = fdf[fdf[a_col]     == sel_area]
    if sel_cust     != "All" and c_col:     fdf = fdf[fdf[c_col]     == sel_cust]
    if sel_supplier != "All" and s_col:     fdf = fdf[fdf[s_col]     == sel_supplier]
    if sel_stage    != "All" and stage_col: fdf = fdf[fdf[stage_col] == sel_stage]
    if sel_prod     != "All" and p_col:     fdf = fdf[fdf[p_col]     == sel_prod]

    return fdf


# ─────────────────────────────────────────
# MAIN ROUTER
# ─────────────────────────────────────────
def show_sample_module(landing_choice):
    st.markdown(SAMPLE_CSS, unsafe_allow_html=True)
    st.markdown(ROUTER_NAV_CSS, unsafe_allow_html=True)
    if landing_choice is None:
        landing_choice = st.session_state.get("landing_choice")

    if not landing_choice:
        from landing_page import show_landing
        show_landing()
        return

    # ── INTELLIGENCE ──────────────────────────────────────────
    if landing_choice == "intelligence":
        if "sample_page" not in st.session_state:
            st.session_state["sample_page"] = "sample_overview"
        current = st.session_state.get("sample_page", "sample_overview")

        # Double-rerun trick for card deletion cache flush
        if st.session_state.pop("_card_deleted", False):
            st.rerun()

        with st.spinner("Loading..."):
            df = load_sample_data()
            history = load_all_latest_feedback()
            if not df.empty:
                df = enrich(df, history)

        # ── Sidebar nav (always) ──

        with st.sidebar:
            st.markdown("---")
            st.markdown(
                "<div style='font-size:0.90 rem;font-weight:1200;letter-spacing:0.18em;"
                "text-transform:uppercase;color:#C9A84C;margin-bottom:8px;'>"
                "Sample Tracker </div>",
                unsafe_allow_html=True
            )
            for page_key, label in INTELLIGENCE_PAGES.items():
                if st.button(label, key=f"snav_{page_key}", width='stretch'):
                    st.session_state["sample_page"] = page_key
                    st.rerun()
            st.markdown("---")

        _highlight_active_nav(f"snav_{current}")

        # ── Sidebar filters — only for pages that need them ──
        if current in INTEL_SIDEBAR_PAGES and not df.empty:
            fdf, sel_prod = render_intelligence_filters(df)
        else:
            # Detailed Info uses in-page filters — pass full df unfiltered
            fdf, sel_prod = df.copy(), "All"

        # ── Route to page ──
        if current == "sample_overview":
            from samples_new.sample_overview import show_overview
            show_overview(fdf, sel_prod)

        elif current == "sample_detailed":
            from samples_new.sample_detailed import show_detailed_info
            show_detailed_info(fdf)

        elif current == "sample_action":
            from samples_new.sample_action import show_action_required
            show_action_required(fdf)

        elif current == "sample_all":
            from samples_new.sample_action import show_all_samples
            show_all_samples(fdf)

    # ── PIPELINE ──────────────────────────────────────────────
    elif landing_choice == "pipeline":
        if "pipeline_page" not in st.session_state:
            st.session_state["pipeline_page"] = "sample_entry"
        current = st.session_state.get("pipeline_page", "sample_entry")

        # ── Sidebar nav (always) ──

        with st.sidebar:
            st.markdown("---")
            st.markdown(
                "<div style='font-size:0.90rem;font-weight:1200;letter-spacing:0.18em;"
                "text-transform:uppercase;color:#C9A84C;margin-bottom:8px;'>"
                "Sample Tracker</div>",
                unsafe_allow_html=True
            )
            for page_key, label in PIPELINE_PAGES.items():
                if st.button(label, key=f"snav_{page_key}", width='stretch'):
                    st.session_state["pipeline_page"] = page_key
                    st.rerun()
            st.markdown("---")

        _highlight_active_nav(f"snav_{current}")

        # ── Load pipeline data only when needed ──
        pdf = None
        if current in ("pipeline_tracker", "notifications", "pipeline_kpi"):
            from sample_pipeline.sample_pipeline_firestore import load_pipeline_entries
            raw_pdf = load_pipeline_entries()
            if current == "pipeline_kpi" and not raw_pdf.empty:
                pdf = render_pipeline_filters(raw_pdf)
            else:
                pdf = raw_pdf


        # ── Route to page ──
        if current == "sample_entry":
            from sample_pipeline.new_enquiry import show_new_enquiry
            show_new_enquiry()

        elif current == "pipeline_tracker":
            from sample_pipeline.pipeline_tracker import show_pipeline_tracker
            show_pipeline_tracker()

        elif current == "notifications":
            from sample_pipeline.notifications import show_notifications
            show_notifications()

        elif current == "pipeline_kpi":
            from sample_pipeline.pipeline_analytics import show_pipeline_analytics
            show_pipeline_analytics(pdf)
