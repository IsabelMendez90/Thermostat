import streamlit as st

# =========================================================
# Page config
# =========================================================
st.set_page_config(page_title="Ecobee-style UI (Streamlit)", layout="centered")

# =========================================================
# Session state defaults
# =========================================================
if "view" not in st.session_state:
    st.session_state.view = "Home"   # Home | Dial | Reports | Menu | Comfort

if "indoor_temp" not in st.session_state:
    st.session_state.indoor_temp = 78
if "humidity" not in st.session_state:
    st.session_state.humidity = 51
if "air_quality" not in st.session_state:
    st.session_state.air_quality = "Fair"
if "hvac_mode" not in st.session_state:
    st.session_state.hvac_mode = "Heat"  # Heat / Cool / Auto / Off

if "comfort" not in st.session_state:
    st.session_state.comfort = "Away"  # Home / Away / Sleep / Morning

if "setpoints" not in st.session_state:
    st.session_state.setpoints = {
        "Home": 73,
        "Away": 64,
        "Sleep": 66,
        "Morning": 70,
    }

# =========================================================
# Convenience
# =========================================================
def current_setpoint() -> int:
    return int(st.session_state.setpoints.get(st.session_state.comfort, 66))

def set_current_setpoint(v: int):
    v = max(45, min(90, int(v)))
    st.session_state.setpoints[st.session_state.comfort] = v

def comfort_icon(name: str) -> str:
    return {
        "Home": "🏠",
        "Away": "🚶",
        "Sleep": "🌙",
        "Morning": "☀️",
    }.get(name, "✨")

# =========================================================
# Query-param router (HTML links can switch views cleanly)
# =========================================================
def _get_qp(name: str):
    # Streamlit versions differ; support both
    try:
        v = st.query_params.get(name, None)
        if isinstance(v, list):
            v = v[0] if v else None
        return v
    except Exception:
        return st.experimental_get_query_params().get(name, [None])[0]

qp_view = _get_qp("view")
if qp_view in {"Home", "Dial", "Reports", "Menu", "Comfort"}:
    st.session_state.view = qp_view

# =========================================================
# Styling (ecobee-ish)
# =========================================================
BASE_BG = "#111827"      # deep navy
CARD_BG = "#1F2937"      # slate
MUTED = "#9CA3AF"        # gray text
WHITE = "#F9FAFB"
ACCENT = "#F97316"       # orange
TEAL = "#22C55E"         # ecobee-ish green

st.markdown(
    f"""
    <style>
      /* App background */
      .stApp {{
        background: radial-gradient(1200px 800px at 50% 30%, #0B1220 0%, {BASE_BG} 55%, #0A1020 100%);
        color: {WHITE};
      }}

      /* Hide Streamlit chrome */
      #MainMenu {{visibility: hidden;}}
      footer {{visibility: hidden;}}
      header {{visibility: hidden;}}

      /* Mobile-ish frame */
      .frame {{
        max-width: 430px;
        margin: 0 auto;
        padding: 18px 14px 92px 14px; /* leave room for bottom nav */
      }}

      /* Top bar */
      .topbar {{
        display:flex; align-items:center; justify-content:space-between;
        padding: 8px 2px 14px 2px;
      }}
      .topbar .title {{
        font-size: 22px; font-weight: 600; letter-spacing: 0.2px;
      }}
      .iconbtn {{
        width: 38px; height: 38px; border-radius: 999px;
        display:flex; align-items:center; justify-content:center;
        border: 1px solid rgba(255,255,255,0.12);
        color: {WHITE};
        opacity: 0.95;
      }}

      /* Status row */
      .statusrow {{
        display:flex; gap: 18px; justify-content:center; align-items:center;
        color: {MUTED};
        font-size: 15px;
        margin-top: 10px;
      }}
      .statusrow .chip {{
        display:flex; gap: 8px; align-items:center;
      }}

      /* Big temp */
      .bigtemp {{
        text-align:center;
        font-size: 120px;
        line-height: 1.0;
        font-weight: 300;
        margin: 14px 0 8px 0;
        color: {WHITE};
      }}

      /* Comfort line */
      .comfortline {{
        text-align:center;
        color: {MUTED};
        font-size: 20px;
        display:flex;
        justify-content:center;
        gap: 10px;
        align-items:center;
      }}

      /* Clickable setpoint pill as an <a> link (NO Streamlit button) */
      .pilllink {{
        width: 140px;
        margin: 18px auto 0 auto;
        display: block;
        text-align: center;
        border-radius: 999px;
        border: 2px solid {ACCENT};
        background: rgba(249,115,22,0.06);
        color: {ACCENT};
        font-weight: 800;
        letter-spacing: 0.4px;
        padding: 10px 0;
        text-decoration: none;
        cursor: pointer;
        font-size: 20px;
      }}
      .pilllink:hover {{
        filter: brightness(1.08);
      }}

      /* Card list (menu / comfort settings) */
      .card {{
        background: rgba(31,41,55,0.9);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        padding: 14px 14px;
      }}
      .row {{
        display:flex; justify-content:space-between; align-items:center;
        padding: 12px 4px;
        border-bottom: 1px solid rgba(255,255,255,0.06);
      }}
      .row:last-child {{ border-bottom: none; }}
      .row .left {{
        display:flex; align-items:center; gap: 12px;
        color: {WHITE};
        font-size: 18px;
      }}
      .row .sub {{
        font-size: 13px; color: {MUTED}; margin-top: 2px;
      }}
      .chev {{ color: rgba(255,255,255,0.55); font-size: 22px; }}

      /* Dial */
      .dialWrap {{
        position: relative;
        height: 430px;
        display:flex;
        align-items:center;
        justify-content:center;
      }}
      .dialNums {{
        position:absolute;
        left:0; right:0;
        text-align:center;
        color: rgba(255,255,255,0.18);
        font-size: 56px;
        font-weight: 300;
        line-height: 1.25;
      }}
      .dialCenter {{
        width: 220px; height: 220px;
        border-radius: 44px;
        background: {ACCENT};
        display:flex; align-items:center; justify-content:center;
        color: {WHITE};
        font-size: 96px;
        font-weight: 300;
        box-shadow: 0 12px 40px rgba(0,0,0,0.35);
      }}
      .dialBtnCol {{
        position:absolute;
        right: 10px;
        display:flex;
        flex-direction:column;
        gap: 16px;
      }}
      .dialBtnCol div.stButton > button {{
        width: 58px !important;
        height: 58px !important;
        border-radius: 999px !important;
        border: 2px solid {ACCENT} !important;
        background: rgba(249,115,22,0.06) !important;
        color: {ACCENT} !important;
        font-size: 28px !important;
        font-weight: 800 !important;
        padding: 0 !important;
      }}

      /* Bottom nav (visual bar) */
      .bottomnav {{
        position: fixed;
        left: 0; right: 0; bottom: 0;
        padding: 10px 0 14px 0;
        background: rgba(17,24,39,0.85);
        backdrop-filter: blur(10px);
        border-top: 1px solid rgba(255,255,255,0.08);
      }}
      .bottomnav .inner {{
        max-width: 430px;
        margin: 0 auto;
        display:flex;
        justify-content:space-around;
        align-items:center;
        padding: 0 20px;
      }}
      .navitem {{
        display:flex; flex-direction:column; align-items:center;
        gap: 6px;
        color: {MUTED};
        font-size: 12px;
      }}
      .navdot {{
        width: 10px; height: 10px; border-radius: 999px;
        background: rgba(255,255,255,0.12);
      }}
      .navitem.active {{
        color: {TEAL};
      }}
      .navitem.active .navdot {{
        background: {TEAL};
      }}

      /* Inputs */
      .stTextInput input {{
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        color: {WHITE} !important;
        border-radius: 14px !important;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# Tiny inline "icons"
# =========================================================
def ico(symbol: str) -> str:
    return f"<span style='font-size:16px; opacity:0.95'>{symbol}</span>"

def topbar(title: str, left_symbol="👤", right_symbol="⚙", left_hint="User", right_hint="Settings"):
    st.markdown(
        f"""
        <div class="topbar">
          <div class="iconbtn" title="{left_hint}">{left_symbol}</div>
          <div class="title">{title}</div>
          <div class="iconbtn" title="{right_hint}">{right_symbol}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def bottom_nav():
    # Real navigation actions (keep your Streamlit buttons here)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Home", use_container_width=True):
            st.session_state.view = "Home"
            st.rerun()
    with c2:
        if st.button("Reports", use_container_width=True):
            st.session_state.view = "Reports"
            st.rerun()
    with c3:
        if st.button("Menu", use_container_width=True):
            st.session_state.view = "Menu"
            st.rerun()

    active = st.session_state.view
    st.markdown(
        f"""
        <div class="bottomnav">
          <div class="inner">
            <div class="navitem {'active' if active=='Home' else ''}">
              <div>{ico('🏠')}</div><div class="navdot"></div><div>Home</div>
            </div>
            <div class="navitem {'active' if active=='Reports' else ''}">
              <div>{ico('📊')}</div><div class="navdot"></div><div>Reports</div>
            </div>
            <div class="navitem {'active' if active=='Menu' else ''}">
              <div>{ico('☰')}</div><div class="navdot"></div><div>Menu</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# =========================================================
# Views
# =========================================================
st.markdown('<div class="frame">', unsafe_allow_html=True)

if st.session_state.view == "Home":
    topbar("My ecobee", left_symbol="👤", right_symbol="⚙")

    sp = current_setpoint()

    st.markdown(
        f"""
        <div class="statusrow">
          <div class="chip">{ico('💧')} <b style="color:{WHITE}">{st.session_state.humidity}%</b></div>
          <div class="chip">{ico('🔥')} <b style="color:{WHITE}">{st.session_state.hvac_mode}</b></div>
          <div class="chip">{ico('🌬')} <b style="color:{WHITE}">{st.session_state.air_quality}</b></div>
        </div>

        <div class="bigtemp">{st.session_state.indoor_temp}</div>

        <div class="comfortline">
          {ico(comfort_icon(st.session_state.comfort))} <span>{st.session_state.comfort}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ✅ The pill itself is the tap target (no extra Streamlit button anywhere)
    st.markdown(f'<a class="pilllink" href="?view=Dial">{sp}</a>', unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    st.caption("Tip: tap the orange setpoint to adjust it (Dial).")

elif st.session_state.view == "Dial":
    topbar("", left_symbol="←", right_symbol="")

    # Optional: real back link (feels like an app)
    st.markdown('<div style="text-align:left; margin:-6px 0 8px 2px;"><a href="?view=Home" style="color:rgba(255,255,255,0.7); text-decoration:none;">← Back</a></div>', unsafe_allow_html=True)

    sp = current_setpoint()

    st.markdown('<div class="dialWrap">', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="dialNums">
          <div style="margin-top:8px">{sp+2}</div>
          <div style="color:rgba(255,255,255,0.35)">{sp+1}</div>
          <div style="height:18px"></div>
          <div style="color:rgba(255,255,255,0.35)">{sp-1}</div>
          <div style="margin-top:6px">{sp-2}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f'<div class="dialCenter">{sp}</div>', unsafe_allow_html=True)

    st.markdown('<div class="dialBtnCol">', unsafe_allow_html=True)
    plus = st.button("＋", key="dial_plus")
    minus = st.button("－", key="dial_minus")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    if plus:
        set_current_setpoint(sp + 1)
        st.rerun()
    if minus:
        set_current_setpoint(sp - 1)
        st.rerun()

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.write(f"Active comfort: **{st.session_state.comfort}**")

elif st.session_state.view == "Reports":
    topbar("Reports", left_symbol="＋", right_symbol="👤", left_hint="Add", right_hint="Profile")

    st.markdown(
        f"""
        <div class="card">
          <div style="font-size:18px; font-weight:650; margin-bottom:8px;">Quick Stats</div>
          <div style="color:rgba(255,255,255,0.72); line-height:1.5;">
            • Indoor temp: <b>{st.session_state.indoor_temp}</b><br/>
            • HVAC mode: <b>{st.session_state.hvac_mode}</b><br/>
            • Humidity: <b>{st.session_state.humidity}%</b><br/>
            • Comfort: <b>{st.session_state.comfort}</b> ({comfort_icon(st.session_state.comfort)})<br/>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.info("Aquí puedes luego conectar tus métricas reales (runtime, setpoints, clusters, etc.). Por ahora es placeholder 😄")

elif st.session_state.view == "Menu":
    topbar("Main Menu", left_symbol="✕", right_symbol="")

    st.text_input("Search thermostat settings", placeholder="Search thermostat settings")

    st.markdown(
        f"""
        <div class="card">
          <div class="row">
            <div class="left">{ico('e')} <div><div><b>eco+</b></div><div class="sub">Enabled</div></div></div>
            <div class="chev">›</div>
          </div>

          <div class="row">
            <div class="left">{ico('🛠')} <div><div><b>System</b></div><div class="sub">HVAC Mode: {st.session_state.hvac_mode}</div></div></div>
            <div class="chev">›</div>
          </div>

          <div class="row">
            <div class="left">{ico('🌬')} <div><div><b>Air Quality</b></div><div class="sub">{st.session_state.air_quality}</div></div></div>
            <div class="chev">›</div>
          </div>

          <div class="row">
            <div class="left">{ico('📡')} <div><div><b>Sensors</b></div><div class="sub">2 Sensors</div></div></div>
            <div class="chev">›</div>
          </div>

          <div class="row">
            <div class="left">{ico('🗓')} <div><div><b>Schedule</b></div><div class="sub">Weekly</div></div></div>
            <div class="chev">›</div>
          </div>

          <div class="row">
            <div class="left">{ico('🛋')} <div><div><b>Comfort Settings</b></div><div class="sub">Home / Away / Sleep / Morning</div></div></div>
            <div class="chev">›</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    if st.button("Open Comfort Settings"):
        st.session_state.view = "Comfort"
        st.rerun()

elif st.session_state.view == "Comfort":
    topbar("Comfort Settings", left_symbol="←", right_symbol="＋")

    st.markdown(
        """
        <div style="color:rgba(255,255,255,0.7); font-size:15px; line-height:1.4; margin-bottom:14px;">
          Comfort settings make sure your home is the right temperature during specific activities in your schedule.
        </div>
        """,
        unsafe_allow_html=True,
    )

    for k in list(st.session_state.setpoints.keys()):
        colA, colB = st.columns([2, 1])
        with colA:
            st.write(f"**{comfort_icon(k)} {k}**")
        with colB:
            v = st.number_input(
                label=f"Setpoint for {k}",
                value=int(st.session_state.setpoints[k]),
                key=f"sp_{k}",
                label_visibility="collapsed",
            )
            st.session_state.setpoints[k] = int(v)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.session_state.comfort = st.selectbox(
        "Active comfort",
        list(st.session_state.setpoints.keys()),
        index=list(st.session_state.setpoints.keys()).index(st.session_state.comfort),
    )

st.markdown("</div>", unsafe_allow_html=True)

# Bottom nav
bottom_nav()
