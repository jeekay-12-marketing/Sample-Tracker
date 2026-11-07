"""
Firestore CRUD for sample pipeline.
One document per sample journey in sample_pipeline/ collection.
"""
import streamlit as st
from datetime import datetime
import pandas as pd
from auth.firebase_config import get_db


# ─────────────────────────────────────────
# STAGE CONSTANTS
# ─────────────────────────────────────────
STAGES = {
    "enquiry":          {"label": "Enquiry Received",      "icon": "📋", "order": 1},
    "supplier_enquiry": {"label": "Supplier Contacted",    "icon": "📤", "order": 2},
    "shipped":          {"label": "Supplier Shipped",      "icon": "🚚", "order": 3},
    "stock_received":   {"label": "Stock Received",        "icon": "📦", "order": 4},
    "handed_over":      {"label": "Handed Over",           "icon": "🤝", "order": 5},
    "legacy":           {"label": "Legacy Entry",          "icon": "📁", "order": 0},
}

STAGE_ORDER = ["enquiry", "supplier_enquiry", "shipped",
               "stock_received", "handed_over"]

# Sheet 2 column order — must match exactly
PIPELINE_SHEET_COLS = [
    "Branch", "Area", "Name of Customer / Party",
    "Contact Person at Customer / Party",
    "Product Mfgd. By Customer / Party",
    "Our Sample Product Name", "Supplier Name",
    "Sample Quantity","Sample Unit", "Handed over By", "Handed over To",
    "Enquiry date",
    "In Stock?",
    "Enquiry sent to Principal date",
    "Supplier Shipment Date",
    "Stock received date",
    "Hand over to customer date",
    "Feedback",
    "Purchased?",
    "Stage",
    "Pipeline Doc ID",
]


# ─────────────────────────────────────────
# CREATE — New Enquiry (Stage 1)
# ─────────────────────────────────────────
def create_pipeline_entry(data: dict) -> str:
    """
    Create a new pipeline entry at stage 'enquiry'.
    Returns the Firestore document ID.
    """
    db = get_db()
    doc_ref = db.collection("sample_pipeline").document()
    doc_ref.set({
        # ── Customer & Product Info ──
        "branch":           data.get("branch", ""),
        "area":             data.get("area", ""),
        "customer":         data.get("customer", ""),
        "contact":          data.get("contact", ""),
        "customer_product": data.get("customer_product", ""),
        "sample_product":   data.get("sample_product", ""),
        "supplier":         data.get("supplier", ""),
        "standard_qty":     data.get("standard_qty", ""),
        "standard_unit":    data.get("standard_unit",""),

        # ── Stage 1 dates ──
        "enquiry_date":     data.get("enquiry_date", ""),
        "in_stock":         data.get("in_stock", "No"),

        # ── Later stages (empty initially) ──
        "supplier_enquiry_date":  "",
        "supplier_shipment_date": "",
        "stock_received_date":    "",
        "handover_date":          "",
        "handed_over_by":         "",
        "handed_over_to":         "",
        "feedback":               "",
        "purchased":              "",

        # ── Meta ──
        "stage":       "enquiry",
        "created_by":  st.session_state.get("email", ""),
        "created_at":  datetime.now().isoformat(),
        "updated_at":  datetime.now().isoformat(),
        "synced":      False,
    })
    load_pipeline_entries.clear()
    return doc_ref.id


# ─────────────────────────────────────────
# UPDATE — Advance stage
# ─────────────────────────────────────────
def update_pipeline_stage(doc_id: str, updates: dict, new_stage: str):
    """Update fields and advance stage."""
    db = get_db()
    updates["stage"]      = new_stage
    updates["updated_at"] = datetime.now().isoformat()
    updates["updated_by"] = st.session_state.get("email", "")
    updates["synced"]     = False
    db.collection("sample_pipeline").document(doc_id).update(updates)
    load_pipeline_entries.clear()


# ─────────────────────────────────────────
# READ
# ─────────────────────────────────────────
@st.cache_data(show_spinner=False, max_entries=200)
def load_pipeline_entries() -> pd.DataFrame:
    """Load all pipeline entries from Firestore."""
    try:
        db   = get_db()
        docs = db.collection("sample_pipeline").stream()
        records = []
        for doc in docs:
            d = doc.to_dict()
            d["_doc_id"] = doc.id
            records.append(d)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)

        # Parse dates
        date_cols = [
            "enquiry_date", "supplier_enquiry_date",
            "supplier_shipment_date", "stock_received_date", "handover_date"
        ]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # Add stage label
        df["stage_label"] = df["stage"].map(
            lambda s: STAGES.get(s, {}).get("label", s)
        )
        df["stage_icon"] = df["stage"].map(
            lambda s: STAGES.get(s, {}).get("icon", "")
        )

        # Days in current stage
        df["days_in_stage"] = (
            pd.Timestamp.now() - df["updated_at"].apply(
                lambda x: pd.to_datetime(x, errors="coerce")
            )
        ).dt.days.fillna(0).astype(int)

        return df

    except Exception as e:
        st.error(f"Failed to load pipeline: {e}")
        return pd.DataFrame()


def get_pipeline_entry(doc_id: str) -> dict:
    """Get single pipeline document."""
    db  = get_db()
    doc = db.collection("sample_pipeline").document(doc_id).get()
    if doc.exists:
        return {"_doc_id": doc.id, **doc.to_dict()}
    return {}


# ─────────────────────────────────────────
# NOTIFICATION CHECKS
# ─────────────────────────────────────────
ALERT_DAYS_MEDIUM = 7    # alert starts after this many days
ALERT_DAYS_HIGH   = 14   # escalates to high after this many days

# One rule per stage that can get "stuck". Stages not listed here
# (handed_over, legacy) never produce alerts.
# The special key "enquiry_in_stock" covers enquiries where the product is
# already in stock but hasn't been handed over yet.
ALERT_RULES = {
    "supplier_enquiry": {
        "type":       "supplier_no_response",
        "icon":       "📤",
        "date_field": "supplier_enquiry_date",
        "title":      "SUPPLIER NOT RESPONDING",
        "detail":     "ISSUE: {supplier} contacted {days} days ago",
    },
    "shipped": {
        "type":       "not_received",
        "icon":       "🚚",
        "date_field": "supplier_shipment_date",
        "title":      "STOCK NOT RECEIVED",
        "detail":     "ISSUE: {product} · Shipped {days} days ago",
    },
    "stock_received": {
        "type":       "not_handed_over",
        "icon":       "📦",
        "date_field": "stock_received_date",
        "title":      "STOCK RECEIVED, NOT HANDED OVER",
        "detail":     "ISSUE: {product} · Received {days} days ago",
    },
    "enquiry_in_stock": {
        "type":       "not_handed_over",
        "icon":       "📦",
        "date_field": "enquiry_date",
        "title":      "IN STOCK, NOT HANDED OVER",
        "detail":     "ISSUE: Product in Stock - Not Handed Over",
    },
}


def get_pipeline_alerts(df: pd.DataFrame) -> list:
    """
    Check pipeline entries against thresholds.
    Alerts are derived only from each entry's CURRENT stage in Firestore,
    so an entry that has moved on (or been handed over) never alerts.
    Returns list of alert dicts.
    """
    if df.empty:
        return []

    alerts = []
    today  = pd.Timestamp.now()

    for _, row in df.iterrows():
        stage    = row.get("stage", "")
        in_stock = row.get("in_stock", "")

        # In-stock rule applies ONLY while still at the enquiry stage.
        rule_key = "enquiry_in_stock" if (stage == "enquiry" and in_stock == "Yes") else stage
        rule = ALERT_RULES.get(rule_key)
        if not rule:
            continue

        start = row.get(rule["date_field"])
        if pd.isna(start):
            continue

        days = (today - start).days
        if days <= ALERT_DAYS_MEDIUM:
            continue

        customer = row.get("customer", "—")
        supplier = row.get("supplier", "—")
        product  = row.get("sample_product", "—")
        branch   = row.get("branch", "—")
        area     = row.get("area", "—")

        alerts.append({
            "type":        rule["type"],
            "icon":        rule["icon"],
            "severity":    "high" if days > ALERT_DAYS_HIGH else "medium",
            "title":       f"{rule['title']} — {customer} || {product}",
            "detail":      rule["detail"].format(supplier=supplier, product=product, days=days),
            "days":        days,
            "doc_id":      row.get("_doc_id", ""),
            "loc_details": f"Branch: {branch}, Area: {area}",
            "branch":      branch,
            "area":        area,
        })

    # Sort by severity then days
    severity_order = {"high": 0, "medium": 1}
    alerts.sort(key=lambda x: (severity_order.get(x["severity"], 2), -x["days"]))
    return alerts
