import pandas as pd
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Zurich HB coordinates
ZURICH_LAT = 47.3782
ZURICH_LON = 8.5402

def calculate_distance_km(lat, lon):
    # Haversine formula
    earth_radius = 6371

    lat1 = radians(ZURICH_LAT)
    lon1 = radians(ZURICH_LON)
    lat2 = radians(lat)
    lon2 = radians(lon)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return earth_radius * c

def add_travel_columns(df):
    df["distance_from_zurich_km"] = df.apply(
        lambda row: calculate_distance_km(row["latitude"], row["longitude"]),
        axis=1
    )

    # Very rough public transit estimate:
    # 45 km/h average including transfers/waiting
    df["estimated_travel_time_min"] = df["distance_from_zurich_km"] / 45 * 60

    return df

files = [
    "skating_rinks.xlsx",
    "ski_resorts.xlsx",
    "snowshoe_trails.xlsx",
    "winter_hiking.xlsx",
    "apres_ski.xlsx"
]

for file in files:
    path = DATA_DIR / file
    df = pd.read_excel(path)

    df = add_travel_columns(df)

    output_name = file.replace(".xlsx", "_with_travel.xlsx")
    df.to_excel(DATA_DIR / output_name, index=False)

    print(f"Saved {output_name}")