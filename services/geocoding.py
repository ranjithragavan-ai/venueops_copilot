import requests
import streamlit as st

@st.cache_data(ttl=3600)
def geocode_city(city_name):
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={city_name}&format=json&limit=1"
        resp = requests.get(url, headers={"User-Agent": "VenueOps-Demo"}, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon']), data[0]['display_name']
    except Exception as e:
        print(f"Geocoding error: {e}")
    return None, None, city_name

@st.cache_data(ttl=3600)
def get_ip_location(client_ip=None):
    """Fetches lat/lon/city based on IP address automatically."""
    try:
        if client_ip:
            # Fetch for specific client IP
            url = f"http://ip-api.com/json/{client_ip}"
        else:
            # Fallback to server/network public IP if client IP isn't available
            url = "http://ip-api.com/json/"
            
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and data.get("status") == "success":
                lat = data.get("lat")
                lon = data.get("lon")
                city = data.get("city", "Local Area")
                country = data.get("country", "")
                display_city = f"{city}, {country}" if country else city
                return lat, lon, display_city
    except Exception as e:
        print(f"IP Location error: {e}")
    return None, None, None
