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
/* This targets the iframe Streamlit uses to display the map */
div.st-emotion-cache-16k74f6 > iframe {
    border: none !important;
}

/* 2. MAKES THE MAP HOVER BORDER LIGHT GRAY/SILVER (AS REQUESTED) */
/* This targets the path elements used for the GeoJson borders */
.leaflet-interactive {
    outline: none !important; /* General selector to remove outline */
}
/* Apply light gray stroke on hover for a subtle 'lift' effect */
.leaflet-container .leaflet-interactive.leaflet-clickable:hover {
    stroke: #CCCCCC !important; 
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
    ("PM25", {"display": "PM2.5 (Air Pollution)", "unit": "µg/m³", "precision": 2}),
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


@st.cache_data
def load_data():
    """Loads data, GeoJSON, the Mismatch Map, and the Hex Colors, and applies filtering/cleaning.
    *** CRITICAL: This section is updated with final country mappings. ***
    """
    
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
    
    # 1. RENAME_ISO_TO_COUNTRY: Used to rename ISO codes in the data to human-readable proxy names
    RENAME_ISO_TO_COUNTRY = {
        "GRL": "Greenland", "EAS": "Asia (Russia Data Proxy)", "ARB": "Arab World (Saudi Arabia Data Proxy)",               
        "EGY": "Egypt, Arab Rep. (Norway Data Proxy)", "MNA": "Middle East/N. Africa (Pakistan Data Proxy)",        
        "ECS": "Europe & C. Asia (UK/WBengal/Euro Proxy)", "AFE": "Africa E&S (Zambia, Sudan Proxy)",                   
        "AFW": "Africa W&C (Tanzania, Togo, SL Proxy)", "MEA": "Middle East/N. Africa/Pakistan (Syria, W. Sahara, Tunisia Proxy)", 
        "TEC": "Europe & C. Asia (IDA/IBRD) (Romania Proxy)", "CEB": "Central European & Baltic (Poland Proxy)",           
        "ECA": "Europe & C. Asia (excl. High Income) (Portugal Proxy)", "NAC": "North America (Uruguay, Paraguay Proxy)",            
        # Existing specific ISO renames
        "GBR": "United Kingdom", "PAK": "Pakistan", "KOR": "Korea, Rep.", "PRK": "Korea, Dem. People's Rep.",
        "IRN": "Iran, Islamic Rep.", "MAC": "Macao SAR, China", "HKG": "Hong Kong SAR, China",
        "COG": "Congo, Rep.", "CPV": "Cabo Verde", "KGZ": "Kyrgyz Republic",
        "LAO": "Lao PDR", "FSM": "Micronesia, Fed. Sts.",
        # --- NEW PROXY: FFF ---
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

    # 2. mismatch_map: Maps GeoJSON country name (clicked on map) to a proxy ISO3 code for data lookup.
    mismatch_map = dict(zip(mismatch_df["GEOJSON_NAME"], mismatch_df["ISO3"]))
    
    try:
        response = requests.get(WORLD_GEOJSON_URL)
        world_geojson = response.json()
    except Exception as e:
        st.warning(f"Failed to load world GeoJSON for map coloring: {e}")
        world_geojson = None
    
    return df, world_geojson, mismatch_map, iso_to_hex


# -----------------------------
# 3. DETAILED ANALYSIS FUNCTIONS
# -----------------------------

def format_value(value, units="", precision=3, is_currency=False):
    """Helper function to format values safely, with explicit missing data message and KPI color."""
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
    
    # KPI color is applied here
    return f"<span style='color: {KPI_VALUE_COLOR};'>{prefix}{value_str}</span> {units}"


def create_data_narrative(row, year):
    """Creates a comprehensive, human-readable narrative text block with detailed explanations."""
    if row.empty or row['COUNTRY'] is None:
        return "No comprehensive data narrative available."

    country_name = row['COUNTRY']
    text = f"### 📊 Data Snapshot: {country_name} ({year})\n\n"
    text += "This section provides a detailed breakdown of all available indicators for the selected country and year, with explanations for easy understanding.\n\n"
    
    sections = collections.OrderedDict([
        ("Development & Economic Stability", ["HDI", "GDP_PER_CAPITA", "GINI_INDEX"]),
        ("Population Structure & Demographics", ["TOTAL_POPULATION", "MEDIAN_AGE_EST", "POPULATION_DENSITY", "MALE_POPULATION", "FEMALE_POPULATION"]),
        ("Health Outcomes & Environmental Risk", ["LIFE_EXPECTANCY", "HEALTH_INSURANCE", "PM25"]),
        ("Vital Statistics & Pandemic Impact", ["BIRTHS", "DEATHS", "COVID_DEATHS", "COVID_CASES"]),
    ])
    
    for section_title, indicators in sections.items():
        text += f"#### {section_title}\n"
        for indicator in indicators:
            detail = ALL_INDICATOR_DETAILS.get(indicator, {})
            display_name = detail.get("display", indicator.replace('_', ' ').title())
            
            if indicator == "MEDIAN_AGE_EST":
                 value = row.get('MEDIAN_AGE_EST', row.get('MEDIAN_AGE_MID', np.nan))
            else:
                 value = row.get(indicator, np.nan)

            formatted = format_value(
                value, 
                units=detail.get("unit", ""), 
                precision=detail.get("precision", 3), 
                is_currency=detail.get("currency", False)
            ).replace(f"</span> {detail.get('unit', '')}", f"</span>")

            context = ""
            unit_desc = f" (Unit: {detail.get('unit', 'No Unit')})"
            if indicator == "HDI": context = "The **Human Development Index (HDI)** measures a country's average achievement in three basic dimensions of human development: a long and healthy life, knowledge, and a decent standard of living." + unit_desc
            elif indicator == "GDP_PER_CAPITA": context = "The **Gross Domestic Product (GDP) per Capita** is the national economic output divided by the total population, indicating average economic prosperity." + unit_desc
            elif indicator == "GINI_INDEX": context = "The **Gini Index** measures income inequality, where 0% represents perfect equality and 100% represents perfect inequality." + unit_desc
            elif indicator == "TOTAL_POPULATION": context = "The total number of people living in the country (reported in Millions)." + unit_desc
            elif indicator == "POPULATION_DENSITY": context = "The average number of people per square kilometer, showing how crowded the country is." + unit_desc
            elif indicator == "MEDIAN_AGE_EST": context = "The age that divides the population into two halves. A lower median age suggests a younger population." + unit_desc
            elif indicator == "LIFE_EXPECTANCY": context = "The average number of years a person is expected to live based on current death rates." + unit_desc
            elif indicator == "HEALTH_INSURANCE": context = "The percentage of the total population covered by some form of health insurance." + unit_desc
            elif indicator == "PM25": context = "The concentration of fine particulate matter in the air, a key indicator of environmental health risk." + unit_desc
            elif indicator == "BIRTHS": context = "The total number of births during the year (reported in thousands, K)." + unit_desc
            elif indicator == "DEATHS": context = "The total number of deaths during the year (reported in thousands, K)." + unit_desc
            elif indicator == "COVID_DEATHS": context = "The cumulative total of COVID-19 deaths per million people up to this year." + unit_desc
            elif indicator == "COVID_CASES": context = "The cumulative total of confirmed COVID-19 cases per million people up to this year." + unit_desc
            
            
            text += f"* **{display_name}:** {formatted} {detail.get('unit', '')}\n  > *Explanation:* {context}\n"
        text += "\n"
    
    return text.replace("K K", "K").replace("M M", "M")


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
            st.markdown(f"<p style='font-size: 14px; font-weight: bold; margin-bottom: 0;'>{details['display']}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-size: 18px;'>{formatted_value_str}</p>", unsafe_allow_html=True)
    
    st.markdown("---")

    # --- 2. Historical Trends (Line Chart & Interactive Year Selector) ---
    # Removed "Interactive Chart" from the title
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

FULL_SNAPSHOT_CONTENT = None 

try:
    df, world_geojson, mismatch_map, iso_to_hex = load_data() 
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
    
    if st.session_state.selected_id:
        country_df_check = df[(df["ISO3"] == st.session_state.selected_id) | (df["COUNTRY"] == st.session_state.selected_id)]
        latest_row_check = country_df_check[country_df_check["YEAR"] == year]
        if not latest_row_check.empty:
            FULL_SNAPSHOT_CONTENT = create_data_narrative(latest_row_check.iloc[0], year)


    # ----------------------------------------------------
    # 2. Render Folium Map & Capture Click 
    # ----------------------------------------------------

    m = folium.Map(location=[10, 0], zoom_start=2, tiles="OpenStreetMap", control_scale=True) 

    def style_function(feature):
        country_iso = feature['id']
        hex_color = iso_to_hex.get(country_iso, '#666666') 
        
        return {
            'fillColor': hex_color,
            'color': 'black', 
            'weight': 0.3,
            'fillOpacity': 0.8
        }

    if world_geojson:
        folium.GeoJson(
            world_geojson,
            name='Color and Click Layer',
            style_function=style_function, 
            # Hover highlight set to a dark color to contrast with the light CSS border
            highlight_function=lambda x: {
                'weight': 3.5,          
                'color': "#3E3838",    
                'fillOpacity': 0.8
            }, 
            tooltip=folium.features.GeoJsonTooltip(fields=['name'], aliases=['Country Name:']),
        ).add_to(m)


    map_data = st_folium(
        m, 
        height=500, 
        width='100%', 
        use_container_width=True,
        key="folium_map_iso_capture", 
        returned_objects=["last_active_feature", "last_clicked"] 
    )

    # --- MAP CLICK CAPTURE LOGIC ---
    clicked_id = None
    if map_data and map_data.get("last_active_feature") and 'id' in map_data["last_active_feature"]:
        iso_from_feature = str(map_data["last_active_feature"]["id"]).strip().upper()
        country_name_from_map = map_data["last_active_feature"]["properties"].get("name")
        
        if country_name_from_map and country_name_from_map in mismatch_map:
            clicked_id = mismatch_map[country_name_from_map]
        elif iso_from_feature in df['ISO3'].values:
            clicked_id = iso_from_feature
            
    if clicked_id is None and map_data and map_data.get("last_clicked"):
        lat = map_data["last_clicked"]["lat"]
        lon = map_data["last_clicked"]["lng"]
        coordinates = [(lat, lon)]
        try:
            results = reverse_geocode.search(coordinates)
            country_name_from_click = results[0]['country']
            
            if country_name_from_click in mismatch_map:
                clicked_id = mismatch_map[country_name_from_click]
            else:
                clicked_row = df[df["COUNTRY"].str.contains(country_name_from_click, case=False, na=False)]
                if not clicked_row.empty: clicked_id = clicked_row.iloc[0]["ISO3"] if clicked_row.iloc[0]["ISO3"] else clicked_row.iloc[0]["COUNTRY"]
        except Exception: pass 
        
    if clicked_id:
        st.session_state.selected_id = clicked_id
        country_df_check = df[(df["ISO3"] == clicked_id) | (df["COUNTRY"] == clicked_id)]
        latest_row_check = country_df_check[country_df_check["YEAR"] == year]
        if not latest_row_check.empty:
            FULL_SNAPSHOT_CONTENT = create_data_narrative(latest_row_check.iloc[0], year)


    # -----------------------------
    # 6. Country Details Section
    # -----------------------------
    if st.session_state.selected_id:
        draw_country_details(df, st.session_state.selected_id, year)
    else:
        st.info("👆 Click any country on the map or use the Select Box above to view detailed insights.")

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
            st.markdown("### Latest Year Comparison")

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

    # -----------------------------
    # 8. Relocated Comprehensive Snapshot (Final Section)
    # -----------------------------
    if FULL_SNAPSHOT_CONTENT:
        st.markdown("---")
        # Removed "(For New Users)" from the expander title
        with st.expander("🔬 View Full Comprehensive Data Snapshot"):
            st.markdown(FULL_SNAPSHOT_CONTENT, unsafe_allow_html=True)
        st.markdown("---")

except Exception as e:
    st.title("🆘 Application Failed to Load")
    st.error("A critical error occurred while starting the application. Check your console logs for details.")
    st.code(f"Error Type: {type(e).__name__}", language='python')
    st.code(f"Error Message: {e}", language='python')
    st.code(traceback.format_exc(), language='python')
    st.warning("Ensure all data files (`.csv`) are present and correctly formatted.")
