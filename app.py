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

@st.cache_data(show_spinner=False)
def reverse_geocode(lat, lon):
    """Reverse geocode coordinates to get location name."""
    url = "https://geocoding-api.open-meteo.com/v1/reverse"
    params = {
        "latitude": lat,
        "longitude": lon,
        "language": "en"
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if "results" in data and len(data["results"]) > 0:
            result = data["results"][0]
            city = result.get("name", "Unknown")
            country = result.get("country", "")
            return f"{city}, {country}" if country else city
    except Exception:
        pass
    return f"{lat}, {lon}"

@st.cache_data(show_spinner=False)
def geocode_zipcode(zipcode):
    """Geocode a zipcode to get location name and coordinates."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": zipcode,
        "count": 1,
        "language": "en",
        "format": "json"
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if "results" in data and len(data["results"]) > 0:
            result = data["results"][0]
            city = result.get("name", "Unknown")
            country = result.get("country", "")
            location_name = f"{city}, {country}" if country else city
            return location_name
    except Exception:
        pass
    return None

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

with open(".streamlit/style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.title("🌤️ Cox Automotive: PollenGuard")
st.markdown("**Purpose:** Optimize fleet wash scheduling across any location")

# 🔍 LOCATION SEARCH
st.subheader("📍 Location")
location_query = st.text_input(
    "Search for a city, address, or ZIP code",
    value="30602"
)

geo = geocode_location(location_query)
if not geo:
    st.error("Location not found. Please try another search.")
    st.stop()

LAT, LON, place_name, country = geo
st.caption(f"Using location: **{place_name}, {country}**")

# INVENTORY INPUT SECTION
st.divider()
st.subheader("🧾 Inventory Input")

if "inventory" not in st.session_state:
    st.session_state.inventory = []

with st.expander("Add single vehicle manually"):
    with st.form("add_vehicle", clear_on_submit=True):
        id_in = st.text_input("ID")
        model_in = st.text_input("Model")
        color_in = st.text_input("Color")
        parked_in = st.selectbox("Parked", options=["Inside", "Outside"], index=1, key="parked_select")
        zipcode_in = st.text_input("Zipcode (optional)")
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
                "zipcode": zipcode_in or "",
                "lat": lat_v,
                "lon": lon_v,
            }
            st.session_state.inventory.append(item)
            st.success("Vehicle added to inventory.")

st.markdown("**Or upload a CSV** (columns: ID,Model,Color,Parked,zipcode,lat,lon)")
upload = st.file_uploader("Upload CSV", type=["csv"])
if upload is not None:
    try:
        uploaded_df = pd.read_csv(upload)
        required = ["ID", "Model", "Color", "Parked", "zipcode", "lat", "lon"]
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
                    "zipcode": str(r.get("zipcode", "")),
                    "lat": lat_v,
                    "lon": lon_v,
                })
            st.success(f"Imported {len(uploaded_df)} rows into inventory.")
    except Exception as e:
        st.error(f"Failed to read CSV: {e}")

# Show current inventory before submit
if st.session_state.inventory:
    st.write("**Current Inventory:**")
    preview_df = pd.DataFrame(st.session_state.inventory)
    if "zipcode" in preview_df.columns and "lat" in preview_df.columns and "lon" in preview_df.columns:
        preview_df = preview_df.drop(columns=[c for c in ["zipcode", "lat", "lon"] if c in preview_df.columns])
    # Capitalize first letter of first word in each string column
    for col in preview_df.columns:
        if preview_df[col].dtype == 'object':
            preview_df[col] = preview_df[col].apply(lambda x: x.capitalize() if isinstance(x, str) else x)
    st.dataframe(preview_df, use_container_width=True, hide_index=True)

# SUBMIT BUTTON
st.divider()
submit_pressed = st.button("Generate Wash Recommendation", type="primary")

# Simulate high pollen toggle (outside submit block so it persists)
sim_mode = st.checkbox("⚠️ Simulate High Pollen (Demo)")

if submit_pressed:
    #  DATA
    data = get_pollen_data(LAT, LON)
    current = data["current"]

    pollen = current.get("pm10", 0)
    aqi = current.get("us_aqi", 0)
    if sim_mode:
        pollen = 85

    color, decision, reason = compute_strategy(pollen)

    # METRICS
    c1, c2, c3 = st.columns(3)
    c1.metric("Pollen (PM10)", round(pollen, 1))
    c2.metric("Air Quality Index", aqi)
    c3.metric("Decision", decision)

    st.divider()

    #  DECISION
    if color == "RED":
        st.error(f"## {decision}\n{reason}")
    elif color == "YELLOW":
        st.warning(f"## {decision}\n{reason}")
    else:
        st.success(f"## {decision}\n{reason}")

    #  AI
    st.subheader("🤖 AI Explanation")
    st.info(ai_explanation(pollen, aqi, decision))

    st.divider()
    
    inv_df = pd.DataFrame(st.session_state.inventory)

    if inv_df.empty:
        st.info("No inventory provided yet. Add items manually or upload a CSV.")
    else:
        # Prepare map data: use vehicle-specific coords if both lat AND lon provided, else use default location
        map_data = []
        for _, row in inv_df.iterrows():
            if pd.notna(row.get("lat")) and pd.notna(row.get("lon")):
                # Vehicle has both coordinates
                map_data.append({"latitude": row["lat"], "longitude": row["lon"], "source": "vehicle", "id": row["ID"]})
            else:
                # Use default location from top of page
                map_data.append({"latitude": LAT, "longitude": LON, "source": "default", "id": row["ID"]})
        
        map_df = pd.DataFrame(map_data)
        
        st.subheader("📍 Fleet Map")
        if not map_df.empty:
            st.map(map_df, latitude="latitude", longitude="longitude")
        else:
            st.info("No coordinates to display on the map.")

        def action(row):
            parked = row.get("Parked", "") or ""
            if color == "RED" and parked == "Outside":
                return "🔴 DO NOT WASH"
            if color == "YELLOW" and parked == "Outside":
                return "🟡 HOLD"
            return "🟢 WASH"

        def get_location(row):
            # If both lat and lon are provided, reverse geocode; otherwise check zipcode
            lat_v = row.get("lat")
            lon_v = row.get("lon")
            zipcode_v = row.get("zipcode", "")
            
            # Both lat and lon: use them (override zipcode)
            if pd.notna(lat_v) and pd.notna(lon_v):
                return reverse_geocode(lat_v, lon_v)
            # Only zipcode or zipcode + one but not both lat/lon: use zipcode
            elif zipcode_v and zipcode_v.strip():
                geo_result = geocode_zipcode(zipcode_v)
                if geo_result:
                    return geo_result
            # Default: use place_name from top
            return place_name

        inv_df["Action"] = inv_df.apply(action, axis=1)
        inv_df["Location"] = inv_df.apply(get_location, axis=1)

        st.subheader("📋 Fleet Action Plan")
        disp = inv_df.copy()
        if "lat" in disp.columns and "lon" in disp.columns:
            disp = disp.drop(columns=[c for c in ["lat", "lon"] if c in disp.columns])
        
        # Add removal buttons
        st.write("**Manage Vehicles:**")
        cols = st.columns([2, 1, 1, 1, 1, 1, 1])
        cols[0].write("**ID**")
        cols[1].write("**Model**")
        cols[2].write("**Color**")
        cols[3].write("**Parked**")
        cols[4].write("**Action**")
        cols[5].write("**Location**")
        cols[6].write("**Remove**")
        
        for idx, (i, row) in enumerate(disp.iterrows()):
            cols = st.columns([2, 1, 1, 1, 1, 1, 1])
            cols[0].write(str(row.get("ID", "")).capitalize())
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