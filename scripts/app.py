import pandas as pd
import streamlit as st
import requests
from io import StringIO
from pathlib import Path

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
        color: #f8fafc;
    }

    h1, h2, h3, p, label, div {
        color: #f8fafc;
    }

    section[data-testid="stSidebar"] {
        background-color: #111827;
    }

    div[data-baseweb="select"] > div {
        background-color: #1e293b;
        color: white;
        border: 1px solid #6366f1;
    }

    span[data-baseweb="tag"] {
        background-color: #4f46e5 !important;
        color: white !important;
    }

    .stSlider > div > div > div > div {
        background-color: #6366f1;
    }

    .stCheckbox label {
        color: white;
    }

    div[data-testid="stMetric"] {
        background-color: #1e1b4b;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #818cf8;
    }

    div[data-testid="stMetric"] label {
        color: #c7d2fe !important;
    }

    div[data-testid="stMetric"] div {
        color: white !important;
    }

    .stButton > button {
        background-color: #4338ca;
        color: white;
        border-radius: 10px;
        border: none;
    }

    .stButton > button:hover {
        background-color: #6366f1;
    }

    hr {
        border-color: #334155;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --------------------------------------------------
# WEATHER FUNCTIONS
# --------------------------------------------------

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

        nime_cols = [
            "reference_timestamp",
            "rre150d0",  # precipitation
            "hns000d0",  # new snow
            "hto000d0"   # snow height
        ]

        smn_cols = [
            "reference_timestamp",
            "sre000d0",  # sunshine
            "tre200d0"   # temperature
        ]

        nime = nime[[c for c in nime_cols if c in nime.columns]]
        smn = smn[[c for c in smn_cols if c in smn.columns]]

        weather = pd.merge(
            nime,
            smn,
            on="reference_timestamp",
            how="outer"
        )

        return weather

    except Exception as e:
        print(f"Weather download failed for {station_id}: {e}")
        return None


@st.cache_data(show_spinner=False)
def calculate_weather_summary(station_id, activity_type):
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
    weather = weather.sort_values("reference_timestamp").tail(7)

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

    # Icon/check display
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
        if avg_sunshine >= 2:
            reasons.append("good sunshine expected")
        if avg_snow_height >= 30:
            reasons.append("good snow coverage")

    elif activity_type == "Snowshoeing":
        score += min(avg_snow_height / 3, 25)
        score += min(avg_sunshine * 3, 20)
        score -= avg_precip * 1.5

        reasons.append("snow and sunshine are good for snowshoeing")
        if avg_snow_height >= 30:
            reasons.append("enough snow for the trail")

    elif activity_type == "Winter hiking":
        score += min(avg_sunshine * 4, 30)
        score -= avg_precip * 2

        reasons.append("sunshine is the main positive factor")
        if avg_precip <= 1:
            reasons.append("low precipitation")

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


# --------------------------------------------------
# LOAD DATASETS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

apres_ski = pd.read_excel(DATA_DIR / "apres_ski.xlsx")
skating = pd.read_excel(DATA_DIR / "skating_rinks.xlsx")
ski = pd.read_excel(DATA_DIR / "ski_resorts.xlsx")
snowshoe = pd.read_excel(DATA_DIR / "snowshoe_trails.xlsx")
winter_hiking = pd.read_excel(DATA_DIR / "winter_hiking.xlsx")

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
# PAGE HEADER
# --------------------------------------------------

st.title("❄️ Swiss Winter Activity Finder")
st.markdown("Find winter activities in Switzerland based on your preferences.")

# --------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------

st.sidebar.header("Choose your preferences")

activity_choice = st.sidebar.multiselect(
    "Activities",
    options=sorted(all_activities["activity_type"].dropna().unique()),
    default=sorted(all_activities["activity_type"].dropna().unique())
)

max_price = st.sidebar.slider(
    "Maximum price (CHF)",
    min_value=0,
    max_value=150,
    value=50
)

use_weather = st.sidebar.checkbox("Use weather-based recommendations ☀️❄️", value=True)

add_apres = st.sidebar.checkbox("Add nearby après-ski suggestions 🍻")

# --------------------------------------------------
# FILTER DATA
# --------------------------------------------------

filtered = all_activities[
    all_activities["activity_type"].isin(activity_choice)
].copy()

filtered = filtered[
    (filtered["price"].isna()) | (filtered["price"] <= max_price)
].copy()

# --------------------------------------------------
# WEATHER SCORING
# --------------------------------------------------

if use_weather and not filtered.empty:
    with st.spinner("Checking weather conditions..."):
        weather_summaries = filtered.apply(
            lambda row: calculate_weather_summary(
                row["station_id"],
                row["activity_type"]
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

# --------------------------------------------------
# FINAL SCORING
# --------------------------------------------------

price_score = 100 - filtered["price"].fillna(0)

filtered["score"] = (
    0.5 * price_score +
    0.5 * filtered["weather_score"].fillna(50)
)

top_3 = filtered.sort_values("score", ascending=False).head(3)

# --------------------------------------------------
# PAGE LAYOUT
# --------------------------------------------------

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

                if pd.notna(row["price"]):
                    st.write(f"**Price:** CHF {row['price']}")

                if pd.notna(row["difficulty"]):
                    st.write(f"**Difficulty:** {row['difficulty']}")

                if pd.notna(row["length_km"]):
                    st.write(f"**Length:** {row['length_km']} km")

                if pd.notna(row["duration_min"]):
                    st.write(f"**Duration:** {row['duration_min']} min")

                if pd.notna(row["weather_score"]):
                    st.write(f"**Weather score:** {round(row['weather_score'], 1)} / 100")
                    st.write(f"**Sun:** {row['sun_checks']}")
                    st.write(f"**Snow:** {row['snow_checks']}")

                    if pd.notna(row["avg_temp"]):
                        st.write(f"**Average temperature:** {row['avg_temp']} °C")

                    st.write(f"**Why:** {row['weather_reason']}")

                st.write(f"**Final score:** {round(row['score'], 1)} / 100")

                st.divider()

with col2:
    st.subheader("📊 Quick Stats")
    st.metric("Matching Activities", len(filtered))
    st.metric("Top Recommendations", len(top_3))

    if use_weather:
        st.metric(
            "Average Weather Score",
            round(filtered["weather_score"].mean(), 1) if not filtered.empty else 0
        )

# --------------------------------------------------
# APRÈS-SKI ADD-ON
# --------------------------------------------------

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

            if "latitude" in closest_apres and "longitude" in closest_apres:
                st.write(
                    f"Location: {closest_apres['latitude']}, {closest_apres['longitude']}"
                )

            st.divider()