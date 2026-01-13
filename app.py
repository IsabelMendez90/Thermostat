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

# Heat / Cool / Auto / Off
if "hvac_mode" not in st.session_state:
    st.session_state.hvac_mode = "Heat"

if "comfort" not in st.session_state:
    st.session_state.comfort = "Away"  # Home / Away / Sleep / Morning

# When hvac_mode == Auto, which setpoint does the dial adjust?
if "dial_kind" not in st.session_state:
    st.session_state.dial_kind = "heat"  # "heat" | "cool"

# Two setpoints per comfort: heat + cool
if "setpoints" not in st.session_state:
    st.session_state.setpoints = {
        "Home":    {"heat": 68, "cool": 75},
        "Away":    {"heat": 64, "cool": 80},
        "Sleep":   {"heat": 66, "cool": 78},
        "Morning": {"heat": 67, "cool": 74},
    }

# =========================================================
# Convenience
# =========================================================
def clamp(v: int, lo: int = 45, hi: int = 90) -> int:
    return max(lo, min(hi, int(v)))

def comfort_icon(name: str) -> str:
    return {"Home": "🏠", "Away": "🚶", "Sleep": "🌙", "Morning": "☀️"}.get(name, "✨")

def get_sp(kind: str) -> int:
    c = st.session_state.comfort
    return int(st.session_state.setpoints[c][kind])

def set_sp(kind: str, v: int):
    c = st.session_state.comfort
    st.session_state.setpoints[c][kind] = clamp(v)

def active_kind_for_mode() -> str:
    mode = st.session_state.hvac_mode
    if mode == "Heat":
        return "heat"
    if mode == "Cool":
        return "cool"
    # Auto: user chooses
    return st.session_state.dial_kind

def pill_text() -> str:
    mode = st.session_state.hvac_mode
    h = get_sp("heat")
    c = get_sp("cool")
    if mode == "Auto":
        return f"{h} / {c}"
    if mode == "Heat":
        return f"{h}"
    if mode == "Cool":
        return f"{c}"
    return "—"

# =========================================================
# Styling (ecobee-ish)
# =========================================================
BASE_BG = "#111827"
MUTED = "#9CA3AF"
WHITE = "#F9FAFB"
ACCENT = "#F97316"
TEAL = "#22C55E"

st.markdown(
    f"""
    <style>
      .stApp {{
        background: radial-gradient(1200px 800px at 50% 30%, #0B1220 0%, {BASE_BG} 55%, #0A1020 100%);
        color: {WHITE};
      }}

      #MainMenu {{visibility: hidden;}}
      footer {{visibility: hidden;}}
      header {{visibility: hidden;}}

      .frame {{
        max-width: 430px;
        margin: 0 auto;
        padding: 18px 14px 92px 14px;
      }}

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

      .statusrow {{
        display:flex; gap: 18px; justify-content:center; align-items:center;
        color: {MUTED};
        font-size: 15px;
        margin-top: 10px;
      }}
      .statusrow .chip {{
        display:flex; gap: 8px; align-items:center;
      }}

      .bigtemp {{
        text-align:center;
        font-size: 120px;
        line-height: 1.0;
        font-weight: 300;
        margin: 14px 0 8px 0;
        color: {WHITE};
      }}

      .comfortline {{
        text-align:center;
        color: {MUTED};
        font-size: 20px;
        display:flex;
        justify-content:center;
        gap: 10px;
        align-items:center;
      }}

      /* ONLY the pill button */
      .pillwrap {{
        width: 160px;
        margin: 18px auto 0 auto;
      }}
      .pillwrap div.stButton > button {{
        width: 160px !important;
        border-radius: 999px !important;
        border: 2px solid {ACCENT} !important;
        background: rgba(249,115,22,0.06) !important;
        color: {ACCENT} !important;
        font-weight: 850 !important;
        letter-spacing: 0.4px !important;
        padding: 10px 0 !important;
        font-size: 20px !important;
      }}

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
        font-weight: 850 !important;
        padding: 0 !important;
      }}

      /* Bottom nav */
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
# UI helpers
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
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Home", use_container_width=True, key="nav_home"):
            st.session_state.view = "Home"
            st.rerun()
    with c2:
        if st.button("Reports", use_container_width=True, key="nav_reports"):
            st.session_state.view = "Reports"
            st.rerun()
    with c3:
        if st.button("Menu", use_container_width=True, key="nav_menu"):
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


    st.markdown('<div class="pillwrap">', unsafe_allow_html=True)
    if st.button(pill_text(), key="pill_btn", help="Tap to adjust setpoint"):
        st.session_state.view = "Dial"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    st.caption("Tip: tap the orange setpoint to adjust it (Dial).")

elif st.session_state.view == "Dial":
    topbar("", left_symbol="←", right_symbol="")

    # Back behavior (simple + predictable)
    back = st.button("Back", key="dial_back")
    if back:
        st.session_state.view = "Home"
        st.rerun()

    # If Auto, choose which setpoint to edit
    if st.session_state.hvac_mode == "Auto":
        choice = st.radio(
            "Adjust which setpoint",
            ["Heat 🔥", "Cool ❄️"],
            horizontal=True,
            label_visibility="collapsed",
            index=0 if st.session_state.dial_kind == "heat" else 1,
            key="dial_choice",
        )
        st.session_state.dial_kind = "heat" if "Heat" in choice else "cool"

    kind = active_kind_for_mode()
    sp = get_sp(kind)

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
        set_sp(kind, sp + 1)
        st.rerun()
    if minus:
        set_sp(kind, sp - 1)
        st.rerun()

    # Show both setpoints for context (ecobee vibes)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.write(
        f"Active comfort: **{st.session_state.comfort}**  •  "
        f"🔥 {get_sp('heat')}  |  ❄️ {get_sp('cool')}"
    )

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
            • Setpoints: 🔥 <b>{get_sp('heat')}</b> | ❄️ <b>{get_sp('cool')}</b><br/>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.info("Later: connect this to real runtime/setpoint/cluster metrics. For now it’s a nice-looking lie. 😄")

elif st.session_state.view == "Menu":
    topbar("Main Menu", left_symbol="✕", right_symbol="")
    st.text_input("Search thermostat settings", placeholder="Search thermostat settings", key="menu_search")

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
            <div class="left">{ico('🛋')} <div><div><b>Comfort Settings</b></div><div class="sub">Home / Away / Sleep / Morning</div></div></div>
            <div class="chev">›</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    if st.button("Open Comfort Settings", key="open_comfort"):
        st.session_state.view = "Comfort"
        st.rerun()

    # Optional: quick HVAC mode switch for testing
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.session_state.hvac_mode = st.selectbox(
        "HVAC mode",
        ["Heat", "Cool", "Auto", "Off"],
        index=["Heat", "Cool", "Auto", "Off"].index(st.session_state.hvac_mode),
        key="hvac_mode_select",
    )

elif st.session_state.view == "Comfort":
    topbar("Comfort Settings", left_symbol="←", right_symbol="＋")

    if st.button("Back", key="comfort_back"):
        st.session_state.view = "Menu"
        st.rerun()

    st.markdown(
        """
        <div style="color:rgba(255,255,255,0.7); font-size:15px; line-height:1.4; margin-bottom:14px;">
          Comfort settings make sure your home is the right temperature during specific activities in your schedule.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Two setpoints per comfort: Heat + Cool
    for k in list(st.session_state.setpoints.keys()):
        rowA, rowB, rowC = st.columns([1.6, 1.0, 1.0])

        with rowA:
            st.write(f"**{comfort_icon(k)} {k}**")

        with rowB:
            h = st.number_input(
                "Heat setpoint",
                value=int(st.session_state.setpoints[k]["heat"]),
                key=f"heat_{k}",
                label_visibility="collapsed",
                step=1,
            )
            st.session_state.setpoints[k]["heat"] = clamp(h)

        with rowC:
            c = st.number_input(
                "Cool setpoint",
                value=int(st.session_state.setpoints[k]["cool"]),
                key=f"cool_{k}",
                label_visibility="collapsed",
                step=1,
            )
            st.session_state.setpoints[k]["cool"] = clamp(c)

        # Tiny hint row (like ecobee icons)
        st.caption(f"🔥 {st.session_state.setpoints[k]['heat']}    ❄️ {st.session_state.setpoints[k]['cool']}")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.session_state.comfort = st.selectbox(
        "Active comfort",
        list(st.session_state.setpoints.keys()),
        index=list(st.session_state.setpoints.keys()).index(st.session_state.comfort),
        key="active_comfort_select",
    )

st.markdown("</div>", unsafe_allow_html=True)

# Bottom nav
bottom_nav()
