import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from sample_pipeline.sample_pipeline_firestore import load_pipeline_entries, PIPELINE_SHEET_COLS

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def fmt(val):
    """
    Normalizes any value for writing to Sheet1. For dates specifically:
    converts to DD-MM-YYYY, matching the format the rest of Sheet1's
    legacy rows already use. This matters because pd.to_datetime(...,
    dayfirst=True) on the READ side infers ONE format for the whole
    column based on the data present — if new rows are written in a
    different format (e.g. plain YYYY-MM-DD strings from
    pipeline_tracker.py's str(date_obj)) than the legacy rows, those
    new rows silently parse as NaT even though the value looks fine on
    its own. Keeping every row in the same format avoids this.
    """
    if val is None or (hasattr(val, '__class__') and val.__class__.__name__ == 'NaTType'):
        return ""
    try:
        import pandas as pd
        if pd.isna(val):
            return ""
    except:
        pass
    if hasattr(val, 'strftime'):
        return val.strftime("%d-%m-%Y")

    s = str(val).strip()
    # Plain 'YYYY-MM-DD' string (e.g. from str(date_obj)) — reformat to
    # DD-MM-YYYY so it matches the rest of the column.
    try:
        import re
        import pandas as pd
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return pd.to_datetime(s, format="%Y-%m-%d").strftime("%d-%m-%Y")
    except Exception:
        pass
    return s


def move_to_main_sheet(doc: dict):
    """
    When pipeline entry reaches handed_over,
    append it to Sheet1 (main sheet) and delete from Sheet2.

    Row is built by HEADER NAME lookup against the live sheet, not a
    fixed position list — Sheet1's column count/order has changed before
    (e.g. 'Our Sample Product Name' added alongside 'Product Name') and
    a positional list silently shifts every value after the insertion
    point, which is what caused the date columns to read as None.
    """
    print(f"[move_to_main_sheet] CALLED with doc._doc_id={doc.get('_doc_id')}")
    try:
        from auth.gspread_config import get_samples_spreadsheet
 
        spreadsheet = get_samples_spreadsheet()

        # ── Append to Sheet1 ──
        ws1     = spreadsheet.sheet1
        headers = [h.strip() for h in ws1.row_values(1)]
        print(f"[move_to_main_sheet] Sheet1 headers: {headers}")
        print(f"[move_to_main_sheet] doc keys/values: { {k: v for k, v in doc.items()} }")

        # Map: exact Sheet1 header name -> value from the pipeline doc.
        # "Our Sample Product Name" intentionally left out (and so blank)
        # pipeline docs only track one product field.
        field_by_header = {
            "Branch":                              fmt(doc.get("branch", "")),
            "Area":                                 fmt(doc.get("area", "")),
            "Enquiry sent to Principal date":       fmt(doc.get("enquiry_date", "")),
            "Hand over to customer date":           fmt(doc.get("handover_date", "")),
            "Name of Customer / Party":             fmt(doc.get("customer", "")),
            "Contact Person at Customer / Party":   fmt(doc.get("contact", "")),
            "Product Mfgd. By Customer / Party":    fmt(doc.get("customer_product", "")),
            "Product Name":                         fmt(doc.get("sample_product", "")),
            "Supplier Name":                        fmt(doc.get("supplier", "")),
            "Sample Quantity":                      fmt(doc.get("standard_qty", "")),
            "Sample Unit":                          fmt(doc.get("standard_unit", "")),
            "Handed over By":                       fmt(doc.get("handed_over_by", "")),
            "Handed over To":                       fmt(doc.get("handed_over_to", "")),
            "Feedback":                             fmt(doc.get("feedback", "")),
            "Purchased?":                           fmt(doc.get("purchased", "")),
        }
        print(f"[move_to_main_sheet] field_by_header: {field_by_header}")

        row = [field_by_header.get(h, "") for h in headers]
        print(f"[move_to_main_sheet] FINAL ROW being appended: {row}")
        ws1.append_row(row, value_input_option="RAW")
        print(f"[move_to_main_sheet] append_row SUCCESS")

        # ── Remove from Sheet2 if exists ──

        # ── Clear caches ──
        from samples_new.sample_constants import load_sample_data
        load_sample_data.clear()
        load_pipeline_entries.clear()

    except Exception as e:
        import traceback
        print(f"[move_to_main_sheet] EXCEPTION: {e}")
        traceback.print_exc()
        raise e
    

    
def ensure_pipeline_headers(ws):
    first = ws.row_values(1)
    if not first or first[0] != "Branch":
        ws.insert_row(PIPELINE_SHEET_COLS, index =1)

def build_sheet_row(d:dict) -> list:
    return [
        fmt(d.get("branch", "")),
        fmt(d.get("area", "")),
        fmt(d.get("customer", "")),
        fmt(d.get("contact", "")),
        fmt(d.get("customer_product", "")),
        fmt(d.get("sample_product", "")),
        fmt(d.get("supplier", "")),
        fmt(d.get("standard_qty", "")),
        fmt(d.get("standard_unit", "")),
        fmt(d.get("handed_over_by", "")),
        fmt(d.get("handed_over_to", "")),
        fmt(d.get("enquiry_date", "")),
        fmt(d.get("in_stock", "")),
        fmt(d.get("supplier_enquiry_date", "")),
        fmt(d.get("supplier_shipment_date", "")),
        fmt(d.get("stock_received_date", "")),
        fmt(d.get("handover_date", "")),
        fmt(d.get("feedback", "")),
        fmt(d.get("purchased", "")),
        fmt(d.get("stage", "")),
        fmt(d.get("_doc_id", "")),
    ]

def sync_pipeline_to_sheet():
    from auth.firebase_config import get_db
    db = get_db()
    unsynced = list(
        db.collection("sample_pipeline")
        .where("synced", "==",  False)
        .stream()
    )
    if not unsynced:
        return 0, 0
    
    try:
        from auth.gspread_config import get_pipeline_sheet
        ws = get_pipeline_sheet()
        ensure_pipeline_headers(ws)
        all_data = ws.get_all_values()
        # Build index od doc id -> row number
        doc_id_col = PIPELINE_SHEET_COLS.index("Pipeline Doc ID")
        existing = {}
        for i, row in enumerate(all_data[1:], start=2):
            if len(row)>doc_id_col and row[doc_id_col]:
                existing[row[doc_id_col]] = i
        
        synced = 0
        errors = 0

        for doc in unsynced:
            try:
                d = doc.to_dict()
                d["_doc_id"] = doc.id
                new_row = build_sheet_row(d)

                if doc.id in existing:
                    # Update existing rows in place
                    row_num = existing[doc.id]
                    col_end = gspread.utils.rowcol_to_a1(row_num, len(PIPELINE_SHEET_COLS))
                    col_start = gspread.utils.rowcol_to_a1(row_num, 1)
                    ws.update(f"{col_start}:{col_end}", [new_row])
                else:
                    # Append new roww
                    ws.append_row(new_row, value_input_option="RAW")

                db.collection("sample_pipeline").document(doc.id).update({
                    "synced": True,
                    "synced_at": datetime.now().isoformat()
                })

                synced +=1
            except Exception as e:
                errors +=1
                continue

        load_pipeline_entries.clear()
        return synced, errors
    
    except Exception as e:
        return 0, len(unsynced)
    

def admin_sync_pipeline():
    """
    UI Version with spinner and feedback
    """
    with st.spinner("Syncing pipeline to Google Sheets..."):
        synced, errors = sync_pipeline_to_sheet()
        if synced==0 and errors == 0:
            st.info("✅ Everything already synced!")
        elif errors == 0:
            st.success(f"✅ {synced} pipeline entries synced!")
        else:
            st.warning(f"⚠️{synced} synced, {errors} failed.")

def silent_pipeline_sync():
    try:
        sync_pipeline_to_sheet()
    except:
        pass