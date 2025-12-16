import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import collections
import traceback 
import requests
import folium
from streamlit_folium import st_folium
import reverse_geocode 

# --- 0. CUSTOM CSS INJECTION FOR STYLING ---
CUSTOM_CSS = """
<style>
/* 1. HIDES THE STREAMLIT BOUNDARY BOX AROUND THE FOLIUM MAP */
div.st-emotion-cache-16k74f6 > iframe {
    border: none !important;
}
/* 2. Map hover effect: Only used for non-popup elements */
.leaflet-interactive {
    outline: none !important; 
}
</style>
"""

# -----------------------------
# GLOBAL CONFIGS
# -----------------------------

WORLD_GEOJSON_URL = 'https://raw.githubusercontent.com/johan/world.geo.json/master/countries.geo.json'

INDICATOR_COLORS = {
    "HDI": "#1f77b4", "LIFE_EXPECTANCY": "#ff7f0e", "GDP_PER_CAPITA": "#2ca02c",
    "GINI_INDEX": "#d62728", "COVID_DEATHS": "#9467bd", "POPULATION_DENSITY": "#8c564b" 
}

ALL_INDICATOR_DETAILS = collections.OrderedDict([
    ("HDI", {"display": "HDI (Development)", "unit": "", "precision": 3}),
    ("LIFE_EXPECTANCY", {"display": "Life Expectancy", "unit": "Yrs", "precision": 1}),
    ("GDP_PER_CAPITA", {"display": "GDP per Capita", "unit": "$", "currency": True}),
    ("GINI_INDEX", {"display": "Gini Index", "unit": "%", "precision": 1}),
    ("MEDIAN_AGE_EST", {"display": "Median Age", "unit": "Yrs", "precision": 1}),
    ("TOTAL_POPULATION", {"display": "Total Population", "unit": "M", "precision": 1}),
    ("POPULATION_DENSITY", {"display": "Population Density", "unit": "ppl/km²", "precision": 0}),
    ("PM25", {"display": "PM25 (Air Pollution)", "unit": "µg/m³", "precision": 2}),
    ("HEALTH_INSURANCE", {"display": "Health Insurance", "unit": "%", "precision": 1}),
    ("BIRTHS", {"display": "Annual Births", "unit": "K", "precision": 1}),
    ("DEATHS", {"display": "Annual Deaths", "unit": "K", "precision": 1}),
    ("COVID_DEATHS", {"display": "COVID Deaths", "unit": "/mil", "precision": 1}),
    ("COVID_CASES", {"display": "COVID Cases", "unit": "/mil", "precision": 1}),
    ("MALE_POPULATION", {"display": "Male Population", "unit": "M", "precision": 1}),
    ("FEMALE_POPULATION", {"display": "Female Population", "unit": "M", "precision": 1}),
])

CHART_INDICATORS = {
    "HDI": "HDI", "Life Expectancy": "LIFE_EXPECTANCY", "GDP per Capita": "GDP_PER_CAPITA",
    "Gini Index": "GINI_INDEX", "Population Density": "POPULATION_DENSITY", "COVID Deaths / mil": "COVID_DEATHS" 
}
# KPI color is set to white/ivory for contrast against black
KPI_VALUE_COLOR = "#FFFFF0" 
KPI_NAME_COLOR = "#EEEEEE"

# -----------------------------
# 1. Page Config
# -----------------------------
st.set_page_config(
    page_title="Global Health Dashboard",
    layout="wide"
)

# Apply custom CSS immediately after config
st.markdown(CUSTOM_CSS, unsafe_allow_html=True) 

# -----------------------------
# 2. DATA LOADING & PREPARATION FUNCTIONS
# -----------------------------

def select_box_callback(country_name_to_iso):
    """Updates selected_id in session state based on select box change."""
    selected_name = st.session_state.country_select_box
    if selected_name:
        current_iso = country_name_to_iso.get(selected_name, selected_name)
        st.session_state.selected_id = current_iso
    else:
        st.session_state.selected_id = None


def format_value(value, units="", precision=3, is_currency=False):
    """Helper function to format values safely with HTML for popups/KPIs."""
    if pd.isna(value) or value is None:
        return "<span style='color: #FF6347;'>**Data Not Available**</span>"
    
    if is_currency:
        prefix = '$'
        if abs(value) >= 1000:
            value_str = f"{int(value):,}"
        else:
            value_str = f"{value:.{precision}f}"
    else:
        prefix = ''
        if value >= 1000 and not (units == 'Yrs' or units == '%'):
            value_str = f"{int(value):,}"
        else:
            value_str = f"{value:.{precision}f}"
    
    # KPI value color HTML tag
    return f"<span style='color: {KPI_VALUE_COLOR};'>{prefix}{value_str}</span> {units}"


def create_data_narrative_for_popup(row, year):
    """
    Creates a simplified, HTML-formatted string suitable for a Folium Popup.
    This content is displayed when a country on the map is clicked.
    """
    if row.empty or row['COUNTRY'] is None:
        return "No comprehensive data narrative available."

    country_name = row['COUNTRY']
    html_content = f"<div style='font-family: sans-serif; max-width: 250px; color: #2C3E50;'>"
    html_content += f"<h4 style='margin-bottom: 5px;'>{country_name} ({year})</h4>"
    html_content += f"<p style='font-size: 10px; margin-top: 0; color: #555;'>*Clicking a country here displays its full data snapshot.*</p>"
    html_content += "<ul>"
    
    # Iterate through a subset of key indicators for the quick popup view
    POPUP_INDICATORS = ["HDI", "LIFE_EXPECTANCY", "GDP_PER_CAPITA", "TOTAL_POPULATION", "GINI_INDEX"]

    for indicator_key in POPUP_INDICATORS:
        details = ALL_INDICATOR_DETAILS.get(indicator_key, {})
        display_name = details.get("display", indicator_key.replace('_', ' ').title())
        
        if indicator_key == "MEDIAN_AGE_EST":
             value = row.get('MEDIAN_AGE_EST', row.get('MEDIAN_AGE_MID', np.nan))
        else:
             value = row.get(indicator_key, np.nan)

        formatted = format_value(
            value,
            units=details.get("unit", ""),
            precision=details.get("precision", 3),
            is_currency=details.get("currency", False)
        ).replace(KPI_VALUE_COLOR, "#000000") # Use black text for the light-themed popup

        # Use <li> tags for a clean list format
        html_content += f"<li style='font-size: 14px;'><b>{display_name}:</b> {formatted}</li>"

    html_content += "</ul>"
    
    # Button-like link to view the full details in the Streamlit area (optional but helpful)
    html_content += f"<p style='margin-top: 10px; text-align: center;'><a href='#' onclick='window.alert(\"Select this country in the dropdown menu to see full charts and KPIs below.\")'>View Full Dashboard Details</a></p>"

    html_content += "</div>"
    return html_content.replace('</span>', '</span>').replace('None', 'N/A')


@st.cache_data
def load_data():
    """Loads data, pre-calculates map popups, and applies filtering/cleaning."""
    
    EXCLUDE_TERMS = [
        "AFRICA", "ASIA", "LATIN AMERICA", "CARIBBEAN", "MIDDLE EAST",
        "HIGH INCOME", "LOW INCOME", "IDA", "IBRD", "UNION", "WORLD", "TOTAL",
        "DEVELOPING", "EASTERN", "WESTERN", "CENTRAL", "PACIFIC", "ARAB", "OECD", 
        "LESS DEVELOPED", "MORE DEVELOPED", "EURO AREA", "UN", "FORMER", "REPUBLIC OF YEMEN",
        "REGIONS", "DEMOGRAPHIC DIVIDEND", "SMALL STATES", "LAND-LOCKED", "NORTH AMERICA", "ANDORRA"
    ]
    
    SPECIFIC_EXCLUSIONS = [
        "CZECHOSLOVAKIA", "WEST BENGAL", "HOLY SEE", 
        "BRITISH VIRGIN ISLANDS", "CAYMAN ISLANDS", "FALKLAND ISLANDS", "GIBRALTAR", 
        "GUERNSEY", "ISLE OF MAN", "JERSEY", "NEW CALEDONIA", "NETHERLANDS ANTILLES",
        "FRENCH GUIANA", "FRENCH POLYNESIA", "GUADELOUPE", "MAYOTTE", "MARTINIQUE",
        "CHANNEL ISLANDS", "MONTSERRAT", "CURACAO", "BONAIRE SINT EUSTATIUS AND SABA",
        "FAROE ISLANDS", "ARUBA", "AMERICAN SAMOA"
    ]
    
    RENAME_ISO_TO_COUNTRY = {
        "GRL": "Greenland", "EAS": "Asia (Russia Data Proxy)", "ARB": "Arab World (Saudi Arabia Data Proxy)",               
        "EGY": "Egypt, Arab Rep. (Norway Data Proxy)", "MNA": "Middle East/N. Africa (Pakistan Data Proxy)",        
        "ECS": "Europe & C. Asia (UK/WBengal/Euro Proxy)", "AFE": "Africa E&S (Zambia, Sudan Proxy)",                   
        "AFW": "Africa W&C (Tanzania, Togo, SL Proxy)", "MEA": "Middle East/N. Africa/Pakistan (Syria, W. Sahara, Tunisia Proxy)", 
        "TEC": "Europe & C. Asia (IDA/IBRD) (Romania Proxy)", "CEB": "Central European & Baltic (Poland Proxy)",           
        "ECA": "Europe & C. Asia (excl. High Income) (Portugal Proxy)", "NAC": "North America (Uruguay, Paraguay Proxy)",            
        "GBR": "United Kingdom", "PAK": "Pakistan", "KOR": "Korea, Rep.", "PRK": "Korea, Dem. People's Rep.",
        "IRN": "Iran, Islamic Rep.", "MAC": "Macao SAR, China", "HKG": "Hong Kong SAR, China",
        "COG": "Congo, Rep.", "CPV": "Cabo Verde", "KGZ": "Kyrgyz Republic",
        "LAO": "Lao PDR", "FSM": "Micronesia, Fed. Sts.",
        "FFF": "Africa Central (New Proxy)",
    }
    
    MUST_KEEP_AGGREGATES = [
        "Americas", "Europe & Central Asia", "East Asia & Pacific", 
        "Arab World", "Middle East, North Africa, Afghanistan & Pakistan (excluding high income)",
        "Africa Eastern and Southern", "Africa Western and Central",
        "Middle East, North Africa, Afghanistan & Pakistan", 
        "Europe & Central Asia (IDA & IBRD countries)",
        "Central Europe and the Baltics", "Europe & Central Asia (excluding high income)",
        "North America", "Latin America & Caribbean"
    ]

    try:
        df = pd.read_csv("final_with_socio_cleaned.csv")
        mismatch_df = pd.read_csv("country_name_mismatch_map.csv")
        
        hex_df = pd.read_csv("Hex.csv", usecols=['iso_alpha', 'hex'], dtype={'iso_alpha': str, 'hex': str})
        hex_df.columns = ['ISO3', 'HEX_CODE']
        iso_to_hex = hex_df[hex_df['ISO3'].str.len() == 3].set_index('ISO3')['HEX_CODE'].to_dict()
        
    except FileNotFoundError as e:
        st.error(f"FATAL ERROR: Missing required file: {e.filename}.")
        st.stop()
    except pd.errors.ParserError as e:
        st.error(f"FATAL ERROR: CSV parsing issue: {e}. Check files.")
        st.stop()

        
    df.columns = [col.upper() for col in df.columns] 
    df["YEAR"] = df["YEAR"].astype(int)
    df["ISO3"] = df["ISO3"].str.strip()
    df["COUNTRY"] = df["COUNTRY"].str.strip()

    df['ORIGINAL_COUNTRY'] = df['COUNTRY'] 
    for iso, correct_name in RENAME_ISO_TO_COUNTRY.items():
        df.loc[df['ISO3'] == iso, 'COUNTRY'] = correct_name

    df_filtered = df.copy()
    must_keep_isos = df_filtered['ISO3'].isin(RENAME_ISO_TO_COUNTRY.keys())
    must_keep_names = df_filtered["ORIGINAL_COUNTRY"].isin(MUST_KEEP_AGGREGATES)
    
    is_specific_exclusion = df_filtered["ORIGINAL_COUNTRY"].str.upper().isin([s.upper() for s in SPECIFIC_EXCLUSIONS])
    
    is_aggregate = pd.Series(False, index=df_filtered.index)
    for term in EXCLUDE_TERMS:
        is_aggregate = is_aggregate | df_filtered["ORIGINAL_COUNTRY"].str.contains(term, case=False, na=False)
    rows_to_keep = (must_keep_isos) | (must_keep_names) | (~is_aggregate & ~is_specific_exclusion)
    df = df_filtered[rows_to_keep].copy()
    df.loc[df['COUNTRY'] == "Americas", 'COUNTRY'] = "Americas (USA Data Proxy)"
    df.drop(columns=['ORIGINAL_COUNTRY'], inplace=True) 

    mismatch_map_df = dict(zip(mismatch_df["GEOJSON_NAME"], mismatch_df["ISO3"]))
    
    # --- Pre-calculate popover HTML for all countries and years ---
    popup_data = {}
    for iso in df['ISO3'].unique():
        country_df = df[df['ISO3'] == iso]
        popup_data[iso] = {}
        for year in country_df['YEAR'].unique():
            row = country_df[country_df['YEAR'] == year].iloc[0]
            popup_html = create_data_narrative_for_popup(row, year)
            popup_data[iso][year] = popup_html

    try:
        response = requests.get(WORLD_GEOJSON_URL)
        world_geojson = response.json()
    except Exception as e:
        st.warning(f"Failed to load world GeoJSON for map coloring: {e}")
        world_geojson = None
    
    return df, world_geojson, mismatch_map_df, iso_to_hex, popup_data


def draw_country_details(df, selected_id, year):
    """Renders the detailed KPI and chart view for a selected country."""

    st.markdown("---")
    st.markdown("## 🔎 Country Detailed Analysis")
    
    is_name_id = isinstance(selected_id, str) and "Proxy" in selected_id

    if is_name_id:
        country_df = df[df["COUNTRY"] == selected_id].sort_values("YEAR")
    else:
        country_df = df[df["ISO3"] == selected_id].sort_values("YEAR")

    if country_df.empty:
        st.info("No detailed data available for this selection.")
        return

    country_name = country_df.iloc[0]["COUNTRY"]
    st.subheader(country_name)
    
    latest_row_check = country_df[country_df["YEAR"] == year]
    
    if latest_row_check.empty:
        st.warning(f"No KPI data for {country_name} for the year {year} is available.")
        return

    latest = latest_row_check.iloc[0] 
    
    # --- 1. Display ALL Key Performance Indicators (KPIs) ---
    st.markdown(f"**Data Snapshot for {year}:**")
    
    cols = st.columns(5)
    
    for i, (key, details) in enumerate(ALL_INDICATOR_DETAILS.items()):
        
        col = cols[i % 5]
        
        if key == "MEDIAN_AGE_EST":
             value = latest.get('MEDIAN_AGE_EST', latest.get('MEDIAN_AGE_MID', np.nan))
        else:
             value = latest.get(key, np.nan)
             
        formatted_value_str = format_value(
            value,
            units=details.get("unit", ""),
            precision=details.get("precision", 3),
            is_currency=details.get("currency", False)
        )
        
        with col:
            st.markdown(f"<p style='font-size: 14px; font-weight: bold; margin-bottom: 0; color: {KPI_NAME_COLOR};'>{details['display']}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-size: 18px;'>{formatted_value_str}</p>", unsafe_allow_html=True)
    
    st.markdown("---")

    # --- 2. Historical Trends (Line Chart - Title cleaned) ---
    st.markdown("#### Historical Trends")
    
    col_chart_select, col_chart_options = st.columns([1, 4])
    
    with col_chart_select:
        trend_option = st.selectbox(
            "Select Trend Range",
            ["Last 5 Years", "Last 10 Years", "All Available Years"],
            key=f"trend_range_{selected_id}"
        )
    
    years_available = sorted(country_df["YEAR"].unique(), reverse=True)
    
    if trend_option == "Last 5 Years":
        n_years = 5
    elif trend_option == "Last 10 Years":
        n_years = 10
    else:
        n_years = len(years_available)

    recent_years = years_available[:n_years]
    recent_df = country_df[country_df["YEAR"].isin(recent_years)]

    cols_chart = st.columns(2)

    for i, (label, col) in enumerate(CHART_INDICATORS.items()):
        
        fig_line_trend = px.line(
            recent_df,
            x="YEAR",
            y=col,
            markers=True,
            title=label,
            color_discrete_sequence=[INDICATOR_COLORS.get(col, '#666666')]
        )
        
        fig_line_trend.update_layout(
            height=300, 
            template="plotly_dark", 
            margin=dict(t=40, b=10, l=10, r=10),
            showlegend=False 
        )

        with cols_chart[i % 2]:
            st.plotly_chart(fig_line_trend, use_container_width=True)


# -----------------------------
# 4. MAIN APPLICATION EXECUTION
# -----------------------------

try:
    df, world_geojson, mismatch_map, iso_to_hex, popup_data = load_data() 
    years = sorted(df["YEAR"].unique())

    country_list = sorted(df["COUNTRY"].unique())
    country_name_to_iso = dict(zip(df[df['ISO3'].str.len() > 0]["COUNTRY"], df[df['ISO3'].str.len() > 0]["ISO3"]))
    country_name_to_iso["Americas (USA Data Proxy)"] = "Americas (USA Data Proxy)"

    if 'selected_id' not in st.session_state:
        st.session_state.selected_id = None 
    if 'comparison_isos' not in st.session_state:
        st.session_state.comparison_isos = []

    
    # 1. Unified Header and Slider Container
    st.markdown("<h2 style='text-align:center;'>🌍 Global Health Dashboard</h2>", unsafe_allow_html=True)
    
    col_map_options, col_year_slider = st.columns([1, 4])
    
    with col_year_slider:
        year = st.slider(
            "Select Year to Analyze",
            min_value=int(min(years)),
            max_value=int(max(years)),
            value=int(max(years)),
            step=1
        )
    
    with col_map_options:
        selected_country_name_fallback = st.selectbox(
            "1. Select Country",
            options=[None] + country_list, 
            index=0,
            key='country_select_box',
            on_change=lambda: select_box_callback(country_name_to_iso)
        )
        current_id = None
        if selected_country_name_fallback:
            current_id = country_name_to_iso.get(selected_country_name_fallback, selected_country_name_fallback)
            st.session_state.selected_id = current_id
    
    st.markdown("---")
    st.markdown("### Interactive Map View")
    st.caption("Click any country on the map to view its quick data snapshot. Use the dropdown above to select a country and view detailed charts below.")


    # ----------------------------------------------------
    # 2. Render Folium Map with Popups on Click
    # ----------------------------------------------------

    m = folium.Map(location=[10, 0], zoom_start=2, tiles="OpenStreetMap", control_scale=True) 

    def style_function(feature):
        country_iso = feature['id']
        hex_color = iso_to_hex.get(country_iso, '#666666') 
        
        return {
            'fillColor': hex_color,
            'color': 'black', 
            'weight': 0.5,
            'fillOpacity': 0.6
        }

    if world_geojson:
        # We iterate over individual features to attach dynamic popups
        for feature in world_geojson['features']:
            country_iso = feature['id']
            country_name = feature['properties'].get('name')
            
            # 1. Determine the ISO/Proxy code for data lookup
            data_iso = mismatch_map.get(country_name, country_iso)
            
            # 2. Retrieve the popup HTML for the selected year
            current_year_popups = popup_data.get(data_iso) or {}
            
            popup_html = current_year_popups.get(year)
            if not popup_html:
                 available_years = sorted(current_year_popups.keys())
                 if available_years:
                     # Find nearest available year (simple approximation)
                     closest_year = min(available_years, key=lambda y: abs(y - year))
                     popup_html = current_year_popups.get(closest_year) or f"No detailed data for {country_name} in or near {year}."
                 else:
                     popup_html = f"No detailed data available for {country_name}."

            # 3. Create a Folium Popup object (opens on click)
            # The popup width is constrained to look neat
            if popup_html:
                 popup = folium.Popup(popup_html, max_width=300, min_width=250)
                 
                 # 4. Create a GeoJson object for this single feature with styles/popup
                 folium.GeoJson(
                     feature,
                     name=country_name,
                     style_function=lambda x: style_function(feature),
                     # FINAL DARK SHADOW HIGHLIGHT FOR "LIFT" EFFECT
                     highlight_function=lambda x: {
                         'color': '#444444',    
                         'weight': 4,          
                         'fillOpacity': 0.5  
                     }, 
                     tooltip=folium.features.GeoJsonTooltip(fields=['name'], aliases=['Country:']),
                     popup=popup # Attach the popup here (opens on click)
                 ).add_to(m)

    st_folium(
        m, 
        height=500, 
        width='100%', 
        use_container_width=True,
        key="folium_map_iso_capture", 
        returned_objects=["last_active_feature", "last_clicked"] 
    )

    # --- Click capture logic remains for the Streamlit KPI/Chart section ---
    # The Folium map handles its own popups now. The logic here still updates the main selection.
    clicked_id = None
    map_data = st.session_state["folium_map_iso_capture"] 

    if map_data and map_data.get("last_active_feature") and 'id' in map_data["last_active_feature"]:
        iso_from_feature = str(map_data["last_active_feature"]["id"]).strip().upper()
        country_name_from_map = map_data["last_active_feature"]["properties"].get("name")
        
        if country_name_from_map and country_name_from_map in mismatch_map:
            clicked_id = mismatch_map[country_name_from_map]
        elif iso_from_feature in df['ISO3'].values:
            clicked_id = iso_from_feature
            
    if clicked_id:
        st.session_state.selected_id = clicked_id
        # Force the selectbox to update to the clicked country name
        country_name_for_select = df[(df["ISO3"] == clicked_id) | (df["COUNTRY"] == clicked_id)].iloc[0]["COUNTRY"]
        st.session_state.country_select_box = country_name_for_select
        st.rerun() # Rerun to update the selection and charts below


    # -----------------------------
    # 6. Country Details Section (Charts and KPIs)
    # -----------------------------
    if st.session_state.selected_id:
        draw_country_details(df, st.session_state.selected_id, year)
    else:
        st.info("👆 Select a country using the dropdown or by clicking the map to view detailed KPIs and Charts below.")

    # -----------------------------
    # 7. Country Comparison Section 
    # -----------------------------
    st.markdown("---")
    st.markdown("## 📈 Country Comparison")
    
    
    col_select, col_metric = st.columns([3, 1])

    with col_select:
        selected_country_names = st.multiselect(
            "2. Select Countries for Comparison (Max 4)",
            options=country_list,
            default=None,
            max_selections=4
        )

    if selected_country_names:
        comparison_ids = []
        for name in selected_country_names:
            comparison_ids.append(country_name_to_iso.get(name, name))
        
        is_iso = df['ISO3'].isin(comparison_ids)
        is_name = df['COUNTRY'].isin(comparison_ids)

        comparison_df = df[is_iso | is_name].sort_values("YEAR")
        
        if not comparison_df.empty:
            
            latest_comparison_df = comparison_df[comparison_df["YEAR"] == year].copy()
            
            num_countries_with_data = latest_comparison_df.dropna(subset=['HDI', 'GDP_PER_CAPITA'], how='all').shape[0]

            with col_metric:
                st.metric(
                    label=f"Data Coverage in {year}", 
                    value=f"{num_countries_with_data} / {len(selected_country_names)}",
                    help="Number of selected countries with at least some key data (HDI or GDP) available for the selected year."
                )
            
            # --- 7.1: Historical Trends Comparison (Interactive Chart Type) ---
            st.markdown("### Historical Trends Comparison")
            
            chart_type = st.radio(
                "Select Trend Visualization Type:",
                ("Bar Chart (Magnitude Comparison)", "Line Chart (Trend Focus)"),
                key="comparison_chart_type",
                horizontal=True
            )
            
            col_comp_trend_select, _ = st.columns([1, 4])
            with col_comp_trend_select:
                comp_trend_option = st.selectbox(
                    "Trend Range",
                    ["Last 5 Years", "Last 10 Years", "All Available Years"],
                    key=f"comp_trend_range"
                )
            
            years_available_comp = sorted(comparison_df["YEAR"].unique(), reverse=True)
            if comp_trend_option == "Last 5 Years": n_years_comp = 5
            elif comp_trend_option == "Last 10 Years": n_years_comp = 10
            else: n_years_comp = len(years_available_comp)

            recent_years_comp = years_available_comp[:n_years_comp]
            recent_comp_df = comparison_df[comparison_df["YEAR"].isin(recent_years_comp)]

            cols_line = st.columns(2)

            for i, (label, col) in enumerate(CHART_INDICATORS.items()):
                
                if chart_type == "Line Chart (Trend Focus)":
                    fig_comp = px.line(
                        recent_comp_df.dropna(subset=[col]),
                        x="YEAR",
                        y=col,
                        color="COUNTRY", 
                        markers=True,
                        title=f"Trend: {label}",
                        hover_data={"COUNTRY": True, "YEAR": True, col: ":.2f"}
                    )
                else:
                    fig_comp = px.bar(
                        recent_comp_df.dropna(subset=[col]),
                        x="YEAR",
                        y=col,
                        color="COUNTRY", 
                        barmode='group',
                        title=f"Trend Magnitude: {label}",
                        hover_data={"COUNTRY": True, "YEAR": True, col: ":.2f"}
                    )
                
                fig_comp.update_layout(
                    height=350, 
                    template="plotly_dark", 
                    margin=dict(t=40, b=10, l=10, r=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )

                with cols_line[i % 2]:
                    st.plotly_chart(fig_comp, use_container_width=True)


            # --- 7.2: Latest Year Comparison (Magnitude Comparison with Gradient) ---
            st.markdown("### Latest Year Comparison (Interactive Bar Charts)")

            if not latest_comparison_df.empty:
                cols_bar = st.columns(2)
                
                for i, (label, col) in enumerate(CHART_INDICATORS.items()):
                    
                    plot_df = latest_comparison_df.dropna(subset=[col]).sort_values(by=col, ascending=False)
                    
                    if plot_df.empty:
                        with cols_bar[i % 2]:
                             st.info(f"Not enough data for {label} comparison in {year}.")
                        continue
                    
                    fig_bar = px.bar(
                        plot_df,
                        x="COUNTRY",
                        y=col,
                        title=f"{label} Value in {year}",
                        color=col, 
                        color_continuous_scale=px.colors.sequential.Plasma, 
                        hover_data={col: ':.2f'} 
                    )

                    fig_bar.update_layout(
                        height=350, 
                        template="plotly_dark", 
                        margin=dict(t=40, b=10, l=10, r=10),
                        xaxis={'categoryorder':'total descending'} 
                    )
                    
                    with cols_bar[i % 2]:
                        st.plotly_chart(fig_bar, use_container_width=True)
            else:
                 st.info(f"No data available for the selected countries in the year {year}.")
        
        else:
            st.warning("No data found for the selected countries.")
    else:
        st.info("Select 2 or more countries above to view comparative historical trends.")

    st.markdown("---")

except Exception as e:
    st.title("🆘 Application Failed to Load")
    st.error("A critical error occurred while starting the application. Check your console logs for details.")
    st.code(f"Error Type: {type(e).__name__}", language='python')
    st.code(f"Error Message: {e}", language='python')
    st.code(traceback.format_exc(), language='python')
    st.warning("Ensure all data files (`.csv`) and the `requirements.txt` file are present.")
