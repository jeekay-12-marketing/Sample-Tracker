"""
New Enquiry form — Stage 1 of the sample pipeline.
Captures customer enquiry details and in-stock check.
"""
import streamlit as st
from datetime import date, datetime
from samples_new.sample_constants import SAMPLE_CSS
from sample_pipeline.sample_pipeline_firestore import create_pipeline_entry
from sample_pipeline.sample_pipeline_sync import silent_pipeline_sync

    
from admin.manage_customers import (load_customers, get_branches, get_areas,
    get_customer_names, get_industry)


# Every widget key used in the form below — needed so we can wipe them
# all cleanly when the user starts a fresh enquiry after a successful submit.
_NE_FORM_KEYS = [
    "ne_enquiry_date", "ne_branch", "ne_area", "ne_area_dis",
    "ne_customer", "ne_customer_dis", "ne_industry", "ne_industry_empty",
    "ne_contact", "ne_cust_prod", "ne_sample_prod", "ne_supplier",
    "ne_unit", "ne_qty_value", "ne_in_stock",
]


def _reset_enquiry_form():
    """Clear all form widget state and go back to a blank form."""
    for k in _NE_FORM_KEYS:
        st.session_state.pop(k, None)
    st.session_state.pop("ne_view", None)
    st.session_state.pop("ne_last_doc_id", None)


def _show_success_page():
    """Dedicated success screen shown instead of the form after submit."""
    st.markdown("""
    <div class="sd-hero">
        <div class="sd-eyebrow">Sample Pipeline</div>
        <div class="sd-title">Enquiry <em>Submitted</em></div>
        <div class="sd-divider"></div>
    </div>""", unsafe_allow_html=True)

    st.success("✅ **Enquiry recorded successfully!**")
    st.balloons()
    st.info("Go to **Pipeline Tracker** to update the status as events happen.")
    if st.button("➕ New Enquiry", type="primary", width='content'):
            _reset_enquiry_form()
            st.rerun()
        

def show_new_enquiry():
    # ── Gate: show success page instead of the form ──
    if st.session_state.get("ne_view") == "success":
        _show_success_page()
        return

    st.markdown(SAMPLE_CSS, unsafe_allow_html=True)

    st.markdown("""
    <style>
    .se-section {
        font-family: 'Outfit', sans-serif;
        font-size: 0.97rem; font-weight: 700;
        letter-spacing: 0.18em; text-transform: uppercase;
        color: #C9A84C; border-bottom: 2px solid #DDD5C5;
        padding-bottom: 8px; margin: 2rem 0 1rem 0;
        position: relative;
    }
    .se-section::after {
        content: ''; position: absolute;
        bottom: -2px; left: 0; width: 40px; height: 2px;
        background: #C9A84C;
    }
    .stage-info {
        background: #FFFFFF;
        border: 1.5px solid #DDD5C5;
        border-left: 5px solid #C9A84C;
        border-radius: 10px;
        padding: 1rem 1.4rem;
        font-family: 'Outfit', sans-serif;
        font-size: 0.90rem;
        color: #1B2A4A;
        margin-bottom: 1.5rem;
    }
    .auto-fill-badge {
        display: inline-flex; align-items: center; gap: 4px;
        background: #E8F5E9; border: 1px solid #A5D6A7;
        border-radius: 20px; padding: 3px 12px;
        font-family: 'Outfit', sans-serif; font-size: 0.75rem;
        font-weight: 500; color: #2E7D32; margin-top: 6px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="sd-hero">
        <div class="sd-eyebrow">Sample Pipeline</div>
        <div class="sd-title">New <em>Enquiry</em></div>
        <div class="sd-sub">Record a new sample enquiry from a customer. Fill what you know now — update the rest as events happen.</div>
        <div class="sd-divider"></div>
    </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div class="stage-info">
        📋 <b>Stage 1 of 5</b> — Enquiry Received<br>
        <span style="color:#6B7A99;font-size:0.90rem;">
        Fill this form as soon as you receive a sample enquiry from the customer.
        You'll update supplier details, shipment info and handover separately.
        </span>
    </div>
    """, unsafe_allow_html=True)

    st.caption(f"Logged in as **{st.session_state.get('email','')}**")

    # ── Load customers ──
    with st.spinner("Loading customer list..."):
        customers = load_customers()

    if not customers:
        st.warning("⚠️ No customers found. Contact admin.")
        return

    # ══════════════════════════════════════
    # SECTION 1 — Customer Info
    # ══════════════════════════════════════
    st.markdown('<div class="se-section">👤 Customer Info</div>',
               unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        enquiry_date = st.date_input(
            "Enquiry Date *",
            value=date.today(), key="ne_enquiry_date"
        )
    with col2:
        branches = get_branches(customers)
        ne_branch = st.selectbox(
            "Branch *",
            ["— Select —"] + branches,
            key="ne_branch"
        )

    col3, col4 = st.columns(2)
    with col3:
        if ne_branch and ne_branch != "— Select —":
            areas    = get_areas(customers, ne_branch)
            ne_area  = st.selectbox("Area *", ["— Select —"] + areas, key="ne_area")
        else:
            st.selectbox("Area *", ["Select branch first"],
                        disabled=True, key="ne_area_dis")
            ne_area = ""

    with col4:
        if ne_area and ne_area != "— Select —":
            cust_names  = get_customer_names(customers, ne_branch, ne_area)
            ne_customer = st.selectbox(
                "Customer *", ["— Select —"] + cust_names, key="ne_customer"
            )
        else:
            st.selectbox("Customer *", ["Select area first"],
                        disabled=True, key="ne_customer_dis")
            ne_customer = ""

    col5, col6 = st.columns(2)
    with col5:
        if ne_customer and ne_customer != "— Select —":
            industry = get_industry(customers, ne_customer)
            st.text_input("Industry", value=industry, disabled=True,
                         key="ne_industry")
            st.markdown('<span class="auto-fill-badge">✓ Auto-filled</span>',
                       unsafe_allow_html=True)
        else:
            st.text_input("Industry", value="", disabled=True,
                         key="ne_industry_empty")
    with col6:
        ne_contact = st.text_input(
            "Contact Person",
            placeholder="e.g. Mr. Raj",
            key="ne_contact"
        )

    ne_cust_prod = st.text_input(
        "Product Manufactured by Customer",
        placeholder="e.g. Mat, Footwear",
        key="ne_cust_prod"
    )

    # ══════════════════════════════════════
    # SECTION 2 — Sample Details
    # ══════════════════════════════════════
    st.markdown('<div class="se-section">🧪 Sample Details</div>',
               unsafe_allow_html=True)

    col7, col8, col9 = st.columns(3)
    with col7:
        ne_sample_prod = st.text_input(
            "Sample Product Name *",
            placeholder="e.g. TBzTD",
            key="ne_sample_prod"
        )
    with col8:
        ne_supplier = st.text_input(
            "Supplier Name",
            placeholder="e.g. Auropol",
            key="ne_supplier"
        )
    with col9:       
        # Radio buttons for unit
        unit_type = st.radio(
            "Unit",
            options=["Grams (g)", "Kilograms (kg)", "Milliliters (ml)", "Litres (L)"],
            horizontal=True,
            key="ne_unit"
        )
        
        # Number input
        qty_value = st.number_input(
            "Value *",
            min_value=0.0,
            step=0.1,
            format="%.2f",
            key="ne_qty_value"
        )
        
        # Auto conversion logic
        if qty_value > 0:
            if unit_type in ["Grams (g)", "Kilograms (kg)"]:
                standard_unit = "kg"
                if unit_type == "Grams (g)":
                    standard_qty = round(qty_value / 1000, 4)   # convert g → kg
                else:
                    standard_qty = round(qty_value, 4)
                    
            else:  # Volume
                standard_unit = "L"
                if unit_type == "Milliliters (ml)":
                    standard_qty = round(qty_value / 1000, 4)   # convert ml → L
                else:
                    standard_qty = round(qty_value, 4)
            
            st.caption(f"**Converted:** {standard_qty} {standard_unit}")
        else:
            standard_qty = 0.0
            standard_unit = ""

    # ══════════════════════════════════════
    # SECTION 3 — In Stock Check
    # ══════════════════════════════════════
    st.markdown('<div class="se-section">📦 Stock Check</div>',
               unsafe_allow_html=True)

    st.markdown(
        "<div style='font-family:Outfit,sans-serif;font-size:0.92rem;"
        "margin-bottom:0.8rem;'>"
        "<b>Is the sample currently in stock</b>?</div>",
        unsafe_allow_html=True
    )

    in_stock = st.radio(
        "In Stock?",
        ["No", "Yes"],
        horizontal=True,
        key="ne_in_stock",
        label_visibility="collapsed"
    )

    if in_stock == "Yes":
        st.markdown(
            "<div style='font-family:Outfit,sans-serif;font-size:0.90rem;"
            "color:#2E7D32;background:#E8F5E9;border-radius:8px;"
            "padding:10px 14px;margin-top:8px;border:1px solid #A5D6A7;'>"
            "✅ Sample is in stock — you can proceed directly to handover. "
            "Record the handover details in <b>Pipeline Tracker</b> after submitting.</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            "<div style='font-family:Outfit,sans-serif;font-size:0.85rem;"
            "color:#E65100;background:#FFF3E0;border-radius:8px;"
            "padding:10px 14px;margin-top:8px;border:1px solid #FFAB40;'>"
            "🟠 Sample not in stock — you'll need to contact the supplier. "
            "Record supplier details in <b>Pipeline Tracker</b> after submitting.</div>",
            unsafe_allow_html=True
        )

    st.divider()

    # ══════════════════════════════════════
    # SUBMIT
    # ══════════════════════════════════════
    if st.button("📋 Submit Enquiry", type="primary",
                width='content', key="ne_submit"):
        errors = []
        if not ne_branch or ne_branch == "— Select —":
            errors.append("Branch is required")
        if not ne_area or ne_area == "— Select —":
            errors.append("Area is required")
        if not ne_customer or ne_customer == "— Select —":
            errors.append("Customer is required")
        if not ne_sample_prod.strip():
            errors.append("Sample Product Name is required")
        if standard_qty == 0.0:
            errors.append("Please enter Sample Quantity")

        if errors:
            for e in errors:
                st.error(f"⚠️ {e}")
        else:
            with st.spinner("Submitting form..."):
                try:
                    doc_id = create_pipeline_entry({
                        "branch":           ne_branch,
                        "area":             ne_area,
                        "customer":         ne_customer,
                        "contact":          ne_contact.strip(),
                        "customer_product": ne_cust_prod.strip(),
                        "sample_product":   ne_sample_prod.strip(),
                        "supplier":         ne_supplier.strip(),
                        "standard_qty": standard_qty,
                        "standard_unit": standard_unit,
                        "enquiry_date":     str(enquiry_date),
                        "in_stock":         in_stock,
                    })
                    silent_pipeline_sync()

                    # Hand off to the success page on the next run — keep
                    # this run's job limited to "save + flag", nothing else.
                    st.session_state["ne_view"] = "success"
                    st.session_state["ne_last_doc_id"] = doc_id

                except Exception as e:
                    st.error(f"Failed to submit: {e}")
                    st.stop()

            # Only reached if the try block above didn't error.
            st.rerun()