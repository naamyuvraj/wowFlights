import json
import re
from fastapi import APIRouter
from pydantic import BaseModel
from config import client
from tools.flights import get_live_flights
from tools.brain import search_airline_policy
from tools.predictor import predict_booking_window

router = APIRouter()

class AgentRequest(BaseModel):
    prompt: str


def _execute_tool(function_name: str, arguments: dict):
    if function_name == "getflights":
        required = ("origin", "destination", "departure_date")
        if not all(arguments.get(k) for k in required):
            return json.dumps({"error": "Missing required arguments for getflights."})
        safe_args = {k: arguments[k] for k in required}
        return get_live_flights(**safe_args)
    if function_name == "searchpolicy":
        query = arguments.get("query")
        if not query:
            return json.dumps({"error": "Missing required argument 'query' for searchpolicy."})
        return search_airline_policy(query=query)
    if function_name == "predict_booking_window":
        required = ("origin", "destination", "departure_date")
        if not all(arguments.get(k) for k in required):
            return json.dumps({"error": "Missing required arguments for predict_booking_window."})
        safe_args = {
            "origin": arguments["origin"],
            "destination": arguments["destination"],
            "departure_date": arguments["departure_date"],
        }
        if "current_base_price" in arguments:
            safe_args["current_base_price"] = arguments["current_base_price"]
        return predict_booking_window(**safe_args)
    return json.dumps({"error": f"Unknown tool: {function_name}"})


def _parse_failed_generation(error_text: str):
    match = re.search(r"<function=([a-zA-Z0-9_]+)>", error_text)
    if not match:
        return None

    function_name = match.group(1)
    start = error_text.find("{", match.end())
    if start == -1:
        return None

    brace_count = 0
    end = -1
    for idx in range(start, len(error_text)):
        char = error_text[idx]
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                end = idx
                break

    if end == -1:
        return None

    candidate_json = error_text[start:end + 1]
    try:
        arguments = json.loads(candidate_json)
    except json.JSONDecodeError:
        return None

    return function_name, arguments


def _format_final_response(raw_data_context: str):
    analytics_system_prompt = """
    You are a strict Data Formatter for a flight agency dashboard. 
    You will be provided with raw data metrics inside a JSON block.
    
    YOUR RULES:
    1. Extract 'action', 'probability_of_price_drop', and 'booking_date_strategy' directly from the data block.
    2. For 'predicted_lowest_price', look at 'historical_median' or 'live_price_evaluated' fields inside the raw text context. Extract the actual numerical price value (e.g., "₹5600"). NEVER output the word 'historical_median' or 'live_price_evaluated' as a literal string value.
    3. Ensure 'recommendation_summary' is a clean, punchy 1-sentence synthesis of whether to buy or wait.
    
    You MUST respond EXACTLY with this JSON schema structure and nothing else:
    {
        "recommendation_summary": "A clean, punchy 1-sentence summary statement.",
        "prediction_engine": {
            "action": "BOOK_NOW or WAIT",
            "probability_of_price_drop": "XX%",
            "predicted_lowest_price": "₹...",
            "booking_date_strategy": "Directly copy the booking_date_strategy sentence from the tool data."
        },
        "optimized_flights": []
    }
    """

    clean_slate_messages = [
        {"role": "system", "content": analytics_system_prompt},
        {
            "role": "user",
            "content": f"Here is the verified raw tool data to format. Convert it into the strict schema values:\n{raw_data_context}",
        },
    ]

    second_response = client.chat.completions.create(
        model='llama-3.1-8b-instant',
        messages=clean_slate_messages,
        response_format={"type": "json_object"},
    )
    final_response_content = second_response.choices[0].message.content
    return json.loads(final_response_content)


flight_tools = [
    {
        "type": "function",
        "function": {
            "name": "getflights",
            "description": "Fetch LIVE, real-time Google Flights options and pricing. Use this whenever the user asks for flights.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "3-letter airport code"},
                    "destination": {"type": "string", "description": "3-letter airport code"},
                    "departure_date": {"type": "string", "description": "YYYY-MM-DD format"}
                },
                "required": ["origin", "destination", "departure_date"]
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "searchpolicy",
            "description": "Search the internal vector database for airline baggage rules, pet policies, and fees.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string", 
                        "description": "The specific question to search, e.g., 'Does United charge for a carry-on?'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "predict_booking_window",
            "description": "Predict the best time to book a flight based on historical trends. Use this when the user asks for advice on when to book for the best price.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "3-letter airport code"},
                    "destination": {"type": "string", "description": "3-letter airport code"},
                    "departure_date": {"type": "string", "description": "YYYY-MM-DD format"}
                },
                "required": ["origin", "destination", "departure_date"]
            }
        }
    }
]


@router.post('/api/concierge')
async def run_concierge(request: AgentRequest):
    messages = [
        {
            "role": "system",
            "content": """You are an elite travel concierge and data analyst.
            CRITICAL RULES:
            1. AIRPORT CODES: You must ALWAYS translate city names into exact 3-letter IATA codes (e.g., Bombay = BOM, Darbhanga = DBR).
            2. You MUST determine if the user wants flight deals, price analysis, or booking strategies.""",
        },
        {"role": "user", "content": request.prompt},
    ]

    try:
        # Step 1: Initial tool detection call
        response = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=messages,
            tools=flight_tools,
            tool_choice='auto',
            parallel_tool_calls=True,
        )
        response_content = response.choices[0].message
        
        origin, destination, departure_date = None, None, None

        if response_content.tool_calls:
            for tool_call in response_content.tool_calls:
                try:
                    args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                
                if "origin" in args: origin = args["origin"]
                if "destination" in args: destination = args["destination"]
                if "departure_date" in args: departure_date = args["departure_date"]
        else:
            # Self-Healing Interception if Groq returned failed generation strings
            parsed_failure = _parse_failed_generation(str(response_content))
            if parsed_failure:
                _, args = parsed_failure
                if "origin" in args: origin = args["origin"]
                if "destination" in args: destination = args["destination"]
                if "departure_date" in args: departure_date = args["departure_date"]

        # Fallback regex extraction if the LLM missed parameters completely
        if not origin or not destination or not departure_date:
            airport_matches = re.findall(r'\b[A-Z]{3}\b', request.prompt)
            date_match = re.search(r'\b\d{4}-\d{2}-\d{2}\b', request.prompt)
            
            origin = airport_matches[0] if len(airport_matches) > 0 else "BOM"
            destination = airport_matches[1] if len(airport_matches) > 1 else "DBR"
            departure_date = date_match.group(0) if date_match else "2026-06-22"

# --- DETERMINISTIC DUAL-INTENT CONTEXT PIPELINE ---
        
        # 1. ALWAYS run live flight search to capture actual inventories and base prices
        print(f"--> [ORCHESTRATOR] Enforcing live flight acquisition for {origin}-{destination}...")
        live_flights_raw = get_live_flights(origin=origin, destination=destination, departure_date=departure_date)
        
        parsed_flights = []
        current_base_price = None
        
        try:
            # Unpack the raw string payload into a native dictionary
            flights_payload = json.loads(live_flights_raw)
            
            # Extract the actual list of flights using the exact key returned by tools/flights.py
            flights_list = flights_payload.get("flights", [])
            
            if isinstance(flights_list, list):
                parsed_flights = flights_list
                prices = []
                for f in flights_list:
                    if 'price' in f:
                        raw_p = f['price']
                        if isinstance(raw_p, (int, float)):
                            prices.append(int(raw_p))
                        else:
                            cleaned_p = str(raw_p).replace('₹', '').replace(',', '').strip()
                            if cleaned_p.isdigit():
                                prices.append(int(cleaned_p))
                if prices:
                    current_base_price = min(prices)
                    
        except Exception as parse_err:
            print(f"--> [ORCHESTRATOR] Flight dictionary parsing bypassed: {parse_err}")

        # 2. Enforce the prediction metrics lookup using the true extracted baseline price
        print(f"--> [ORCHESTRATOR] Enforcing real-time strategy math with base price: {current_base_price}...")
        prediction_raw = predict_booking_window(
            origin=origin, 
            destination=destination, 
            departure_date=departure_date, 
            current_base_price=current_base_price
        )

        # 3. Format the strategy data context block using only the prediction statistics
        raw_prediction_context = f"Data from predict_booking_window:\n{prediction_raw}\n\n"
        
        # 4. Get the pristine analysis structure back from the formatting model
        final_json_response = _format_final_response(raw_prediction_context)

        # 5. HARD-CODE THE BINDING OF FLIGHTS VIA PYTHON
        final_json_response["optimized_flights"] = parsed_flights[:5]
            
        return final_json_response
    except Exception as e:
        return {
            "success": False,
            "message": "Concierge engine failed to process this request.",
            "detail": str(e),
        }