import requests

def get_live_weather():
    """
    Fetches live weather data from Open-Meteo for the stadium location.
    """
    # Hardcoded to Chennai for the demo (or you can change to any stadium's coordinates)
    lat, lon = 13.0827, 80.2707 
    city = "Chennai, India"

    # 2. Get weather for those coordinates
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
