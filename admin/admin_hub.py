import streamlit as st
from auth.auth_functions import (
 get_all_users, 
    remove_user, change_user_password,
    create_user_directly)

from admin.manage_customers import (
    load_customers, add_customer, update_customer, delete_customer,
    BRANCH_OPTIONS
)

# ══════════════════════════════════════════════════════
# COMBINED STYLES  (admin_page.py + manage_customers.py, deduped)
# ══════════════════════════════════════════════════════
HUB_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=Outfit:wght@300;400;500;600;700&display=swap');

:root {
    --navy:      #1B2A4A;
    --gold:      #C9A84C;
    --gold-lt:   #E8C96A;
    --cream:     #FAF7F2;
    --warm-gray: #F0EBE1;
    --border:    #DDD5C5;
    --muted:     #6B7A99;
    --text:      #1B2A4A;
    --green:     #155724;
    --green-bg:  #D4EDDA;
    --green-bd:  #C3E6CB;
    --red:       #721C24;
    --red-bg:    #F8D7DA;
    --red-bd:    #F5C6CB;
    --yellow:    #856404;
    --yellow-bg: #FFF3CD;
    --yellow-bd: #FFEAA7;
}

/* ── Page background ── */
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main {
    background-color: var(--cream) !important;
}
[data-testid="stHeader"] {
    background-color: var(--cream) !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: var(--navy) !important;
    border-right: 3px solid var(--gold) !important;
}
section[data-testid="stSidebar"] * {
    color: #E8E4DC !important;
    font-family: 'Outfit', sans-serif !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    color: #E8C97A !important;
    border: 1px solid var(--gold) !important;
    border-radius: 8px !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    margin-bottom: 4px !important;
    transition: all 0.2s ease !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(201, 168, 76, 0.15) !important;
    border-color: var(--gold-lt) !important;
    color: #FFFFFF !important;
}

/* ── Page title ── */
.admin-header {
    font-family: 'Cormorant Garamond', serif;
    font-size: 2.8rem;
    font-weight: 700;
    color: var(--navy);
    line-height: 1.1;
    letter-spacing: -0.5px;
    margin-bottom: 0.2rem;
}
.admin-sub {
    font-family: 'Outfit', sans-serif;
    font-size: 1rem;
    font-weight: 400;
    color: var(--muted);
    margin-bottom: 0.5rem;
}

/* ── Section titles (admin panel) ── */
.section-title {
    font-family: 'Cormorant Garamond', serif;
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--navy);
    border-bottom: 2px solid var(--border);
    padding-bottom: 8px;
    margin: 2.5rem 0 1.2rem 0;
    position: relative;
}
.section-title::after {
    content: '';
    position: absolute;
    bottom: -2px;
    left: 0;
    width: 50px;
    height: 2px;
    background: var(--gold);
}

/* ── Section label (manage customers) ── */
.mc-section {
    font-family: 'Outfit', sans-serif;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--gold);
    border-bottom: 2px solid var(--border);
    padding-bottom: 8px;
    margin: 2rem 0 1rem 0;
    position: relative;
}
.mc-section::after {
    content: '';
    position: absolute;
    bottom: -2px;
    left: 0;
    width: 40px;
    height: 2px;
    background: var(--gold);
}

/* ── Column headers ── */
.col-header {
    font-family: 'Outfit', sans-serif;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
    padding-bottom: 4px;
}

/* ── Name & email (admin panel) ── */
.user-name {
    font-family: 'Outfit', sans-serif;
    font-size: 0.98rem;
    font-weight: 600;
    color: var(--navy);
    margin-bottom: 2px;
    padding-top: 8px;
}
.user-email {
    font-family: 'Outfit', sans-serif;
    font-size: 0.85rem;
    font-weight: 400;
    color: var(--muted);
    padding-bottom: 8px;
}

/* ── Status badges (admin panel) ── */
.badge-pending {
    background: var(--yellow-bg);
    color: var(--yellow);
    border: 1px solid var(--yellow-bd);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.75rem;
    font-weight: 700;
    font-family: 'Outfit', sans-serif;
    letter-spacing: 0.05em;
    display: inline-block;
    margin-top: 10px;
}
.badge-approved {
    background: var(--green-bg);
    color: var(--green);
    border: 1px solid var(--green-bd);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.75rem;
    font-weight: 700;
    font-family: 'Outfit', sans-serif;
    display: inline-block;
    margin-top: 10px;
}
.badge-denied {
    background: var(--red-bg);
    color: var(--red);
    border: 1px solid var(--red-bd);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.75rem;
    font-weight: 700;
    font-family: 'Outfit', sans-serif;
    display: inline-block;
    margin-top: 10px;
}

/* ── Buttons (shared) ── */
.stButton > button {
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.88rem !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    padding: 8px 14px !important;
    transition: all 0.2s ease !important;
    background: var(--navy) !important;
    color: #E8C97A !important;
    border: 1.5px solid var(--gold) !important;
    width: 100% !important;
}
.stButton > button:hover {
    background: var(--gold) !important;
    color: var(--navy) !important;
}

/* ── Sync button ── */
.sync-btn .stButton > button {
    font-size: 1rem !important;
    padding: 12px 20px !important;
    background: var(--gold) !important;
    color: var(--navy) !important;
    border: none !important;
    font-weight: 700 !important;
}
.sync-btn .stButton > button:hover {
    background: var(--gold-lt) !important;
    box-shadow: 0 4px 16px rgba(201, 168, 76, 0.3) !important;
}

/* ── Inputs ── */
input, textarea,
[data-testid="stTextInput"] input {
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.95rem !important;
    border: 1.5px solid var(--border) !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    background: #FFFFFF !important;
    color: var(--navy) !important;
}
input:focus,
[data-testid="stTextInput"] input:focus {
    border-color: var(--gold) !important;
    box-shadow: 0 0 0 3px rgba(201,168,76,0.12) !important;
}
[data-testid="stWidgetLabel"] p,
[data-testid="stTextInput"] label,
label {
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.05em !important;
    color: var(--navy) !important;
}

/* ── Selectbox ── */
[data-testid="stSelectbox"] > div > div {
    font-family: 'Outfit', sans-serif !important;
    font-size: 1rem !important;
    border-radius: 8px !important;
    border: 1.5px solid var(--border) !important;
    background: #FFFFFF !important;
    min-height: 46px !important;
}
[data-testid="stSelectbox"] input {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}

/* ── Tab styling ── */
[data-testid="stTabs"] [role="tab"] {
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    color: var(--muted) !important;
    padding: 8px 20px !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: var(--navy) !important;
    font-weight: 600 !important;
    border-bottom: 2px solid var(--gold) !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1.5px solid var(--border) !important;
    border-left: 4px solid var(--red-bd) !important;
    border-radius: 10px !important;
    box-shadow: 0 2px 8px rgba(27,42,74,0.06) !important;
}
[data-testid="stExpander"] summary {
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: var(--red) !important;
    padding: 12px 16px !important;
}
[data-testid="stExpander"]:has(summary:contains("Create")),
[data-testid="stExpander"]:has(summary:contains("View")),
[data-testid="stExpander"]:has(summary:contains("⋮")) {
    border-left: 4px solid var(--gold) !important;
}
[data-testid="stExpander"]:has(summary:contains("Create")) summary,
[data-testid="stExpander"]:has(summary:contains("View")) summary,
[data-testid="stExpander"]:has(summary:contains("⋮")) summary {
    color: var(--navy) !important;
}

/* ── Alerts ── */
.stAlert {
    border-radius: 8px !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.9rem !important;
}

/* ── Dividers ── */
hr {
    border-color: var(--border) !important;
    margin: 6px 0 !important;
}

/* ── st.code ── */
.stCode {
    font-size: 0.9rem !important;
    border-radius: 6px !important;
    background: var(--warm-gray) !important;
}

/* ── Sync section card ── */
.sync-card {
    background: #FFFFFF;
    border: 1.5px solid var(--border);
    border-left: 5px solid var(--gold);
    border-radius: 12px;
    padding: 1.4rem 1.8rem;
    margin-top: 2rem;
    box-shadow: 0 2px 12px rgba(27,42,74,0.06);
}
.sync-card-title {
    font-family: 'Cormorant Garamond', serif;
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--navy);
    margin-bottom: 0.3rem;
}
.sync-card-sub {
    font-family: 'Outfit', sans-serif;
    font-size: 0.85rem;
    color: var(--muted);
    margin-bottom: 1rem;
}

/* ── Customer row card (manage customers) ── */
.customer-row {
    background: #FFFFFF;
    border: 1.5px solid var(--border);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.6rem;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
    box-shadow: 0 1px 4px rgba(27, 42, 74, 0.04);
}
.customer-row:hover {
    border-color: var(--gold);
    box-shadow: 0 4px 16px rgba(27, 42, 74, 0.08);
}
.customer-name {
    font-family: 'Outfit', sans-serif;
    font-weight: 600;
    color: var(--navy);
    font-size: 1rem;
    margin-bottom: 4px;
}
.customer-meta {
    font-family: 'Outfit', sans-serif;
    color: var(--muted);
    font-size: 0.82rem;
    margin-top: 4px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

/* ── Generic count badge (manage customers) ── */
.badge {
    display: inline-flex;
    align-items: center;
    background: var(--warm-gray);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 2px 10px;
    font-family: 'Outfit', sans-serif;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--navy);
    white-space: nowrap;
}
</style>
"""

HUB_TITLE_HTML = """
<div style="margin-bottom: 0.5rem;">
    <div class="admin-header">⚙️ Admin <em style="color:#C9A84C; font-style:italic;">Hub</em></div>
    <div class="admin-sub">Manage access requests, users and the customer master list.</div>
    <div style="width:60px; height:3px; background:linear-gradient(90deg,#C9A84C,#E8C96A); border-radius:2px; margin-top:0.8rem;"></div>
</div>
"""


# ══════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════
def show_admin_hub():
    st.markdown(HUB_CSS, unsafe_allow_html=True)
    st.markdown(HUB_TITLE_HTML, unsafe_allow_html=True)


    tab_admin, tab_customers = st.tabs(["⚙️  Admin Panel", "👥  Manage Customers"])

    with tab_admin:
        _render_admin_panel()

    with tab_customers:
        _render_manage_customers()


# ══════════════════════════════════════════════════════
# ADMIN PANEL CONTENT  (from admin_page.py::show_admin_page)
# ══════════════════════════════════════════════════════
def _render_admin_panel():
    # ══════════════════════════════════════
    # PENDING REQUESTS
    # ══════════════════════════════════════
    #This section has been removed!
    
    # ══════════════════════════════════════
    # ALL USERS
    # ══════════════════════════════════════
    st.markdown('<div class="section-title">All Users</div>', unsafe_allow_html=True)

    all_users = get_all_users()
    all_users = [u for u in all_users if u.get("role") != "admin"]

    if not all_users:
        st.info("No users yet.")
    else:
        uh1, uh2, uh3, uh4, uh5 = st.columns([3, 3, 1, 2, 1])
        for col, label in zip(
            [uh1, uh2, uh3, uh4, uh5],
            ["Name", "Email", "Status", "Password", "Action"]
        ):
            col.markdown(
                f"<span style='font-family:Libre Baskerville,serif; font-size:11px;"
                f"font-weight:700; letter-spacing:1px; text-transform:uppercase;"
                f"color:#5A6A85;'>{label}</span>",
                unsafe_allow_html=True
            )

        st.markdown("<hr style='margin:4px 0 8px 0; border-color:#D9D0BE;'>", unsafe_allow_html=True)

        for user in all_users:
            u1, u2, u3, u4, u5 = st.columns([3, 3, 1, 2, 1])

            with u1:
                st.markdown(f'<div class="user-name">{user["full_name"]}</div>', unsafe_allow_html=True)

            with u2:
                st.markdown(f'<div class="user-email">{user["email"]}</div>', unsafe_allow_html=True)

            with u3:
                status = user.get("status", "approved")
                badge_class = f"badge-{status}"
                st.markdown(f'<span class="{badge_class}">{status.capitalize()}</span>', unsafe_allow_html=True)

            with u4:
                with st.expander("View / Change"):
                    stored = user.get("password_plain", "–")
                    st.code(stored, language=None)
                    new_p = st.text_input(
                        "New password",
                        key=f"newp_{user['uid']}",
                        type="password",
                        placeholder="New password"
                    )
                    if st.button("Update", key=f"updp_{user['uid']}", width='stretch'):
                        if new_p:
                            change_user_password(user['email'], new_p, user['uid'])
                            st.success("Updated!")
                            st.rerun()
                        else:
                            st.error("Enter a new password.")

            with u5:
                st.write("")
                if st.button("Remove", key=f"remove_{user['uid']}", width='stretch'):
                    remove_user(user['uid'], user['email'])
                    st.warning(f"Removed {user['full_name']}")
                    st.rerun()

            st.markdown("<hr style='margin:4px 0; border-color:#EDE8DF;'>", unsafe_allow_html=True)

    # ══════════════════════════════════════
    # CREATE USER
    # ══════════════════════════════════════
    st.markdown('<div class="section-title">Create User</div>', unsafe_allow_html=True)

    with st.expander("➕  Create a new user directly", expanded=False):
        cc1, cc2, cc3, cc4 = st.columns([2, 2, 2, 1])

        with cc1:
            new_full_name = st.text_input("Full Name", key="create_full_name", placeholder="e.g. John Smith")
        with cc2:
            new_email = st.text_input("Email Address", key="create_email", placeholder="e.g. john@company.com")
        with cc3:
            new_password = st.text_input("Password", key="create_password", type="password", placeholder="Min. 6 chars")
        with cc4:
            st.write("")
            st.write("")
            create_clicked = st.button("Create User", key="create_user_btn", width='stretch')

        if create_clicked:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

            if not new_full_name or not new_email or not new_password:
                st.error("Please fill in all fields.")
            elif len(new_full_name.strip()) < 2:
                st.error("Please enter a valid full name.")
            elif any(char.isdigit() for char in new_full_name):
                st.error("Name should not contain numbers.")
            elif not re.match(email_pattern, new_email.strip()):
                st.error("Please enter a valid email address (e.g. name@example.com)")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                ok, msg = create_user_directly(
                    new_email.strip(), new_full_name.strip(), new_password
                )
                if ok:
                    st.success(f"✅ User {new_full_name} created successfully!")
                else:
                    st.error(msg)


# ══════════════════════════════════════════════════════
# MANAGE CUSTOMERS CONTENT  (from manage_customers.py::show_manage_customers)
# ══════════════════════════════════════════════════════
def _render_manage_customers():
    tab1, tab2 = st.tabs(["📋  Customer List", "➕  Add New Customer"])

    # ══════════════════════════════════════
    # TAB 1 — Customer List
    # ══════════════════════════════════════
    with tab1:
        customers = load_customers()

        if not customers:
            st.info("No customers added yet. Use the 'Add New Customer' tab to get started.")
        else:
            col_s, col_b = st.columns([3, 1])
            with col_s:
                search = st.text_input(
                    "🔍 Search",
                    placeholder="Search by name, area, industry...",
                    key="mc_search",
                    label_visibility="collapsed"
                )
            with col_b:
                filter_branch = st.selectbox(
                    "Branch", ["All"] + BRANCH_OPTIONS,
                    key="mc_filter_branch",
                    label_visibility="collapsed"
                )

            prev_search = st.session_state.get("_prev_mc_search", "")
            prev_branch = st.session_state.get("_prev_mc_branch", "All")

            if search != prev_search or filter_branch != prev_branch:
                st.session_state["mc_page"] = 0
                st.session_state["_prev_mc_search"] = search
                st.session_state["_prev_mc_branch"] = filter_branch

            filtered = customers
            if filter_branch != "All":
                filtered = [c for c in filtered if c.get("branch") == filter_branch]
            if search:
                s = search.lower()
                filtered = [c for c in filtered if
                            s in c.get("name", "").lower() or
                            s in c.get("area", "").lower() or
                            s in c.get("industry", "").lower()]

            ITEMS_PER_PAGE = 20
            page_num = st.session_state.get("mc_page", 0)
            total_filtered = len(filtered)
            total_pages = max(1, (total_filtered - 1) // ITEMS_PER_PAGE + 1)
            start = page_num * ITEMS_PER_PAGE
            end = start + ITEMS_PER_PAGE
            page_customers = filtered[start:end]

            st.markdown(
                f"<div style='font-family:Outfit,sans-serif;font-size:0.8rem;"
                f"color:#5A6A85;margin-bottom:0.8rem;'>"
                f"Showing {start+1}–{min(end, total_filtered)} of {total_filtered} customer(s)</div>",
                unsafe_allow_html=True
            )

            for c in page_customers:
                with st.container():
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        st.markdown(f"""
                        <div class="customer-row">
                            <div class="customer-name">{c.get('name', '—')}</div>
                            <div class="customer-meta">
                                <span class="badge">📍 {c.get('branch', '—')}</span>
                                <span class="badge">🗺 {c.get('area', '—')}</span>
                                <span class="badge">🏭 {c.get('industry', '—')}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c2:
                        with st.expander("Edit Details..."):
                            new_branch = st.selectbox("Branch", BRANCH_OPTIONS,
                                                       index=BRANCH_OPTIONS.index(c["branch"])
                                                       if c.get("branch") in BRANCH_OPTIONS else 0,
                                                       key=f"eb_{c['id']}")
                            new_area = st.text_input("Area", value=c.get("area", ""), key=f"ea_{c['id']}")
                            new_name = st.text_input("Name", value=c.get("name", ""), key=f"en_{c['id']}")
                            new_industry = st.text_input("Industry", value=c.get("industry", ""), key=f"ei_{c['id']}")
                            col_save, col_del = st.columns(2)
                            with col_save:
                                if st.button("💾 Save", key=f"save_{c['id']}", width='content'):
                                    ok, msg = update_customer(c["id"], new_branch, new_area, new_name, new_industry)
                                    if ok:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            with col_del:
                                if st.button("🗑 Delete", key=f"del_{c['id']}", width='content', type="primary"):
                                    ok, msg = delete_customer(c["id"], c.get("name", ""))
                                    if ok:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)

            col_prev, col_info, col_next = st.columns([1, 2, 1])
            with col_prev:
                if st.button("← Prev", disabled=(page_num == 0), key="mc_prev", width='content'):
                    st.session_state["mc_page"] = page_num - 1
                    st.rerun()
            with col_info:
                st.markdown(
                    f"<div style='text-align:center;font-family:Outfit,sans-serif;"
                    f"font-size:0.85rem;color:#6B7A99;padding-top:6px;'>"
                    f"Page {page_num+1} of {total_pages}</div>",
                    unsafe_allow_html=True
                )
            with col_next:
                if st.button("Next →", disabled=(page_num >= total_pages - 1), key="mc_next", width='content'):
                    st.session_state["mc_page"] = page_num + 1
                    st.rerun()

    # ══════════════════════════════════════
    # TAB 2 — Add New Customer
    # ══════════════════════════════════════
    with tab2:
        st.markdown('<div class="mc-section">Customer Details</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            new_branch = st.selectbox("Branch *", BRANCH_OPTIONS, key="nc_branch")
        with col2:
            new_area = st.text_input("Area *", placeholder="e.g. Coimbatore", key="nc_area")

        col3, col4 = st.columns(2)
        with col3:
            new_name = st.text_input("Customer Name *", placeholder="e.g. ABC Rubber Pvt Ltd", key="nc_name")
        with col4:
            new_industry = st.text_input("Industry *", placeholder="e.g. Rubber, Automotive", key="nc_industry")

        st.divider()

        if st.button("➕ Add Customer", type="primary", width='content', key="nc_submit"):
            if not new_area.strip() or not new_name.strip() or not new_industry.strip():
                st.error("⚠️ All fields are required.")
            else:
                ok, msg = add_customer(new_branch, new_area, new_name, new_industry)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.warning(msg)