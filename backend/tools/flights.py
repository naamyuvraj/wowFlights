import os  # <-- Add this at the very top
import requests
import json
# Remove or leave 'from config import SERPAPI_KEY'

def get_live_flights(origin: str, destination: str, departure_date: str):
    print(f'Executing tool for {origin} to {destination} on {departure_date}')

    # Natively pluck the key live from the active process space
    api_key = os.environ.get("SERPAPI_KEY")
    
    if not api_key:
        print("--> [SERPAPI] CRITICAL WARNING: Key not found in os.environ! Checking fallback...")
        # Fallback layer just in case
        try:
            from config import SERPAPI_KEY
            api_key = SERPAPI_KEY
        except Exception:
            pass
            
    if not api_key:
        raise ValueError("SERPAPI_KEY not found in environment variables.")
        
    params = {
        "engine": "google_flights",
        "departure_id": origin,    
        "arrival_id": destination,  
        "outbound_date": departure_date, 
        "currency": "INR",
        "hl": "en",
        "api_key": api_key
    }
    
    try:
        response = requests.get('https://serpapi.com/search', params=params)
        data = response.json()
        
        # Safe array selection structure
        raw_flights = data.get('best_flights', [])
        if not raw_flights:
            print("--> [SERPAPI] 'best_flights' was empty. Checking 'other_flights'...")
            raw_flights = data.get('other_flights', [])
            
        best_flight = raw_flights[:5]
        price_insights = data.get('price_insights', {})

        insights_data = {
            "price_level": price_insights.get("price_level", "Unknown"),
            "typical_range": price_insights.get("typical_price_range", ["N/A", "N/A"])
        }

        cleaned_flights = []
        for flight in best_flight:
            flight_details = flight.get('flights', [{}])[0]
            cleaned_flights.append({
                "airline": flight_details.get('airline', 'N/A'),
                "flight_number": flight_details.get('flight_number', 'N/A'),
                "price": f"₹{flight.get('price', 'N/A')}",
                'duration': flight.get('duration', 'N/A')
            })
            
        return json.dumps({
            "flights": cleaned_flights,
            "insights": insights_data
        })
        
    except Exception as e:
        print(f"Error fetching flight data: {e}")
        return json.dumps({"error": "Failed to fetch flight data."})