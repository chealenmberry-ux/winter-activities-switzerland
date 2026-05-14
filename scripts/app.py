import pandas as pd
import streamlit as st
import requests
from io import StringIO
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2

st.set_page_config(
    page_title="Swiss Winter Activity Finder",
    page_icon="❄️",
    layout="wide"
)

st.markdown(
    """
    <style>
    .stApp {
        background-color: #0a0f1f;
        color: white;
    }

    section[data-testid="stSidebar"] {
        background-color: #111827;
    }

    h1, h2, h3, p, label {
        color: white;
    }

    div[data-testid="stMetric"] {
        background-color: #1e1b4b;
        padding: 15px;
        border-radius: 10px;
    }

    hr {
        border-color: #334155;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Travel time functions
ZURICH_LAT = 47.3782
ZURICH_LON = 8.5402

def calculate_distance_from_zurich(lat, lon):
    if pd.isna(lat) or pd.isna(lon):
        return None

    earth_radius = 6371

    lat1 = radians(ZURICH_LAT)
    lon1 = radians(ZURICH_LON)
    lat2 = radians(lat)
    lon2 = radians(lon)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return earth_radius * c


def estimate_travel_time(distance_km):
    if pd.isna(distance_km):
        return None

    return distance_km / 45 * 60


# Weather functions
@st.cache_data(show_spinner=False)
def download_weather_data(station_id):
    station_id = str(station_id).strip().lower()

    try:
        nime_url = (
            f"https://data.geo.admin.ch/ch.meteoschweiz.ogd-nime/"
            f"{station_id}/ogd-nime_{station_id}_d_recent.csv"
        )

        smn_url = (
            f"https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/"
            f"{station_id}/ogd-smn_{station_id}_d_recent.csv"
        )

        nime_response = requests.get(nime_url, timeout=10)
        smn_response = requests.get(smn_url, timeout=10)

        nime_response.raise_for_status()
        smn_response.raise_for_status()

        nime = pd.read_csv(StringIO(nime_response.text), sep=";")
        smn = pd.read_csv(StringIO(smn_response.text), sep=";")

        nime.columns = nime.columns.str.strip().str.lower()
        smn.columns = smn.columns.str.strip().str.lower()

        nime_cols = ["reference_timestamp", "rre150d0", "hns000d0", "hto000d0"]
        smn_cols = ["reference_timestamp", "sre000d0", "tre200d0"]

        nime = nime[[c for c in nime_cols if c in nime.columns]]
        smn = smn[[c for c in smn_cols if c in smn.columns]]

        weather = pd.merge(nime, smn, on="reference_timestamp", how="outer")

        return weather

    except Exception as e:
        print(f"Weather download failed for {station_id}: {e}")
        return None


@st.cache_data(show_spinner=False)
def calculate_weather_summary(station_id, activity_type, selected_month):
    if pd.isna(station_id):
        return {
            "weather_score": 50,
            "sun_checks": "☀️",
            "snow_checks": "❄️",
            "avg_temp": None,
            "weather_reason": "Weather data unavailable"
        }

    weather = download_weather_data(station_id)

    if weather is None or weather.empty:
        return {
            "weather_score": 50,
            "sun_checks": "☀️",
            "snow_checks": "❄️",
            "avg_temp": None,
            "weather_reason": "Weather data unavailable"
        }

    weather["reference_timestamp"] = pd.to_datetime(
        weather["reference_timestamp"],
        errors="coerce"
    )

    weather = weather.dropna(subset=["reference_timestamp"])

    # Keep only selected month
    weather = weather[
        weather["reference_timestamp"].dt.month == selected_month
    ]

    # Use all historical data from this month
    weather = weather.sort_values("reference_timestamp")

    if weather.empty:
        return {
            "weather_score": 50,
            "sun_checks": "☀️",
            "snow_checks": "❄️",
            "avg_temp": None,
            "weather_reason": "Weather data unavailable"
        }

    avg_sunshine = weather["sre000d0"].mean() if "sre000d0" in weather else 0
    avg_snow_height = weather["hto000d0"].mean() if "hto000d0" in weather else 0
    avg_new_snow = weather["hns000d0"].mean() if "hns000d0" in weather else 0
    avg_precip = weather["rre150d0"].mean() if "rre150d0" in weather else 0
    avg_temp = weather["tre200d0"].mean() if "tre200d0" in weather else None

    avg_sunshine = 0 if pd.isna(avg_sunshine) else avg_sunshine
    avg_snow_height = 0 if pd.isna(avg_snow_height) else avg_snow_height
    avg_new_snow = 0 if pd.isna(avg_new_snow) else avg_new_snow
    avg_precip = 0 if pd.isna(avg_precip) else avg_precip

    if avg_sunshine >= 5:
        sun_checks = "☀️ ✅✅✅"
    elif avg_sunshine >= 2:
        sun_checks = "☀️ ✅✅"
    elif avg_sunshine > 0:
        sun_checks = "☀️ ✅"
    else:
        sun_checks = "☀️ —"

    if avg_snow_height >= 80:
        snow_checks = "❄️ ✅✅✅"
    elif avg_snow_height >= 30:
        snow_checks = "❄️ ✅✅"
    elif avg_snow_height > 0:
        snow_checks = "❄️ ✅"
    else:
        snow_checks = "❄️ —"

    score = 50
    reasons = []

    if activity_type == "Skiing":
        score += min(avg_snow_height / 2, 30)
        score += min(avg_new_snow * 2, 15)
        score += min(avg_sunshine * 3, 15)
        score -= avg_precip * 2
        reasons.append("snow conditions are important for skiing")

    elif activity_type == "Snowshoeing":
        score += min(avg_snow_height / 3, 25)
        score += min(avg_sunshine * 3, 20)
        score -= avg_precip * 1.5
        reasons.append("snow and sunshine are good for snowshoeing")

    elif activity_type == "Winter hiking":
        score += min(avg_sunshine * 4, 30)
        score -= avg_precip * 2
        reasons.append("sunshine is the main positive factor")

    elif activity_type == "Ice skating":
        score += min(avg_sunshine * 3, 15)
        score -= avg_precip * 2

        if avg_temp is not None and avg_temp < 0:
            score += 25
            reasons.append("cold temperatures are good for ice skating")
        else:
            reasons.append("temperature may be less ideal for ice skating")

    score = max(0, min(100, score))

    return {
        "weather_score": round(score, 1),
        "sun_checks": sun_checks,
        "snow_checks": snow_checks,
        "avg_temp": round(avg_temp, 1) if avg_temp is not None and not pd.isna(avg_temp) else None,
        "weather_reason": ", ".join(reasons)
    }


# Load data
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

apres_ski = pd.read_excel(DATA_DIR / "apres_ski.xlsx")
skating = pd.read_excel(DATA_DIR / "skating_rinks_with_travel.xlsx")
ski = pd.read_excel(DATA_DIR / "ski_resorts_with_travel.xlsx")
snowshoe = pd.read_excel(DATA_DIR / "snowshoe_trails_with_travel.xlsx")
winter_hiking = pd.read_excel(DATA_DIR / "winter_hiking_with_travel.xlsx")

difficulty_translation = {
    "leicht": "Easy",
    "mittel": "Moderate",
    "schwer": "Hard",
    "einfach": "Easy",
    "anspruchsvoll": "Hard"
}

snowshoe["difficulty"] = snowshoe["difficulty"].replace(difficulty_translation)
winter_hiking["difficulty"] = winter_hiking["difficulty"].replace(difficulty_translation)

skating["activity_type"] = "Ice skating"
ski["activity_type"] = "Skiing"
snowshoe["activity_type"] = "Snowshoeing"
winter_hiking["activity_type"] = "Winter hiking"

standard_columns = [
    "name",
    "activity_type",
    "latitude",
    "longitude",
    "price",
    "length_km",
    "elevation_gain_m",
    "duration_min",
    "difficulty",
    "station_id"
]

all_activities = pd.concat(
    [
        skating.reindex(columns=standard_columns),
        ski.reindex(columns=standard_columns),
        snowshoe.reindex(columns=standard_columns),
        winter_hiking.reindex(columns=standard_columns),
    ],
    ignore_index=True
)

# --------------------------------------------------
# LOAD WEATHER STATION MATCHES
# --------------------------------------------------
weather_matches = pd.read_excel(
    DATA_DIR / "activity_locations_with_weather_stations.xlsx"
)

# Clean column names
weather_matches.columns = weather_matches.columns.str.strip()

# Create helper rounded coordinate columns
all_activities["lat_round"] = all_activities["latitude"].round(4)
all_activities["lon_round"] = all_activities["longitude"].round(4)

weather_matches["lat_round"] = weather_matches["lat_left"].round(4)
weather_matches["lon_round"] = weather_matches["lon_left"].round(4)

# Build lookup table: activity coordinates -> MeteoSwiss station abbreviation
weather_lookup = weather_matches[
    ["lat_round", "lon_round", "station_abbr"]
].drop_duplicates()

# Rename station_abbr to station_id for the website logic
weather_lookup = weather_lookup.rename(
    columns={"station_abbr": "station_id"}
)

# IMPORTANT: remove old empty station_id if it exists
if "station_id" in all_activities.columns:
    all_activities = all_activities.drop(columns=["station_id"])

# Merge station_id into activity table
all_activities = all_activities.merge(
    weather_lookup,
    on=["lat_round", "lon_round"],
    how="left"
)

# Remove helper columns
all_activities = all_activities.drop(
    columns=["lat_round", "lon_round"]
)

all_activities["distance_from_zurich_km"] = all_activities.apply(
    lambda row: calculate_distance_from_zurich(row["latitude"], row["longitude"]),
    axis=1
)

all_activities["travel_time_min"] = all_activities["distance_from_zurich_km"].apply(
    estimate_travel_time
)

# Header
st.title("❄️ Swiss Winter Activity Finder")
st.write("This app suggests winter activities based on difficulty, weather, price, and estimated travel time.")
st.caption("Travel time is estimated from Zürich HB using coordinates, so it is approximate.")

# Sidebar
st.sidebar.header("Choose your preferences")

activity_choice = st.sidebar.radio(
    "Choose one activity",
    options=sorted(all_activities["activity_type"].dropna().unique())
)

max_price = st.sidebar.slider(
    "Maximum price (CHF)",
    min_value=0,
    max_value=150,
    value=50
)

max_travel_time = st.sidebar.slider(
    "Maximum estimated travel time from Zürich HB (minutes)",
    min_value=0,
    max_value=300,
    value=180
)

use_weather = st.sidebar.checkbox("Use weather-based recommendations ☀️❄️", value=True)
selected_month = st.sidebar.selectbox(
    "Choose travel month",
    options=[
        "October",
        "November",
        "December",
        "January",
        "February",
        "March",
        "April"
    ],
    index=3  # January default
)

month_mapping = {
    "October": 10,
    "November": 11,
    "December": 12,
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4
}

selected_month_number = month_mapping[selected_month]
add_apres = st.sidebar.checkbox("Add nearby après-ski suggestions 🍻")

# Start filtering
filtered = all_activities[
    all_activities["activity_type"] == activity_choice
].copy()

# Difficulty filter only for snowshoeing and winter hiking
if activity_choice in ["Snowshoeing", "Winter hiking"]:

    st.sidebar.markdown("### Select difficulty levels")

    easy_checked = st.sidebar.checkbox("Easy", value=True)
    moderate_checked = st.sidebar.checkbox("Moderate", value=True)
    hard_checked = st.sidebar.checkbox("Hard", value=True)

    selected_difficulties = []

    if easy_checked:
        selected_difficulties.append("Easy")

    if moderate_checked:
        selected_difficulties.append("Moderate")

    if hard_checked:
        selected_difficulties.append("Hard")

    filtered = filtered[
        filtered["difficulty"].isin(selected_difficulties)
    ].copy()

filtered = filtered[
    (filtered["price"].isna()) | (filtered["price"] <= max_price)
].copy()

filtered = filtered[
    (filtered["travel_time_min"].isna()) |
    (filtered["travel_time_min"] <= max_travel_time)
].copy()

# Weather scoring
if use_weather and not filtered.empty:
    with st.spinner("Checking weather conditions..."):
        weather_summaries = filtered.apply(
            lambda row: calculate_weather_summary(
                row["station_id"],
                row["activity_type"],
                selected_month_number
            ),
            axis=1
        )

        filtered["weather_score"] = weather_summaries.apply(lambda x: x["weather_score"])
        filtered["sun_checks"] = weather_summaries.apply(lambda x: x["sun_checks"])
        filtered["snow_checks"] = weather_summaries.apply(lambda x: x["snow_checks"])
        filtered["avg_temp"] = weather_summaries.apply(lambda x: x["avg_temp"])
        filtered["weather_reason"] = weather_summaries.apply(lambda x: x["weather_reason"])
else:
    filtered["weather_score"] = 50
    filtered["sun_checks"] = "☀️ —"
    filtered["snow_checks"] = "❄️ —"
    filtered["avg_temp"] = None
    filtered["weather_reason"] = "Weather scoring not used"

# Final score
price_score = 100 - filtered["price"].fillna(0)

filtered["travel_score"] = 100 - abs(
    filtered["travel_time_min"].fillna(max_travel_time) - max_travel_time
)

filtered["travel_score"] = filtered["travel_score"].clip(lower=0, upper=100)

# Difficulty is already required by filtering.
# Weather is most important, price is second, distance/travel time is least important.
filtered["score"] = (
    0.6 * filtered["weather_score"].fillna(50) +
    0.3 * price_score +
    0.1 * filtered["travel_score"]
)

top_3 = filtered.sort_values("score", ascending=False).head(3)

# Page layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🏔️ Top Recommendations")

    if top_3.empty:
        st.warning("No activities match your selected preferences.")
    else:
        for _, row in top_3.iterrows():
            with st.container():
                st.markdown(f"### {row['name']}")
                st.write(f"**Activity:** {row['activity_type']}")

                if pd.notna(row["difficulty"]):
                    st.write(f"**Difficulty:** {row['difficulty']}")

                if pd.notna(row["price"]):
                    st.write(f"**Price:** CHF {row['price']}")

                if pd.notna(row["length_km"]):
                    st.write(f"**Length:** {row['length_km']} km")

                if pd.notna(row["duration_min"]):
                    st.write(f"**Duration:** {row['duration_min']} min")

                if pd.notna(row["distance_from_zurich_km"]):
                    st.write(f"**Distance from Zürich:** {round(row['distance_from_zurich_km'], 1)} km")

                if pd.notna(row["travel_time_min"]):
                    st.write(f"**Estimated travel time from Zürich:** {round(row['travel_time_min'])} min")

                st.write(f"**Weather score:** {round(row['weather_score'], 1)} / 100")
                st.write(f"**Sun:** {row['sun_checks']}")
                st.write(f"**Snow:** {row['snow_checks']}")

                if pd.notna(row["avg_temp"]):
                    st.write(f"**Average temperature:** {row['avg_temp']} °C")

                st.write(f"**Why:** {row['weather_reason']}")
                st.write(f"**Final score:** {round(row['score'], 1)} / 100")

                # Google search link
                google_search_url = (
                    "https://www.google.com/search?q="
                    + row["name"].replace(" ", "+")
                )

                st.markdown(
                    f'[🔎 Find the Activity on Google]({google_search_url})'
                )

                st.divider()

with col2:
    st.subheader("📊 Quick Stats")
    st.metric("Matching Activities", len(filtered))
    st.metric("Top Recommendations", len(top_3))

    if use_weather:
        average_weather = round(filtered["weather_score"].mean(), 1) if not filtered.empty else 0
        st.metric("Average Weather Score", average_weather)

# Après-ski add-on
if add_apres and not top_3.empty:
    st.subheader("🍻 Nearby Après-Ski Suggestions")

    for _, activity in top_3.iterrows():
        if pd.notna(activity["latitude"]) and pd.notna(activity["longitude"]):

            apres_ski["distance_score"] = (
                (apres_ski["latitude"] - activity["latitude"]) ** 2
                + (apres_ski["longitude"] - activity["longitude"]) ** 2
            )

            closest_apres = apres_ski.sort_values("distance_score").iloc[0]

            st.markdown(f"### Near {activity['name']}")
            st.write(f"**Après-ski option:** {closest_apres['name']}")

            if pd.notna(closest_apres["address"]):

                google_maps_url = (
                    "https://www.google.com/maps/search/?api=1&query="
                    + closest_apres["address"].replace(" ", "+")
                )

                st.markdown(
                    f'**Location:** '
                    f'<a href="{google_maps_url}" target="_blank">'
                    f'{closest_apres["address"]}</a>',
                    unsafe_allow_html=True
                )

            st.divider()