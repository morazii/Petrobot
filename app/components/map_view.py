import plotly.express as px
import pandas as pd
import streamlit as st

def render_map(data: list[dict]):
    """
    Render a Plotly scatter mapbox for well coordinates.
    Expects data to have: name, field, operator, status, environment, lat, lon.
    """
    if not data:
        return
        
    df = pd.DataFrame(data)
    
    # Ensure lat/lon exist
    if 'lat' not in df.columns or 'lon' not in df.columns:
        st.error("Map data is missing coordinates.")
        return
        
    # Create the map
    fig = px.scatter_mapbox(
        df, 
        lat="lat", 
        lon="lon", 
        hover_name="name",
        hover_data={
            "lat": False,
            "lon": False,
            "field": True,
            "operator": True,
            "status": True,
            "environment": True
        },
        color="status" if "status" in df.columns else None,
        color_discrete_sequence=px.colors.qualitative.Bold,
        zoom=7,
        height=600,
        title=f"Geographic Well Distribution ({len(df)} wells)"
    )
    
    fig.update_layout(
        mapbox_style="carto-darkmatter",
        margin={"r":0,"t":40,"l":0,"b":0},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            bgcolor="rgba(11, 20, 31, 0.8)",
            bordercolor="rgba(119, 147, 171, 0.4)",
            borderwidth=1,
            font=dict(color="#d7e4f1"),
        ),
        title=dict(font=dict(color="#e6eef7")),
    )
    
    st.plotly_chart(fig, use_container_width=True)
