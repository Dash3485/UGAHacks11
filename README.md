# PollenGuard

**PollenGuard** is a data-driven decision support tool that helps automotive fleet operators optimize vehicle wash scheduling based on real-time air quality and pollen conditions. Built with Streamlit and powered by live environmental data and AI-generated explanations, PollenGuard reduces unnecessary washes, saves water, and improves fleet presentation efficiency.

---

##  Problem
Fleet operators frequently wash vehicles on fixed schedules, even when there is a high pollen count or poor air quality, this will immediately undo the cleaning. This leads to:
- Wasted water and labor
- Increased operational costs
- Inefficient sustainability practices

---

##  Solution
PollenGuard  evaluates local pollen (PM10) and air quality data to determine whether fleets should:
- **WASH ALL**
- **LIMITED WASH**
- **HOLD WASH**

An integrated AI explanation layer translates environmental data into clear, non-technical reasoning for managers and stakeholders.

---

##  Key Features
-  **Location-based search** (city, address, zipcode)
-  **Live air quality & pollen data** via Open-Meteo API
-  **AI-generated decision explanations** using Google Gemini
-  **Interactive fleet map visualization**
-  **Actionable fleet-level wash recommendations**
-  **Estimated water savings calculation**
-  **High pollen simulation mode** for demos

---

##  Decision Logic
| Condition | Action |
|--------|--------|
| Low pollen (PM10 ≤ 20) |  Wash all vehicles |
| Moderate pollen (20 < PM10 < 40) |  Limited wash |
| High pollen (PM10 ≥ 40) |  Hold wash |

---

##  Tech Stack
- **Frontend / App Framework:** Streamlit
- **Data:** Open-Meteo Air Quality API
- **AI:** Google Gemini (`gemini-flash-latest`)
- **Mapping:** Streamlit map visualization
- **Language:** Python 3.9+

---

##  Running Locally

###  Clone the repository
```bash
git clone https://github.com/Dash3485/UGAHacks11.git
cd UGAHacks11
