import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. Load your data ---
# Replace with your actual CSV file
DATA_FILE = "HEX.csv"
data = pd.read_csv(DATA_FILE)

# Ensure the year column is int
data['Year'] = data['Year'].astype(int)

# --- 2. Sidebar: Year selection ---
year = st.sidebar.slider("Select Year", min_value=int(data['Year'].min()), 
                         max_value=int(data['Year'].max()), value=int(data['Year'].max()))

# Filter data for selected year
year_data = data[data['Year'] == year]

# --- 3. Create a Plotly map ---
fig = px.choropleth(
    year_data,
    locations="ISO3",  # Column with country codes
    color="HDI",       # Example metric
    hover_name="Country",  
    hover_data={"HDI": True, "GDP per Capita": True, "Gini Index": True,
                "Life Expectancy": True, "Median Age": True, "COVID Deaths / mil": True,
                "ISO3": False},  # Hide ISO3 in hover
    color_continuous_scale="Viridis",
    projection="natural earth"
)

fig.update_layout(
    title=f"Global Health Dashboard - {year}",
    margin={"r":0,"t":50,"l":0,"b":0}
)

# --- 4. Streamlit page ---
st.title("🌍 Global Health Dashboard")
st.plotly_chart(fig, use_container_width=True)

# Optional: Show selected country details below map
st.markdown("Click on a country to see details in hover popup!")
