import streamlit as st
from auth.firebase_config import get_db
from datetime import datetime

from google.cloud.firestore_v1.base_query import FieldFilter


# ─────────────────────────────────────────
# FIRESTORE HELPERS
# ─────────────────────────────────────────

@st.cache_data(show_spinner=False, max_entries=250)
def load_customers():
    """
    Load all customers from Firestore.
    Returns list of dicts with branch, area, name, industry.
    Cached for 5 minutes.
    """
    try:
        db   = get_db()
        docs = db.collection("customers").order_by("name").stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]
    except Exception as e:
        st.error(f"Failed to load customers: {e}")
        return []


def add_customer(branch, area, name, industry):
    """Add a new customer to Firestore."""
    db = get_db()

    # Check duplicate
    existing = db.collection("customers")\
                 .where(filter=FieldFilter("name", "==", name.strip()))\
                 .where(filter=FieldFilter("branch", "==", branch))\
                 .get()
    if existing:
        return False, f"Customer '{name}' already exists under {branch}."

    db.collection("customers").add({
        "branch":     branch,
        "area":       area.strip(),
        "name":       name.strip(),
        "industry":   industry.strip(),
        "created_at": datetime.now().isoformat(),
    })

    # Clear cache so dropdowns refresh
    load_customers.clear()
    return True, f"Customer '{name}' added successfully!"


def update_customer(doc_id, branch, area, name, industry):
    """Update an existing customer."""
    db = get_db()
    db.collection("customers").document(doc_id).update({
        "branch":     branch,
        "area":       area.strip(),
        "name":       name.strip(),
        "industry":   industry.strip(),
        "updated_at": datetime.now().isoformat(),
    })
    load_customers.clear()
    return True, "Customer updated!"


def delete_customer(doc_id, name):
    """Delete a customer."""
    db = get_db()
    db.collection("customers").document(doc_id).delete()
    load_customers.clear()
    return True, f"Customer '{name}' deleted."


# ─────────────────────────────────────────
# DRILL-DOWN HELPERS (used in entry_form)
# ─────────────────────────────────────────

def get_branches(customers):
    return sorted(set(c["branch"] for c in customers if c.get("branch")))


def get_areas(customers, branch):
    return sorted(set(
        c["area"] for c in customers
        if c.get("branch") == branch and c.get("area")
    ))


def get_customer_names(customers, branch, area):
    return sorted(
        c["name"] for c in customers
        if c.get("branch") == branch and c.get("area") == area and c.get("name")
    )


def get_industry(customers, name):
    for c in customers:
        if c.get("name") == name:
            return c.get("industry", "")
    return ""


# ─────────────────────────────────────────
# MANAGE CUSTOMERS PAGE
# ─────────────────────────────────────────

BRANCH_OPTIONS = ["KOTTAYAM", "COIMBATORE", "THRISSUR", "CHANGANACHERRY", "MUMBAI", "KOZHIKODE"]

