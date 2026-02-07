import streamlit as st
import pandas as pd
import requests
from google import genai

# ---------------- CONFIG ----------------
POLLEN_LOW = 20
POLLEN_HIGH = 40
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
    res = data["results"][0]
    return res["latitude"], res["longitude"], res["name"], res.get("country", "")

@st.cache_data(show_spinner=False)
def reverse_geocode(lat, lon):
    url = "https://geocoding-api.open-meteo.com/v1/reverse"
    params = {"latitude": lat, "longitude": lon, "language": "en"}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if "results" in data and data["results"]:
            res = data["results"][0]
            city = res.get("name", "Unknown")
            country = res.get("country", "")
            return f"{city}, {country}" if country else city
    except Exception:
        pass
    return f"{lat}, {lon}"

# ---------------- DATA ----------------
@st.cache_data(show_spinner=False)
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
        return None, "AI explanation unavailable (missing API key)."

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

        return response.text.strip(), None

    except Exception as e:
        msg = str(e).lower()
        if "quota" in msg or "resource_exhausted" in msg:
            return None, "⚠️ AI quota has been reached. Please try again later."
        return None, f"AI explanation failed: {e}"

# ---------------- UI ----------------
st.set_page_config(page_title="Cox PollenGuard", page_icon="🌤️")

st.title("🌤️ Cox Automotive: PollenGuard")
st.markdown("**Purpose:** Optimize fleet wash scheduling across any location")

# ---------- LOCATION ----------
st.subheader("📍 Location")
location_query = st.text_input("Search for a city, address, or ZIP code", value="30602")

geo = geocode_location(location_query)
if not geo:
    st.error("Location not found. Please try another search.")
    st.stop()

LAT, LON, place_name, country = geo
st.caption(f"Using location: **{place_name}, {country}**")

# ---------- INVENTORY INPUT ----------
st.divider()
st.subheader("🧾 Inventory Input")

if "inventory" not in st.session_state:
    st.session_state.inventory = []

if "ai_result" not in st.session_state:
    st.session_state.ai_result = None

if "ai_error" not in st.session_state:
    st.session_state.ai_error = None

with st.expander("Add single vehicle manually"):
    with st.form("add_vehicle", clear_on_submit=True):
        make_in = st.text_input("Make")
        model_in = st.text_input("Model")
        color_in = st.text_input("Color")
        parked_in = st.selectbox("Parked", ["Inside", "Outside"], index=1)
        lat_in = st.text_input("Latitude (optional)")
        lon_in = st.text_input("Longitude (optional)")
        submit_add = st.form_submit_button("Add to inventory")

        if submit_add:
            try:
                lat_v = float(lat_in) if lat_in.strip() else None
                lon_v = float(lon_in) if lon_in.strip() else None
            except Exception:
                st.error("Latitude and Longitude must be numeric.")
                lat_v, lon_v = None, None

            st.session_state.inventory.append({
                "Make": make_in,
                "Model": model_in,
                "Color": color_in,
                "Parked": parked_in,
                "lat": lat_v,
                "lon": lon_v,
            })
            st.success("Vehicle added.")

st.markdown("**Or upload a CSV** (Make, Model, Color, Parked, lat, lon)")
upload = st.file_uploader("Upload CSV", type=["csv"])
if upload:
    df_up = pd.read_csv(upload)
    required = ["Make", "Model", "Color", "Parked", "lat", "lon"]
    missing = [c for c in required if c not in df_up.columns]
    if missing:
        st.error(f"CSV missing columns: {', '.join(missing)}")
    else:
        for _, r in df_up.iterrows():
            st.session_state.inventory.append({
                "Make": str(r["Make"]),
                "Model": str(r["Model"]),
                "Color": str(r["Color"]),
                "Parked": str(r["Parked"]),
                "lat": float(r["lat"]) if pd.notna(r["lat"]) else None,
                "lon": float(r["lon"]) if pd.notna(r["lon"]) else None,
            })
        st.success(f"Imported {len(df_up)} vehicles.")

if st.session_state.inventory:
    preview = pd.DataFrame(st.session_state.inventory).drop(columns=["lat", "lon"], errors="ignore")
    for col in preview.columns:
        if preview[col].dtype == "object":
            preview[col] = preview[col].str.capitalize()
    st.dataframe(preview, use_container_width=True, hide_index=True)

# ---------- CONTROLS ----------
st.divider()
sim_mode = st.checkbox("⚠️ Simulate High Pollen (Demo)")
submit_pressed = st.button("Generate Wash Recommendation", type="primary")

# Simulate pollen checkbox (outside submit block so it persists)
if "sim_mode" not in st.session_state:
    st.session_state.sim_mode = False
sim_mode = st.checkbox("⚠️ Simulate High Pollen (Demo)", value=st.session_state.sim_mode)
st.session_state.sim_mode = sim_mode

if submit_pressed:
    #  DATA
    data = get_pollen_data(LAT, LON)
    current = data["current"]

    pollen = current.get("pm10", 0)
    aqi = current.get("us_aqi", 0)

    if st.session_state.sim_mode:
        pollen = 85

    color, decision, reason = compute_strategy(pollen)

    c1, c2, c3 = st.columns(3)
    c1.metric("Pollen (PM10)", pollen)
    c2.metric("Air Quality Index", aqi)
    c3.metric("Decision", decision)

    tabs = st.tabs(["📊 Dashboard", "🤖 AI Explanation", "🗺 Fleet Map", "📋 Action Plan"])

    with tabs[0]:
        if color == "RED":
            st.error(f"## {decision}\n{reason}")
        elif color == "YELLOW":
            st.warning(f"## {decision}\n{reason}")
        else:
            st.success(f"## {decision}\n{reason}")

    with tabs[1]:
        ai_disabled = st.session_state.ai_error is not None and "quota" in st.session_state.ai_error.lower()

        if st.button("Generate AI Explanation", disabled=ai_disabled):
            res, err = ai_explanation(pollen, aqi, decision)
            st.session_state.ai_result = res
            st.session_state.ai_error = err

        if st.session_state.ai_result:
            st.info(st.session_state.ai_result)
        elif st.session_state.ai_error:
            st.warning(st.session_state.ai_error)
        else:
            st.caption("Click the button to generate an AI explanation (uses limited quota).")

    with tabs[2]:
        inv_df = pd.DataFrame(st.session_state.inventory)
        if not inv_df.empty:
            st.map(pd.DataFrame({
                "latitude": inv_df["lat"].fillna(LAT),
                "longitude": inv_df["lon"].fillna(LON),
            }))
        else:
            st.info("No inventory provided.")

    with tabs[3]:
        inv_df = pd.DataFrame(st.session_state.inventory)
        if inv_df.empty:
            st.info("No inventory provided.")
        else:
            st.info("No coordinates to display on the map.")

        def action(row):
            parked = row.get("Parked", "") or ""
            
            # Determine pollen for this vehicle
            vehicle_pollen = pollen
            if pd.notna(row.get("lat")) and pd.notna(row.get("lon")):
                # Vehicle has custom coordinates - fetch actual pollen data (not simulated)
                try:
                    vehicle_data = get_pollen_data(row["lat"], row["lon"])
                    vehicle_pollen = vehicle_data["current"].get("pm10", pollen)
                except Exception:
                    vehicle_pollen = pollen
            
            # Compute action based on vehicle's pollen level
            vehicle_color, _, _ = compute_strategy(vehicle_pollen)
            
            if vehicle_color == "RED" and parked == "Outside":
                return "🔴 DO NOT WASH"
            if vehicle_color == "YELLOW" and parked == "Outside":
                return "🟡 HOLD"
            return "🟢 WASH"

            inv_df["Action"] = inv_df.apply(action, axis=1)
            inv_df["Location"] = inv_df.apply(
                lambda r: reverse_geocode(r["lat"], r["lon"]) if pd.notna(r["lat"]) else place_name,
                axis=1
            )

            display = inv_df.drop(columns=["lat", "lon"], errors="ignore")
            st.dataframe(display, use_container_width=True, hide_index=True)

            saved = inv_df[inv_df["Action"] != "🟢 WASH"].shape[0] * 40
            st.info(f"💧 Estimated water saved today: **{saved} gallons**")
