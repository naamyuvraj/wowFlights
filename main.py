import os
import json
from click import prompt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
api_key =os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in environment variables.")
client = Groq(api_key=api_key)
app = FastAPI()

class FlightRequest(BaseModel):
    origin: str
    destination: str
    departure_date: str


def get_mock_flights(origin: str, destination: str, departure_date: str):
    print (f'Executing tool for {origin} to {destination} on {departure_date}')
    mock_database_response = [
        {"airline": "SkyHigh Airways", "flight_number": "SH123", "price": "$350", "duration": "4h 15m"},
        {"airline": "Oceanic Airlines", "flight_number": "OA815", "price": "$410", "duration": "3h 50m"}
    ]
    return json.dumps(mock_database_response)

flight_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_mock_flights",
            "description": "Fetch live, real-time flight options, prices, and durations between two cities for a specific date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "The starting city or airport code."
                    },
                    "destination": {
                        "type": "string",
                        "description": "The destination city or airport code."
                    },
                    "departure_date": {
                        "type": "string",
                        "description": "The date of departure."
                    }
                },
                "required": ["origin", "destination", "departure_date"]
            }
        }
    }
]

@app.post('/api/flights')
async def get_flights(request: FlightRequest):

    messages = [
        {"role": "system", "content": "You are a helpful travel assistant. Always use the provided tools to look up real flights. When you have the data, return a final response strictly in JSON format."},
        {"role": "user", "content": f'Find flights from {request.origin} to {request.destination} on {request.departure_date}'}
    ]

    try:
        
        response =client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=messages,
            tools=flight_tools,
            tool_choice='auto',
        )

        response_content = response.choices[0].message

        if response_content.tool_calls:
            messages.append(response_content)

            for tool_call in response_content.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                if function_name == "get_mock_flights":
                    tool_response = get_mock_flights(
                        origin=arguments.get('origin'),
                        destination=arguments.get('destination'),
                        departure_date=arguments.get('departure_date')
                    )
                    messages.append({
                        'tool_call_id':tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_response
                    })
            second_response = client.chat.completions.create(
                model='llama-3.1-8b-instant',
                messages=messages,
                response_format={"type": "json_object"},
            )
            final_response_content = second_response.choices[0].message.content
            return json.loads(final_response_content)
        else:
            return {"success": False, "message": "AI failed to call the flight tool."}     
                     
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))