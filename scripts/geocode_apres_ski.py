#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May  7 11:08:26 2026

@author: chealenberry
"""

import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time

# -----------------------------
# LOAD EXCEL FILE
# -----------------------------

file_path = "apres_ski_simplified_queries.xlsx"

# Read the Excel file
df = pd.read_excel(file_path)

# -----------------------------
# INITIALIZE GEOCODER
# -----------------------------

geolocator = Nominatim(
    user_agent="switzerland_winter_activity_project"
)

# RateLimiter prevents overloading the API
geocode = RateLimiter(
    geolocator.geocode,
    min_delay_seconds=1
)

# -----------------------------
# GEOCODING
# -----------------------------

latitudes = []
longitudes = []

for idx, row in df.iterrows():

    query = row["Suggested Geocoding Query"]
    name = row["Après Ski Venue"]

    try:
        location = geocode(query)

        if location:
            latitudes.append(location.latitude)
            longitudes.append(location.longitude)

            print(f"FOUND: {name}")

        else:
            latitudes.append(None)
            longitudes.append(None)

            print(f"NOT FOUND: {name}")

    except Exception as e:

        latitudes.append(None)
        longitudes.append(None)

        print(f"ERROR with {name}: {e}")

    # small pause for API safety
    time.sleep(1)

# -----------------------------
# ADD RESULTS TO DATAFRAME
# -----------------------------

df["latitude"] = latitudes
df["longitude"] = longitudes

# -----------------------------
# SAVE OUTPUT
# -----------------------------

output_file = "apres_ski_coordinates.xlsx"

df.to_excel(output_file, index=False)

print("\nDONE!")
print(f"Saved file as: {output_file}")