##  PollenGuard

**Names: Collin Cabrera, Dash Duxbury, Turner Lent**

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

##  Tools used
- **Frontend / App Framework:** Streamlit
- **Data:** Open-Meteo Air Quality API, Pandas
- **AI:** Google Gemini (`gemini-flash-latest`)
- **Mapping:** Streamlit map visualization
- **Language:** Python 3.9+

--- 
##  Problems that group ran into 
-** A problem that we ran into was it was our first time working collaboratively on a shared git hub repository. We stuggled at first with pushing at the same time and with figuring out how to distribute work equally and efficiently. After some trial and error and online tutorials we over came the issue and ended up working more cohesvily as a group. Another issue we ran into as a group was the front end of our project. We wanted a simple and streamline experience for the user but werent sure what we should use. We settled on streamline as it seemed to fulfill what we were looking for.
---

## To run project you need to plug in own gemini api key

###  Clone the repository
```bash
git clone https://github.com/Dash3485/UGAHacks11.git
cd UGAHacks11
