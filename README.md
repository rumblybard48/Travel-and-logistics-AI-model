# AI Travel and Logistics Assistant

This project implements an AI-powered assistant using Google's Gemini API. The system is designed to handle travel-related and logistics-related queries by integrating external tools such as geolocation services, distance calculation, and shipment tracking.

The assistant supports function calling, allowing it to intelligently invoke predefined tools based on user input.

## Features

- Natural language interaction using Gemini API
- Travel assistance (time, recommendations, distance calculation)
- Logistics support (shipment tracking, cost estimation)
- Integration with geolocation services (Nominatim)
- Distance calculation using geodesic formulas
- Extensible tool-based architecture
- Support for multiple AI models (modular design)

## Tech Stack

- Python
- Google Generative AI (Gemini API)
- Geopy (Nominatim)
- OpenRouteService (for routing and ETA)
- dotenv (environment variable management)

## Setup Instructions

### 1. Clone the repository

git clone https://github.com/your-username/your-repo.git

cd your-repo

### 2. Create virtual environment

python -m venv venv
venv\Scripts\activate

### 3. Install dependencies

pip install -r requirements.txt

### 4. Configure environment variables

Create a `.env` file in the root directory:


GOOGLE_API_KEY=your_gemini_api_key
OPEN_ROUTE_SERVICE_APIKEY=your_openrouteservice_key

### 5. Run the application

python main.py

## Available Functional Tools

### Travel Tools
- Get local time for a specific timezone
- Calculate distance between two locations
- Provide travel recommendations

### Logistics Tools
- Track shipment using tracking number
- Estimate shipping cost based on weight and distance
- Estimate delivery time (ETA) using routing APIs

## Example Prompts

What is the current time in Tokyo?
What is the distance between Paris and Rome?
Track shipment with tracking number A1
Estimate shipping cost for 20kg from Dubai to Qatar

## How It Works

1. User enters a natural language query  
2. Gemini model processes the query  
3. The model selects an appropriate tool (function)  
4. The tool executes and returns structured data  
5. The response is formatted and returned to the user

## Limitations

- Geocoding may fail for vague or incomplete locations  
- Requires valid API keys for external services  
- Accuracy depends on third-party APIs  
- Not optimized for production deployment  

## Future Improvements

- Add air freight and sea freight modules  
- Improve geocoding reliability  
- Integrate Google Maps API for better routing  
- Build a frontend interface  
- Add real-time shipment tracking APIs  
