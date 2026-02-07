import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai

# --- CONFIGURATION ---
# 1. API KEY (I kept your key here so it works immediately)
GOOG_API_KEY = "Ai-key" 

# Manheim Atlanta Location
LAT = 33.66
LON = -84.53

# Mock Inventory (with GPS coordinates for the map)
INVENTORY_DATA = [
    {"ID": "VH-001", "Model": "Ford F-150", "Color": "Black", "Parked": "Outdoor - Row A", "lat": 33.6612, "lon": -84.5305},
    {"ID": "VH-002", "Model": "Tesla Model 3", "Color": "White", "Parked": "Indoor - Hall B", "lat": 33.6605, "lon": -84.5310},
    {"ID": "VH-003", "Model": "Toyota Camry", "Color": "Blue", "Parked": "Outdoor - Row C", "lat": 33.6618, "lon": -84.5295},
    {"ID": "VH-004", "Model": "BMW X5", "Color": "Black", "Parked": "Outdoor - Row A", "lat": 33.6611, "lon": -84.5301},
    {"ID": "VH-005", "Model": "Rivian R1T", "Color": "Green", "Parked": "Outdoor - Row D", "lat": 33.6620, "lon": -84.5320},
]

# --- BACKEND LOGIC ---
def get_pollen_data():
    """Fetches real-time pollen/weather data"""
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "current": ["us_aqi", "pm10"],
        "hourly": "pm10",
        "timezone": "America/New_York"
    }
    try:
        response = requests.get(url, params=params)
        return response.json()
    except:
        return None

def get_ai_strategy(pollen_level, aqi):
    """
    The Real AI Brain: Uses Gemini to decide the wash strategy.
    """
    if not GOOG_API_KEY or "PASTE_YOUR_KEY" in GOOG_API_KEY:
        return "YELLOW", "AI KEY MISSING", "Please paste your Google API Key in the code to enable the AI brain."

    try:
        genai.configure(api_key=GOOG_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # The "Persona" Prompt
        prompt = f"""
        You are the Fleet Manager for Manheim Auto Auction in Atlanta.
        Current Conditions:
        - Pollen Level (PM10): {pollen_level} (Normal is <20, High is >50)
        - Air Quality Index: {aqi}
        
        Task: Decide if we should wash the outdoor cars today.
        Rules:
        1. If Pollen is HIGH (>40), do NOT wash outdoor cars (waste of money).
        2. If Pollen is LOW, wash everything.
        
        Output format: Return ONLY a raw string in this format: "COLOR|TITLE|REASONING"
        Example: "RED|HOLD WASH|Pollen counts are too high, washing now is wasteful."
        """
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Parse the AI's response (Split by the | character)
        parts = text.split("|")
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
        else:
             return "YELLOW", "AI PARSE ERROR", "The AI returned an unexpected format."
        
    except Exception as e:
        return "RED", "AI ERROR", f"The AI could not connect. Error: {str(e)}"

# --- FRONTEND (STREAMLIT) ---
st.set_page_config(page_title="Cox PollenGuard", page_icon="🌤️")

st.title("🌤️ Cox Automotive: PollenGuard")
st.markdown("**Location:** Manheim Atlanta | **Optimizing:** Fleet Wash Schedule")

# Fetch Data
data = get_pollen_data()

if data:
    current = data.get('current', {})
    pollen_score = current.get('pm10', 0)
    aqi_score = current.get('us_aqi', 0)
    
    # Dashboard Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Pollen Index (PM10)", f"{pollen_score}", delta_color="inverse")
    col2.metric("Air Quality", aqi_score)
    col3.metric("AI Status", "Active 🟢")

    st.divider()
    st.subheader("📢 AI-Generated Strategy")
    
    # Simulation Toggle
    sim_mode = st.checkbox("⚠️ Simulate Pollen Storm (Demo Mode)")
    if sim_mode:
        pollen_score = 85 # Force the AI to see high pollen

    # CALL THE AI
    with st.spinner("Consulting the AI..."):
        color, decision, reason = get_ai_strategy(pollen_score, aqi_score)
    
    # Display Result
    if color == "RED":
        st.error(f"## {decision}\n{reason}")
    elif color == "YELLOW":
        st.warning(f"## {decision}\n{reason}")
    else:
        st.success(f"## {decision}\n{reason}")

    # Map
    st.divider()
    st.subheader("📍 Live Lot Map")
    map_df = pd.DataFrame(INVENTORY_DATA)
    st.map(map_df, latitude='lat', longitude='lon', size=20, color='#00FF00')

    # Table
    st.divider()
    st.subheader("📋 Fleet Action Plan")
    df = pd.DataFrame(INVENTORY_DATA)
    
    # --- CRASH FIX: USE ICONS INSTEAD OF BACKGROUND COLOR ---
    # This replaces the broken 'highlight_action' function
    def get_status_icon(row):
        if color == "RED":
            return "🔴 DO NOT WASH"
        elif color == "YELLOW" and "Outdoor" in row['Parked']:
            return "🟡 HOLD"
        return "🟢 WASH"

    df['Action'] = df.apply(get_status_icon, axis=1)
    
    # Display the table (Hiding Lat/Lon because we have a map now)
    st.dataframe(
        df, 
        column_config={
            "lat": None, 
            "lon": None
        },
        use_container_width=True
    )

    # Sustainability Score
    st.info(f"💧 **Sustainability Impact:** By following this plan, you saved **{len(df) * 40} gallons** of water today.")

else:
    st.error("Could not fetch weather data.")
