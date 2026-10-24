"""
Central Firestore operations for sample feedback management.
All feedback is stored under:
  sample_feedback/{customer}_{product}_{ho_date}/entries/{auto_id}
"""
import streamlit as st
from datetime import datetime
import pandas as pd
from auth.firebase_config import get_db


# ─────────────────────────────────────────
# KEY BUILDER
# ─────────────────────────────────────────
def build_sample_key(customer: str, product: str, ho_date) -> str:
    """Build a safe Firestore document ID from the 3 identifiers."""
    import re
    ho_str = str(ho_date)[:10] if ho_date else "unknown"
    raw    = f"{customer}_{product}_{ho_str}"
    # Replace chars not safe in Firestore doc IDs
    safe   = re.sub(r"[^a-zA-Z0-9_\-]", "_", raw)
    return safe[:490]  # Firestore doc ID limit is 500 chars


# ─────────────────────────────────────────
# FEEDBACK ENTRIES
# ─────────────────────────────────────────
def add_feedback(customer: str, product: str, ho_date,
                 feedback_text: str, feedback_date=None):
    """Add a new feedback entry for a sample."""
    db  = get_db()
    key = build_sample_key(customer, product, ho_date)
    fb_date = str(feedback_date) if feedback_date else datetime.now().strftime("%Y-%m-%d")

    db.collection("sample_feedback").document(key)\
      .collection("entries").add({
          "feedback":     feedback_text.strip(),
          "feedback_date": fb_date,
          "added_by":     st.session_state.get("email", ""),
          "added_at":     datetime.now().isoformat(),
      })

    # Also update parent doc metadata for quick querying
    db.collection("sample_feedback").document(key).set({
        "customer":  customer,
        "product":   product,
        "ho_date":   str(ho_date)[:10],
        "last_updated": datetime.now().isoformat(),
    }, merge=True)

    # Clear cache
    load_feedback_for_sample.clear()
    load_all_latest_feedback.clear()
    sync_latest_feedback_to_sheet(customer, product, ho_date)




def add_feedback_with_status(customer: str, product: str, ho_date,
                              feedback_text: str, feedback_date=None,
                              fb_status: str = "Pending",  purchased="Purchase Data Not Available"):
    """Add feedback with explicit user-provided classification."""
    db  = get_db()
    key = build_sample_key(customer, product, ho_date)
    fb_date = str(feedback_date) if feedback_date else datetime.now().strftime("%Y-%m-%d")

    db.collection("sample_feedback").document(key)      .collection("entries").add({
          "feedback":      feedback_text.strip(),
          "feedback_date": fb_date,
          "fb_status":     fb_status,   # ← user-provided classification
          "purchased":     purchased, 
          "added_by":      st.session_state.get("email", ""),
          "added_at":      datetime.now().isoformat(),
      })

    db.collection("sample_feedback").document(key).set({
        "customer":     customer,
        "product":      product,
        "ho_date":      str(ho_date)[:10],
        "last_updated": datetime.now().isoformat(),
    }, merge=True)

    load_feedback_for_sample.clear()
    load_all_latest_feedback.clear()
    # ← sync latest to sheet
    sync_latest_feedback_to_sheet(customer, product, ho_date)


def _normalized_date(value) -> str:
    """Normalize an individual date value to ISO without column inference."""
    if value is None or str(value).strip() in ("", "nan", "None"):
        return ""
    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    return "" if pd.isna(parsed) else parsed.date().isoformat()


def _feedback_order(entry: dict):
    """Sort by feedback date, breaking same-day ties by latest edit/add time."""
    return (
        _normalized_date(entry.get("feedback_date")),
        str(entry.get("edited_at") or entry.get("added_at") or ""),
    )


def sync_latest_feedback_to_sheet(customer: str, product: str, ho_date) -> bool:
    """Write the latest Firestore feedback to every matching Sheet1 row."""
    try:
        from auth.gspread_config import get_samples_sheet
        import gspread

        db = get_db()
        key = build_sample_key(customer, product, ho_date)
        docs = (db.collection("sample_feedback").document(key)
                  .collection("entries").stream())
        entries = [{"id": doc.id, **doc.to_dict()} for doc in docs]
        entries.sort(key=_feedback_order)
        latest = entries[-1] if entries else {}
        latest_text = str(latest.get("feedback", "") or "").strip()

        ws = get_samples_sheet()
        all_data = ws.get_all_values()
        if not all_data:
            raise RuntimeError("The main sheet is empty; its header row is missing.")

        headers = [h.strip().casefold() for h in all_data[0]]
        try:
            cust_col = headers.index("name of customer / party")
            prod_col = headers.index("product name")
            date_col = headers.index("hand over to customer date")
            fb_col = headers.index("feedback")
        except ValueError as exc:
            raise RuntimeError(
                "The main sheet is missing a required customer, product, "
                "handover date, or Feedback header."
            ) from exc

        purchased_col = headers.index("purchased?") if "purchased?" in headers else None
        target_date = _normalized_date(ho_date)
        target_customer = " ".join(str(customer).split()).casefold()
        target_product = " ".join(str(product).split()).casefold()
        updates = []

        for row_num, row in enumerate(all_data[1:], start=2):
            row_customer = " ".join(
                (str(row[cust_col]) if len(row) > cust_col else "").split()
            ).casefold()
            row_product = " ".join(
                (str(row[prod_col]) if len(row) > prod_col else "").split()
            ).casefold()
            row_date = _normalized_date(row[date_col] if len(row) > date_col else "")

            if (row_customer == target_customer and row_product == target_product
                    and row_date == target_date):
                feedback_cell = gspread.utils.rowcol_to_a1(row_num, fb_col + 1)
                updates.append({"range": feedback_cell, "values": [[latest_text]]})

                if purchased_col is not None and "purchased" in latest:
                    purchased_cell = gspread.utils.rowcol_to_a1(row_num, purchased_col + 1)
                    updates.append({
                        "range": purchased_cell,
                        "values": [[latest.get("purchased", "")]],
                    })

        if not updates:
            raise RuntimeError(
                f"No main-sheet row matched {customer} / {product} / {target_date}."
            )

        ws.batch_update(updates, value_input_option="RAW")

        from samples_new.sample_constants import load_sample_data
        load_sample_data.clear()
        st.session_state.pop("feedback_sheet_sync_error", None)
        return True

    except Exception as exc:
        print(f"[sync_latest_feedback_to_sheet] {exc}")
        st.session_state["feedback_sheet_sync_error"] = str(exc)
        return False

def delete_feedback(customer: str, product: str, ho_date, entry_id: str):
    """Delete a specific feedback entry."""
    db  = get_db()
    key = build_sample_key(customer, product, ho_date)
    db.collection("sample_feedback").document(key)\
      .collection("entries").document(entry_id).delete()

    load_feedback_for_sample.clear()
    load_all_latest_feedback.clear()
    sync_latest_feedback_to_sheet(customer, product, ho_date)


@st.cache_data(ttl=120, show_spinner=False)
def load_feedback_for_sample(customer: str, product: str, ho_date) -> list:
    """
    Load all feedback entries for a specific sample.
    Returns list of dicts sorted by feedback_date ascending.
    """
    try:
        db  = get_db()
        key = build_sample_key(customer, product, ho_date)
        docs = (db.collection("sample_feedback").document(key)
                  .collection("entries").stream())
        entries = [{"id": d.id, **d.to_dict()} for d in docs]
        entries.sort(key=_feedback_order)
        return entries
    except Exception:
        return []


@st.cache_data(ttl=1200, show_spinner=False)
def load_all_latest_feedback() -> dict:
    try:
        db = get_db()

        # Query 1: one pass over parent docs → doc_id -> (customer, product, ho_date)
        parent_docs = db.collection("sample_feedback").stream()
        id_to_key = {}
        for doc in parent_docs:
            d = doc.to_dict()
            id_to_key[doc.id] = (
                str(d.get("customer", "")).strip(),
                str(d.get("product",  "")).strip(),
                str(d.get("ho_date",  ""))[:10],
            )

        # Query 2: every entry, across every sample, in ONE shot
        all_entries = db.collection_group("entries").stream()
        grouped: dict = {}
        for entry_doc in all_entries:
            parent_id = entry_doc.reference.parent.parent.id
            if parent_id not in id_to_key:
                continue  # orphaned entry — parent doc missing/deleted
            grouped.setdefault(parent_id, []).append(entry_doc.to_dict())

        result = {}
        for parent_id, entries in grouped.items():
            if not entries:
                continue
            entries.sort(key=_feedback_order)
            result[id_to_key[parent_id]] = entries[-1]  # most recent
        return result
    except Exception:
        return {}

def _normalize_feedback_status(fb_status: str = None):
    if fb_status is None:
        return None
    status = str(fb_status).strip().casefold()
    return {
        "positive": "Positive",
        "negative": "Negative",
        "pending": "Pending",
        "hold": "Hold",
    }.get(status)


def classify_feedback(text: str, fb_status: str = None) -> str:
    """
    If fb_status explicitly provided (user-classified), use it directly.
    Otherwise fall back to keyword matching. Supports: Positive, Negative, Pending, Hold
    """
    normalized_status = _normalize_feedback_status(fb_status)
    if normalized_status:
        return normalized_status
    if not text or str(text).strip() in ("","nan","None","-","_"):
        return "Pending"
    v = str(text).lower()
    pos  = ["good","positive","is interested","approved","accepted",
            "excellent","great","liked","satisfied","happy",
            "ok","fine","proceed","confirmed","yes", "are interested"]
    
    neg  = ["reject","negative","not interested","declined",
            "no","bad","poor","failed","not suitable","cancelled"]
    
    hold = ["hold","on hold","wait","waiting","defer","later","pause"]

    if any(k in v for k in pos):  return "Positive"
    if any(k in v for k in neg):  return "Negative"
    if any(k in v for k in hold): return "Hold"
    return "Pending"

def get_urgency(days: int, has_feedback: bool, fb_status: str = None, feedback_text: str = "") -> str:
    fb_status = _normalize_feedback_status(fb_status)
    if fb_status == "Hold":
        return "Hold"
    if fb_status == "Positive":
        return "Responded"
    if fb_status == "Negative":
        return "Responded"
    if fb_status == "Pending":
        if days <= 6:  return "Freshly Handed"
        if days <= 14: return "Initial Follow-up"
        if days <= 20: return "Push Required"
        return "Critical"
    # fb_status is None — sheet feedback, classify via keywords
    if has_feedback:
        kw_status = classify_feedback(feedback_text, None)  # keyword only
        if kw_status == "Positive": return "Responded"
        if kw_status == "Negative": return "Responded"
        # Keyword said Pending or couldn't classify → urgency by days
        if days <= 6:  return "Freshly Handed"
        if days <= 14: return "Initial Follow-up"
        if days <= 20: return "Push Required"
        return "Critical"
    # No feedback at all
    if days <= 6:  return "Freshly Handed"
    if days <= 14: return "Initial Follow-up"
    if days <= 20: return "Push Required"
    return "Critical"

# ─────────────────────────────────────────
# ADMIN HELPERS
# ─────────────────────────────────────────
def is_admin() -> bool:
    """Check if the current logged-in user is the admin."""
    user_email  = st.session_state.get("email", "")
    admin_email = st.secrets.get("admin", {}).get("ADMIN_EMAIL", "")
    return bool(user_email) and \
           user_email.strip().lower() == admin_email.strip().lower()


def delete_entire_card(customer: str, product: str, ho_date: str):
    """
    Admin-only: completely remove a sample card.

    1. Delete all feedback entries subcollection from Firestore
    2. Delete the parent sample_feedback document
    3. Delete the matching row from Sheet1

    PipelineData is NOT touched — by the time a card appears in
    Detailed Info it has already been moved out of PipelineData.
    """
    db  = get_db()
    key = build_sample_key(customer, product, ho_date)

    # ── 1. Delete all entries in the subcollection ──
    entries_ref = db.collection("sample_feedback").document(key)\
                    .collection("entries")
    for entry_doc in entries_ref.stream():
        entry_doc.reference.delete()

    # ── 2. Delete the parent document ──
    db.collection("sample_feedback").document(key).delete()

    # ── 3. Delete the row from Sheet1 ──
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        SCOPE = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds    = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPE
        )
        client   = gspread.authorize(creds)
        sheet_id = st.secrets["spreadsheets"]["samples"]
        ws       = client.open_by_key(sheet_id).sheet1
        all_data = ws.get_all_values()
        headers  = [h.strip() for h in all_data[0]]

        try:
            cust_col = headers.index("Name of Customer / Party")
            prod_col = headers.index("Product Name")
            date_col = headers.index("Hand over to customer date")
        except ValueError as e:
            print(f"[delete_entire_card] Missing header: {e}")
            return

        target_date = str(ho_date)[:10]

        for i, row in enumerate(all_data[1:], start=2):
            row_cust = str(row[cust_col]).strip().lower() if len(row) > cust_col else ""
            row_prod = str(row[prod_col]).strip().lower() if len(row) > prod_col else ""
            row_date = str(row[date_col]).strip()[:10]   if len(row) > date_col else ""

            try:
                row_date = str(pd.to_datetime(row_date, dayfirst=True).date())
            except Exception:
                pass

            if (row_cust == customer.strip().lower() and
                row_prod == product.strip().lower() and
                row_date == target_date):
                ws.delete_rows(i)
                print(f"[delete_entire_card] Deleted Sheet1 row {i} "
                      f"for {customer} / {product} / {target_date}")
                break

    except Exception as e:
        import traceback
        print(f"[delete_entire_card] Sheet deletion error: {e}")
        traceback.print_exc()

    # ── 4. Clear caches ──
    load_feedback_for_sample.clear()
    load_all_latest_feedback.clear()
