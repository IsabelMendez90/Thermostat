import streamlit as st
from openai import OpenAI

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

# Two setpoints per comfort: Heat + Cool
if "setpoints" not in st.session_state:
    st.session_state.setpoints = {
        "Home": {"heat": 68, "cool": 76},
        "Away": {"heat": 64, "cool": 82},
        "Sleep": {"heat": 66, "cool": 78},
        "Morning": {"heat": 70, "cool": 75},
    }

# Dial target (heat/cool)
if "dial_target" not in st.session_state:
    st.session_state.dial_target = "heat"  # "heat" or "cool"

# LLM messages
if "assistant_messages" not in st.session_state:
    st.session_state.assistant_messages = []  # [{"role":"user|assistant","content":"..."}]

if "assistant_last_reply" not in st.session_state:
    st.session_state.assistant_last_reply = "Ask me anything about your thermostat."

# =========================================================
# Convenience
# =========================================================
def comfort_icon(name: str) -> str:
    return {"Home": "🏠", "Away": "🚶", "Sleep": "🌙", "Morning": "☀️"}.get(name, "✨")

def clamp(v: int, lo: int = 45, hi: int = 90) -> int:
    return max(lo, min(hi, int(v)))

def get_sp(comfort: str, target: str) -> int:
    return int(st.session_state.setpoints.get(comfort, {}).get(target, 66))

def set_sp(comfort: str, target: str, v: int):
    v = clamp(v)
    if comfort not in st.session_state.setpoints:
        st.session_state.setpoints[comfort] = {"heat": 66, "cool": 78}
    st.session_state.setpoints[comfort][target] = v

def current_setpoint() -> int:
    return get_sp(st.session_state.comfort, st.session_state.dial_target)

def set_current_setpoint(v: int):
    set_sp(st.session_state.comfort, st.session_state.dial_target, v)

def ico(symbol: str) -> str:
    return f"<span style='font-size:16px; opacity:0.95'>{symbol}</span>"

# =========================================================
# OpenRouter (LLM)
# =========================================================
def get_openrouter_client() -> OpenAI:
    api_key = st.secrets.get("OPENROUTER_API_KEY", "")
    if not api_key:
        st.error("Missing OPENROUTER_API_KEY in Streamlit secrets.")
        st.stop()
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

def call_openrouter(user_text: str, model: str = "mistralai/devstral-2512:free") -> str:
    client = get_openrouter_client()

    site_url = st.secrets.get("YOUR_SITE_URL", "")
    site_name = st.secrets.get("YOUR_SITE_NAME", "Streamlit Ecobee")

    # Provide compact state context (so it acts “inside” your thermostat)
    state = {
        "hvac_mode": st.session_state.hvac_mode,
        "comfort": st.session_state.comfort,
        "indoor_temp": st.session_state.indoor_temp,
        "humidity": st.session_state.humidity,
        "air_quality": st.session_state.air_quality,
        "setpoints": st.session_state.setpoints.get(st.session_state.comfort, {}),
    }

    # Keep context short
    history = st.session_state.assistant_messages[-8:]

    messages = [
        {
            "role": "system",
            "content": (
                "You are an ecobee-style thermostat assistant. "
                "Be concise and practical. "
                "If asked to change setpoints, propose exact HEAT and COOL values."
            ),
        },
        {"role": "system", "content": f"Current thermostat state: {state}"},
        *history,
        {"role": "user", "content": user_text},
    ]

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        extra_headers={"HTTP-Referer": site_url, "X-Title": site_name},
    )
    return completion.choices[0].message.content.strip()

# =========================================================
# Styling (ecobee-ish)
# =========================================================
BASE_BG = "#111827"
CARD_BG = "#1F2937"
MUTED = "#9CA3AF"
WHITE = "#F9FAFB"
ACCENT = "#F97316"   # heat
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
        padding: 18px 14px 170px 14px; /* room for assistant bar + nav */
      }}

      .topbar {{
        display:flex; align-items:center; justify-content:space-between;
        padding: 8px 2px 14px 2px;
      }}
      .topbar .title {{ font-size: 22px; font-weight: 600; letter-spacing: 0.2px; }}
      .iconbtn {{
        width: 38px; height: 38px; border-radius: 999px;
        display:flex; align-items:center; justify-content:center;
        border: 1px solid rgba(255,255,255,0.12);
        color: {WHITE}; opacity: 0.95;
      }}

      .statusrow {{
        display:flex; gap: 18px; justify-content:center; align-items:center;
        color: {MUTED}; font-size: 15px; margin-top: 10px;
      }}
      .statusrow .chip {{ display:flex; gap: 8px; align-items:center; }}

      .bigtemp {{
        text-align:center; font-size: 120px; line-height: 1.0; font-weight: 300;
        margin: 14px 0 8px 0; color: {WHITE};
      }}

      .comfortline {{
        text-align:center; color: {MUTED}; font-size: 20px;
        display:flex; justify-content:center; gap: 10px; align-items:center;
      }}

      /* Home heat/cool pills */
      .pillRow {{
        display:flex; justify-content:center; gap: 12px; margin-top: 18px;
      }}
      .pill {{
        width: 132px; border-radius: 999px; padding: 10px 0; text-align:center;
        border: 2px solid rgba(255,255,255,0.14);
        background: rgba(255,255,255,0.03);
        font-weight: 800; letter-spacing: 0.4px;
      }}
      .pill .label {{
        display:flex; justify-content:center; gap: 8px; align-items:center;
        font-size: 12px; color: rgba(255,255,255,0.65); font-weight: 650; margin-bottom: 2px;
      }}
      .pill.heat {{
        border-color: rgba(249,115,22,0.75);
        color: {ACCENT}; background: rgba(249,115,22,0.06);
      }}
      .pill.cool {{
        border-color: rgba(96,165,250,0.75);
        color: rgba(96,165,250,0.95);
        background: rgba(96,165,250,0.06);
      }}

      /* Dial */
      .dialWrap {{
        position: relative; height: 430px;
        display:flex; align-items:center; justify-content:center;
      }}
      .dialNums {{
        position:absolute; left:0; right:0; text-align:center;
        color: rgba(255,255,255,0.18);
        font-size: 56px; font-weight: 300; line-height: 1.25;
      }}
      .dialCenter {{
        width: 220px; height: 220px; border-radius: 44px;
        display:flex; align-items:center; justify-content:center;
        color: {WHITE}; font-size: 96px; font-weight: 300;
        box-shadow: 0 12px 40px rgba(0,0,0,0.35);
      }}
      .dialCenter.heat {{ background: {ACCENT}; }}
      .dialCenter.cool {{ background: rgba(96,165,250,0.95); }}

      .dialBtnCol {{
        position:absolute; right: 10px; display:flex; flex-direction:column; gap: 16px;
      }}
      .dialBtnCol div.stButton > button {{
        width: 58px !important; height: 58px !important; border-radius: 999px !important;
        border: 2px solid rgba(255,255,255,0.14) !important;
        background: rgba(255,255,255,0.05) !important;
        color: {WHITE} !important; font-size: 28px !important; font-weight: 800 !important; padding: 0 !important;
      }}

      /* Bottom nav */
      .bottomnav {{
        position: fixed; left: 0; right: 0; bottom: 0;
        padding: 10px 0 14px 0;
        background: rgba(17,24,39,0.85);
        backdrop-filter: blur(10px);
        border-top: 1px solid rgba(255,255,255,0.08);
      }}
      .bottomnav .inner {{
        max-width: 430px; margin: 0 auto;
        display:flex; justify-content:space-around; align-items:center; padding: 0 20px;
      }}
      .navitem {{
        display:flex; flex-direction:column; align-items:center; gap: 6px;
        color: {MUTED}; font-size: 12px;
      }}
      .navdot {{ width: 10px; height: 10px; border-radius: 999px; background: rgba(255,255,255,0.12); }}
      .navitem.active {{ color: {TEAL}; }}
      .navitem.active .navdot {{ background: {TEAL}; }}

      /* Assistant bar FIXED above bottom nav */
      .assistantbar {{
        position: fixed; left: 0; right: 0; bottom: 86px;
        padding: 10px 0 12px 0;
        pointer-events: none;
      }}
      .assistantbar .inner {{
        max-width: 430px; margin: 0 auto; padding: 0 14px;
        pointer-events: auto;
      }}
      .assistantbubble {{
        width: 100%;
        border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.10);
        background: rgba(17,24,39,0.75);
        backdrop-filter: blur(10px);
        padding: 10px 12px;
      }}
      .assistantbubble .reply {{
        color: rgba(255,255,255,0.90);
        font-size: 13px; line-height: 1.3;
        margin-bottom: 8px;
      }}

      .assistantInput .stTextInput input {{
        height: 38px !important;
        border-radius: 14px !important;
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        color: {WHITE} !important;
      }}

      /* Global button style */
      div.stButton > button {{
        border-radius: 999px !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        background: rgba(255,255,255,0.03) !important;
        color: {WHITE} !important;
        padding: 10px 14px !important;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# UI helpers
# =========================================================
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

def assistant_bar():
    # FIX: include .inner so pointer-events works + SHOW the reply bubble
    st.markdown('<div class="assistantbar"><div class="inner">', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="assistantbubble">
          <div class="reply">{st.session_state.assistant_last_reply}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Input + send
    with st.form("assistant_form", clear_on_submit=True):
        st.markdown('<div class="assistantInput">', unsafe_allow_html=True)
        user_msg = st.text_input(
            "Assistant",
            key="assistant_input",
            placeholder="Ask the assistant…",
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)
        sent = st.form_submit_button("Send")

    st.markdown("</div></div>", unsafe_allow_html=True)  # close inner + assistantbar

    if sent:
        user_msg = (user_msg or "").strip()
        if not user_msg:
            return

        # Save user message
        st.session_state.assistant_messages.append({"role": "user", "content": user_msg})

        # Call model (with visible spinner + visible errors)
        try:
            with st.spinner("Thinking…"):
                reply = call_openrouter(user_msg)
        except Exception as e:
            st.session_state.assistant_last_reply = f"LLM error: {e}"
            st.rerun()

        # Save assistant reply
        st.session_state.assistant_messages.append({"role": "assistant", "content": reply})
        st.session_state.assistant_last_reply = reply
        st.rerun()

# =========================================================
# Views
# =========================================================
st.markdown('<div class="frame">', unsafe_allow_html=True)

if st.session_state.view == "Home":
    topbar("My ecobee", left_symbol="👤", right_symbol="⚙")

    heat_sp = get_sp(st.session_state.comfort, "heat")
    cool_sp = get_sp(st.session_state.comfort, "cool")

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

        <div class="pillRow">
          <div class="pill heat">
            <div class="label">{ico('🔥')} Heat</div>
            <div style="font-size:20px;">{heat_sp}</div>
          </div>
          <div class="pill cool">
            <div class="label">{ico('❄️')} Cool</div>
            <div style="font-size:20px;">{cool_sp}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    colA, colB = st.columns(2)
    with colA:
        if st.button("Adjust Heat", use_container_width=True):
            st.session_state.dial_target = "heat"
            st.session_state.view = "Dial"
            st.rerun()
    with colB:
        if st.button("Adjust Cool", use_container_width=True):
            st.session_state.dial_target = "cool"
            st.session_state.view = "Dial"
            st.rerun()

elif st.session_state.view == "Dial":
    target = st.session_state.dial_target
    topbar("Setpoint", left_symbol="←", right_symbol="")

    sp = current_setpoint()
    center_class = "heat" if target == "heat" else "cool"
    label = "🔥 Heat" if target == "heat" else "❄️ Cool"

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
    st.markdown(f'<div class="dialCenter {center_class}">{sp}</div>', unsafe_allow_html=True)

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

    st.write(f"Editing: **{label}** for **{st.session_state.comfort}**")
    if st.button("Back to Home", use_container_width=True):
        st.session_state.view = "Home"
        st.rerun()

elif st.session_state.view == "Reports":
    topbar("Reports", left_symbol="＋", right_symbol="👤")
    st.markdown(
        f"""
        <div style="background: rgba(31,41,55,0.9); border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 18px; padding: 14px 14px;">
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

elif st.session_state.view == "Menu":
    topbar("Main Menu", left_symbol="✕", right_symbol="")
    st.text_input("Search thermostat settings", placeholder="Search thermostat settings")

    if st.button("Open Comfort Settings", use_container_width=True):
        st.session_state.view = "Comfort"
        st.rerun()

elif st.session_state.view == "Comfort":
    topbar("Comfort Settings", left_symbol="←", right_symbol="＋")

    st.markdown(
        """
        <div style="color:rgba(255,255,255,0.7); font-size:15px; line-height:1.4; margin-bottom:14px;">
          Each comfort has two setpoints: Heat (🔥) and Cool (❄️).
        </div>
        """,
        unsafe_allow_html=True,
    )

    for k in list(st.session_state.setpoints.keys()):
        colA, colB, colC = st.columns([2.2, 1.2, 1.2])
        with colA:
            st.write(f"**{comfort_icon(k)} {k}**")
        with colB:
            v_heat = st.number_input(
                label=f"Heat setpoint for {k}",
                value=int(get_sp(k, "heat")),
                key=f"heat_{k}",
                label_visibility="collapsed",
                step=1,
            )
            set_sp(k, "heat", int(v_heat))
        with colC:
            v_cool = st.number_input(
                label=f"Cool setpoint for {k}",
                value=int(get_sp(k, "cool")),
                key=f"cool_{k}",
                label_visibility="collapsed",
                step=1,
            )
            set_sp(k, "cool", int(v_cool))

    st.session_state.comfort = st.selectbox(
        "Active comfort",
        list(st.session_state.setpoints.keys()),
        index=list(st.session_state.setpoints.keys()).index(st.session_state.comfort),
    )

st.markdown("</div>", unsafe_allow_html=True)

# Fixed assistant bar + bottom nav
assistant_bar()
bottom_nav()
