import os
import requests
import json

# Manually test the exact payload structure
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "YOUR_ACTUAL_SERP_KEY_HERE")

params = {
    "engine": "google_flights",
    "departure_id": "BOM",    
    "arrival_id": "DBR",  
    "outbound_date": "2026-06-22", 
    "currency": "INR",
    "hl": "en",
    "api_key": SERPAPI_KEY
}

print("--> Hitting SerpAPI directly...")
response = requests.get('https://serpapi.com/search', params=params)
data = response.json()

print("\n--- ROOT KEYS FOUND IN RESPONSE ---")
print(data.keys())

if "error" in data:
    print(f"\n🔴 SerpAPI Error: {data['error']}")

print("\n--- DATA CHECK ---")
print(f"best_flights count: {len(data.get('best_flights', []))}")
print(f"other_flights count: {len(data.get('other_flights', []))}")