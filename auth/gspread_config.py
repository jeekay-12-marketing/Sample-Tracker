"""
Shared gspread client — authorize ONCE per Streamlit server process and
reuse everywhere, instead of every file (sample_firestore, sample_dashboard,
sample_entry, sample_pipeline_sync, sample_constants) doing its own fresh
Credentials.from_service_account_info() + gspread.authorize() on every
single sheet read/write.

@st.cache_resource caches the object itself (not serialized like
@st.cache_data would), and persists across reruns AND across different
users' sessions on the same server — appropriate here since a gspread
Client is a stateless API wrapper, not per-user data.
"""
import streamlit as st

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


@st.cache_resource(show_spinner=False)
def get_gspread_client():
    """Authorize gspread once per server process. All files that touch
    Google Sheets should import and call this instead of re-authenticating
    inline."""
    import gspread
    from google.oauth2.service_account import Credentials

    try:
        creds_dict = st.secrets["gcp_service_account"]
    except Exception:
        import os, json
        creds_dict = json.loads(os.environ["GCP_SERVICE_ACCOUNT"])

    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def get_samples_spreadsheet():
    """The 'samples' Spreadsheet object itself — cached separately from any
    one worksheet, for callers (like move_to_main_sheet) that need more than
    one worksheet out of the same spreadsheet (e.g. both Sheet1 and
    PipelineData). A Worksheet object doesn't have .sheet1 / .worksheet() —
    those are Spreadsheet methods — so anything needing multiple sheets
    should start here, not from get_samples_sheet()/get_pipeline_sheet()."""
    client   = get_gspread_client()
    sheet_id = st.secrets["spreadsheets"]["samples"]
    return client.open_by_key(sheet_id)


@st.cache_resource(show_spinner=False)
def get_samples_sheet():
    """Convenience wrapper: the 'samples' spreadsheet's Sheet1, cached
    alongside the client itself (same worksheet object reused everywhere)."""
    return get_samples_spreadsheet().sheet1


@st.cache_resource(show_spinner=False)
def get_pipeline_sheet():
    """Convenience wrapper: the 'PipelineData' worksheet inside the same
    'samples' spreadsheet, created on first access if it doesn't exist yet.
    Cached like get_samples_sheet() — the worksheet lookup/create-check only
    runs once per server process instead of on every call."""
    spreadsheet = get_samples_spreadsheet()
    try:
        ws = spreadsheet.worksheet("PipelineData")
    except Exception:
        ws = spreadsheet.add_worksheet(title="PipelineData", rows=5000, cols=25)
    return ws