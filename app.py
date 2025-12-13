import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="🌍 Global Health Dashboard",
    layout="wide"
)

# -----------------------------
# Load data
# -----------------------------
df = pd.read_csv("final_with_socio_cleaned.csv")

with open("countries.geo.json") as f:
    geojson = json.load(f)

# Ensure correct dtypes
df["Year"] = df["Year"].astype(int)

# -----------------------------
# Session state
# -----------------------------
if "selected_country" not in st.session_state:
    st.session_state.selected_country = None

# -----------------------------
# Sidebar - Year slider
# -----------------------------
year = st.sidebar.slider(
    "Select Year",
    int(df["Year"].min()),
    int(df["Year"].max()),
    int(df["Year"].max())
)

year_df = df[df["Year"] == year]

# -----------------------------
# World Map
# -----------------------------
fig = px.choropleth(
    year_df,
    geojson=geojson,
    locations="ISO3",
    featureidkey="properties.ISO_A3",
    color="HDI",
    hover_name="Country",
    color_continuous_scale="Viridis",
)

fig.update_geos(
    showcountries=True,
    showcoastlines=False,
    projection_type="natural earth"
)

fig.update_layout(
    margin=dict(l=0, r=0, t=0, b=0),
    height=600
)

# -----------------------------
# Capture click
# -----------------------------
click = st.plotly_chart(
    fig,
    use_container_width=True,
    key="map"
)

# Streamlit workaround: use selectbox fallback
country_list = sorted(year_df["Country"].unique())
selected = st.selectbox(
    "Click not detected? Select country manually:",
    [""] + country_list
)

if selected:
    st.session_state.selected_country = selected

# -----------------------------
# Floating popup (CSS)
# -----------------------------
if st.session_state.selected_country:
    row = year_df[year_df["Country"] == st.session_state.selected_country].iloc[0]

    st.markdown(
        f"""
        <style>
        .popup {{
            position: fixed;
            right: 30px;
            top: 120px;
            background: white;
            padding: 20px;
            width: 320px;
            border-radius: 12px;
            box-shadow: 0px 8px 30px rgba(0,0,0,0.25);
            z-index: 9999;
        }}
        </style>

        <div class="popup">
            <h3>📊 {row['Country']}</h3>
            <b>Year:</b> {year}<br>
            <b>HDI:</b> {row['HDI']}<br>
            <b>GDP per Capita:</b> {row['GDP_per_capita']}<br>
            <b>Gini Index:</b> {row['Gini_Index']}<br>
            <b>Life Expectancy:</b> {row['Life_Expectancy']}<br>
            <b>Median Age:</b> {row['Median_Age_Est']}<br>
            <b>COVID Deaths / mil:</b> {row['COVID_Deaths']}<br>
        </div>
        """,
        unsafe_allow_html=True
    )
