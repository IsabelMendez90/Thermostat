# app.py
# Ecobee-style Streamlit UI + OpenRouter assistant + Open-Meteo outdoor temp (with location picker)
# -------------------------------------------------------------

import json
import re
from typing import Any, Dict, Optional, Tuple, List

import requests
import streamlit as st
from openai import OpenAI
from streamlit_js_eval import get_geolocation

# =========================================================
# Page config
# =========================================================
st.set_page_config(page_title="Ecobee-style UI (Streamlit)", layout="centered")

# =========================================================
# Session state defaults
# =========================================================
def init_state():
    ss = st.session_state

    ss.setdefault("view", "Home")  # Home | Dial | Reports | Menu | Comfort

    ss.setdefault("indoor_temp", 78)
    ss.setdefault("humidity", 51)
    ss.setdefault("air_quality", "Fair")

    # HVAC + fan
    ss.setdefault("hvac_mode", "Heat")  # Off / Heat / Cool / Auto / Aux
    ss.setdefault("fan_on", False)      # False=Auto, True=On

    # Comfort + setpoints
    ss.setdefault("comfort", "Away")
    ss.setdefault(
        "setpoints",
        {
            "Home": {"heat": 68, "cool": 76},
            "Away": {"heat": 64, "cool": 82},
            "Sleep": {"heat": 66, "cool": 78},
            "Morning": {"heat": 70, "cool": 75},
        },
    )
    ss.setdefault("dial_target", "heat")  # heat or cool

    # Assistant
    ss.setdefault("assistant_messages", [])
    ss.setdefault("assistant_last_reply", "Ask me anything about your thermostat.")
    ss.setdefault("pending_action", None)   # dict or None
    ss.setdefault("pending_explainer", "")  # why/impact text

    # Location + weather
    ss.setdefault("location", "Berkeley, California")
    ss.setdefault("outdoor_temp_f", None)  # float or None
    ss.setdefault("outdoor_humidity", None)  # float or None
    ss.setdefault("weather_status", "Not updated")

    # Geocoding candidates
    ss.setdefault("geo_results", [])       # list of dicts
    ss.setdefault("geo_choice", 0)         # index in geo_results

init_state()

# =========================================================
# Convenience
# =========================================================
def comfort_icon(name: str) -> str:
    return {"Home": "🏠", "Away": "🚶", "Sleep": "🌙", "Morning": "☀️"}.get(name, "✨")

def ico(symbol: str) -> str:
    return f"<span style='font-size:16px; opacity:0.95'>{symbol}</span>"

def clamp(v: int, lo: int = 45, hi: int = 90) -> int:
    return max(lo, min(hi, int(v)))

def get_sp(comfort: str, target: str) -> int:
    return int(st.session_state.setpoints.get(comfort, {}).get(target, 66))

def set_sp(comfort: str, target: str, v: int):
    v = clamp(v)
    st.session_state.setpoints.setdefault(comfort, {"heat": 66, "cool": 78})
    st.session_state.setpoints[comfort][target] = v

def current_setpoint() -> int:
    return get_sp(st.session_state.comfort, st.session_state.dial_target)

def set_current_setpoint(v: int):
    set_sp(st.session_state.comfort, st.session_state.dial_target, v)

def fan_label() -> str:
    return "On" if st.session_state.fan_on else "Auto"

# =========================================================
# Weather via Open-Meteo (free, no key)
#   - Geocoding returns multiple candidates; user picks one
#   - Browser geolocation uses GPS for accurate location
# =========================================================
def geocode_candidates(location_text: str) -> Tuple[List[dict], str]:
    q = (location_text or "").strip()
    if not q:
        return [], "Type a location first."

    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": q, "count": 5, "language": "en", "format": "json"},
            timeout=10,
        )
        geo.raise_for_status()
        gj = geo.json()
        results = gj.get("results") or []
        if not results:
            return [], f"No matches for '{q}'. Try a more complete address like 'Berkeley, California, USA'."
        return results, f"Found {len(results)} match(es) for '{q}'."
    except Exception as e:
        return [], f"Geocoding error: {e}"

def fetch_current_weather(lat: float, lon: float) -> Tuple[Optional[float], Optional[float], str]:
    """Fetch temperature (F) and humidity (%) from Open-Meteo"""
    try:
        wx = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
            },
            timeout=10,
        )
        wx.raise_for_status()
        wj = wx.json()
        current = wj.get("current", {})
        
        temp = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")
        
        if temp is None:
            return None, None, "Weather data unavailable (no temperature in response)"
        
        return float(temp), float(humidity) if humidity is not None else None, "OK"
    except requests.exceptions.Timeout:
        return None, None, "Weather request timed out. Try again."
    except requests.exceptions.RequestException as e:
        return None, None, f"Weather API error: {str(e)}"
    except Exception as e:
        return None, None, f"Unexpected error: {str(e)}"

def nice_place(r: dict) -> str:
    name = r.get("name", "")
    admin1 = r.get("admin1", "")
    country = r.get("country", "")
    cc = r.get("country_code", "")
    if country and cc:
        country = f"{country} ({cc})"
    parts = [p for p in [name, admin1, country] if p]
    return ", ".join(parts) if parts else "Unknown"

# =========================================================
# OpenRouter client (LLM)
# =========================================================
def get_openrouter_client() -> OpenAI:
    api_key = st.secrets.get("OPENROUTER_API_KEY", "")
    if not api_key:
        st.error("Missing OPENROUTER_API_KEY in Streamlit secrets.")
        st.stop()
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

def thermostat_state_summary() -> Dict[str, Any]:
    return {
        "indoor_temp_f": st.session_state.indoor_temp,
        "outdoor_temp_f": st.session_state.outdoor_temp_f,
        "outdoor_humidity_pct": st.session_state.outdoor_humidity,
        "indoor_humidity_pct": st.session_state.humidity,
        "air_quality": st.session_state.air_quality,
        "hvac_mode": st.session_state.hvac_mode,
        "fan": fan_label(),
        "comfort": st.session_state.comfort,
        "setpoints_active": st.session_state.setpoints.get(st.session_state.comfort, {}),
        "location": st.session_state.location,
        "controls_available": {
            "hvac_modes": ["Off", "Heat", "Cool", "Auto", "Aux"],
            "fan_toggle": ["Auto", "On"],
            "comforts": list(st.session_state.setpoints.keys()),
            "setpoints": ["heat", "cool"],
        },
    }

ACTION_TAG_RE = re.compile(r"<ACTION>\s*(\{.*?\})\s*</ACTION>", re.DOTALL)

def parse_action_from_text(text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    m = ACTION_TAG_RE.search(text)
    if not m:
        return None, text.strip()

    raw = m.group(1)
    try:
        action = json.loads(raw)
    except Exception:
        return None, text.strip()

    cleaned = ACTION_TAG_RE.sub("", text).strip()
    return action, cleaned

def call_openrouter(user_text: str, model: str = "mistralai/devstral-2512:free") -> Tuple[str, Optional[Dict[str, Any]]]:
    client = get_openrouter_client()
    site_url = st.secrets.get("YOUR_SITE_URL", "")
    site_name = st.secrets.get("YOUR_SITE_NAME", "Streamlit Ecobee")

    state = thermostat_state_summary()
    history = st.session_state.assistant_messages[-8:]

    system = (
        "You are an ecobee-style thermostat assistant inside a Streamlit UI.\n"
        "You MUST follow this protocol:\n"
        "1) First give a short helpful answer.\n"
        "2) If (and only if) the user requests a change that exists in UI, propose ONE action.\n"
        "3) Proposed actions MUST be encoded in a single JSON block inside tags exactly like:\n"
        "<ACTION>{\"type\":\"set_hvac_mode\",\"mode\":\"Auto\"}</ACTION>\n\n"
        "Allowed action types and schemas:\n"
        "- set_hvac_mode: {\"type\":\"set_hvac_mode\",\"mode\":\"Off|Heat|Cool|Auto|Aux\"}\n"
        "- set_fan: {\"type\":\"set_fan\",\"fan\":\"Auto|On\"}\n"
        "- set_comfort: {\"type\":\"set_comfort\",\"comfort\":\"Home|Away|Sleep|Morning\"}\n"
        "- set_setpoint: {\"type\":\"set_setpoint\",\"target\":\"heat|cool\",\"value\":INT,\"comfort\":\"(optional)\"}\n"
        "- set_location: {\"type\":\"set_location\",\"location\":\"text\"}\n\n"
        "Important:\n"
        "- Never claim the change has already happened. Only propose it.\n"
        "- Mention comfort/energy tradeoffs briefly before proposing the action.\n"
        "- If the user asks for climate reasoning, use location and outdoor_temp if available.\n"
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "system", "content": f"Current thermostat state (JSON): {json.dumps(state)}"},
        *history,
        {"role": "user", "content": user_text},
    ]

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        extra_headers={"HTTP-Referer": site_url, "X-Title": site_name},
    )

    raw = completion.choices[0].message.content.strip()
    action, cleaned = parse_action_from_text(raw)
    return cleaned, action

def apply_action(action: Dict[str, Any]) -> str:
    t = action.get("type")

    if t == "set_hvac_mode":
        mode = action.get("mode")
        if mode in ["Off", "Heat", "Cool", "Auto", "Aux"]:
            st.session_state.hvac_mode = mode
            return f"Applied: HVAC mode → {mode}"
        return "Invalid HVAC mode"

    if t == "set_fan":
        fan = action.get("fan")
        if fan == "On":
            st.session_state.fan_on = True
            return "Applied: Fan → On"
        if fan == "Auto":
            st.session_state.fan_on = False
            return "Applied: Fan → Auto"
        return "Invalid fan value"

    if t == "set_comfort":
        comfort = action.get("comfort")
        if comfort in st.session_state.setpoints:
            st.session_state.comfort = comfort
            return f"Applied: Comfort → {comfort}"
        return "Invalid comfort"

    if t == "set_setpoint":
        target = action.get("target")
        value = action.get("value")
        comfort = action.get("comfort", st.session_state.comfort)

        if target not in ["heat", "cool"]:
            return "Invalid setpoint target"
        try:
            value_i = clamp(int(value))
        except Exception:
            return "Invalid setpoint value"

        st.session_state.setpoints.setdefault(comfort, {"heat": 66, "cool": 78})
        set_sp(comfort, target, value_i)
        return f"Applied: {comfort} {target} setpoint → {value_i}"

    if t == "set_location":
        loc = (action.get("location") or "").strip()
        if not loc:
            return "Invalid location"
        st.session_state.location = loc
        st.session_state.outdoor_temp_f = None
        st.session_state.outdoor_humidity = None
        st.session_state.weather_status = "Not updated"
        st.session_state.geo_results = []
        st.session_state.geo_choice = 0
        return f"Applied: Location → {loc}"

    return "Unknown action type"

# =========================================================
# Styling
# =========================================================
BASE_BG = "#111827"
WHITE = "#F9FAFB"
MUTED = "#9CA3AF"
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
        padding: 18px 14px 190px 14px;
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
        display:flex; gap: 12px; justify-content:center; align-items:center;
        color: {MUTED}; font-size: 13px; margin-top: 10px; flex-wrap: wrap;
      }}
      .statusrow .chip {{
        display:flex; gap: 8px; align-items:center;
        border: 1px solid rgba(255,255,255,0.10);
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(255,255,255,0.03);
      }}

      .bigtemp {{
        text-align:center; font-size: 120px; line-height: 1.0; font-weight: 300;
        margin: 14px 0 8px 0; color: {WHITE};
      }}

      .comfortline {{
        text-align:center; color: {MUTED}; font-size: 20px;
        display:flex; justify-content:center; gap: 10px; align-items:center;
      }}

      .pillRow {{
        display:flex; justify-content:center; gap: 12px; margin-top: 16px;
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

      /* Assistant bar */
      .assistantbar {{
        position: fixed; left: 0; right: 0; bottom: 86px;
        padding: 10px 0 12px 0; pointer-events: none;
      }}
      .assistantbar .inner {{
        max-width: 430px; margin: 0 auto; padding: 0 14px; pointer-events: auto;
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
        color: rgba(255,255,255,0.92);
        font-size: 13px; line-height: 1.35;
        margin-bottom: 8px;
      }}
      .pending {{
        margin-top: 8px;
        border-top: 1px solid rgba(255,255,255,0.08);
        padding-top: 8px;
        color: rgba(255,255,255,0.82);
        font-size: 12px;
      }}

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
def topbar(title: str, left_symbol="👤", right_symbol="⚙"):
    st.markdown(
        f"""
        <div class="topbar">
          <div class="iconbtn">{left_symbol}</div>
          <div class="title">{title}</div>
          <div class="iconbtn">{right_symbol}</div>
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

def describe_action(action: Dict[str, Any]) -> str:
    t = action.get("type")
    if t == "set_hvac_mode":
        return f"Proposed change: HVAC mode → **{action.get('mode')}**"
    if t == "set_fan":
        return f"Proposed change: Fan → **{action.get('fan')}**"
    if t == "set_comfort":
        return f"Proposed change: Comfort → **{action.get('comfort')}**"
    if t == "set_setpoint":
        comfort = action.get("comfort", st.session_state.comfort)
        return f"Proposed change: **{comfort}** {action.get('target')} setpoint → **{action.get('value')}**"
    if t == "set_location":
        return f"Proposed change: Location → **{action.get('location')}**"
    return "Proposed change: (unknown)"

def assistant_bar():
    st.markdown('<div class="assistantbar"><div class="inner">', unsafe_allow_html=True)

    pending = st.session_state.pending_action
    pending_html = ""
    if pending:
        pending_html = f"""
        <div class="pending">
          {describe_action(pending)}<br/>
          <span style="opacity:0.85">{st.session_state.pending_explainer}</span>
        </div>
        """

    st.markdown(
        f"""
        <div class="assistantbubble">
          <div class="reply">{st.session_state.assistant_last_reply}</div>
          {pending_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if pending:
        c_ok, c_no = st.columns(2)
        with c_ok:
            if st.button("Confirm", use_container_width=True):
                status = apply_action(st.session_state.pending_action)
                st.session_state.pending_action = None
                st.session_state.pending_explainer = ""
                st.session_state.assistant_last_reply = f"{status}. UI updated."
                st.rerun()
        with c_no:
            if st.button("Cancel", use_container_width=True):
                st.session_state.pending_action = None
                st.session_state.pending_explainer = ""
                st.session_state.assistant_last_reply = "Cancelled. No changes made."
                st.rerun()

    with st.form("assistant_form", clear_on_submit=True):
        user_msg = st.text_input(
            "Assistant",
            key="assistant_input",
            placeholder="Ask… e.g. 'Switch to Auto', 'Fan On', 'Set Sleep cool to 78', 'Set location to Berkeley CA'",
            label_visibility="collapsed",
        )
        sent = st.form_submit_button("Send")

    st.markdown("</div></div>", unsafe_allow_html=True)

    if sent:
        user_msg = (user_msg or "").strip()
        if not user_msg:
            return

        st.session_state.assistant_messages.append({"role": "user", "content": user_msg})
        try:
            with st.spinner("Thinking…"):
                reply_text, action = call_openrouter(user_msg)
        except Exception as e:
            st.session_state.assistant_last_reply = f"LLM error: {e}"
            st.rerun()

        st.session_state.assistant_messages.append({"role": "assistant", "content": reply_text})
        st.session_state.assistant_last_reply = reply_text

        if action:
            st.session_state.pending_action = action
            st.session_state.pending_explainer = "Confirm to apply. This may affect comfort and energy use."

        st.rerun()

# =========================================================
# Views
# =========================================================
st.markdown('<div class="frame">', unsafe_allow_html=True)

if st.session_state.view == "Home":
    topbar("My ecobee", left_symbol="👤", right_symbol="⚙")

    heat_sp = get_sp(st.session_state.comfort, "heat")
    cool_sp = get_sp(st.session_state.comfort, "cool")

    # Build outdoor weather display
    outdoor_chip = "Outdoor: —"
    if st.session_state.outdoor_temp_f is not None:
        outdoor_chip = f"Outdoor: {st.session_state.outdoor_temp_f:.0f}°F"
        if st.session_state.outdoor_humidity is not None:
            outdoor_chip += f", {st.session_state.outdoor_humidity:.0f}% RH"

    st.markdown(
        f"""
        <div class="statusrow">
          <div class="chip">{ico('💧')} <b style="color:{WHITE}">{st.session_state.humidity}%</b></div>
          <div class="chip">{ico('🌬')} <b style="color:{WHITE}">{st.session_state.air_quality}</b></div>
          <div class="chip">{ico('📍')} <b style="color:{WHITE}">{st.session_state.location}</b></div>
          <div class="chip">{ico('🌡️')} <b style="color:{WHITE}">{outdoor_chip}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f'<div class="bigtemp">{st.session_state.indoor_temp}</div>', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="comfortline">
          {ico(comfort_icon(st.session_state.comfort))} <span>{st.session_state.comfort}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Mode + fan controls (the assistant can propose changing these)
    c1, c2 = st.columns([1.4, 1.0])
    with c1:
        hvac_modes = ["Off", "Heat", "Cool", "Auto", "Aux"]
        st.session_state.hvac_mode = st.selectbox(
            "System Mode",
            hvac_modes,
            index=hvac_modes.index(st.session_state.hvac_mode),
            label_visibility="collapsed",
        )
    with c2:
        st.session_state.fan_on = st.toggle("Fan On", value=st.session_state.fan_on)

    st.markdown(
        f"""
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

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ===== IMPROVED WEATHER UPDATE SECTION =====
    st.markdown("### 🌤️ Outdoor Weather")
    
    # Location input and auto-detect button
    col_input, col_auto = st.columns([2, 1])
    with col_input:
        st.session_state.location = st.text_input(
            "Location", 
            value=st.session_state.location, 
            placeholder="e.g., Berkeley, California, USA",
            label_visibility="collapsed"
        )
    with col_auto:
        if st.button("📍 Auto", use_container_width=True, help="Auto-detect location using GPS"):
            with st.spinner("Getting your location..."):
                # Get browser geolocation (GPS-based, much more accurate!)
                loc = get_geolocation()
                
                if loc and 'coords' in loc:
                    lat = loc['coords']['latitude']
                    lon = loc['coords']['longitude']
                    
                    # Reverse geocode to get city name
                    try:
                        reverse_geo = requests.get(
                            "https://geocoding-api.open-meteo.com/v1/search",
                            params={
                                "name": f"{lat},{lon}",
                                "count": 1,
                                "language": "en",
                                "format": "json"
                            },
                            timeout=10
                        )
                        reverse_geo.raise_for_status()
                        geo_data = reverse_geo.json()
                        
                        if geo_data.get('results'):
                            result = geo_data['results'][0]
                            location_str = nice_place(result)
                        else:
                            location_str = f"{lat:.4f}, {lon:.4f}"
                    except:
                        location_str = f"{lat:.4f}, {lon:.4f}"
                    
                    st.session_state.location = location_str
                    
                    # Immediately fetch weather for detected location
                    temp_f, humidity, weather_status = fetch_current_weather(lat, lon)
                    
                    if temp_f is None:
                        st.session_state.outdoor_temp_f = None
                        st.session_state.outdoor_humidity = None
                        st.session_state.weather_status = f"❌ {weather_status} for {location_str}"
                        st.session_state.assistant_last_reply = st.session_state.weather_status
                    else:
                        st.session_state.outdoor_temp_f = temp_f
                        st.session_state.outdoor_humidity = humidity
                        humidity_text = f", {humidity:.0f}% RH" if humidity else ""
                        st.session_state.weather_status = f"✅ GPS location: {location_str}"
                        st.session_state.assistant_last_reply = f"Location detected! {temp_f:.0f}°F{humidity_text} in {location_str}"
                    
                    # Clear any previous geocoding results
                    st.session_state.geo_results = []
                    st.session_state.geo_choice = 0
                else:
                    st.session_state.assistant_last_reply = "❌ Could not access location. Please allow location access in your browser or enter manually."
                    st.session_state.weather_status = "Location access denied or unavailable"
                
                st.rerun()

    if st.button("🔄 Update Outdoor Weather", use_container_width=True):
        with st.spinner("Fetching location and weather..."):
            # Step 1: Geocode
            results, geo_status = geocode_candidates(st.session_state.location)
            
            if not results:
                st.session_state.weather_status = geo_status
                st.session_state.outdoor_temp_f = None
                st.session_state.outdoor_humidity = None
                st.session_state.assistant_last_reply = f"❌ {geo_status}"
                st.rerun()
            
            # Step 2: Use first result (or user's choice if they selected one)
            st.session_state.geo_results = results
            idx = min(int(st.session_state.geo_choice), len(results) - 1)
            chosen = results[idx]
            lat, lon = chosen["latitude"], chosen["longitude"]
            place = nice_place(chosen)
            
            # Step 3: Fetch weather
            temp_f, humidity, weather_status = fetch_current_weather(lat, lon)
            
            if temp_f is None:
                st.session_state.outdoor_temp_f = None
                st.session_state.outdoor_humidity = None
                st.session_state.weather_status = f"❌ {weather_status} for {place}"
                st.session_state.assistant_last_reply = st.session_state.weather_status
            else:
                st.session_state.outdoor_temp_f = temp_f
                st.session_state.outdoor_humidity = humidity
                humidity_text = f", {humidity:.0f}% RH" if humidity else ""
                st.session_state.weather_status = f"✅ Updated for {place}"
                st.session_state.assistant_last_reply = f"Weather updated! {temp_f:.0f}°F{humidity_text} in {place}"
            
            st.rerun()

    # Show multiple location candidates if available
    if st.session_state.geo_results and len(st.session_state.geo_results) > 1:
        st.markdown("**Multiple locations found. Select the correct one:**")
        labels = [
            f"{nice_place(r)} • ({r.get('latitude'):.3f}, {r.get('longitude'):.3f})"
            for r in st.session_state.geo_results
        ]
        st.session_state.geo_choice = st.selectbox(
            "Select location",
            list(range(len(labels))),
            index=min(st.session_state.geo_choice, len(labels)-1),
            format_func=lambda i: labels[i],
            label_visibility="collapsed"
        )
        st.info("After selecting, click 'Update Outdoor Weather' again to fetch weather for this location.")

    # Status display
    if st.session_state.weather_status != "Not updated":
        if "✅" in st.session_state.weather_status:
            st.success(st.session_state.weather_status)
        elif "❌" in st.session_state.weather_status:
            st.error(st.session_state.weather_status)
        else:
            st.info(st.session_state.weather_status)

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
    st.write("Reports placeholder (connect telemetry later).")

elif st.session_state.view == "Menu":
    topbar("Main Menu", left_symbol="✕", right_symbol="")
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

assistant_bar()
bottom_nav()
