import streamlit as st
from auth.auth_functions import login_user, get_user_record, send_email_otp, verify_email_otp
import base64
import time
from auth.firebase_config import get_db


ADMIN_EMAIL = st.secrets["admin"]["ADMIN_EMAIL"]

def show_login_page(cookies):
    db = get_db()
    # ── Safe cookie access ──
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IM+Fell+English:ital@0;1&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap');

    .stApp {
        background: linear-gradient(135deg, #1B2A4A 0%, #243556 50%, #1B2A4A 100%) !important;
    }
    #MainMenu, footer, header { visibility: hidden; }
    section[data-testid="stSidebar"] { display: none !important; }

    .block-container {
        max-width: 600px !important;
        margin: 40px auto 0 auto !important;
        padding: 50px !important;
        background: #FFFFFF !important;
        border-radius: 12px !important;
        border-top: 5px solid #C9A84C !important;
        box-shadow: 0 24px 64px rgba(0,0,0,0.35) !important;
        position: absolute !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
    }
    .stTextInput label {
        font-family: 'Libre Baskerville', serif !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 1.2px !important;
        text-transform: uppercase !important;
        color: #5A6A85 !important;
    }
    .stTextInput input {
        font-family: 'Libre Baskerville', serif !important;
        font-size: 17px !important;
        color: #1B2A4A !important;
        border: 1px solid #D9D0BE !important;
        border-radius: 6px !important;
        padding: 12px 14px !important;
        background: #FDFBF7 !important;
    }
    .stTextInput input:focus {
        border-color: #C9A84C !important;
        box-shadow: 0 0 0 2px rgba(201,168,76,0.15) !important;
    }
    .stButton > button {
        background: #1B2A4A !important;
        color: #E8C97A !important;
        border: 2px solid #C9A84C !important;
        border-radius: 8px !important;
        font-family: 'Libre Baskerville', serif !important;
        font-size: 17px !important;
        font-weight: 700 !important;
        letter-spacing: 0.8px !important;
        padding: 14px 0 !important;
        margin-top: 8px;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        background: #C9A84C !important;
        color: #1B2A4A !important;
    }
    .stAlert {
        border-radius: 8px !important;
        font-family: 'Libre Baskerville', serif !important;
        font-size: 13px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Branding ──
    def get_base64(img_path):
        with open(img_path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    logo = get_base64("logo.png")

    st.markdown(f"""
        <div style="text-align:center; margin-bottom:10px;">
            <img src="data:image/png;base64,{logo}" width="400" height="200"
            style="border-radius:8px;">
        </div>
        <div style="font-family:'IM Fell English',serif; font-size:26px;
                    color:#1B2A4A; text-align:center; margin-bottom:4px;">
            SAMPLE TRACKER DASHBOARD 🧐
        </div>
        <div style="font-family:'Libre Baskerville',serif; font-size:11px;
                    color:#5A6A85; text-align:center; letter-spacing:1.8px;
                    text-transform:uppercase; margin-bottom:6px;">
            Track your Samples!
        </div>
        <div style="width:48px; height:3px; background:#C9A84C;
                    margin: 0 auto 28px auto; border-radius:2px;"></div>
    """, unsafe_allow_html=True)

    # ── 2FA screen — INSIDE function, BEFORE tabs ──
    if st.session_state.get("awaiting_2fa"):

        otp_age = time.time() - st.session_state.get("otp_sent_time", 0)
        if otp_age > 300:
            st.error("OTP expired. Please login again.")
            for k in ["awaiting_2fa", "pending_uid", "pending_email",
                      "email_otp", "otp_sent_time"]:
                st.session_state.pop(k, None)
            st.rerun()

        st.markdown(f"""
            <div style="font-family:'Libre Baskerville',serif; font-size:13px;
                        color:#5A6A85; margin-bottom:8px; line-height:1.7;">
                A 6-digit OTP has been sent to<br>
                <strong style="color:#1B2A4A;">
                    {st.session_state['pending_email']}
                </strong><br>
                Enter it below. Expires in 5 minutes.
            </div>
        """, unsafe_allow_html=True)

        otp_code = st.text_input("Enter OTP", key="otp_input",
                                  placeholder="000000", max_chars=6)

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            if st.button("Verify OTP", key="verify_2fa", width='stretch'):
                ok, msg = verify_email_otp(otp_code)
                if ok:
                    import secrets
                    from google.cloud import firestore as fs
                
                    session_token = secrets.token_hex(32)
                
                    uid   = st.session_state["pending_uid"]
                    email = st.session_state["pending_email"]
                
                    st.session_state["logged_in"] = True
                    st.session_state["role"]      = "admin"
                    st.session_state["uid"]       = uid
                    st.session_state["email"]     = email
                
                    db.collection("users").document(uid).set({
                        "email": email,
                        "role": "admin",
                        "is_active": True,
                        "session_tokens": fs.ArrayUnion([session_token])  # ← changed
                    }, merge=True)
                
                    cookies["uid"]   = uid
                    cookies["email"] = email
                    cookies["role"]  = "admin"
                    cookies["token"] = session_token
                    cookies.save()
                
                    for k in ["awaiting_2fa", "pending_uid", "pending_email",
                              "email_otp", "otp_sent_time"]:
                        st.session_state.pop(k, None)
                    st.rerun()
                else:
                    st.error(msg)

        with col2:
            if st.button("Resend", key="resend_otp", width='stretch'):
                try:
                    send_email_otp(st.session_state["pending_email"])
                    st.session_state["otp_sent_time"] = time.time()
                    st.success("OTP resent!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

        with col3:
            if st.button("← Back", key="back_2fa", width='stretch'):
                for k in ["awaiting_2fa", "pending_uid", "pending_email",
                          "email_otp", "otp_sent_time"]:
                    st.session_state.pop(k, None)
                st.rerun()

        st.stop()  # ← tabs never render during 2FA

    # ── Normal login — only when NOT in 2FA ──
    email = st.text_input("Email Address", key="login_email")
    password = st.text_input("Password", type="password", key="login_pass")

    if st.button("Sign In", key="login_btn", width='stretch'):
        if not email or not password:
            st.error("Please fill in all fields.")
        else:
            result = login_user(email, password)
            if "error" in result:
                st.error("Invalid email or password.")
            else:
                uid = result["localId"]
                if email == ADMIN_EMAIL:
                    try:
                        send_email_otp(email)
                        st.session_state["awaiting_2fa"]  = True
                        st.session_state["otp_sent_time"] = time.time()
                        st.session_state["pending_uid"]   = uid
                        st.session_state["pending_email"] = email
                        st.success("OTP sent to your email!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to send OTP: {e}")
                else:
                    user_record = get_user_record(uid)
                    if not user_record:
                        st.error("No access request found. Please request access first.")
                    elif user_record["status"] == "pending":
                        st.warning("⏳ Your request is pending admin approval.")
                    elif user_record["status"] == "denied":
                        st.error("Access denied. Contact your administrator.")
                    elif user_record["status"] == "approved":
                        import secrets
                        from google.cloud import firestore as fs

                        session_token = secrets.token_hex(32)

                        st.session_state["logged_in"] = True
                        st.session_state["role"]      = "user"
                        st.session_state["uid"]       = uid
                        st.session_state["email"]     = email

                        db.collection("users").document(uid).update({
                            "is_active": True,
                            "session_tokens": fs.ArrayUnion([session_token])
                        })

                        cookies["uid"]   = uid
                        cookies["email"] = email
                        cookies["role"]  = "user"
                        cookies["token"] = session_token
                        cookies.save()

                        st.rerun()

    st.markdown("""
        <hr style="border:none; border-top:1px solid #EDE8DF; margin:28px 0 16px 0;">
        <div style="font-family:'Libre Baskerville',serif; font-size:11px;
                    color:#A0A8B8; text-align:center;">
            Samira Chemicals &nbsp;·&nbsp; Confidential Access Only
        </div>
    """, unsafe_allow_html=True)