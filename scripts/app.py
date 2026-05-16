import pandas as pd
import streamlit as st
import requests
from io import StringIO
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2
import folium
from streamlit_folium import st_folium


# Page setup
st.set_page_config(
    page_title="Swiss Winter Activity Finder",
    page_icon="❄️",
    layout="wide"
)


# Custom CSS because the default Streamlit theme was too bright for a winter app
st.markdown("""
<style>
    <style>
    .stApp {
        background-color: #0a0f1f;
        color: #f8fafc;
    }

    .main .block-container {
        padding-top: 1rem;
        background-color: #0a0f1f;
    }

    header[data-testid="stHeader"] {
        background: transparent;
    }

    [data-testid="stToolbar"] {
        right: 2rem;
    }

    div[data-testid="stContainer"] {
        background-color: #f0f2f6;
        border-radius: 18px;
        padding: 20px;
        color: #31333f;
    }

    div[data-testid="stContainer"] p,
    div[data-testid="stContainer"] h2 {
        color: #31333f !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ==================================================
# BASIC SETTINGS
# ==================================================

# Zurich HB coordinates
ZURICH_LAT = 47.3782
ZURICH_LON = 8.5402

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


# ==================================================
# TRAVEL TIME FUNCTIONS
# ==================================================

def get_distance_from_zurich(lat, lon):
    # Haversine formula, adapted from examples online
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
    # We estimate travel time from distance. This is not exact public transit time.
    if pd.isna(distance_km):
        return None

    average_speed = 45
    return distance_km / average_speed * 60


# ==================================================
# WEATHER FUNCTIONS
# ==================================================

@st.cache_data(show_spinner=False)
def download_weather_data(station_id):
    # Downloads recent MeteoSwiss data for a station
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

        nime = nime[[col for col in nime_cols if col in nime.columns]]
        smn = smn[[col for col in smn_cols if col in smn.columns]]

        weather = pd.merge(nime, smn, on="reference_timestamp", how="outer")
        return weather

    except Exception:
        return None


def get_weather_score(station_id, activity_type, selected_month):
    # Default score if we do not have weather data
    default_weather = {
        "weather_score": 50,
        "sun_checks": "☀️ —",
        "snow_checks": "❄️ —",
        "avg_temp": None
    }

    if pd.isna(station_id):
        return default_weather

    weather = download_weather_data(station_id)

    if weather is None or weather.empty:
        return default_weather

    weather["reference_timestamp"] = pd.to_datetime(
        weather["reference_timestamp"],
        errors="coerce"
    )

    weather = weather.dropna(subset=["reference_timestamp"])

    # Keep only the selected month
    weather = weather[
        weather["reference_timestamp"].dt.month == selected_month
    ]

    if weather.empty:
        return default_weather

    avg_sunshine = weather["sre000d0"].mean() if "sre000d0" in weather else 0
    avg_snow_height = weather["hto000d0"].mean() if "hto000d0" in weather else 0
    avg_new_snow = weather["hns000d0"].mean() if "hns000d0" in weather else 0
    avg_precip = weather["rre150d0"].mean() if "rre150d0" in weather else 0
    avg_temp = weather["tre200d0"].mean() if "tre200d0" in weather else None

    # Replace missing values with 0 so the score does not crash
    avg_sunshine = 0 if pd.isna(avg_sunshine) else avg_sunshine
    avg_snow_height = 0 if pd.isna(avg_snow_height) else avg_snow_height
    avg_new_snow = 0 if pd.isna(avg_new_snow) else avg_new_snow
    avg_precip = 0 if pd.isna(avg_precip) else avg_precip

    # Simple icon summary for the website output
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

    # These scores are our simple ranking assumptions
    if activity_type == "Skiing":
        score += min(avg_snow_height / 2, 30)
        score += min(avg_new_snow * 2, 15)
        score += min(avg_sunshine * 3, 15)
        score -= avg_precip * 2

    elif activity_type == "Snowshoeing":
        score += min(avg_snow_height / 3, 25)
        score += min(avg_sunshine * 3, 20)
        score -= avg_precip * 1.5

    elif activity_type == "Winter hiking":
        score += min(avg_sunshine * 4, 30)
        score -= avg_precip * 2

    elif activity_type == "Ice skating":
        score += min(avg_sunshine * 3, 15)
        score -= avg_precip * 2

        if avg_temp is not None and avg_temp < 0:
            score += 25

    score = max(0, min(100, score))

    return {
        "weather_score": round(score, 1),
        "sun_checks": sun_checks,
        "snow_checks": snow_checks,
        "avg_temp": round(avg_temp, 1) if avg_temp is not None and not pd.isna(avg_temp) else None
    }


# ==================================================
# LOAD AND PREPARE DATA
# ==================================================

apres_ski = pd.read_excel(DATA_DIR / "apres_ski.xlsx")
skating = pd.read_excel(DATA_DIR / "skating_rinks_with_travel.xlsx")
ski = pd.read_excel(DATA_DIR / "ski_resorts_with_travel.xlsx")
snowshoe = pd.read_excel(DATA_DIR / "snowshoe_trails_with_travel.xlsx")
winter_hiking = pd.read_excel(DATA_DIR / "winter_hiking_with_travel.xlsx")

# Translate German difficulty labels from the original datasets
difficulty_translation = {
    "leicht": "Easy",
    "mittel": "Moderate",
    "schwer": "Hard",
    "einfach": "Easy",
    "anspruchsvoll": "Hard"
}

snowshoe["difficulty"] = snowshoe["difficulty"].replace(difficulty_translation)
winter_hiking["difficulty"] = winter_hiking["difficulty"].replace(difficulty_translation)

# Add activity labels so we can combine the datasets
skating["activity_type"] = "Ice skating"
ski["activity_type"] = "Skiing"
snowshoe["activity_type"] = "Snowshoeing"
winter_hiking["activity_type"] = "Winter hiking"

# These are the columns we want from each file
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


# ==================================================
# MATCH ACTIVITIES TO WEATHER STATIONS
# ==================================================

# This file was made during preprocessing. It connects activity coordinates
# to the nearest MeteoSwiss station.
weather_matches = pd.read_excel(DATA_DIR / "activity_locations_with_weather_stations.xlsx")
weather_matches.columns = weather_matches.columns.str.strip()

# Coordinates are not always exactly identical, so we round them before matching.
all_activities["lat_round"] = all_activities["latitude"].round(4)
all_activities["lon_round"] = all_activities["longitude"].round(4)

weather_matches["lat_round"] = weather_matches["lat_left"].round(4)
weather_matches["lon_round"] = weather_matches["lon_left"].round(4)

weather_lookup = weather_matches[
    ["lat_round", "lon_round", "station_abbr"]
].drop_duplicates()

weather_lookup = weather_lookup.rename(columns={"station_abbr": "station_id"})

# We already had an empty station_id column in some files, so drop it first.
if "station_id" in all_activities.columns:
    all_activities = all_activities.drop(columns=["station_id"])

all_activities = all_activities.merge(
    weather_lookup,
    on=["lat_round", "lon_round"],
    how="left"
)

all_activities = all_activities.drop(columns=["lat_round", "lon_round"])


# Add estimated distance and travel time from Zurich
all_activities["distance_from_zurich_km"] = all_activities.apply(
    lambda row: get_distance_from_zurich(row["latitude"], row["longitude"]),
    axis=1
)

all_activities["travel_time_min"] = all_activities["distance_from_zurich_km"].apply(
    estimate_travel_time
)


# ==================================================
# WEBSITE HEADER
# ==================================================

st.title("❄️ Swiss Winter Activity Finder")
st.write("This app suggests winter activities based on difficulty, weather, price, and estimated travel time.")
st.caption("Travel time is estimated from Zürich HB using coordinates, so it is approximate.")


# ==================================================
# SIDEBAR INPUTS
# ==================================================

st.sidebar.header("Choose your preferences:")

activity_choice = st.sidebar.radio(
    "What activity do you want to do?",
    options=sorted(all_activities["activity_type"].dropna().unique())
)

# Filter by activity first so the rest of the questions can adapt
filtered = all_activities[
    all_activities["activity_type"] == activity_choice
].copy()

# Difficulty only applies to snowshoeing and winter hiking in our datasets
if activity_choice in ["Snowshoeing", "Winter hiking"]:

    st.sidebar.markdown("### How difficult do you want it to be?")

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

# Price only matters for paid activities
if activity_choice == "Ice skating":
    max_price = st.sidebar.slider(
        "How much are you willing to spend (CHF)?",
        min_value=0,
        max_value=10,
        value=10
    )

    filtered = filtered[
        (filtered["price"].isna()) | (filtered["price"] <= max_price)
    ].copy()

elif activity_choice == "Skiing":
    max_price = st.sidebar.slider(
        "How much are you willing to spend (CHF)?",
        min_value=0,
        max_value=150,
        value=50
    )

    filtered = filtered[
        (filtered["price"].isna()) | (filtered["price"] <= max_price)
    ].copy()

else:
    max_price = None

max_travel_time = st.sidebar.slider(
    "How much time are you willing to spend travelling from Zürich HB (mins)?",
    min_value=0,
    max_value=300,
    value=180
)

use_weather = st.sidebar.checkbox("Use weather-based recommendations ☀️❄️", value=True)

if use_weather:
    selected_month = st.sidebar.selectbox(
        "When are you going?",
        options=[
            "October",
            "November",
            "December",
            "January",
            "February",
            "March",
            "April"
        ],
        index=3
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
else:
    selected_month_number = None

add_apres = st.sidebar.checkbox("Add nearby après-ski suggestions 🍻")


# ==================================================
# FILTER AND SCORE ACTIVITIES
# ==================================================

filtered = filtered[
    (filtered["travel_time_min"].isna()) |
    (filtered["travel_time_min"] <= max_travel_time)
].copy()

if use_weather and not filtered.empty:
    with st.spinner("Checking weather conditions..."):
        weather_summaries = filtered.apply(
            lambda row: get_weather_score(
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

else:
    filtered["weather_score"] = 50
    filtered["sun_checks"] = "☀️ —"
    filtered["snow_checks"] = "❄️ —"
    filtered["avg_temp"] = None

# Price score: lower price is better
price_score = 100 - filtered["price"].fillna(0)

# Travel score: we favour options close to the user's max travel time but still under it
filtered["travel_score"] = 100 - abs(
    filtered["travel_time_min"].fillna(max_travel_time) - max_travel_time
)

filtered["travel_score"] = filtered["travel_score"].clip(lower=0, upper=100)

# Difficulty is already a hard filter.
# Then we rank mostly by weather, then price, then travel convenience.
filtered["score"] = (
    0.6 * filtered["weather_score"].fillna(50) +
    0.3 * price_score +
    0.1 * filtered["travel_score"]
)

top_3 = filtered.sort_values("score", ascending=False).head(3)


# ==================================================
# MAIN PAGE OUTPUT
# ==================================================

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

                st.write(f"**Final score:** {round(row['score'], 1)} / 100")

                google_search_url = "https://www.google.com/search?q=" + row["name"].replace(" ", "+")
                st.markdown(f"[🔎 Find the activity on Google]({google_search_url})")

                st.divider()


# ==================================================
# MAP
# ==================================================

m = folium.Map(location=[47.3769, 8.5417], zoom_start=8)

folium.Marker(
    [47.3782, 8.5402],
    popup="Zürich HB",
    tooltip="Start: Zürich HB",
    icon=folium.Icon(color="blue", icon="home")
).add_to(m)

for _, row in top_3.iterrows():
    if pd.notna(row["latitude"]) and pd.notna(row["longitude"]):
        folium.Marker(
            [row["latitude"], row["longitude"]],
            popup=row["name"],
            tooltip=row["name"],
            icon=folium.Icon(color="purple", icon="info-sign")
        ).add_to(m)

st_folium(m, width=1100, height=500, returned_objects=[])


# ==================================================
# QUICK STATS
# ==================================================

with col2:
    if use_weather and not filtered.empty:
        average_weather = round(filtered["weather_score"].mean(), 1)
    else:
        average_weather = "-"

    with st.container(border=True):
        st.markdown("## 📊 Quick Stats")

        st.write(f"**Matching Activities:** {len(filtered)}")
        st.write(f"**Top Recommendations:** {len(top_3)}")
        st.write(f"**Average Weather Score:** {average_weather}")

# ==================================================
# APRÈS-SKI ADD-ON
# ==================================================

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
                    f'**Location:** <a href="{google_maps_url}" target="_blank">'
                    f'{closest_apres["address"]}</a>',
                    unsafe_allow_html=True
                )

            st.divider()