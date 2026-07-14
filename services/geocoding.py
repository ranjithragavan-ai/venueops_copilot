import requests

def geocode_city(city_name):
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={city_name}&format=json&limit=1"
        resp = requests.get(url, headers={"User-Agent": "VenueOps-Demo"}, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                # Return lat, lon, and the nicely formatted display name
                return float(data[0]['lat']), float(data[0]['lon']), data[0]['display_name']
    except Exception as e:
        print(f"Geocoding error: {e}")
    return None, None, city_name
