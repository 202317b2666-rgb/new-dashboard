import streamlit as st
import plotly.express as px
import pandas as pd

st.title("Plotly Test")

df = pd.DataFrame({
    "Country": ["India", "USA", "Brazil"],
    "ISO3": ["IND", "USA", "BRA"],
    "HDI": [0.446, 0.926, 0.765]
})

fig = px.choropleth(df, locations="ISO3", color="HDI", hover_name="Country", projection="natural earth")
st.plotly_chart(fig)
