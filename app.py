import streamlit as st
import base64

import re

from auth.firebase_config import init_firebase, get_db
from auth.login_page import show_login_page
from admin.admin_hub import show_admin_hub

from samples_new.sample_router_ import show_sample_module


init_firebase()
db = get_db()

from streamlit_cookies_manager import EncryptedCookieManager
cookies = EncryptedCookieManager(
    prefix="jeekay_",
    password=st.secrets["cookies"]["secret_key"]
)
if not cookies.ready():
    st.stop()

def is_session_valid(uid, email, token):
    try:
        if not token:
            return False
        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            return False
        data = user_doc.to_dict()
        return (
            data.get("email") == email and
            data.get("is_active", False) and
            token in data.get("session_tokens", [])  # ← check list
        )
    except:
        return False

# ── REMOVE all query params code, REPLACE with this ──
if not st.session_state.get("logged_in"):
    uid_c   = cookies.get("uid")
    email_c = cookies.get("email")
    role_c  = cookies.get("role")
    token_c = cookies.get("token")

    if uid_c and email_c and role_c and token_c:
        if is_session_valid(uid_c, email_c, token_c):
            st.session_state["logged_in"] = True
            st.session_state["uid"]       = uid_c
            st.session_state["email"]     = email_c
            st.session_state["role"]      = role_c
        else:
            cookies["uid"]   = ""
            cookies["email"] = ""
            cookies["role"]  = ""
            cookies["token"] = ""
            cookies.save()
            st.session_state["logged_in"] = False

# ── Auth gate ──
if not st.session_state.get("logged_in"):
    show_login_page(cookies)
    st.stop()



# ── Page routing ──
if st.session_state["role"] == "admin":
    if "page" not in st.session_state:
        st.session_state["page"] = "dashboard"

    with st.sidebar:
        email = st.session_state['email']
        st.markdown(
            f"""
            <div style="
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(201,168,76,0.4);
                border-radius: 8px;
                padding: 10px 14px;
                margin-bottom: 8px;
                display: flex;
                align-items: center;
                gap: 10px;
            ">
                <span style="font-size: 1.1rem;">👤</span>
                <span style="
                    color: #E8C97A;
                    font-family: 'Libre Baskerville', serif;
                    font-size: 13px;
                    font-weight: 700;
                    word-break: break-all;
                ">{email}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        # ── Utility action buttons (Admin Hub / Home / Logout) — translucent indigo ──
        st.markdown("""
        <style>
        section[data-testid="stSidebar"] .st-key-admin_hub_btn .stButton > button,
        section[data-testid="stSidebar"] .st-key-home_btn .stButton > button,
        section[data-testid="stSidebar"] .st-key-logout_btn .stButton > button {
            background: rgba(147, 112, 219, 0.16) !important;
            border: 1.5px solid rgba(147, 112, 219, 0.55) !important;
            color: #D8CFFA !important;
        }
        section[data-testid="stSidebar"] .st-key-admin_hub_btn .stButton > button:hover,
        section[data-testid="stSidebar"] .st-key-home_btn .stButton > button:hover,
        section[data-testid="stSidebar"] .st-key-logout_btn .stButton > button:hover {
            background: rgba(147, 112, 219, 0.30) !important;
            border-color: rgba(147, 112, 219, 0.8) !important;
            color: #FFFFFF !important;
        }
        </style>
        """, unsafe_allow_html=True)

        if st.button("⚙️ Admin Hub", key="admin_hub_btn", width='stretch'):
            st.session_state["page"] = "admin"
            st.rerun()

        if st.button("🏠 Home", key="home_btn", width='stretch'):
            st.session_state["page"] = "samples"
            st.session_state["landing_choice"] = None
            st.rerun()

        if st.button("⏻️ Logout", key="logout_btn", width='stretch'):
                from google.cloud import firestore as fs
                token = cookies.get("token")
                uid = st.session_state.get("uid")
                if uid and token:
                    db.collection("users").document(st.session_state["uid"]).update({
                        "is_active": False,
                         "session_tokens": fs.ArrayRemove([token])
                    })
                cookies["uid"]   = ""
                cookies["email"] = ""
                cookies["role"]  = ""
                cookies["token"] = ""
                cookies.save()
                for key in ["logged_in", "uid", "email", "role", "page", 
                    "wr_df", "wr_branch_val", "wr_start_val", 
                    "wr_end_val", "wr_owner"]:  
                    st.session_state.pop(key, None)
                st.rerun()
            
    if st.session_state["page"] == "admin":
        show_admin_hub()
        st.stop()
    if "landing_choice" not in st.session_state:
        st.session_state["landing_choice"] = None

    # Main routing
    if st.session_state["landing_choice"] is None:
        from landing_page import show_landing
        show_landing()
    else:
        show_sample_module(st.session_state["landing_choice"])

else:
    with st.sidebar:
        def get_base64(img_path):
            with open(img_path, "rb") as f:
                return base64.b64encode(f.read()).decode()

        logo = get_base64("logo.png")

        st.markdown(f"""
                <div style="text-align:center; margin-bottom:10px;">
                    <img src="data:image/png;base64,{logo}" width="400" height="200"
                    style="border-radius:8px;">
                </div>
            """, unsafe_allow_html=True)

        email = st.session_state['email']
        st.markdown(
            f"""
            <div style="
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(201,168,76,0.4);
                border-radius: 8px;
                padding: 10px 14px;
                margin-bottom: 8px;
                display: flex;
                align-items: center;
                gap: 10px;
            ">
                <span style="font-size: 1.1rem;">👤</span>
                <span style="
                    color: #E8C97A;
                    font-family: 'Libre Baskerville', serif;
                    font-size: 13px;
                    font-weight: 700;
                    word-break: break-all;
                ">{email}</span>
            </div>
            """,
            unsafe_allow_html=True
        )   
        if st.button("🏠 Home", key="home_btn", width='stretch'):
            st.session_state["page"] = "samples"
            st.session_state["landing_choice"] = None
            st.rerun()
     
    
        if st.button("⏻️ Logout", key="logout_btn", width='stretch'):
            from google.cloud import firestore as fs
            token = cookies.get("token")
            uid = st.session_state.get("uid")
            if uid and token:
                db.collection("users").document(uid).update({
                    "session_tokens": fs.ArrayRemove([token])  # remove only this device
                })
            cookies["uid"]   = ""
            cookies["email"] = ""
            cookies["role"]  = ""
            cookies["token"] = ""
            cookies.save()
            for key in ["logged_in", "uid", "email", "role", "page", 
            "wr_df", "wr_branch_val", "wr_start_val", 
            "wr_end_val", "wr_owner"]:  # ← add wr_ keys
                st.session_state.pop(key, None)
            st.rerun()
    if "landing_choice" not in st.session_state:
        st.session_state["landing_choice"] = None

    # Main routing
    if st.session_state.get("landing_choice") is None:
        from landing_page import show_landing
        show_landing()
    else:
        show_sample_module(st.session_state["landing_choice"])
    

# ---- CONFIG ----
st.set_page_config(layout="wide")

# ---- CUSTOM CSS ----
st.markdown("""
<style>
/* ── Google Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=IM+Fell+English:ital@0;1&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap');

/* ── Root variables ── */
:root {
    --navy:       #1B2A4A;
    --navy-light: #243556;
    --gold:       #C9A84C;
    --gold-light: #E8C97A;
    --cream:      #F5F1EA;
    --card-bg:    #FFFFFF;
    --text-main:  #1B2A4A;
    --text-muted: #5A6A85;
    --border:     #D9D0BE;
    --shadow:     0 4px 20px rgba(27,42,74,0.10);
}

/* ══════════════════════════════════════
   APP BACKGROUND & BASE FONT
══════════════════════════════════════ */
.stApp {
    background: var(--cream);
    font-family: 'Libre Baskerville', serif;
    font-size: 17px;
    color: var(--text-main);
}

/* ══════════════════════════════════════
   SIDEBAR
══════════════════════════════════════ */
section[data-testid="stSidebar"] {
    background: var(--navy) !important;
    border-right: 3px solid var(--gold);
}
section[data-testid="stSidebar"] * {
    color: #E8E4DC !important;
    font-family: 'Libre Baskerville', serif;
    font-size: 15px;
}
section[data-testid="stSidebar"] h2 {
    color: var(--gold-light) !important;
    font-family: 'IM Fell English', serif !important;
    font-size: 20px !important;
    letter-spacing: 0.5px;
}
section[data-testid="stSidebar"] .stSelectbox label {
    color: var(--gold-light) !important;
    font-family: 'Libre Baskerville', serif !important;
    font-size: 14px !important;
    font-weight: 700 !important;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}
section[data-testid="stSidebar"] .stSelectbox > div > div {
    background: var(--navy-light) !important;
    border: 1px solid var(--gold) !important;
    color: #E8E4DC !important;
    border-radius: 6px;
}

[data-testid="stSidebarCollapseButton"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}

button[kind="header"] {
    display: none !important;
}

.st-emotion-cache-zq5wmm {
    display: none !important;
}

section[data-testid="stSidebar"] > div:first-child > div:first-child > button {
    display: none !important;
}
/* ══════════════════════════════════════
   HEADINGS
══════════════════════════════════════ */
h1, h2, h3 {
    font-family: 'IM Fell English', serif !important;
    color: var(--navy) !important;
}
[data-testid="stSubheader"] {
    font-size: 24px !important;
    font-family: 'IM Fell English', serif !important;
    color: var(--navy) !important;
    border-bottom: 2px solid var(--gold);
    padding-bottom: 8px;
    margin-top: 28px !important;
    margin-bottom: 20px !important;
}

/* ══════════════════════════════════════
   KPI METRIC CARDS
══════════════════════════════════════ */
[data-testid="stMetric"] {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-top: 4px solid var(--gold);
    border-radius: 10px;
    padding: 20px 24px !important;
    box-shadow: var(--shadow);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 28px rgba(27,42,74,0.15);
}
[data-testid="stMetricLabel"] > div {
    font-size: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 1.4px !important;
    text-transform: uppercase !important;
    color: var(--text-muted) !important;
    font-family: 'Libre Baskerville', serif !important;
    margin-bottom: 6px;
}
[data-testid="stMetricValue"] {
    font-size: 30px !important;
    font-weight: 700 !important;
    color: var(--navy) !important;
    font-family: 'Libre Baskerville', serif !important;
    line-height: 1.2;
}

/* ══════════════════════════════════════
   DATAFRAME TABLE
══════════════════════════════════════ */

/* Increase cell font */
[data-testid="stDataFrame"] div[role="gridcell"] {
    font-size: 30px !important;
}

/* Increase header font */
[data-testid="stDataFrame"] div[role="columnheader"] {
    font-size: 40px !important;
    font-weight: 600;
}

/* Optional: row height [this will make it look less cramped] */
[data-testid="stDataFrame"] div[role="row"] {
    min-height: 35px;
}
[data-testid="stDataFrame"] {
    zoom: 1.1;
}
            
/* ═════════════════════════════════════
   DOWNLOAD BUTTON
══════════════════════════════════════ */
.stDownloadButton > button {
    background: var(--navy) !important;
    color: var(--gold-light) !important;
    border: 2px solid var(--gold) !important;
    border-radius: 8px !important;
    font-family: 'Libre Baskerville', serif !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    padding: 10px 28px !important;
    letter-spacing: 0.5px;
    transition: all 0.2s ease;
    margin-top: 10px;
}
.stDownloadButton > button:hover {
    background: var(--gold) !important;
    color: var(--navy) !important;
}

/* ══════════════════════════════════════
   CUSTOMER INSIGHT CARDS (HTML divs)
══════════════════════════════════════ */
.insight-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: var(--shadow);
    overflow: hidden;
    margin-bottom: 16px;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.insight-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 28px rgba(27,42,74,0.15);
}
.insight-header {
    background: var(--navy);
    color: var(--gold-light) !important;
    font-family: 'Libre Baskerville', serif;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    padding: 10px 16px;
    border-bottom: 2px solid var(--gold);
}
.insight-body {
    font-family: 'Libre Baskerville', serif;
    font-size: 15px;
    line-height: 1.8;
    color: var(--text-main);
    padding: 16px;
    min-height: 72px;
    background: var(--card-bg);
}

/* ── Reset Filters button ── */
section[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    color: var(--gold-light) !important;
    border: 1px solid var(--gold) !important;
    border-radius: 6px !important;
    font-family: 'Libre Baskerville', serif !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    letter-spacing: 0.8px;
    padding: 8px 12px !important;
    margin-bottom: 16px;
    width: 100%;
    transition: all 0.2s ease;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--gold) !important;
    color: var(--navy) !important;
}
            
/* ══════════════════════════════════════
   MISC
══════════════════════════════════════ */
hr {
    border-color: var(--border) !important;
    margin: 8px 0 !important;
}
[data-testid="column"] {
    padding-left: 8px !important;
    padding-right: 8px !important;
}
</style>
""", unsafe_allow_html=True)
