from firebase_admin import auth
from auth.firebase_config import get_db
import streamlit as st
import requests
from firebase_admin import auth
import re
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google.cloud.firestore_v1.base_query import FieldFilter

def send_email_otp(admin_email):
    otp = str(random.randint(100000, 999999))
    st.session_state["email_otp"] = otp

    sender = st.secrets["gmail"]["sender_email"]
    password = st.secrets["gmail"]["app_password"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your Login OTP — Sample Tracker"
    msg["From"] = sender
    msg["To"] = admin_email

    html = f"""
    <div style="font-family: Georgia, serif; max-width: 400px; margin: 0 auto;
                border: 1px solid #D9D0BE; border-top: 4px solid #C9A84C;
                border-radius: 8px; padding: 32px; background: #FFFFFF;">
        <div style="font-size: 22px; color: #1B2A4A; margin-bottom: 8px;">
            Jeekay Dashboard
        </div>
        <div style="font-size: 13px; color: #5A6A85; margin-bottom: 24px;">
            Your one-time login code:
        </div>
        <div style="font-size: 36px; font-weight: bold; color: #1B2A4A;
                    letter-spacing: 8px; text-align: center;
                    background: #F5F1EA; padding: 16px; border-radius: 6px;
                    border: 1px solid #D9D0BE; margin-bottom: 24px;">
            {otp}
        </div>
        <div style="font-size: 12px; color: #5A6A85;">
            This code expires in <strong>5 minutes</strong>. 
            Do not share it with anyone.
        </div>
    </div>
    """

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, admin_email, msg.as_string())

    return otp

def verify_email_otp(entered_code):
    stored = st.session_state.get("email_otp")
    if not stored:
        return False, "OTP expired or not generated."
    if entered_code.strip() == stored:
        st.session_state.pop("email_otp", None)
        return True, "Verified!"
    return False, "Invalid OTP."


def login_user(email, password):
    """Verify user via Firebase Auth REST API"""
    api_key = st.secrets["keys"]["firebase_web_api_key"]
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    r = requests.post(url, json=payload)
    return r.json()


def get_user_record(uid):
    db = get_db()
    doc = db.collection("users").document(uid).get()
    if doc.exists:
        return doc.to_dict()
    return None

def get_all_requests():
    db = get_db()
    return [doc.to_dict() for doc in db.collection("users").stream()]

def update_user_status(uid, status):
    db = get_db()
    db.collection("users").document(uid).update({"status": status})

def approve_user(email, full_name, doc_id, password):
    api_key = st.secrets["keys"]["firebase_web_api_key"]

    # Create user in Firebase Auth
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    r = requests.post(url, json=payload)
    data = r.json()

    if "error" in data:
        return False, data["error"]["message"]

    uid = data["localId"]
    db = get_db()

    # Add to users collection
    db.collection("users").document(uid).set({
        "uid": uid,
        "email": email,
        "full_name": full_name,
        "role": "user",
        "status": "approved",
        "password_plain": password,  # stored so admin can view it
    })

    # Delete from pending
    db.collection("pending_requests").document(doc_id).delete()
    return True, f"User {email} created successfully!"




def get_all_users():
    db = get_db()
    docs = db.collection("users").stream()
    return [d.to_dict() for d in docs]

def remove_user(uid, email):
    # Delete from Firebase Auth
    from auth.firebase_config import init_firebase  # ← add this
    from firebase_admin import auth
    init_firebase() 
    try:
        auth.delete_user(uid)
    except Exception:
        pass
    # Delete from Firestore
    db = get_db()
    db.collection("users").document(uid).delete()


def change_user_password(email, new_password, uid):
    from firebase_admin import auth
    auth.update_user(uid, password=new_password)
    db = get_db()
    db.collection("users").document(uid).update({
        "password_plain": new_password,
        "is_active": False,
        "session_tokens": []  # ← wipe all devices
    })

def create_user_directly(email, full_name, password):
    import requests
    api_key = st.secrets["keys"]["firebase_web_api_key"]
    db = get_db()

    # Check duplicates in users only
    existing = db.collection("users").where(filter=FieldFilter("email", "==", email)).get()
    if existing:
        return False, "A user with this email already exists."

    # Create in Firebase Auth
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    r = requests.post(url, json=payload)
    data = r.json()

    if "error" in data:
        return False, data["error"]["message"]

    uid = data["localId"]

    # If a pending request exists for this email, clean it up
    pending = db.collection("pending_requests").where(filter=FieldFilter("email", "==", email)).get()
    for doc in pending:
        db.collection("pending_requests").document(doc.id).delete()

    # Save to Firestore
    db.collection("users").document(uid).set({
        "uid": uid,
        "email": email,
        "full_name": full_name,
        "role": "user",
        "status": "approved",
        "password_plain": password,
    })
    return True, f"User {full_name} created!"


