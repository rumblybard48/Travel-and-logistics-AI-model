import google.generativeai as genai
import os
from dotenv import load_dotenv
import openrouteservice
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
load_dotenv()
geolocator = Nominatim(user_agent="shipping_cost_tool")

OPEN_ROUTE_SERVICE_APIKEY = os.getenv("OPEN_ROUTE_SERVICE_APIKEY")

client = openrouteservice.Client(key=OPEN_ROUTE_SERVICE_APIKEY)

# logistics_model.py

import streamlit as st

def run_logistics_model():
    st.subheader("🚚 Logistics Assistant")

    try:
        model = configure_logistics_model()
    except ValueError as ve:
        st.error(str(ve))
        return
    
    if "logistics_chat" not in st.session_state:
        st.session_state.logistics_chat = model.start_chat(enable_automatic_function_calling=True)
        st.session_state.logistics_history = []

    user_input = st.chat_input("Ask your logistics assistant...")

    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)

        try:
            response = st.session_state.logistics_chat.send_message(user_input)
            st.session_state.logistics_history.append((user_input, response.text.strip()))
        except Exception as e:
            st.error(f"Error: {e}")
            return

    for user_msg, bot_msg in st.session_state.logistics_history:
        with st.chat_message("user"):
            st.markdown(user_msg)
        with st.chat_message("assistant"):
            st.markdown(bot_msg)

def get_coordinates(location_name: str):
    location = geolocator.geocode(location_name)
    if location:
        return [location.longitude, location.latitude]
    else:
        return None

def recommend_storage_type(product_name: str) -> str:
    """
    Uses Gemini's reasoning to determine optimal storage conditions for a product.
    Returns a general recommendation like 'room temperature', 'cold storage', 'frozen storage', etc.
    """
    from google.generativeai import GenerativeModel
    model = GenerativeModel(model_name="gemini-1.5-flash")

    prompt = (
        f"What type of storage is ideal for {product_name}? "
        "Consider whether it is perishable, temperature sensitive, or prone to spoilage. "
        "Answer with one of the categories: room temperature, cold storage, freezing storage, or dry storage. "
        "Explain your reasoning briefly."
    )

    response = model.generate_content(prompt)
    return response.text.strip()

def estimate_shipping_cost_by_location(origin: str, destination: str, weight_kg: float, service_type: str = "standard"):
    """
    Estimate shipping cost between origin and destination by truck.

    Args:
        origin (str): Name of the origin city or area.
        destination (str): Name of the destination city or area.
        weight_kg (float): Cargo weight in kilograms.
        service_type (str): Type of service - "standard" or "express".

    Returns:
        str: Estimated cost in USD.
    """
    origin_coords = get_coordinates(origin)
    destination_coords = get_coordinates(destination)
    
    if not origin_coords or not destination_coords:
        return "Could not determine coordinates for one or both locations."
    
    try:
        route = client.directions(
            coordinates=[origin_coords, destination_coords],
            profile="driving-car",
            format="geojson"
        )
        distance_km = route['features'][0]['properties']['summary']['distance'] / 1000

        rate_per_km = 0.02 if service_type == "standard" else 0.05
        base_cost = 5.0
        cost = base_cost + (weight_kg * rate_per_km * distance_km)

        return f"Estimated shipping cost from {origin} to {destination} ({distance_km:.1f} km) for {weight_kg}kg cargo via {service_type} truck: ${cost:.2f}"
    except Exception as e:
        return f"An error occurred while calculating cost: {e}"

geolocator = Nominatim(user_agent="air_freight_tool")

def get_air_distance_km(origin: str, destination: str):
    location1 = geolocator.geocode(origin)
    location2 = geolocator.geocode(destination)
    if not location1 or not location2:
        return None
    coords1 = (location1.latitude, location1.longitude)
    coords2 = (location2.latitude, location2.longitude)
    return geodesic(coords1, coords2).kilometers

def estimate_air_freight_cost(weight_kg: float, origin: str, destination: str, service_class: str = "economy"):
    """
    Calculates the estimated air freight shipping cost between two international locations based on weight, distance, and service class.
    
    Args:
        weight_kg (float): Weight of the cargo in kilograms.
        origin (str): Name of the origin city or airport.
        destination (str): Name of the destination city or airport.
        service_class (str): Type of air freight service. Accepts 'economy' or 'express'. Default is 'economy'.
    
    Returns:
        str: A formatted string containing the estimated cost in USD.
    """
    distance_km = get_air_distance_km(origin, destination)
    if distance_km is None:
        return "Error: Could not resolve one or both locations."
    
    rate_per_km = 0.08 if service_class == "economy" else 0.15
    base_cost = 50.0
    cost = base_cost + (weight_kg * rate_per_km * distance_km)
    return f"Estimated air freight cost ({service_class}) from {origin} to {destination}: ${cost:.2f}"

def configure_logistics_model():
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GOOGLE_API_KEY in .env")
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        tools=[
        recommend_storage_type,
        estimate_shipping_cost_by_location,
        estimate_air_freight_cost,
        get_coordinates]
    )
    return model