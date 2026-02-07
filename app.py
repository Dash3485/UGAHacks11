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

    inv_df = pd.DataFrame(st.session_state.inventory)

    if inv_df.empty:
        st.info("No inventory provided yet. Add items manually or upload a CSV.")
    else:
        # Define action function first (before applying to df)
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

        def get_location(row):
            # If both lat and lon are provided, reverse geocode to get location name; otherwise show the default location
            if pd.notna(row.get("lat")) and pd.notna(row.get("lon")):
                return reverse_geocode(row["lat"], row["lon"])
            else:
                return place_name

        inv_df["Action"] = inv_df.apply(action, axis=1)
        inv_df["Location"] = inv_df.apply(get_location, axis=1)

        # Determine overall decision based on all vehicle actions
        wash_vehicles = (inv_df["Action"] == "🟢 WASH").sum()
        hold_vehicles = (inv_df["Action"] != "🟢 WASH").sum()
        total_vehicles = len(inv_df)

        # Override the overall decision if there's a mix
        if wash_vehicles > 0 and hold_vehicles > 0:
            # Mixed state: some wash, some hold
            color = "ORANGE"
            wash_list = inv_df[inv_df["Action"] == "🟢 WASH"]["Make"].apply(lambda x: x.capitalize()).tolist()
            hold_list = inv_df[inv_df["Action"] != "🟢 WASH"]["Make"].apply(lambda x: x.capitalize()).tolist()
            decision = "MIXED FLEET"
            reason = f"Wash: {', '.join(wash_list)}\n\nHold/Do Not Wash: {', '.join(hold_list)}"
        elif wash_vehicles == total_vehicles:
            # All vehicles can wash
            color = "GREEN"
            decision = "WASH ALL"
            reason = "All vehicles are clear to wash."
        else:
            # All vehicles on hold
            color = "RED"
            decision = "HOLD WASH"
            reason = "One or more vehicles require washing to be held."

        # METRICS
        c1, c2, c3 = st.columns(3)
        c1.metric("Pollen (PM10)", round(pollen, 1))
        c2.metric("Air Quality Index", aqi)
        c3.metric("Decision", decision)

        st.divider()

        #  DECISION
        if color == "RED":
            st.error(f"## {decision}\n{reason}")
        elif color == "ORANGE":
            st.warning(f"## {decision}\n{reason}")
        else:
            st.success(f"## {decision}\n{reason}")

        #  AI
        st.subheader("🤖 AI Explanation")
        st.info(ai_explanation(pollen, aqi, decision))

        st.divider()

        st.divider()
        
        # Prepare map data: use vehicle-specific coords if both lat AND lon provided, else use default location
        map_data = []
        for _, row in inv_df.iterrows():
            if pd.notna(row.get("lat")) and pd.notna(row.get("lon")):
                # Vehicle has both coordinates
                map_data.append({"latitude": row["lat"], "longitude": row["lon"], "source": "vehicle", "id": row.get("Make", "")})
            else:
                # Use default location from top of page
                map_data.append({"latitude": LAT, "longitude": LON, "source": "default", "id": row.get("Make", "")})
        
        map_df = pd.DataFrame(map_data)
        
        st.subheader("📍 Fleet Map")
        if not map_df.empty:
            st.map(map_df, latitude="latitude", longitude="longitude")
        else:
            st.info("No coordinates to display on the map.")

        st.subheader("📋 Fleet Action Plan")
        if "lat" in disp.columns and "lon" in disp.columns:
            disp = disp.drop(columns=[c for c in ["lat", "lon"] if c in disp.columns])
        
        # Add removal buttons
        st.write("**Manage Vehicles:**")
        cols = st.columns([2, 1, 1, 1, 1, 1, 1])
        cols[0].write("**Make**")
        cols[1].write("**Model**")
        cols[2].write("**Color**")
        cols[3].write("**Parked**")
        cols[4].write("**Action**")
        cols[5].write("**Location**")
        cols[6].write("**Remove**")
        
        for idx, (i, row) in enumerate(disp.iterrows()):
            cols = st.columns([2, 1, 1, 1, 1, 1, 1])
            cols[0].write(str(row.get("Make", "")).capitalize())
            cols[1].write(str(row.get("Model", "")).capitalize())
            cols[2].write(str(row.get("Color", "")).capitalize())
            cols[3].write(str(row.get("Parked", "")).capitalize())
            cols[4].write(row.get("Action", ""))
            cols[5].write(str(row.get("Location", "")))
            if cols[6].button("❌", key=f"remove_{idx}"):
                st.session_state.inventory.pop(i)
                st.rerun()

            saved = inv_df[inv_df["Action"] != "🟢 WASH"].shape[0] * 40
            st.info(f"💧 Estimated water saved today: **{saved} gallons**")
