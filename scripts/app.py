import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Swiss Winter Activity Finder",
    page_icon="❄️",
    layout="wide"
)

# Simple custom colours
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

    /* Sidebar multiselect box */
    div[data-baseweb="select"] > div {
        background-color: #1e293b;
        color: white;
        border: 1px solid #6366f1;
    }

    /* Selected multiselect tags */
    span[data-baseweb="tag"] {
        background-color: #4f46e5 !important;
        color: white !important;
    }

    /* Slider */
    .stSlider > div > div > div > div {
        background-color: #6366f1;
    }

    /* Checkbox */
    .stCheckbox label {
        color: white;
    }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background-color: #1e1b4b;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #818cf8;
    }

    /* Metric text */
    div[data-testid="stMetric"] label {
        color: #c7d2fe !important;
    }

    div[data-testid="stMetric"] div {
        color: white !important;
    }

    /* Buttons */
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

# Load datasets
apres_ski = pd.read_excel("../data/apres_ski.xlsx")
skating = pd.read_excel("../data/skating_rinks.xlsx")
ski = pd.read_excel("../data/ski_resorts.xlsx")
snowshoe = pd.read_excel("../data/snowshoe_trails.xlsx")
winter_hiking = pd.read_excel("../data/winter_hiking.xlsx")

# Translate difficulty labels
difficulty_translation = {
    "leicht": "Easy",
    "mittel": "Moderate",
    "schwer": "Hard",
    "einfach": "Easy",
    "anspruchsvoll": "Hard"
}

snowshoe["difficulty"] = snowshoe["difficulty"].replace(difficulty_translation)
winter_hiking["difficulty"] = winter_hiking["difficulty"].replace(difficulty_translation)

# Add activity labels
skating["activity_type"] = "Ice skating"
ski["activity_type"] = "Skiing"
snowshoe["activity_type"] = "Snowshoeing"
winter_hiking["activity_type"] = "Winter hiking"

# Standard columns for main activities
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
]

# Combine main activity datasets
all_activities = pd.concat(
    [
        skating.reindex(columns=standard_columns),
        ski.reindex(columns=standard_columns),
        snowshoe.reindex(columns=standard_columns),
        winter_hiking.reindex(columns=standard_columns),
    ],
    ignore_index=True
)

# Header
st.title("❄️ Swiss Winter Activity Finder")
st.markdown("Find winter activities in Switzerland based on your preferences.")

# Sidebar filters
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

add_apres = st.sidebar.checkbox("Add nearby après-ski suggestions 🍻")

# Filter data
filtered = all_activities[
    all_activities["activity_type"].isin(activity_choice)
]

filtered = filtered[
    (filtered["price"].isna()) | (filtered["price"] <= max_price)
]

# Simple beginner-friendly scoring system
filtered["score"] = 100 - filtered["price"].fillna(0)

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

                if pd.notna(row["price"]):
                    st.write(f"**Price:** CHF {row['price']}")

                if pd.notna(row["difficulty"]):
                    st.write(f"**Difficulty:** {row['difficulty']}")

                if pd.notna(row["length_km"]):
                    st.write(f"**Length:** {row['length_km']} km")

                if pd.notna(row["duration_min"]):
                    st.write(f"**Duration:** {row['duration_min']} min")

                st.divider()

with col2:
    st.subheader("📊 Quick Stats")
    st.metric("Matching Activities", len(filtered))
    st.metric("Top Recommendations", len(top_3))

# Après-ski add-on section
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
