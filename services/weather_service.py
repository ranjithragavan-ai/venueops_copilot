import requests

def get_live_weather(lat=None, lon=None):
    """
    Fetches live weather data from Open-Meteo for the given coordinates.
    """
    city = "Current Location"
    
    if lat is None or lon is None:
        # Default to MetLife Stadium if no coordinates provided
        lat, lon = 40.8128, -74.0742 
        city = "Stadium Location"
    else:
        # Reverse geocoding to get the city name using BigDataCloud
        try:
            geo_url = f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lon}&localityLanguage=en"
            geo_resp = requests.get(geo_url, timeout=5)
            if geo_resp.status_code == 200:
                geo_data = geo_resp.json()
                fetched_city = geo_data.get("city") or geo_data.get("locality") or "Local Area"
                country = geo_data.get("countryName", "")
                city = f"{fetched_city}, {country}"
        except Exception as e:
            print(f"Error reverse geocoding: {e}")

    # Get weather for coordinates
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        current = data.get("current", {})
        temp = current.get("temperature_2m", "N/A")
        code = current.get("weather_code", 0)
        
        # Simple WMO weather code mapping
        condition = "Clear"
        icon = "☀️"
        if code in [1, 2, 3]:
            condition = "Partly Cloudy"
            icon = "⛅"
        elif code in [45, 48]:
            condition = "Foggy"
            icon = "🌫️"
        elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
            condition = "Rain"
            icon = "🌧️"
        elif code in [71, 73, 75, 85, 86]:
            condition = "Snow"
            icon = "🌨️"
        elif code in [95, 96, 99]:
            condition = "Thunderstorm"
            icon = "⛈️"
            
        return {
            "condition": condition,
            "temperature_c": temp,
            "icon": icon,
            "city": city
        }
    except Exception as e:
        print(f"Error fetching weather: {e}")
        return {
            "condition": "Unknown",
            "temperature_c": "N/A",
            "icon": "❓",
            "city": city
        }
