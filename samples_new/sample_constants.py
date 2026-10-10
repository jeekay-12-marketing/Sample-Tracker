"""
Shared constants, CSS, chart helpers and data loader
used across all sample pages.
"""
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ─────────────────────────────────────────
# COLUMN NAMES
# ─────────────────────────────────────────
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

COL_BRANCH      = "Branch"
COL_AREA        = "Area"
COL_ENQ_DATE    = "Enquiry sent to Principal date"
COL_HO_DATE     = "Hand over to customer date"
COL_CUSTOMER    = "Name of Customer / Party"
COL_CONTACT     = "Contact Person at Customer / Party"
COL_CUST_PROD   = "Product Mfgd. By Customer / Party"
COL_SAMPLE_PROD = "Product Name"
COL_SUPPLIER = "Supplier Name"
COL_QTY         = "Sample Quantity"
COL_HO_BY       = "Handed over By"
COL_HO_TO       = "Handed over To"
COL_FEEDBACK    = "Feedback"
COL_PURCHASED = "Purchased?"



ALL_COLS = [
    COL_BRANCH, COL_AREA, COL_ENQ_DATE, COL_HO_DATE,
    COL_CUSTOMER, COL_CONTACT, COL_CUST_PROD,
    COL_SAMPLE_PROD, COL_QTY, COL_HO_BY, COL_HO_TO, COL_FEEDBACK,
    COL_SUPPLIER, COL_PURCHASED
]

CHART_COLORS = ["#1B2A4A","#C9A84C","#5A6A85","#E8C96A",
                "#8A9BBB","#2E7D32","#B71C1C","#E65100"]

# ─────────────────────────────────────────
# DATA LOADER
# ─────────────────────────────────────────



@st.cache_data(ttl=1800, show_spinner=False)
def load_sample_data() -> pd.DataFrame:
    try:
        from auth.gspread_config import get_samples_sheet 
        ws        = get_samples_sheet()
        records  = ws.get_all_records()
        if not records:
            return pd.DataFrame(columns=ALL_COLS)
        df = pd.DataFrame(records)
        df.columns = df.columns.str.strip()
        for col in [COL_ENQ_DATE, COL_HO_DATE]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
        for col in [COL_BRANCH, COL_AREA, COL_CUSTOMER,
                    COL_SAMPLE_PROD, COL_HO_BY, COL_HO_TO, COL_FEEDBACK]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.title()
                df[col] = df[col].replace(["nan","None",""], pd.NA)
        return df
    except Exception as e:
        import traceback
        print(f"[load_sample_data] EXCEPTION: {e}")
        traceback.print_exc()
        st.error(f"Failed to load sample data: {e}")
        return pd.DataFrame(columns=ALL_COLS)




# ─────────────────────────────────────────
# CHART LAYOUT
# ─────────────────────────────────────────
def chart_layout(fig, height=340):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(250,247,242,1)",
        font=dict(family="Outfit", color="#6B7A99", size=11),
        margin=dict(l=10, r=10, t=30, b=10),
        height=height,
        xaxis=dict(gridcolor="#DDD5C5", linecolor="#DDD5C5"),
        yaxis=dict(gridcolor="#DDD5C5", linecolor="#DDD5C5"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    )
    return fig


# ─────────────────────────────────────────
# BADGE HELPERS
# ─────────────────────────────────────────
def urgency_badge(urgency: str) -> str:
    cfg = {
        "Freshly Handed":    ("badge-fresh",   "🟢"),
        "Initial Follow-up": ("badge-initial", "🟡"),
        "Push Required":     ("badge-push",    "🟠"),
        "Hold":              ("badge-hold", "⏸"),
        "Critical":          ("badge-critical","🔴"),
        "Responded":         ("badge-responded","✅"),
    }
    cls, icon = cfg.get(urgency, ("badge-fresh",""))
    return f'<span class="{cls}">{icon} {urgency}</span>'


def feedback_badge(status: str) -> str:
    cfg = {
        "Positive": ("badge-positive","👍"),
        "Negative": ("badge-negative","👎"),
        "Pending":  ("badge-pending", "⏳"),
        "Hold": ("badge-hold", "⏸"),
    }
    cls, icon = cfg.get(status, ("badge-pending","⏳"))
    return f'<span class="{cls}">{icon} {status}</span>'


# ─────────────────────────────────────────
# SHARED CSS
# ─────────────────────────────────────────
SAMPLE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=Outfit:wght@300;400;500;600;700&display=swap');

:root {
    --navy:      #1B2A4A;
    --gold:      #C9A84C;
    --gold-lt:   #E8C96A;
    --cream:     #FAF7F2;
    --warm-gray: #F0EBE1;
    --border:    #DDD5C5;
    --muted:     #6B7A99;
    --green:     #2E7D32;
    --red:       #B71C1C;
    --amber:     #E65100;
}

[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main {
    background-color: var(--cream) !important;
}
[data-testid="stHeader"] { background-color: var(--cream) !important; }

section[data-testid="stSidebar"] {
    background: var(--navy) !important;
    border-right: 3px solid var(--gold) !important;
}
section[data-testid="stSidebar"] * {
    color: #E8E4DC !important;
    font-family: 'Outfit', sans-serif !important;

}

/* ── Sidebar filter labels ── */
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    color: #C9A84C !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
}

section[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    color: #E8C97A !important;
    border: 1px solid var(--gold) !important;
    border-radius: 8px !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    margin-bottom: 4px !important;
    transition: all 0.2s ease !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(201,168,76,0.15) !important;
    color: #FFFFFF !important;
}

/* ── Sidebar selectbox text ── */
section[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(201,168,76,0.4) !important;
    color: #FFFFFF !important;
}

section[data-testid="stSidebar"] [data-testid="stSelectbox"] span {
    color: #FFFFFF !important;
}

@keyframes pulse-red {
    0%   { box-shadow: 0 0 0 0 rgba(183,28,28,0.5); }
    70%  { box-shadow: 0 0 0 8px rgba(183,28,28,0); }
    100% { box-shadow: 0 0 0 0 rgba(183,28,28,0); }
}
@keyframes pulse-orange {
    0%   { box-shadow: 0 0 0 0 rgba(230,81,0,0.45); }
    70%  { box-shadow: 0 0 0 8px rgba(230,81,0,0); }
    100% { box-shadow: 0 0 0 0 rgba(230,81,0,0); }
}

.badge-critical {
    display:inline-flex;align-items:center;gap:5px;
    background:#FFEBEE;border:1.5px solid #EF9A9A;color:#B71C1C;
    border-radius:20px;padding:4px 12px;font-size:0.89rem;
    font-weight:700;font-family:'Outfit',sans-serif;
    animation:pulse-red 1.4s infinite;letter-spacing:0.04em;
}
.badge-push {
    display:inline-flex;align-items:center;gap:5px;
    background:#FFF3E0;border:1.5px solid #FFAB40;color:#E65100;
    border-radius:20px;padding:4px 12px;font-size:0.89rem;
    font-weight:700;font-family:'Outfit',sans-serif;
    animation:pulse-orange 1.8s infinite;letter-spacing:0.04em;
}
.badge-initial {
    display:inline-flex;align-items:center;gap:5px;
    background:#FFF8E1;border:1.5px solid #FFD54F;color:#F57F17;
    border-radius:20px;padding:4px 12px;font-size:0.89rem;
    font-weight:700;font-family:'Outfit',sans-serif;
}
.badge-fresh {
    display:inline-flex;align-items:center;gap:5px;
    background:#E8F5E9;border:1.5px solid #A5D6A7;color:#2E7D32;
    border-radius:20px;padding:4px 12px;font-size:0.89rem;
    font-weight:700;font-family:'Outfit',sans-serif;
}
.badge-responded {
    display:inline-flex;align-items:center;gap:5px;
    background:#E3F2FD;border:1.5px solid #90CAF9;color:#1565C0;
    border-radius:20px;padding:4px 12px;font-size:0.89rem;
    font-weight:700;font-family:'Outfit',sans-serif;
}
.badge-positive {
    display:inline-flex;align-items:center;gap:4px;
    background:#E8F5E9;border:1px solid #A5D6A7;color:#2E7D32;
    border-radius:20px;padding:3px 10px;font-size:0.89rem;
    font-weight:600;font-family:'Outfit',sans-serif;
}
.badge-negative {
    display:inline-flex;align-items:center;gap:4px;
    background:#FFEBEE;border:1px solid #EF9A9A;color:#B71C1C;
    border-radius:20px;padding:3px 10px;font-size:0.89rem;
    font-weight:600;font-family:'Outfit',sans-serif;
}
.badge-pending {
    display:inline-flex;align-items:center;gap:4px;
    background:#FFF8E1;border:1px solid #FFD54F;color:#F57F17;
    border-radius:20px;padding:3px 10px;font-size:0.89rem;
    font-weight:600;font-family:'Outfit',sans-serif;
}

.badge-hold {
    display:inline-flex;align-items:center;gap:4px;
    background:#EDE7F6;border:1px solid #B39DDB;color:#4527A0;
    border-radius:20px;padding:3px 10px;font-size:0.89rem;
    font-weight:600;font-family:'Outfit',sans-serif;
}

.sd-hero { padding:1.5rem 0 1rem 0; margin-bottom:1rem; }
.sd-eyebrow {
    font-family:'Outfit',sans-serif;font-size:0.72rem;font-weight:600;
    letter-spacing:0.22em;text-transform:uppercase;
    color:var(--gold);margin-bottom:0.4rem;
}
.sd-title {
    font-family:'Cormorant Garamond',serif;font-size:2.8rem;
    font-weight:700;color:var(--navy);line-height:1.1;margin-bottom:0.3rem;
}
.sd-title em { color:var(--gold);font-style:italic; }
.sd-sub {
    font-family:'Outfit',sans-serif;font-size:0.95rem;
    color:var(--muted);font-weight:400;
}
.sd-divider {
    width:60px;height:3px;
    background:linear-gradient(90deg,var(--gold),var(--gold-lt));
    border-radius:2px;margin:0.8rem 0 1.5rem 0;
}
.sd-section {
    font-family:'Cormorant Garamond',serif;font-size:1.5rem;font-weight:700;
    color:var(--navy);border-bottom:2px solid var(--border);
    padding-bottom:8px;margin:2.5rem 0 1.2rem 0;position:relative;
}
.sd-section::after {
    content:'';position:absolute;bottom:-2px;left:0;
    width:45px;height:2px;background:var(--gold);
}

.kpi-card {
    background:#FFFFFF;border:1.5px solid var(--border);border-radius:14px;
    padding:1.4rem 1.6rem;position:relative;overflow:hidden;
    box-shadow:0 2px 10px rgba(27,42,74,0.06);
    transition:transform 0.15s ease,box-shadow 0.15s ease;height:100%;
}
.kpi-card:hover { transform:translateY(-2px);box-shadow:0 6px 24px rgba(27,42,74,0.1); }
.kpi-card::before {
    content:'';position:absolute;top:0;left:0;right:0;height:3px;
    background:linear-gradient(90deg,var(--gold),var(--gold-lt));
}
.kpi-card.green::before { background:linear-gradient(90deg,#2E7D32,#4CAF50); }
.kpi-card.amber::before { background:linear-gradient(90deg,#E65100,#FF9800); }
.kpi-card.red::before   { background:linear-gradient(90deg,#B71C1C,#EF5350); }
.kpi-card.blue::before  { background:linear-gradient(90deg,#1565C0,#42A5F5); }
.kpi-label {
    font-family:'Outfit',sans-serif;font-size:0.7rem;font-weight:700;
    letter-spacing:0.14em;text-transform:uppercase;
    color:var(--muted);margin-bottom:0.5rem;
}
.kpi-value {
    font-family:'Cormorant Garamond',serif;font-size:2.6rem;
    font-weight:700;color:var(--navy);line-height:1;margin-bottom:0.2rem;
}
.kpi-value.green { color:var(--green); }
.kpi-value.amber { color:var(--amber); }
.kpi-value.red   { color:var(--red); }
.kpi-value.blue  { color:#1565C0; }
.kpi-sub { font-family:'Outfit',sans-serif;font-size:0.75rem;color:var(--muted); }

/* Sample detail card */
.sample-card {
    background:#FFFFFF;border:1.5px solid var(--border);
    border-radius:14px;padding:1.4rem 1.8rem;margin-bottom:1.2rem;
    box-shadow:0 2px 10px rgba(27,42,74,0.06);position:relative;overflow:hidden;
}
.sample-card::before {
    content:'';position:absolute;top:0;left:0;right:0;height:3px;
    background:linear-gradient(90deg,var(--gold),var(--gold-lt));
}
.sample-card-title {
    font-family:'Cormorant Garamond',serif;font-size:1.5rem;font-weight:700;
    color:var(--navy);margin-bottom:4px;text-transform:uppercase;
}
.sample-card-product {
    font-family:'Outfit',sans-serif;font-size:1.15rem;
    color:var(--gold);font-weight:600;margin-bottom:0.8rem;
}
.sample-card-meta {
    font-family:'Outfit',sans-serif;font-size:0.98rem;
    color:var(--muted);margin-bottom:0.6rem;
    display:flex;flex-wrap:wrap;gap:12px;
}
.fb-timeline {
    border-left:3px solid var(--border);margin-left:8px;padding-left:16px;
    margin-top:1rem;
}
.fb-entry {
    position:relative;margin-bottom:1rem;
}
.fb-entry::before {
    content:'';position:absolute;left:-22px;top:6px;
    width:10px;height:10px;border-radius:50%;
    background:var(--gold);border:2px solid #FFFFFF;
    box-shadow:0 0 0 2px var(--gold);
}
.fb-entry-meta {
    font-family:'Outfit',sans-serif;font-size:0.9rem;
    color:var(--muted);margin-bottom:3px;
}
.fb-entry-text {
    font-family:'Outfit',sans-serif;font-size:0.98rem;
    color:var(--navy);background:var(--warm-gray);
    border-radius:6px;padding:8px 12px;
}
.fb-entry-label {
    font-family:'Outfit',sans-serif;font-size:0.9rem;font-weight:700;
    letter-spacing:0.1em;text-transform:uppercase;
    color:var(--muted);margin-bottom:6px;margin-top:8px;
}

/* Action required card */
.action-card {
    background:#FFFFFF;border:1.5px solid var(--border);
    border-radius:12px;padding:1.1rem 1.4rem;margin-bottom:0.8rem;
    font-family:'Outfit',sans-serif;transition:box-shadow 0.15s;
}
.action-card:hover { box-shadow:0 4px 16px rgba(27,42,74,0.1); }
.action-card.critical { border-left:5px solid #B71C1C; }
.action-card.push     { border-left:5px solid #E65100; }
.action-card.initial  { border-left:5px solid #F57F17; }
.action-card.fresh    { border-left:5px solid #2E7D32; }
.action-card-top {
    display:flex;justify-content:space-between;
    align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:6px;
}
.action-card-name { font-size:1.25rem;font-weight:700;color:var(--navy); }
.action-card-meta { font-size:1.05rem;color:var(--muted);margin-top:2px; }
.action-card-fb {
    font-size:1.025rem;color:var(--navy);
    background:var(--warm-gray);border-radius:6px;
    padding:6px 10px;margin-top:6px;font-style:italic;
}

.action-card.hold { border-left: 5px solid #4527A0; }

[data-testid="stWidgetLabel"] p, label {
    font-family:'Outfit',sans-serif !important;
    font-size:0.92rem !important;font-weight:500 !important;
    color:var(--navy) !important;
}
[data-testid="stSelectbox"] > div > div {
    font-family:'Outfit',sans-serif !important;font-size:1rem !important;
    border-radius:8px !important;border:1.5px solid var(--border) !important;
    background:#FFFFFF !important;
}
[data-testid="stSelectbox"] input {
    border:none !important;box-shadow:none !important;
    background:transparent !important;
}
[data-testid="stTextArea"] textarea {
    font-family:'Outfit',sans-serif !important;font-size:0.95rem !important;
    border-radius:8px !important;border:1.5px solid var(--border) !important;
}
[data-testid="stDataFrame"] {
    border-radius:10px !important;
    border:1.5px solid var(--border) !important;overflow:hidden !important;
}
.stButton > button {
    font-family:'Outfit',sans-serif !important;
    font-weight:600 !important;font-size:0.9rem !important;
    border-radius:8px !important;
}
</style>
"""
