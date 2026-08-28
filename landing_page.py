"""
Landing page — shown after login.
Two entry points: Sample Intelligence (post-handover) and Pipeline Manager (pre-handover).
"""
import streamlit as st
import base64
from samples_new.sample_constants import SAMPLE_CSS


LANDING_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=Outfit:wght@300;400;500;600;700&display=swap');

.landing-hero {
    text-align: center;
    padding: 3rem 0 2.5rem 0;
}
.landing-eyebrow {
    font-family: 'Outfit', sans-serif;
    font-size: 0.72rem; font-weight: 700;
    letter-spacing: 0.25em; text-transform: uppercase;
    color: #C9A84C; margin-bottom: 0.6rem;
}
.landing-title {
    font-family: 'Cormorant Garamond', serif;
    font-size: 5rem; font-weight: 700;
    color: #1B2A4A; line-height: 1.1;
    margin-bottom: 0.5rem;
}
.landing-title em { color: #C9A84C; font-style: italic; }
.landing-sub {
    font-family: 'Outfit', sans-serif;
    font-size: 0.95rem; color: #6B7A99;
    font-weight: 400; margin-bottom: 0;
}
.landing-divider {
    width: 60px; height: 3px;
    background: linear-gradient(90deg, #C9A84C, #E8C96A);
    border-radius: 2px; margin: 1.2rem auto 2.5rem auto;
}

/* Entry cards */
.entry-card {
    background: #FFFFFF;
    border: 1.5px solid #DDD5C5;
    border-radius: 20px;
    padding: 2.4rem 2rem;
    text-align: center;
    position: relative;
    overflow: hidden;
    height: 100%;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    cursor: pointer;
}
.entry-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(27,42,74,0.12);
}
.entry-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 4px;
}
.entry-card.intelligence::before {
    background: linear-gradient(90deg, #1B2A4A, #5A6A85);
}
.entry-card.pipeline::before {
    background: linear-gradient(90deg, #C9A84C, #E8C96A);
}
.entry-icon {
    font-size: 3rem; margin-bottom: 1rem; display: block;
}
.entry-title {
    font-family: 'Cormorant Garamond', serif;
    font-size: 2rem; font-weight: 700;
    color: #1B2A4A; margin-bottom: 0.4rem;
}
.entry-subtitle {
    font-family: 'Outfit', sans-serif;
    font-size: 1.6rem; color: #C9A84C;
    font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.1em; margin-bottom: 1rem;
}
.entry-desc {
    font-family: 'Outfit', sans-serif;
    font-size: 1.2rem; color: #6B7A99;
    line-height: 1.6; margin-bottom: 1.5rem;
}
.entry-pages {
    display: flex; flex-wrap: wrap;
    justify-content: center; gap: 6px;
    margin-bottom: 2.8rem;
}
.entry-page-badge {
    display: inline-block;
    background: #FAF7F2;
    border: 1px solid #DDD5C5;
    border-radius: 20px;
    padding: 3px 12px;
    font-family: 'Outfit', sans-serif;
    font-size: 1.2rem; color: #1B2A4A;
    font-weight: 500;
}

/* Target the button inside the pipeline container */
.pipeline-btn-container div[data-testid="stButton"] button,
.st-key-btn_pipeline button {
    display: inline-block !important;
    background: #1B2A4A !important;
    color: #E8C96A !important;
    border: 1.5px solid #C9A84C !important;
    border-radius: 10px !important;
    padding: 10px 28px !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 1.92rem !important; 
    font-weight: 700 !important;
    text-decoration: none !important;
    transition: all 0.2s ease !important;
}

/* Target the button inside the intelligence container */
.intel-btn-container div[data-testid="stButton"] button,
.st-key-btn_intelligence button {
    display: inline-block !important;
    background: #1B2A4A !important;
    color: #E8C96A !important;
    border: 1.5px solid #C9A84C !important;
    border-radius: 10px !important;
    padding: 10px 28px !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 2.4rem !important; 
    font-weight: 700 !important;
    text-decoration: none !important;
    transition: all 0.2s ease !important;
}
</style>
"""


def show_landing():
    st.markdown(SAMPLE_CSS, unsafe_allow_html=True)
    st.markdown(LANDING_CSS, unsafe_allow_html=True)

    # Hero Section
    st.markdown(f"""
    <div class="landing-hero">
        <div class="landing-title">Sample <em>Tracker</em></div>
        <div class="landing-sub">
            Welcome, <b>Team Samira!</b> &nbsp;·&nbsp; What would you like to do today?
        </div>
        <div class="landing-divider"></div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")

    with col1:  # Pipeline Card
        st.markdown("""
        <div class="entry-card pipeline">
            <span class="entry-icon">🔄</span>
            <div class="entry-title">Sample Tracker</div>
            <div class="entry-subtitle">Before Handover</div>
            <div class="entry-desc">
                Record new enquiries, track samples through each stage 
                from supplier to customer handover.
            </div>
            <div class="entry-pages">
                <span class="entry-page-badge">➕ New Enquiry</span>
                <span class="entry-page-badge">🔄 Pipeline Tracker</span>
                <span class="entry-page-badge">📈 Analytics</span>
                <span class="entry-page-badge">🔔 Notifications</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="pipeline-btn-container" style="margin-top: 1.2rem;">', unsafe_allow_html=True)
        
        if st.button("---- ENTER PIPELINE MANAGER ---→", 
                     key="btn_pipeline",
                     width='content'):
            st.session_state["landing_choice"] = "pipeline"
            st.rerun()
            from samples_new.sample_router_ import show_sample_module
            show_sample_module(landing_choice="pipeline")
        
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:  # Intelligence Card
        st.markdown("""
        <div class="entry-card intelligence">
            <span class="entry-icon">📊</span>
            <div class="entry-title">Sample Tracker</div>
            <div class="entry-subtitle">After Handover</div>
            <div class="entry-desc">
                Analyse feedback, track urgency, generate reports 
                and understand which products are working.
            </div>
            <div class="entry-pages">
                <span class="entry-page-badge">📊 Overview</span>
                <span class="entry-page-badge">🔍 Detailed Info</span>
                <span class="entry-page-badge">🚨 Action Required</span>
                <span class="entry-page-badge">📋 All Samples</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="intel-btn-container" style="margin-top: 1.2rem;">', unsafe_allow_html=True)
        
        if st.button("---- ENTER SAMPLE INTELLIGENCE ---→",
                     key="btn_intelligence",
                     width='content',
                     type="primary"):
            st.session_state["landing_choice"] = "intelligence"
            st.rerun()
            from samples_new.sample_router_ import show_sample_module
            show_sample_module(landing_choice="intelligence")
        
        st.markdown('</div>', unsafe_allow_html=True)
    # ── Footer ──
    st.markdown("""
    <div style="text-align:center;font-family:Outfit,sans-serif;
                font-size:0.78rem;color:#DDD5C5;margin-top:3rem;">
        · Samira Chemicals · Sample Intelligence Dashboard
    </div>
    """, unsafe_allow_html=True)