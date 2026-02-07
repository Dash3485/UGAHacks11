import streamlit as st
import pandas as pd
import requests
from google import genai

# ---------------- CONFIG ----------------
POLLEN_LOW = 20
POLLEN_HIGH = 40

# Inventory will be provided by the user via the UI (session state / CSV upload)

GOOG_API_KEY = st.secrets.get("GOOGLE_API_KEY")

# ---------------- GEO ----------------
@st.cache_data(show_spinner=False)
def geocode_location(query):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": query,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    if "results" not in data:
        return None

    result = data["results"][0]
    return result["latitude"], result["longitude"], result["name"], result.get("country", "")

# ---------------- DATA ----------------
def get_pollen_data(lat, lon):
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ["us_aqi", "pm10"],
        "timezone": "auto"
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

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
            model="models/gemini-flash-latest",
            contents=prompt,
        )

        return response.text.strip()

    except Exception as e:
        return f"AI explanation failed: {e}"

# ---------------- UI ----------------
st.set_page_config(page_title="Cox PollenGuard", page_icon="🌤️")

st.title("🌤️ Cox Automotive: PollenGuard")
st.markdown("**Purpose:** Optimize fleet wash scheduling across any location")

# 🔍 LOCATION SEARCH
st.subheader("📍 Location")
location_query = st.text_input(
    "Search for a city, address, or ZIP code",
    value="Manheim Atlanta"
)

geo = geocode_location(location_query)
if not geo:
    st.error("Location not found. Please try another search.")
    st.stop()

LAT, LON, place_name, country = geo
st.caption(f"Using location: **{place_name}, {country}**")

# 🌦 DATA
data = get_pollen_data(LAT, LON)
current = data["current"]

pollen = current.get("pm10", 0)
aqi = current.get("us_aqi", 0)

sim_mode = st.checkbox("⚠️ Simulate High Pollen (Demo)")
if sim_mode:
    pollen = 85

color, decision, reason = compute_strategy(pollen)

# 📊 METRICS
c1, c2, c3 = st.columns(3)
c1.metric("Pollen (PM10)", round(pollen, 1))
c2.metric("Air Quality Index", aqi)
c3.metric("Decision", decision)

st.divider()

# 🚦 DECISION
if color == "RED":
    st.error(f"## {decision}\n{reason}")
elif color == "YELLOW":
    st.warning(f"## {decision}\n{reason}")
else:
    st.success(f"## {decision}\n{reason}")

# 🤖 AI
st.subheader("🤖 AI Explanation")
st.info(ai_explanation(pollen, aqi, decision))

# Map
st.divider()
st.subheader("🧾 Inventory Input")

if "inventory" not in st.session_state:
    st.session_state.inventory = []

with st.expander("Add single vehicle manually"):
    with st.form("add_vehicle", clear_on_submit=True):
        id_in = st.text_input("ID")
        model_in = st.text_input("Model")
        color_in = st.text_input("Color")
        parked_in = st.text_input("Parked (e.g., Outdoor - Row A)")
        lat_in = st.text_input("Latitude (optional)")
        lon_in = st.text_input("Longitude (optional)")
        add_submit = st.form_submit_button("Add to inventory")
        if add_submit:
            try:
                lat_v = float(lat_in) if lat_in.strip() != "" else None
                lon_v = float(lon_in) if lon_in.strip() != "" else None
            except Exception:
                st.error("Latitude and Longitude must be numeric or left blank.")
                lat_v = None
                lon_v = None

            item = {
                "ID": id_in or "",
                "Model": model_in or "",
                "Color": color_in or "",
                "Parked": parked_in or "",
                "lat": lat_v,
                "lon": lon_v,
            }
            st.session_state.inventory.append(item)
            st.success("Vehicle added to inventory.")

st.markdown("**Or upload a CSV** (columns: ID,Model,Color,Parked,lat,lon)")
upload = st.file_uploader("Upload CSV", type=["csv"])
if upload is not None:
    try:
        uploaded_df = pd.read_csv(upload)
        required = ["ID", "Model", "Color", "Parked", "lat", "lon"]
        missing = [c for c in required if c not in uploaded_df.columns]
        if missing:
            st.error(f"CSV missing columns: {', '.join(missing)}")
        else:
            for _, r in uploaded_df.iterrows():
                lat_v = float(r["lat"]) if pd.notna(r["lat"]) else None
                lon_v = float(r["lon"]) if pd.notna(r["lon"]) else None
                st.session_state.inventory.append({
                    "ID": str(r.get("ID", "")),
                    "Model": str(r.get("Model", "")),
                    "Color": str(r.get("Color", "")),
                    "Parked": str(r.get("Parked", "")),
                    "lat": lat_v,
                    "lon": lon_v,
                })
            st.success(f"Imported {len(uploaded_df)} rows into inventory.")
    except Exception as e:
        st.error(f"Failed to read CSV: {e}")

inv_df = pd.DataFrame(st.session_state.inventory)

if inv_df.empty:
    st.info("No inventory provided yet. Add items manually or upload a CSV.")
else:
    # Map: show only rows with valid coordinates
    coords_df = inv_df.dropna(subset=["lat", "lon"]) if not inv_df.empty else pd.DataFrame()
    st.divider()
    st.subheader("📍 Fleet Map")
    if not coords_df.empty:
        st.map(coords_df, latitude="lat", longitude="lon")
    else:
        st.info("No valid coordinates to display on the map.")

    def action(row):
        parked = row.get("Parked", "") or ""
        if color == "RED" and "Outdoor" in parked:
            return "🔴 DO NOT WASH"
        if color == "YELLOW" and "Outdoor" in parked:
            return "🟡 HOLD"
        return "🟢 WASH"

    inv_df["Action"] = inv_df.apply(action, axis=1)

    st.divider()
    st.subheader("📋 Fleet Action Plan")
    disp = inv_df.copy()
    if "lat" in disp.columns and "lon" in disp.columns:
        disp = disp.drop(columns=[c for c in ["lat", "lon"] if c in disp.columns])
    st.dataframe(disp, use_container_width=True)

    saved = inv_df[inv_df["Action"] != "🟢 WASH"].shape[0] * 40
    st.info(f"💧 Estimated water saved today: **{saved} gallons**")