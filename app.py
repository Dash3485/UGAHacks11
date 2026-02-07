import streamlit as st
import pandas as pd
import requests
from google import genai

# ---------------- CONFIG ----------------
LAT = 33.66
LON = -84.53

POLLEN_LOW = 20
POLLEN_HIGH = 40

INVENTORY_DATA = [
    {"ID": "VH-001", "Model": "Ford F-150", "Color": "Black", "Parked": "Outdoor - Row A", "lat": 33.6612, "lon": -84.5305},
    {"ID": "VH-002", "Model": "Tesla Model 3", "Color": "White", "Parked": "Indoor - Hall B", "lat": 33.6605, "lon": -84.5310},
    {"ID": "VH-003", "Model": "Toyota Camry", "Color": "Blue", "Parked": "Outdoor - Row C", "lat": 33.6618, "lon": -84.5295},
    {"ID": "VH-004", "Model": "BMW X5", "Color": "Black", "Parked": "Outdoor - Row A", "lat": 33.6611, "lon": -84.5301},
    {"ID": "VH-005", "Model": "Rivian R1T", "Color": "Green", "Parked": "Outdoor - Row D", "lat": 33.6620, "lon": -84.5320},
]

GOOG_API_KEY = st.secrets.get("GOOGLE_API_KEY")

# ---------------- DATA ----------------
def get_pollen_data():
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "current": ["us_aqi", "pm10"],
        "timezone": "America/New_York"
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        st.error(f"Weather API error: {e}")
        return None

# ---------------- LOGIC ----------------
def compute_strategy(pollen):
    if pollen >= POLLEN_HIGH:
        return "RED", "HOLD WASH", "Pollen levels are high; washing now would be wasteful."
    elif pollen <= POLLEN_LOW:
        return "GREEN", "WASH ALL", "Low pollen levels make today ideal for washing."
    else:
        return "YELLOW", "LIMITED WASH", "Moderate pollen levels — wash only priority vehicles."

def ai_explanation(pollen, aqi, decision):
    if not GOOG_API_KEY:
        return "AI explanation unavailable (missing API key)."

    try:
        client = genai.Client(api_key=GOOG_API_KEY)

        prompt = f"""
        You are a fleet operations analyst.
        Explain this decision clearly for a non-technical manager.

        Pollen (PM10): {pollen}
        Air Quality Index: {aqi}
        Decision: {decision}

        Respond in 2–3 sentences.
        """

        response = client.models.generate_content(
            model="models/gemini-flash-latest",  # ✅ CONFIRMED AVAILABLE
            contents=prompt,
        )

        return response.text.strip()

    except Exception as e:
        return f"AI explanation failed: {e}"

# ---------------- UI ----------------
st.set_page_config(page_title="Cox PollenGuard", page_icon="🌤️")

st.title("🌤️ Cox Automotive: PollenGuard")
st.markdown("**Location:** Manheim Atlanta | **Purpose:** Optimize fleet wash scheduling")

data = get_pollen_data()
if not data:
    st.stop()

current = data["current"]
pollen = current.get("pm10", 0)
aqi = current.get("us_aqi", 0)

sim_mode = st.checkbox("⚠️ Simulate High Pollen (Demo)")
if sim_mode:
    pollen = 85

color, decision, reason = compute_strategy(pollen)

# Metrics
c1, c2, c3 = st.columns(3)
c1.metric("Pollen (PM10)", pollen)
c2.metric("Air Quality Index", aqi)
c3.metric("Decision", decision)

st.divider()

# Decision Display
if color == "RED":
    st.error(f"## {decision}\n{reason}")
elif color == "YELLOW":
    st.warning(f"## {decision}\n{reason}")
else:
    st.success(f"## {decision}\n{reason}")

# AI Explanation
st.subheader("🤖 AI Explanation")
st.info(ai_explanation(pollen, aqi, decision))

# Map
st.divider()
st.subheader("📍 Fleet Map")
st.map(pd.DataFrame(INVENTORY_DATA), latitude="lat", longitude="lon")

# Table
df = pd.DataFrame(INVENTORY_DATA)

def action(row):
    if color == "RED" and "Outdoor" in row["Parked"]:
        return "🔴 DO NOT WASH"
    if color == "YELLOW" and "Outdoor" in row["Parked"]:
        return "🟡 HOLD"
    return "🟢 WASH"

df["Action"] = df.apply(action, axis=1)

st.divider()
st.subheader("📋 Fleet Action Plan")
st.dataframe(df.drop(columns=["lat", "lon"]), width="stretch")

# Sustainability
saved = df[df["Action"] != "🟢 WASH"].shape[0] * 40
st.info(f"💧 Estimated water saved today: **{saved} gallons**")
