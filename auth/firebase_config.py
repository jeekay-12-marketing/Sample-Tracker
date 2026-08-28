import firebase_admin
from firebase_admin import credentials, auth, firestore
import streamlit as st

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)

def get_db():
    return firestore.client()
