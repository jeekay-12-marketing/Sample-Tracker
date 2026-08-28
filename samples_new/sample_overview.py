"""
Sample Overview — main landing page after login.
Tab 1: Charts overview with global sidebar filters
Tab 2: Supplier-wise breakdown
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from samples_new.sample_constants import (
     SAMPLE_CSS, CHART_COLORS, chart_layout,
    COL_BRANCH, COL_AREA, COL_CUSTOMER, COL_SAMPLE_PROD,
    COL_HO_DATE, COL_FEEDBACK, COL_PURCHASED, COL_SUPPLIER
)
from samples_new.sample_firestore import (
    classify_feedback, get_urgency
)



# ─────────────────────────────────────────
# ENRICH DATAFRAME
# ─────────────────────────────────────────
def enrich(df: pd.DataFrame, history: dict) -> pd.DataFrame:
    df = df.copy()

    def get_latest(row):
        ho     = row[COL_HO_DATE]
        ho_str = str(ho.date()) if pd.notna(ho) else ""
        key    = (
            str(row.get(COL_CUSTOMER, "")).strip(),
            str(row.get(COL_SAMPLE_PROD, "")).strip(),
            ho_str
        )
        entry = history.get(key)
        if entry:
            return entry.get("feedback", "")
        fb = row.get(COL_FEEDBACK, "")
        return "" if pd.isna(fb) else str(fb)

    df["Latest Feedback"]  = df.apply(get_latest, axis=1)
    df["Feedback Status"]  = df["Latest Feedback"].apply(classify_feedback)
    df["Days Since HO"]    = (
        pd.Timestamp.now() - df[COL_HO_DATE]
    ).dt.days.fillna(0).astype(int)
    df["Has Feedback"]     = df["Feedback Status"] != "Pending"
    df["Urgency"]          = df.apply(
        lambda r: get_urgency(r["Days Since HO"], r["Has Feedback"]), axis=1
    )
    return df


# ─────────────────────────────────────────
# KPI HELPER
# ─────────────────────────────────────────
def kpi(label, value, sub="", variant="default"):
    card_cls = f"kpi-card {variant}" if variant != "default" else "kpi-card"
    val_cls  = variant if variant != "default" else ""
    st.markdown(f"""
    <div class="{card_cls}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value {val_cls}">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# SIDEBAR GLOBAL FILTERS
# ─────────────────────────────────────────
def render_sidebar_filters(df: pd.DataFrame):
    """
    Renders global filters in sidebar.
    Returns filtered dataframe.
    """
    with st.sidebar:
        st.markdown(
            "<div style='font-size:0.68rem;font-weight:700;letter-spacing:0.18em;"
            "text-transform:uppercase;color:#C9A84C;margin:1rem 0 8px 0;'>Filters</div>",
            unsafe_allow_html=True
        )

        # ── Branch ──
        branches   = ["All"] + sorted(df[COL_BRANCH].dropna().unique().tolist())
        sel_branch = st.selectbox("Branch", branches, key="g_branch")

        # ── Area — drills down by branch ──
        if sel_branch != "All":
            area_pool = df[df[COL_BRANCH] == sel_branch]
        else:
            area_pool = df
        areas    = ["All"] + sorted(area_pool[COL_AREA].dropna().unique().tolist())
        sel_area = st.selectbox("Area", areas, key="g_area")

        # ── Customer — drills down by branch + area ──
        cust_pool = area_pool
        if sel_area != "All":
            cust_pool = cust_pool[cust_pool[COL_AREA] == sel_area]
        customers  = ["All"] + sorted(cust_pool[COL_CUSTOMER].dropna().unique().tolist())
        sel_cust   = st.selectbox("Customer", customers, key="g_customer")

        # ── Product ──
        products   = ["All"] + sorted(df[COL_SAMPLE_PROD].dropna().unique().tolist())
        sel_prod   = st.selectbox("Product", products, key="g_product")

        # ── Urgency ──
        urg_opts   = ["All", "Critical", "Push Required",
                      "Initial Follow-up", "Freshly Handed", "Responded"]
        sel_urg    = st.selectbox("Urgency", urg_opts, key="g_urgency")

        # ── Feedback Status ──
        fb_opts    = ["All", "Positive", "Negative", "Pending"]
        sel_fb     = st.selectbox("Feedback Status", fb_opts, key="g_fb")

        if st.button("🔄 Reset Filters", key="g_reset", width='stretch'):
            for k in ["g_branch","g_area","g_customer",
                      "g_product","g_urgency","g_fb"]:
                st.session_state.pop(k, None)
            st.rerun()

    # ── Apply filters ──
    fdf = df.copy()
    if sel_branch != "All": fdf = fdf[fdf[COL_BRANCH]        == sel_branch]
    if sel_area   != "All": fdf = fdf[fdf[COL_AREA]          == sel_area]
    if sel_cust   != "All": fdf = fdf[fdf[COL_CUSTOMER]      == sel_cust]
    if sel_prod   != "All": fdf = fdf[fdf[COL_SAMPLE_PROD]   == sel_prod]
    if sel_urg    != "All": fdf = fdf[fdf["Urgency"]         == sel_urg]
    if sel_fb     != "All": fdf = fdf[fdf["Feedback Status"] == sel_fb]

    return fdf, sel_prod


# ─────────────────────────────────────────
# MAIN OVERVIEW PAGE
# ─────────────────────────────────────────
def show_overview(fdf=None, sel_prod="All"):
    st.markdown(SAMPLE_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="sd-hero">
        <div class="sd-eyebrow">Sample Intelligence</div>
        <div class="sd-title">Sample <em>Overview</em></div>
        <div class="sd-sub">Big picture — feedback health, urgency and sample trends.</div>
        <div class="sd-divider"></div>
    </div>""", unsafe_allow_html=True)

    # fdf and sel_prod passed from router (global filters already applied)
    if fdf is None or fdf.empty:
        st.warning("No samples match the current filters.")
        return

    # ── Date Range (page-level — applies on top of the sidebar filters) ──
    valid_dates = fdf[COL_HO_DATE].dropna()
    if not valid_dates.empty:
        data_min = valid_dates.min().date()
        data_max = valid_dates.max().date()

        st.markdown(
            "<div style='font-family:Outfit,sans-serif;font-size:0.72rem;"
            "font-weight:700;letter-spacing:0.15em;text-transform:uppercase;"
            "color:#6B7A99;margin-bottom:6px;'>📅 Date Range (Hand-over Date)</div>",
            unsafe_allow_html=True
        )

        PRESETS = [
            ("30d",    "Last 30 Days"),
            ("60d",    "Last 60 Days"),
            ("90d",    "Last 90 Days"),
            ("120d",   "Last 120 Days"),
            ("all",    "All Time"),
            ("custom", "🗓 Custom Range"),
        ]
        active_preset = st.session_state.get("ov_date_preset", "all")

        preset_cols = st.columns(len(PRESETS))
        for (key, label), col in zip(PRESETS, preset_cols):
            with col:
                if st.button(label, key=f"ov_preset_{key}", width='stretch'):
                    st.session_state["ov_date_preset"] = key
                    st.rerun()

        # Highlight the active preset button
        st.markdown(f"""
        <style>
        .st-key-ov_preset_{active_preset} .stButton > button {{
            background: rgba(201, 168, 76, 0.35) !important;
            color: #FFF6E0 !important;
            border: 2px solid #E8C96A !important;
            font-weight: 800 !important;
        }}
        </style>
        """, unsafe_allow_html=True)

        if active_preset == "custom":
            date_range = st.date_input(
                "Select a custom date range",
                value=(data_min, data_max),
                min_value=data_min,
                max_value=data_max,
                key="ov_custom_range",
                label_visibility="collapsed"
            )
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_date, end_date = date_range
            else:
                # User has only picked the start date so far — wait for both
                start_date, end_date = data_min, data_max
        elif active_preset == "all":
            start_date, end_date = data_min, data_max
        else:
            days       = int(active_preset.replace("d", ""))
            start_date = max(data_min, data_max - pd.Timedelta(days=days))
            end_date   = data_max

        fdf = fdf[
            fdf[COL_HO_DATE].dt.date.between(start_date, end_date)
        ]

        st.caption(
            f"📦 {len(fdf)} samples · "
            f"{start_date.strftime('%d %b %Y')} – {end_date.strftime('%d %b %Y')}"
        )
        st.markdown("<div style='margin-bottom:0.8rem;'></div>", unsafe_allow_html=True)

    if fdf.empty:
        st.warning("No samples in the selected date range.")
        return

    total    = len(fdf)
    positive = len(fdf[fdf["Feedback Status"] == "Positive"])
    negative = len(fdf[fdf["Feedback Status"] == "Negative"])
    pending  = len(fdf[fdf["Feedback Status"] == "Pending"])
    critical = len(fdf[fdf["Urgency"] == "Critical"])
    push     = len(fdf[fdf["Urgency"] == "Push Required"])
    purchased = len(fdf[fdf["Purchased?"] == "Yes"])
    conv_rt  = f"{positive/total*100:.0f}%" if total > 0 else "—"
    conv_rt_p = f"{purchased/total*100:.0f}%" if total > 0 else "—"

    if total == 0:
        st.warning("No samples match the current filters.")
        return

    # ── Tabs ──
    try:
        tab1, tab2, tab3 = st.tabs(["📊  Overview", "🏭  Supplier Wise", "👥  Customer Wise"])

        # ══════════════════════════════════════
        # TAB 1 — OVERVIEW
        # ══════════════════════════════════════
        with tab1:

            # ── KPI Cards ──
            c1,c2,c3,c4,c5,c6, c7 = st.columns(7)
            with c1: kpi("Total Samples", total)
            with c2: kpi("Positive",  positive, f"{conv_rt} rate", "green")
            with c3: kpi("Negative",  negative, "rejected", "red")
            with c4: kpi("Pending",   pending,  "no feedback yet", "amber")
            with c5: kpi("🔴 Critical",  critical, "21+ days", "red")
            with c6: kpi("🟠 Push Reqd", push,     "15-20 days", "amber")
            with c7: kpi("Purchased Samples", purchased, f"{conv_rt_p} rate", "green")

            st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)

            # ── Row 1: Branch bar + Feedback pie ──
            col_a, col_b = st.columns(2, gap="large")

            with col_a:
                st.markdown('<div class="sd-section">Samples by Branch</div>',
                        unsafe_allow_html=True)
                bc = fdf[COL_BRANCH].value_counts().reset_index()
                bc.columns = ["Branch", "Count"]
                fig = px.bar(bc, x="Branch", y="Count",
                            color_discrete_sequence=[CHART_COLORS[0]], text="Count")
                fig.update_traces(textposition="outside")
                st.plotly_chart(chart_layout(fig), width='stretch',
                            config={"displayModeBar": False})

            with col_b:
                st.markdown('<div class="sd-section">Feedback Status</div>',
                        unsafe_allow_html=True)
                fb_counts = fdf["Feedback Status"].value_counts().reset_index()
                fb_counts.columns = ["Status", "Count"]
                fig2 = px.pie(
                    fb_counts, names="Status", values="Count",
                    color="Status",
                    color_discrete_map={
                        "Positive": "#2E7D32",
                        "Negative": "#B71C1C",
                        "Pending":  "#F57F17"
                    }, hole=0.5
                )
                fig2.update_traces(textinfo="percent+label", textfont_size=13)
                st.plotly_chart(chart_layout(fig2), width='stretch',
                            config={"displayModeBar": False})

            # ── Row 2: Urgency donut + Timeline ──
            col_c, col_d = st.columns(2, gap="large")

            with col_c:
                st.markdown('<div class="sd-section">Urgency Distribution</div>',
                        unsafe_allow_html=True)
                urg_colors = {
                    "Freshly Handed":    "#2E7D32",
                    "Initial Follow-up": "#F57F17",
                    "Push Required":     "#E65100",
                    "Critical":          "#B71C1C",
                    "Responded":         "#1565C0"
                }
                uc = fdf["Urgency"].value_counts().reset_index()
                uc.columns = ["Urgency", "Count"]
                fig3 = px.pie(uc, names="Urgency", values="Count",
                            color="Urgency", color_discrete_map=urg_colors, hole=0.5)
                fig3.update_traces(textinfo="percent+label", textfont_size=12)
                st.plotly_chart(chart_layout(fig3), width='stretch',
                            config={"displayModeBar": False})

            with col_d:
                st.markdown('<div class="sd-section">Activity Timeline - Handed Over Samples </div>',
                        unsafe_allow_html=True)
                st.caption("Count of Samples handed over - Month wise")
                tl = (
                    fdf[fdf[COL_HO_DATE].notna()]
                    .groupby(fdf[COL_HO_DATE].dt.to_period("M"))
                    .size().reset_index()
                )
                tl.columns = ["Month", "Samples"]
                tl["Month"] = tl["Month"].astype(str)
                fig4 = px.line(tl, x="Month", y="Samples", markers=True,
                            color_discrete_sequence=[CHART_COLORS[0]],
                            line_shape="spline")
                fig4.update_yaxes(title_text="Count of Samples")
                fig4.update_traces(line_width=2.5, marker_size=7)
                st.plotly_chart(chart_layout(fig4), width='stretch',
                            config={"displayModeBar": False})

            # ── Products stacked bar ──
            st.markdown('<div class="sd-section">Products — Feedback Breakdown</div>',
                    unsafe_allow_html=True)

            # If product filter is active → show just that product
            # Otherwise → show top 10
            if sel_prod != "All":
                prod_df   = fdf.copy()
                chart_title = f"Product: {sel_prod}"
            else:
                top_prods = fdf[COL_SAMPLE_PROD].value_counts().head(10).index.tolist()
                prod_df   = fdf[fdf[COL_SAMPLE_PROD].isin(top_prods)].copy()
                chart_title = "Top 10 Products"

            st.caption(chart_title)

            prod_fb = (
                prod_df
                .groupby([COL_SAMPLE_PROD, "Feedback Status"])
                .size().reset_index(name="Count")
            )

            # Keep order: most sampled first
            prod_order = prod_df[COL_SAMPLE_PROD].value_counts().index.tolist()

            fig5 = px.bar(
                prod_fb, x="Count", y=COL_SAMPLE_PROD,
                color="Feedback Status", orientation="h",
                color_discrete_map={
                    "Positive": "#2E7D32",
                    "Negative": "#B71C1C",
                    "Pending":  "#F57F17"
                },
                barmode="stack",
                category_orders={COL_SAMPLE_PROD: prod_order}
            )
            fig5.update_layout(yaxis=dict(autorange="reversed"))
            st.plotly_chart(
                chart_layout(fig5, height=max(350, len(prod_order)*40)),
                width='stretch',
                config={"displayModeBar": False}
            )

        # ══════════════════════════════════════
        # TAB 2 — SUPPLIER WISE
        # ══════════════════════════════════════

        with tab2:
                st.markdown("""
                <div style="font-family:Outfit,sans-serif;font-size:0.9rem;
                            color:#6B7A99;margin-bottom:1.2rem;">
                    Select a supplier to see product-wise feedback breakdown.
                </div>
                """, unsafe_allow_html=True)

                if COL_SUPPLIER not in fdf.columns:
                    st.warning(f"⚠️ '{COL_SUPPLIER}' column not found.")
                else:
                    suppliers = sorted(fdf[COL_SUPPLIER].dropna().unique().tolist())
                    suppliers = [s for s in suppliers if str(s).strip() not in ("","nan","None")]

                    if not suppliers:
                        st.warning("No supplier data found.")
                    else:
                        sel_supplier = st.selectbox(
                            "Select Supplier",
                            ["— Select —"] + suppliers,
                            key="tab2_supplier"
                        )

                        if sel_supplier == "— Select —":
                            st.info("👆 Select a supplier to view their product breakdown.")
                        else:
                            sup_df = fdf[fdf[COL_SUPPLIER] == sel_supplier].copy()
                            if sup_df.empty:
                                st.warning(f"No samples found for supplier: {sel_supplier}")
                            else:

                                # ── Supplier KPIs ──
                                sup_total     = len(sup_df)
                                sup_positive  = len(sup_df[sup_df["Feedback Status"] == "Positive"])
                                sup_negative  = len(sup_df[sup_df["Feedback Status"] == "Negative"])
                                sup_pending   = len(sup_df[sup_df["Feedback Status"] == "Pending"])
                                sup_purchased = len(sup_df[sup_df[COL_PURCHASED] == "Yes"])
                                sup_products  = sup_df[COL_SAMPLE_PROD].nunique()

                                st.markdown(
                                    f"<div style='font-family:Cormorant Garamond,serif;font-size:1.6rem;"
                                    f"font-weight:700;color:#1B2A4A;margin:0.5rem 0 1rem 0;'>"
                                    f"{sel_supplier}</div>",
                                    unsafe_allow_html=True
                                )

                                k1,k2,k3,k4,k5,k6 = st.columns(6)
                                with k1: kpi("Total Samples", sup_total)
                                with k2: kpi("Products",      sup_products, "unique products")
                                with k3: kpi("Positive",  sup_positive, variant="green")
                                with k4: kpi("Negative",  sup_negative, variant="red")
                                with k5: kpi("Pending",   sup_pending,  variant="amber")
                                with k6: kpi("Purchased", sup_purchased, variant="green")

                                st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)

                                # ── Product-wise stacked bar ──
                                st.markdown('<div class="sd-section">Product-wise Feedback</div>',
                                        unsafe_allow_html=True)

                                prod_sup_order = sup_df[COL_SAMPLE_PROD].value_counts().index.tolist()
                                sup_prod_fb    = (
                                    sup_df
                                    .groupby([COL_SAMPLE_PROD, "Feedback Status"])
                                    .size().reset_index(name="Count")
                                )

                                fig6 = px.bar(
                                    sup_prod_fb, x="Count", y=COL_SAMPLE_PROD,
                                    color="Feedback Status", orientation="h",
                                    color_discrete_map={
                                        "Positive": "#2E7D32",
                                        "Negative": "#B71C1C",
                                        "Pending":  "#F57F17"
                                    },
                                    barmode="stack",
                                    category_orders={COL_SAMPLE_PROD: prod_sup_order}
                                )
                                st.plotly_chart(
                                    chart_layout(fig6, height=max(350, len(prod_sup_order)*45)),
                                    width='stretch',
                                    config={"displayModeBar": False}
                                )

                                # ── Per-product detail table ──
                                st.markdown('<div class="sd-section">Product Summary</div>',
                                        unsafe_allow_html=True)

                                summary = (
                                    sup_df
                                    .groupby(COL_SAMPLE_PROD)
                                    .agg(
                                        Total      =(COL_SAMPLE_PROD, "count"),
                                        Positive   =("Feedback Status", lambda x: (x=="Positive").sum()),
                                        Negative   =("Feedback Status", lambda x: (x=="Negative").sum()),
                                        Pending    =("Feedback Status", lambda x: (x=="Pending").sum()),
                                        Purchased  =(COL_PURCHASED, lambda x: (x=="Yes").sum()),
                                    )
                                    .reindex(prod_sup_order)  # ← same order as the chart above
                                    .reset_index()
                                    .rename(columns={COL_SAMPLE_PROD: "Product"})
                                )
                                summary["Conversion %"] = (
                                    summary["Purchased"] / summary["Total"] * 100
                                ).round(0).astype(int).astype(str) + "%"

                                st.dataframe(summary, width='stretch', hide_index=True)
        
        # ══════════════════════════════════════
        # TAB 3 — CUSTOMER WISE
        # ══════════════════════════════════════
        with tab3:
            st.markdown("""
            <div style="font-family:Outfit,sans-serif;font-size:0.9rem;
                        color:#6B7A99;margin-bottom:1.2rem;">
                Select a customer to see product-wise feedback breakdown.
            </div>
            """, unsafe_allow_html=True)

            fdf_new = fdf.copy()
            #st.write(fdf_new)

            if COL_CUSTOMER not in fdf.columns:
                st.warning(f"⚠️ '{COL_CUSTOMER}' column not found in your sheet. ")
            else:
                customers_list = sorted(fdf[COL_CUSTOMER].dropna().unique().tolist())
                customers_list = [c for c in customers_list
                                if str(c).strip() not in ("","nan","None")]
                if not customers_list:
                                st.warning("No customers found with current filters.")
                else:
                    sel_customer = st.selectbox(
                    "Select Customer",
                    ["— Select —"] + customers_list,
                    key="tab3_customer"
            )

                    if sel_customer == "— Select —":
                        st.info("👆 Select a customer to view their sample breakdown.")
                    else:
                        cust_df = fdf[fdf[COL_CUSTOMER] == sel_customer].copy()

                        if cust_df.empty:
                            st.warning(f"No samples found for: {sel_customer}")
                        else:
                            # ── Customer KPIs ──
                            cust_total     = len(cust_df)
                            cust_positive  = len(cust_df[cust_df["Feedback Status"] == "Positive"])
                            cust_negative  = len(cust_df[cust_df["Feedback Status"] == "Negative"])
                            cust_pending   = len(cust_df[cust_df["Feedback Status"] == "Pending"])
                            cust_purchased = len(cust_df[cust_df[COL_PURCHASED] == "Yes"])
                            cust_products  = cust_df[COL_SAMPLE_PROD].nunique()

                            st.markdown(
                                f"<div style='font-family:Cormorant Garamond,serif;"
                                f"font-size:1.6rem;font-weight:700;color:#1B2A4A;"
                                f"margin:0.5rem 0 1rem 0;'>{sel_customer}</div>",
                                unsafe_allow_html=True
                            )
                            
                            k1,k2,k3,k4,k5,k6 = st.columns(6)
                            with k1: kpi("Total Samples", cust_total)
                            with k2: kpi("Products",      cust_products, "unique products")
                            with k3: kpi("Positive",  cust_positive, variant="green")
                            with k4: kpi("Negative",  cust_negative, variant="red")
                            with k5: kpi("Pending",   cust_pending,  variant="amber")
                            with k6: kpi("Purchased", cust_purchased, variant="green")

                            st.markdown("<div style='margin-top:1.5rem;'></div>",
                                        unsafe_allow_html=True)

                            # ── Product-wise stacked bar ──
                            st.markdown('<div class="sd-section">Product-wise Feedback</div>',
                                        unsafe_allow_html=True)

                            prod_cust_order = cust_df[COL_SAMPLE_PROD].value_counts().index.tolist()
                            cust_prod_fb    = (
                                cust_df
                                .groupby([COL_SAMPLE_PROD, "Feedback Status"])
                                .size().reset_index(name="Count")
                            )

                            fig_c = px.bar(
                                cust_prod_fb, x="Count", y=COL_SAMPLE_PROD,
                                color="Feedback Status", orientation="h",
                                color_discrete_map={
                                    "Positive": "#2E7D32",
                                    "Negative": "#B71C1C",
                                    "Pending":  "#F57F17"
                                },
                                barmode="stack",
                                category_orders={COL_SAMPLE_PROD: prod_cust_order}
                            )
                            st.plotly_chart(
                                chart_layout(fig_c, height=max(300, len(prod_cust_order)*45)),
                                width='stretch',
                                config={"displayModeBar": False},
                                key="ov_cust_products"
                            )

                            # ── Summary table ──
                            st.markdown('<div class="sd-section">Product Summary</div>',
                                        unsafe_allow_html=True)

                            summary = (
                                cust_df
                                .groupby(COL_SAMPLE_PROD)
                                .agg(
                                    Total     =(COL_SAMPLE_PROD, "count"),
                                    Positive  =("Feedback Status", lambda x: (x=="Positive").sum()),
                                    Negative  =("Feedback Status", lambda x: (x=="Negative").sum()),
                                    Pending   =("Feedback Status", lambda x: (x=="Pending").sum()),
                                    Purchased =(COL_PURCHASED, lambda x: (x=="Yes").sum()),
                                )
                                .reindex(prod_cust_order)  # ← same order as the chart above
                                .reset_index()
                                .rename(columns={COL_SAMPLE_PROD: "Product"})
                            )
                            summary["Conversion %"] = (
                                summary["Purchased"] / summary["Total"] * 100
                            ).round(0).astype(int).astype(str) + "%"

                            st.dataframe(summary, width='stretch', hide_index=True)
    except Exception as e:
        import traceback
        st.error(f"Error: {e}")
        st.code(traceback.format_exc())