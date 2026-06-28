import json
import time
from datetime import datetime
from urllib.parse import quote

import requests
import streamlit as st
import streamlit.components.v1 as components

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="EduMind AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Role config ───────────────────────────────────────────────────────────────
ROLE_CFG = {
    "Student": {
        "accent": "#6366f1", "accent2": "#818cf8", "glow": "rgba(99,102,241,0.35)",
        "grad": "linear-gradient(135deg,#4338ca,#6366f1)", "icon": "🎓", "label": "Student",
        "badge_bg": "rgba(99,102,241,0.15)", "badge_border": "rgba(99,102,241,0.4)",
    },
    "Faculty": {
        "accent": "#10b981", "accent2": "#34d399", "glow": "rgba(16,185,129,0.35)",
        "grad": "linear-gradient(135deg,#065f46,#10b981)", "icon": "🧑‍🏫", "label": "Faculty",
        "badge_bg": "rgba(16,185,129,0.15)", "badge_border": "rgba(16,185,129,0.4)",
    },
    "Admin": {
        "accent": "#f59e0b", "accent2": "#fbbf24", "glow": "rgba(245,158,11,0.35)",
        "grad": "linear-gradient(135deg,#92400e,#f59e0b)", "icon": "🛡️", "label": "Admin",
        "badge_bg": "rgba(245,158,11,0.15)", "badge_border": "rgba(245,158,11,0.4)",
    },
}

SUGGESTIONS = {
    "Student": [
        ("📋", "What are the exam guidelines?"),
        ("📅", "When does the academic year start?"),
        ("🏫", "Explain the code of conduct"),
        ("💰", "How do I apply for a scholarship?"),
    ],
    "Faculty": [
        ("📋", "Summarise the internal examination SOP"),
        ("💰", "What are the research grant deadlines?"),
        ("📜", "Outline faculty operational procedures"),
        ("📢", "How do I submit a circular?"),
    ],
    "Admin": [
        ("📚", "What documents are indexed?"),
        ("📢", "Show administrative circulars for Q1"),
        ("📋", "Summarise research grant SOP"),
        ("📝", "What are the operational procedure updates?"),
    ],
}

QUERY_CATEGORIES = ["Policy", "Exam", "Admin", "Finance", "Facility", "Research", "Other"]

# ── Session state ─────────────────────────────────────────────────────────────
def _default(k):
    """Return a fresh default value so mutable objects are not shared across reruns."""
    return {
        "token": None, "role": None, "username": None,
        "messages": [], "query_count": 0,
        "ingested_docs": [], "api_healthy": None,
        "quick_login": None, "query_cats": {},
        "chat_session_id": None,
    }[k]

_DEFAULT_KEYS = [
    "token", "role", "username", "messages", "query_count",
    "ingested_docs", "api_healthy", "quick_login", "query_cats",
    "chat_session_id",
]
for _k in _DEFAULT_KEYS:
    if _k not in st.session_state:
        st.session_state[_k] = _default(_k)

# Keep DEFAULTS dict available for logout() reset
DEFAULTS = {k: None for k in _DEFAULT_KEYS}  # used by logout() key list only

# ── Helpers ───────────────────────────────────────────────────────────────────
def cfg():
    return ROLE_CFG.get(st.session_state.role, ROLE_CFG["Student"])

def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}

def ts():
    return datetime.now().strftime("%H:%M")

def initials(name):
    parts = name.replace("_", " ").split()
    return "".join(p[0].upper() for p in parts[:2])

def check_api_health():
    try:
        r = requests.get(f"{API_BASE}/docs", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

def logout():
    for k in _DEFAULT_KEYS:
        st.session_state[k] = _default(k)
    st.rerun()

def categorise(query):
    q = query.lower()
    if any(w in q for w in ["exam", "test", "marks", "grade", "result"]): return "Exam"
    if any(w in q for w in ["fee", "scholarship", "grant", "finance", "fund"]): return "Finance"
    if any(w in q for w in ["hostel", "facility", "campus", "library", "cafeteria"]): return "Facility"
    if any(w in q for w in ["research", "paper", "publication", "journal"]): return "Research"
    if any(w in q for w in ["admin", "circular", "sop", "procedure", "upload"]): return "Admin"
    if any(w in q for w in ["policy", "rule", "conduct", "guideline", "regulation"]): return "Policy"
    return "Other"

# ── Global CSS ────────────────────────────────────────────────────────────────
def inject_css():
    accent = cfg()["accent"] if st.session_state.role else "#6366f1"
    accent2 = cfg()["accent2"] if st.session_state.role else "#818cf8"
    glow = cfg()["glow"] if st.session_state.role else "rgba(99,102,241,0.35)"
    grad = cfg()["grad"] if st.session_state.role else "linear-gradient(135deg,#4338ca,#6366f1)"

    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Reset & base ── */
html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif !important;
}}
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{
    padding: 1rem 2rem 1rem 2rem !important;
    max-width: 100% !important;
}}

/* ── Animated aurora background ── */
[data-testid="stAppViewContainer"] {{
    background: #060d1f !important;
    position: relative;
    overflow-x: hidden;
}}
[data-testid="stAppViewContainer"]::before,
[data-testid="stAppViewContainer"]::after {{
    content: '';
    position: fixed;
    border-radius: 50%;
    filter: blur(120px);
    opacity: 0.12;
    pointer-events: none;
    z-index: 0;
    animation: aurora1 18s ease-in-out infinite alternate;
}}
[data-testid="stAppViewContainer"]::before {{
    width: 700px; height: 700px;
    background: radial-gradient(circle, {accent} 0%, transparent 70%);
    top: -200px; left: -200px;
}}
[data-testid="stAppViewContainer"]::after {{
    width: 600px; height: 600px;
    background: radial-gradient(circle, #7c3aed 0%, transparent 70%);
    bottom: -150px; right: -150px;
    animation: aurora2 22s ease-in-out infinite alternate;
}}
@keyframes aurora1 {{
    0%   {{ transform: translate(0,0) scale(1); opacity:0.12; }}
    50%  {{ transform: translate(80px,60px) scale(1.15); opacity:0.18; }}
    100% {{ transform: translate(40px,120px) scale(0.95); opacity:0.10; }}
}}
@keyframes aurora2 {{
    0%   {{ transform: translate(0,0) scale(1); opacity:0.10; }}
    50%  {{ transform: translate(-60px,-80px) scale(1.2); opacity:0.16; }}
    100% {{ transform: translate(-30px,40px) scale(0.9); opacity:0.08; }}
}}

/* ── Stacking context fix ── */
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"],
.stMarkdown, .stButton, .stForm,
.stTextInput, .stFileUploader, .stTabs {{
    position: relative;
    z-index: 1;
}}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width:6px; height:6px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.12); border-radius:999px; }}
::-webkit-scrollbar-thumb:hover {{ background: rgba(255,255,255,0.22); }}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {{
    background: rgba(6,13,31,0.92) !important;
    backdrop-filter: blur(16px) !important;
    border-right: 1px solid rgba(255,255,255,0.07) !important;
}}
section[data-testid="stSidebar"] * {{ color: #e2e8f0 !important; }}
section[data-testid="stSidebar"] .stButton > button {{
    background: rgba(255,255,255,0.06) !important;
    color: #e2e8f0 !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
    width: 100% !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    transition: all 0.2s ease !important;
    padding: 0.5rem 0.75rem !important;
}}
section[data-testid="stSidebar"] .stButton > button:hover {{
    background: {accent} !important;
    border-color: {accent} !important;
    box-shadow: 0 0 18px {glow} !important;
    color: white !important;
}}

/* ── Inputs ── */
.stTextInput > div > div > input {{
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 12px !important;
    color: #f1f5f9 !important;
    font-size: 0.95rem !important;
    padding: 0.65rem 1rem !important;
    transition: all 0.2s ease !important;
}}
.stTextInput > div > div > input:focus {{
    border-color: {accent} !important;
    box-shadow: 0 0 0 3px {glow} !important;
    background: rgba(255,255,255,0.08) !important;
}}
.stTextInput > div > div > input::placeholder {{ color: rgba(255,255,255,0.3) !important; }}
.stTextInput label {{ color: rgba(255,255,255,0.6) !important; font-size:0.85rem !important; }}

/* ── Form submit button ── */
.stFormSubmitButton > button {{
    background: {grad} !important;
    border: none !important;
    border-radius: 12px !important;
    color: white !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.02em !important;
    padding: 0.7rem 1.5rem !important;
    width: 100% !important;
    transition: all 0.25s ease !important;
    box-shadow: 0 4px 24px {glow} !important;
}}
.stFormSubmitButton > button:hover {{
    transform: translateY(-1px) !important;
    box-shadow: 0 8px 32px {glow} !important;
    opacity: 0.92 !important;
}}

/* ── Regular primary button ── */
.stButton > button[kind="primary"] {{
    background: {grad} !important;
    border: none !important;
    border-radius: 10px !important;
    color: white !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 4px 20px {glow} !important;
}}
.stButton > button[kind="primary"]:hover {{
    transform: translateY(-1px) !important;
    box-shadow: 0 8px 28px {glow} !important;
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
    background: rgba(255,255,255,0.04) !important;
    border-radius: 14px !important;
    padding: 5px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    gap: 4px !important;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 10px !important;
    color: rgba(255,255,255,0.5) !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    padding: 0.4rem 1.1rem !important;
    transition: all 0.2s ease !important;
}}
.stTabs [aria-selected="true"] {{
    background: {grad} !important;
    color: white !important;
    box-shadow: 0 2px 12px {glow} !important;
}}

/* ── Progress bar ── */
.stProgress > div > div > div {{
    background: {grad} !important;
    border-radius: 999px !important;
}}
.stProgress > div > div {{
    background: rgba(255,255,255,0.08) !important;
    border-radius: 999px !important;
}}

/* ── Chat input ── */
[data-testid="stChatInput"] textarea {{
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 16px !important;
    color: #f1f5f9 !important;
    font-size: 0.95rem !important;
    transition: all 0.2s ease !important;
}}
[data-testid="stChatInput"] textarea:focus {{
    border-color: {accent} !important;
    box-shadow: 0 0 0 3px {glow} !important;
    background: rgba(255,255,255,0.09) !important;
}}
[data-testid="stChatInput"] button {{
    background: {grad} !important;
    border-radius: 10px !important;
    box-shadow: 0 2px 12px {glow} !important;
}}

/* ── Expander ── */
.streamlit-expanderHeader {{
    background: rgba(255,255,255,0.04) !important;
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: rgba(255,255,255,0.7) !important;
    font-size: 0.85rem !important;
}}
.streamlit-expanderContent {{
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-top: none !important;
    border-radius: 0 0 10px 10px !important;
}}

/* ── File uploader ── */
[data-testid="stFileUploader"] {{
    background: rgba(255,255,255,0.03) !important;
    border: 2px dashed rgba(255,255,255,0.15) !important;
    border-radius: 16px !important;
    transition: all 0.2s ease !important;
    padding: 1.5rem !important;
}}
[data-testid="stFileUploader"]:hover {{
    border-color: {accent} !important;
    background: rgba(99,102,241,0.05) !important;
}}
[data-testid="stFileUploader"] * {{ color: rgba(255,255,255,0.6) !important; }}

/* ── Alerts / toast ── */
.stAlert {{
    background: rgba(255,255,255,0.05) !important;
    border-radius: 12px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #e2e8f0 !important;
}}
[data-testid="stSuccessAlert"] {{
    border-color: rgba(16,185,129,0.4) !important;
    background: rgba(16,185,129,0.08) !important;
}}
[data-testid="stErrorAlert"] {{
    border-color: rgba(239,68,68,0.4) !important;
    background: rgba(239,68,68,0.08) !important;
}}
[data-testid="stInfoAlert"] {{
    border-color: rgba(99,102,241,0.4) !important;
    background: rgba(99,102,241,0.08) !important;
}}
[data-testid="stWarningAlert"] {{
    border-color: rgba(245,158,11,0.4) !important;
    background: rgba(245,158,11,0.08) !important;
}}

/* ── Download button ── */
[data-testid="stDownloadButton"] > button {{
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
    font-size: 0.85rem !important;
    width: 100% !important;
    transition: all 0.2s ease !important;
}}
[data-testid="stDownloadButton"] > button:hover {{
    background: rgba(255,255,255,0.1) !important;
    border-color: {accent} !important;
}}

/* ── Divider ── */
hr {{ border-color: rgba(255,255,255,0.08) !important; }}

/* ── Animations ── */
@keyframes float {{
    0%,100% {{ transform: translateY(0px); }}
    50%      {{ transform: translateY(-8px); }}
}}
@keyframes slideUp {{
    from {{ opacity:0; transform: translateY(14px); }}
    to   {{ opacity:1; transform: translateY(0); }}
}}
@keyframes fadeIn {{
    from {{ opacity:0; }}
    to   {{ opacity:1; }}
}}
@keyframes pulse-ring {{
    0%   {{ box-shadow: 0 0 0 0 rgba(34,197,94,0.5); }}
    70%  {{ box-shadow: 0 0 0 8px rgba(34,197,94,0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(34,197,94,0); }}
}}
@keyframes typingBounce {{
    0%,80%,100% {{ transform: translateY(0); opacity:0.4; }}
    40%         {{ transform: translateY(-6px); opacity:1; }}
}}
@keyframes loginFloat {{
    0%,100% {{ transform: translateY(0px) rotate(0deg); }}
    33%     {{ transform: translateY(-6px) rotate(1deg); }}
    66%     {{ transform: translateY(-3px) rotate(-0.5deg); }}
}}

/* ── Message bubbles ── */
.msg-wrap {{
    animation: slideUp 0.3s ease forwards;
    margin-bottom: 0.75rem;
}}
.msg-row {{
    display: flex; gap: 10px; align-items: flex-end;
}}
.msg-row.user {{ flex-direction: row-reverse; }}
.avatar-circle {{
    width: 32px; height: 32px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.72rem; font-weight: 700; flex-shrink: 0;
    letter-spacing: 0.02em;
}}
.msg-bubble {{
    max-width: 68%; padding: 0.75rem 1rem;
    font-size: 0.92rem; line-height: 1.6;
    position: relative; word-wrap: break-word;
}}
.msg-bubble.user {{
    background: {grad};
    color: white; border-radius: 18px 18px 4px 18px;
    box-shadow: 0 4px 20px {glow};
}}
.msg-bubble.assistant {{
    background: rgba(255,255,255,0.06);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,255,0.1);
    border-left: 3px solid {accent};
    color: #e2e8f0; border-radius: 18px 18px 18px 4px;
}}
.msg-footer {{
    display: flex; align-items: center; gap: 8px;
    margin-top: 5px; font-size: 0.7rem; color: rgba(255,255,255,0.3);
}}
.msg-row.user .msg-footer {{ flex-direction: row-reverse; }}

/* ── Source pills ── */
.source-pills {{ display:flex; flex-wrap:wrap; gap:5px; margin-top:8px; }}
.source-pill {{
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 999px; padding: 3px 10px;
    font-size: 0.72rem; color: rgba(255,255,255,0.55);
    cursor: default; transition: all 0.15s;
}}
.source-pill:hover {{
    background: {accent}22;
    border-color: {accent};
    color: {accent2};
}}

/* ── Typing indicator ── */
.typing-wrap {{
    animation: fadeIn 0.3s ease;
    display: flex; gap: 10px; align-items: flex-end; margin-bottom:0.75rem;
}}
.typing-bubble {{
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    border-left: 3px solid {accent};
    border-radius: 18px 18px 18px 4px;
    padding: 0.75rem 1.1rem; display:flex; gap:5px; align-items:center;
}}
.typing-dot {{
    width:7px; height:7px; border-radius:50%;
    background: {accent}; opacity:0.4;
    animation: typingBounce 1.2s ease-in-out infinite;
}}
.typing-dot:nth-child(2) {{ animation-delay: 0.2s; }}
.typing-dot:nth-child(3) {{ animation-delay: 0.4s; }}

/* ── Streaming cursor ── */
.cursor {{
    display:inline-block; width:7px; height:1.05em;
    background:{accent}; margin-left:2px; vertical-align:text-bottom;
    animation: blink 1s steps(2,start) infinite;
}}
@keyframes blink {{ 0%,50% {{ opacity:1; }} 50.01%,100% {{ opacity:0; }} }}

/* ── Suggestion chips ── */
.chip-btn {{
    display: inline-flex; align-items:center; gap:6px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 999px; padding: 6px 14px;
    font-size: 0.82rem; color: rgba(255,255,255,0.65);
    cursor: pointer; transition: all 0.2s ease;
    white-space: nowrap;
}}
.chip-btn:hover {{
    background: {accent}22;
    border-color: {accent};
    color: {accent2};
    box-shadow: 0 0 14px {glow};
    transform: translateY(-1px);
}}

/* ── Stat cards ── */
.stat-card {{
    background: rgba(255,255,255,0.04);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 1.2rem 1.4rem;
    transition: all 0.2s ease;
}}
.stat-card:hover {{
    background: rgba(255,255,255,0.07);
    border-color: {accent}55;
    box-shadow: 0 4px 24px {glow};
    transform: translateY(-2px);
}}
.stat-num {{
    font-size: 2.2rem; font-weight: 800;
    background: {grad}; -webkit-background-clip: text;
    -webkit-text-fill-color: transparent; background-clip: text;
    line-height: 1.1;
}}
.stat-label {{ font-size: 0.78rem; color: rgba(255,255,255,0.45); margin-top:4px; }}

/* ── Section title ── */
.section-title {{
    font-size: 1.1rem; font-weight: 700; color: #f1f5f9;
    padding-left: 0.8rem;
    border-left: 3px solid {accent};
    margin: 1.2rem 0 0.8rem;
}}

/* ── Glass card ── */
.glass-card {{
    background: rgba(255,255,255,0.04);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px; padding: 1.4rem 1.6rem;
}}

/* ── Health pulse ── */
.health-live {{
    display:inline-block; width:10px; height:10px; border-radius:50%;
    background:#22c55e; animation: pulse-ring 2s ease-out infinite;
    margin-right: 6px; vertical-align: middle;
}}
.health-dead {{
    display:inline-block; width:10px; height:10px; border-radius:50%;
    background:#ef4444; margin-right:6px; vertical-align:middle;
}}

/* ── Empty state ── */
.empty-state {{
    text-align: center; padding: 4rem 2rem; animation: fadeIn 0.5s ease;
}}
.empty-icon {{
    font-size: 4rem; animation: float 4s ease-in-out infinite;
    display: block; margin-bottom: 1rem;
}}
.empty-title {{
    font-size: 1.4rem; font-weight: 700;
    background: {grad}; -webkit-background-clip: text;
    -webkit-text-fill-color: transparent; background-clip: text;
    margin-bottom: 0.5rem;
}}
.empty-sub {{ font-size: 0.9rem; color: rgba(255,255,255,0.4); }}

/* ── Doc row ── */
.doc-row {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.75rem 1rem; border-radius: 12px; margin: 5px 0;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    font-size: 0.88rem; color: #e2e8f0;
    transition: all 0.15s ease;
}}
.doc-row:hover {{
    background: rgba(255,255,255,0.06);
    border-color: {accent}44;
}}
.doc-meta {{ font-size:0.75rem; color: rgba(255,255,255,0.35); }}

/* ── User table ── */
.user-row {{
    display: grid; grid-template-columns: 1fr 120px 90px;
    align-items: center; gap:1rem;
    padding: 0.75rem 1rem; border-radius: 12px; margin: 4px 0;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    transition: all 0.15s ease;
}}
.user-row:hover {{ background: rgba(255,255,255,0.06); }}
.user-row.header {{
    background: transparent; border-color: transparent;
    font-size:0.72rem; font-weight:600;
    color: rgba(255,255,255,0.35); letter-spacing: 0.08em;
    text-transform: uppercase;
}}
.avatar-sm {{
    width:28px; height:28px; border-radius:50%;
    display:inline-flex; align-items:center; justify-content:center;
    font-size:0.68rem; font-weight:700; margin-right:8px;
    vertical-align: middle;
}}
.role-pill {{
    display:inline-block; padding:3px 10px; border-radius:999px;
    font-size:0.75rem; font-weight:600;
}}

/* ── Login page overrides ── */
.login-outer {{
    display:flex; flex-direction:column; align-items:center;
    justify-content:center; min-height:82vh; padding:2rem;
}}
.login-card {{
    width:100%; max-width:440px;
    background: rgba(255,255,255,0.045);
    backdrop-filter: blur(24px);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 24px; padding: 2.8rem 3rem;
    animation: loginFloat 6s ease-in-out infinite;
    box-shadow: 0 24px 80px rgba(0,0,0,0.5), 0 0 60px rgba(99,102,241,0.1);
}}
.login-logo {{
    text-align:center; font-size:3.2rem;
    animation: float 3s ease-in-out infinite;
    margin-bottom:0.3rem;
}}
.login-brand {{
    text-align:center; font-size:1.8rem; font-weight:800;
    background: linear-gradient(135deg,#a5b4fc,#818cf8,#6366f1);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text; margin-bottom:0.25rem;
}}
.login-sub {{
    text-align:center; color:rgba(255,255,255,0.4);
    font-size:0.88rem; margin-bottom:2rem;
}}
.quick-login-label {{
    font-size:0.78rem; color:rgba(255,255,255,0.35);
    text-align:center; margin:1.2rem 0 0.6rem;
    letter-spacing:0.06em; text-transform:uppercase;
}}
.quick-pill {{
    display:inline-flex; align-items:center; gap:5px;
    padding:5px 14px; border-radius:999px;
    font-size:0.8rem; font-weight:600; cursor:pointer;
    border: 1px solid; transition: all 0.2s ease;
}}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar():
    c = cfg()
    with st.sidebar:
        st.markdown(f"""
        <div style="padding:0.5rem 0 1rem;">
            <div style="font-size:1.3rem;font-weight:800;
                background:linear-gradient(135deg,#a5b4fc,{c['accent']});
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                background-clip:text;">EduMind AI</div>
            <div style="font-size:0.72rem;color:rgba(255,255,255,0.3);
                letter-spacing:0.06em;text-transform:uppercase;margin-top:2px;">
                Institutional Knowledge Platform</div>
        </div>
        """, unsafe_allow_html=True)

        # Avatar card
        ini = initials(st.session_state.username)
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);
            border-radius:16px;padding:1rem;margin-bottom:1rem;text-align:center;">
            <div style="width:52px;height:52px;border-radius:50%;
                background:{c['grad']};
                display:flex;align-items:center;justify-content:center;
                font-size:1rem;font-weight:800;color:white;margin:0 auto 0.6rem;
                box-shadow:0 4px 20px {c['glow']};">
                {ini}
            </div>
            <div style="font-weight:600;font-size:0.95rem;color:#f1f5f9;">
                {st.session_state.username}</div>
            <div style="margin-top:5px;">
                <span style="background:{c['badge_bg']};border:1px solid {c['badge_border']};
                    border-radius:999px;padding:3px 12px;font-size:0.73rem;
                    font-weight:600;color:{c['accent']};">
                    {c['icon']} {c['label']}
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Health indicator
        if st.session_state.api_healthy is None:
            st.session_state.api_healthy = check_api_health()
        ok = st.session_state.api_healthy
        dot = "health-live" if ok else "health-dead"
        label = "API Online" if ok else "API Offline"
        st.markdown(
            f'<div style="font-size:0.82rem;color:rgba(255,255,255,0.5);margin-bottom:0.5rem;">'
            f'<span class="{dot}"></span>{label}</div>',
            unsafe_allow_html=True,
        )
        if st.button("↻  Refresh", key="sb_refresh"):
            st.session_state.api_healthy = check_api_health()
            st.rerun()

        st.divider()

        # Stats row
        qc = st.session_state.query_count
        mc = len(st.session_state.messages)
        dc = len(st.session_state.ingested_docs)
        cols = st.columns(2)
        with cols[0]:
            st.markdown(f"""
            <div class="stat-card" style="padding:0.8rem;text-align:center;">
                <div class="stat-num" style="font-size:1.5rem;">{qc}</div>
                <div class="stat-label">Queries</div>
            </div>""", unsafe_allow_html=True)
        with cols[1]:
            val = dc if st.session_state.role == "Admin" else mc
            lbl = "Docs" if st.session_state.role == "Admin" else "Messages"
            st.markdown(f"""
            <div class="stat-card" style="padding:0.8rem;text-align:center;">
                <div class="stat-num" style="font-size:1.5rem;">{val}</div>
                <div class="stat-label">{lbl}</div>
            </div>""", unsafe_allow_html=True)

        st.divider()

        # Actions
        if st.button("🗑️  Clear Chat", key="sb_clear"):
            st.session_state.messages = []
            st.session_state.query_count = 0
            st.session_state.query_cats = {}
            st.rerun()

        if st.session_state.messages:
            chat_text = "\n\n".join(
                f"[{m['role'].upper()} {m.get('time','')}]\n{m['content']}"
                for m in st.session_state.messages
            )
            st.download_button(
                "⬇️  Export Chat",
                data=chat_text,
                file_name=f"edumind_chat_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                key="sb_export",
            )

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("🚪  Sign Out", key="sb_signout"):
            logout()

# ── Login ─────────────────────────────────────────────────────────────────────
def show_login():
    # Quick-login handler
    if st.session_state.quick_login:
        creds = {
            "student": ("student_test", "Student@123"),
            "faculty": ("faculty_test", "Faculty@123"),
            "admin":   ("admin_test",   "Admin@123"),
        }
        role_key = st.session_state.quick_login
        st.session_state.quick_login = None
        uname, pwd = creds[role_key]
        try:
            r = requests.post(f"{API_BASE}/api/auth/login",
                              json={"username": uname, "password": pwd}, timeout=10)
            if r.status_code == 200:
                d = r.json()
                st.session_state.token    = d["access_token"]
                st.session_state.role     = d["role"]
                st.session_state.username = uname
                st.session_state.messages = []
                st.rerun()
        except Exception:
            pass

    # Render brand header + form together inside the centre column
    # (Previously the card HTML was outside the columns which pushed the form below
    # the 82 vh card and off-screen.  Putting everything inside mid column fixes it.)
    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        st.markdown("""
        <div class="login-outer" style="min-height:unset;padding:3rem 0 1rem;">
            <div class="login-card">
                <div class="login-logo">🎓</div>
                <div class="login-brand">EduMind AI</div>
                <div class="login-sub">Institutional Agentic Knowledge Platform</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Sign In  →", use_container_width=True)

        if submitted:
            if not username or not password:
                st.warning("Please fill in both fields.")
            else:
                with st.spinner("Authenticating…"):
                    try:
                        r = requests.post(f"{API_BASE}/api/auth/login",
                                          json={"username": username, "password": password},
                                          timeout=10)
                        if r.status_code == 200:
                            d = r.json()
                            st.session_state.token    = d["access_token"]
                            st.session_state.role     = d["role"]
                            st.session_state.username = username
                            st.session_state.messages = []
                            st.rerun()
                        else:
                            st.error(r.json().get("detail", "Login failed"))
                    except requests.exceptions.ConnectionError:
                        st.error("Cannot reach API server. Make sure FastAPI is running on port 8000.")

        st.markdown("<div class='quick-login-label'>Quick demo access</div>", unsafe_allow_html=True)
        q1, q2, q3 = st.columns(3)
        with q1:
            if st.button("🎓 Student", use_container_width=True, key="ql_s"):
                st.session_state.quick_login = "student"
                st.rerun()
        with q2:
            if st.button("🧑‍🏫 Faculty", use_container_width=True, key="ql_f"):
                st.session_state.quick_login = "faculty"
                st.rerun()
        with q3:
            if st.button("🛡️ Admin", use_container_width=True, key="ql_a"):
                st.session_state.quick_login = "admin"
                st.rerun()

# ── Chat ──────────────────────────────────────────────────────────────────────
def show_chat():
    c = cfg()

    # Empty state
    if not st.session_state.messages:
        st.markdown(f"""
        <div class="empty-state">
            <span class="empty-icon">💬</span>
            <div class="empty-title">Ask me anything</div>
            <div class="empty-sub">I have access to institutional documents, policies, and procedures.</div>
        </div>
        """, unsafe_allow_html=True)

        # Suggestion chips
        st.markdown("<div style='display:flex;flex-wrap:wrap;gap:8px;justify-content:center;padding-bottom:1.5rem;'>", unsafe_allow_html=True)
        chips = SUGGESTIONS.get(st.session_state.role, [])
        cols = st.columns(len(chips))
        for i, (icon, text) in enumerate(chips):
            with cols[i]:
                if st.button(f"{icon} {text}", key=f"chip_{i}", use_container_width=True):
                    st.session_state["_pending"] = text
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        # Render messages
        for msg in st.session_state.messages:
            is_user  = msg["role"] == "user"
            side     = "user" if is_user else "assistant"
            bubble   = "user" if is_user else "assistant"
            ini      = initials(st.session_state.username) if is_user else "AI"
            av_bg    = c["grad"] if is_user else "rgba(255,255,255,0.1)"
            av_color = "white"
            time_str = msg.get("time", "")

            sources_html = ""
            if msg.get("sources"):
                pills = "".join(
                    f'<span class="source-pill">📎 {s}</span>'
                    for s in msg["sources"]
                )
                sources_html = f'<div class="source-pills">{pills}</div>'

            st.markdown(f"""
            <div class="msg-wrap">
                <div class="msg-row {side}">
                    <div class="avatar-circle" style="background:{av_bg};color:{av_color};
                        box-shadow:0 2px 12px {c['glow'] if is_user else 'rgba(0,0,0,0.3)'};">
                        {ini}
                    </div>
                    <div>
                        <div class="msg-bubble {bubble}">{msg['content']}</div>
                        {sources_html}
                        <div class="msg-footer">{time_str}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Chat input
    pending = st.session_state.get("_pending", None)
    if pending:
        del st.session_state["_pending"]
    prompt  = st.chat_input("Ask about policies, procedures, resources…")
    if pending and not prompt:
        prompt = pending

    if prompt:
        now = ts()
        st.session_state.messages.append({"role": "user", "content": prompt, "time": now})
        st.session_state.query_count += 1
        cat = categorise(prompt)
        st.session_state.query_cats[cat] = st.session_state.query_cats.get(cat, 0) + 1

        # Typing indicator
        placeholder = st.empty()
        placeholder.markdown(f"""
        <div class="typing-wrap">
            <div class="avatar-circle" style="background:rgba(255,255,255,0.1);color:white;">AI</div>
            <div class="typing-bubble">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Stream the answer LIVE from the SSE endpoint. The full RAG pipeline
        # can take 60s+ on first/cold queries; streaming resets the read clock
        # on every chunk, so a generous per-read timeout never trips while the
        # backend is actively producing tokens. (The old non-streaming POST used
        # timeout=15 and raised ReadTimeout even though the backend succeeded.)
        sid = st.session_state.get("chat_session_id") or ""
        url = (f"{API_BASE}/api/chat/auth/stream"
               f"?q={quote(prompt)}&session_id={quote(sid)}")
        answer_buf = ""
        sources    = []
        try:
            with requests.get(url, headers=auth_headers(), stream=True,
                              timeout=(10, 300)) as resp:
                if resp.status_code == 401:
                    placeholder.empty()
                    st.error("Session expired — please sign in again.")
                    time.sleep(1); logout()
                elif resp.status_code != 200:
                    placeholder.empty()
                    st.error(f"API error ({resp.status_code}).")
                else:
                    for raw in resp.iter_lines(decode_unicode=True):
                        if not raw or not raw.startswith("data: "):
                            continue
                        data = raw[6:]
                        if data == "[DONE]":
                            break
                        if data.startswith("[META]"):
                            try:
                                meta    = json.loads(data[6:])
                                sources = meta.get("source_documents", [])
                                if meta.get("session_id"):
                                    st.session_state.chat_session_id = meta["session_id"]
                            except Exception:
                                pass
                            continue
                        if data.startswith("[ERROR"):
                            answer_buf += "\n\n_[Error generating response]_"
                            break
                        # Normal token — restore escaped newlines, render live.
                        answer_buf += data.replace("\\n", "\n")
                        placeholder.markdown(
                            f'<div class="msg-bubble assistant">{answer_buf}'
                            f'<span class="cursor"></span></div>',
                            unsafe_allow_html=True,
                        )
            placeholder.empty()
            if answer_buf:
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer_buf,
                     "sources": sources, "time": ts()}
                )
        except requests.exceptions.ConnectionError:
            placeholder.empty()
            st.error("Cannot reach API server.")
        except requests.exceptions.ReadTimeout:
            placeholder.empty()
            st.error("The model took too long to respond. Please try again.")
        st.rerun()

# ── Faculty analytics ─────────────────────────────────────────────────────────
def show_analytics():
    import pandas as pd

    c = cfg()
    st.markdown('<div class="section-title">Session Analytics</div>', unsafe_allow_html=True)

    qc = st.session_state.query_count
    mc = len(st.session_state.messages)
    ac = sum(1 for m in st.session_state.messages if m["role"] == "assistant")

    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown(f'<div class="stat-card"><div class="stat-num">{qc}</div>'
                    f'<div class="stat-label">Queries sent</div></div>', unsafe_allow_html=True)
    with s2:
        st.markdown(f'<div class="stat-card"><div class="stat-num">{ac}</div>'
                    f'<div class="stat-label">AI responses</div></div>', unsafe_allow_html=True)
    with s3:
        st.markdown(f'<div class="stat-card"><div class="stat-num">{mc}</div>'
                    f'<div class="stat-label">Total messages</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">Query breakdown by category</div>', unsafe_allow_html=True)

    # Build chart data — pad all categories so chart always renders
    chart_data = {cat: st.session_state.query_cats.get(cat, 0) for cat in QUERY_CATEGORIES}
    df = pd.DataFrame.from_dict({"Queries": chart_data})
    st.bar_chart(df, color=c["accent"], height=220, use_container_width=True)

    # Timeline
    if st.session_state.messages:
        st.markdown('<div class="section-title">Query timeline</div>', unsafe_allow_html=True)
        queries = [(m["content"], m.get("time","")) for m in st.session_state.messages if m["role"] == "user"]
        for i, (q, t) in enumerate(queries, 1):
            st.markdown(f"""
            <div class="doc-row">
                <div style="display:flex;align-items:center;gap:10px;">
                    <div style="width:24px;height:24px;border-radius:50%;
                        background:{c['grad']};display:flex;align-items:center;
                        justify-content:center;font-size:0.7rem;font-weight:700;
                        color:white;flex-shrink:0;">{i}</div>
                    <span>{q}</span>
                </div>
                <span class="doc-meta">{t}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center;padding:3rem;color:rgba(255,255,255,0.3);font-size:0.9rem;">
            No queries yet. Send a message in the Chat tab.
        </div>
        """, unsafe_allow_html=True)

# ── Admin ingestor ────────────────────────────────────────────────────────────
def show_ingestor():
    c = cfg()
    st.markdown('<div class="section-title">SOP / Circular Document Ingestor</div>', unsafe_allow_html=True)
    st.markdown(
        "<p style='color:rgba(255,255,255,0.45);font-size:0.9rem;margin-bottom:1.2rem;'>"
        "Upload institutional PDFs to index them into the knowledge base.</p>",
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Drag & drop PDFs here, or click to browse",
        type=["pdf"], accept_multiple_files=True, label_visibility="visible",
    )

    if uploaded:
        st.markdown(f"""
        <div style="margin:0.8rem 0;font-size:0.85rem;color:rgba(255,255,255,0.5);">
            {len(uploaded)} file(s) selected
        </div>
        """, unsafe_allow_html=True)
        for f in uploaded:
            kb = f.size / 1024
            st.markdown(f"""
            <div class="doc-row">
                <div>📄 <strong style="color:#f1f5f9;">{f.name}</strong></div>
                <span class="doc-meta">{kb:.1f} KB</span>
            </div>
            """, unsafe_allow_html=True)

        if st.button("⬆️  Ingest All Documents", type="primary", key="ingest_btn"):
            bar = st.progress(0, text="Preparing…")
            for i, f in enumerate(uploaded):
                bar.progress((i) / len(uploaded), text=f"Ingesting {f.name}…")
                try:
                    r = requests.post(
                        f"{API_BASE}/api/upload",
                        files={"file": (f.name, f.getvalue(), "application/pdf")},
                        headers=auth_headers(), timeout=30,
                    )
                    if r.status_code == 200:
                        st.session_state.ingested_docs.append(
                            {"name": f.name, "size": f.size, "time": ts()}
                        )
                        st.success(f"✅  {f.name} ingested")
                    else:
                        st.error(f"❌  {f.name} — {r.json().get('detail','failed')}")
                except requests.exceptions.ConnectionError:
                    st.error("Cannot reach API server.")
            bar.progress(1.0, text="Done!")

    # Registry
    if st.session_state.ingested_docs:
        st.markdown('<div class="section-title" style="margin-top:2rem;">Ingested documents</div>',
                    unsafe_allow_html=True)
        for doc in st.session_state.ingested_docs:
            kb = doc["size"] / 1024
            st.markdown(f"""
            <div class="doc-row">
                <div style="display:flex;align-items:center;gap:10px;">
                    <div style="width:32px;height:32px;border-radius:8px;
                        background:{c['grad']};display:flex;align-items:center;
                        justify-content:center;font-size:0.9rem;">📄</div>
                    <div>
                        <div style="color:#f1f5f9;font-weight:500;">{doc['name']}</div>
                        <div class="doc-meta">{kb:.1f} KB · {doc['time']}</div>
                    </div>
                </div>
                <span style="background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.3);
                    border-radius:999px;padding:3px 10px;font-size:0.72rem;
                    color:#10b981;font-weight:600;">Indexed</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center;padding:3rem;color:rgba(255,255,255,0.25);font-size:0.9rem;">
            No documents ingested yet in this session.
        </div>
        """, unsafe_allow_html=True)

# ── Admin user directory ──────────────────────────────────────────────────────
def show_user_directory():
    st.markdown('<div class="section-title">User Directory</div>', unsafe_allow_html=True)

    users = [
        ("student_test", "Student", "#6366f1", "rgba(99,102,241,0.15)", "rgba(99,102,241,0.35)"),
        ("faculty_test", "Faculty", "#10b981", "rgba(16,185,129,0.15)", "rgba(16,185,129,0.35)"),
        ("admin_test",   "Admin",   "#f59e0b", "rgba(245,158,11,0.15)",  "rgba(245,158,11,0.35)"),
    ]

    st.markdown("""
    <div class="user-row header">
        <div>USER</div><div>ROLE</div><div>STATUS</div>
    </div>
    """, unsafe_allow_html=True)

    for uname, role, accent, bg, border in users:
        ini = initials(uname)
        grad = ROLE_CFG[role]["grad"]
        st.markdown(f"""
        <div class="user-row">
            <div style="display:flex;align-items:center;">
                <div class="avatar-sm" style="background:{grad};color:white;">{ini}</div>
                <span style="color:#f1f5f9;font-weight:500;">{uname}</span>
            </div>
            <div>
                <span class="role-pill" style="background:{bg};border:1px solid {border};color:{accent};">
                    {ROLE_CFG[role]['icon']} {role}
                </span>
            </div>
            <div>
                <span style="color:#22c55e;font-size:0.82rem;font-weight:600;">● Active</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ── Page routers ──────────────────────────────────────────────────────────────
def page_student():
    render_sidebar()
    st.markdown(f"""
    <div style="padding:0.5rem 0 1rem;">
        <h2 style="color:#f1f5f9;font-weight:700;margin:0;">Knowledge Assistant</h2>
        <p style="color:rgba(255,255,255,0.35);font-size:0.88rem;margin:4px 0 0;">
            Searching public institutional documents</p>
    </div>
    """, unsafe_allow_html=True)
    show_chat()

def page_faculty():
    render_sidebar()
    tab1, tab2 = st.tabs(["💬  Chat", "📊  Analytics"])
    with tab1:
        show_chat()
    with tab2:
        show_analytics()

def page_admin():
    render_sidebar()
    tab1, tab2, tab3 = st.tabs(["💬  Chat", "📥  Document Ingestor", "👥  User Directory"])
    with tab1:
        show_chat()
    with tab2:
        show_ingestor()
    with tab3:
        show_user_directory()

# ── Main ──────────────────────────────────────────────────────────────────────
inject_css()

if st.session_state.token is None:
    show_login()
elif st.session_state.role == "Admin":
    page_admin()
elif st.session_state.role == "Faculty":
    page_faculty()
else:
    page_student()
