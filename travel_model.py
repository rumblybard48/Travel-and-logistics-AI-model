import google.generativeai as genai
from datetime import datetime
import pytz
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from dotenv import load_dotenv
import timezonefinder
import os
import pycountry

# --- Modified run_travel_model for Streamlit ---
import streamlit as st

def run_travel_model():
    st.subheader("✈️ Travel Assistant")

    # Step 1: Configure the Gemini model
    try:
        model = configure_travel_model()
    except ValueError as ve:
        st.error(str(ve))
        return

    # Step 2: Start the chat session
    if "travel_chat" not in st.session_state:
        st.session_state.travel_chat = model.start_chat(enable_automatic_function_calling=True)
        st.session_state.travel_history = []

    # Step 3: Input box for user
    user_input = st.chat_input("Ask your travel assistant...")

    if user_input:
        # Show user message
        with st.chat_message("user"):
            st.markdown(user_input)

        # Process and store response
        try:
            response = st.session_state.travel_chat.send_message(user_input)
            st.session_state.travel_history.append((user_input, response.text.strip()))
        except Exception as e:
            st.error(f"Error: {e}")
            return

    # Step 4: Show conversation history
    for user_msg, bot_msg in st.session_state.travel_history:
        with st.chat_message("user"):
            st.markdown(user_msg)
        with st.chat_message("assistant"):
            st.markdown(bot_msg)

# --- Travel Functions ---

def get_location_info(location: str):
    try:
        geolocator = Nominatim(user_agent="travel_ai")
        loc = geolocator.geocode(location)
        if not loc:
            return f"Could not find location: {location}"
        
        tf = timezonefinder.TimezoneFinder()
        timezone = tf.timezone_at(lat=loc.latitude, lng=loc.longitude)
        
        country = geolocator.reverse((loc.latitude, loc.longitude), language="en").raw['address'].get('country')
        currency = pycountry.countries.get(name=country).alpha_2
        return f"{location} is in {country}. Timezone: {timezone}."
    except Exception as e:
        return f"Error fetching location info: {e}"

def suggest_packing_list(destination: str, travel_style: str = "casual"):
    return f"Packing list for {travel_style} trip to {destination}: \n- Clothes\n- Charger\n- ID\n- Sunscreen\n(Weather-based suggestions coming soon!)"

def local_time(timezone: str):
    try:
        tz = pytz.timezone(timezone)
        local = datetime.now(tz)
        return f"Current time in {timezone} is: {local.strftime('%Y-%m-%d %H:%M:%S')}"
    except pytz.UnknownTimeZoneError:
        return f"Invalid timezone '{timezone}'. Please use the format Region/City."

def calculate_distance(origin: str, destination: str):
    geolocator = Nominatim(user_agent="travel_ai")
    try:
        loc1 = geolocator.geocode(origin)
        loc2 = geolocator.geocode(destination)
        if not loc1 or not loc2:
            return "One or both locations not found."
        coords1 = (loc1.latitude, loc1.longitude)
        coords2 = (loc2.latitude, loc2.longitude)
        distance = geodesic(coords1, coords2).kilometers
        return f"Distance between {origin} and {destination}: {distance:.2f} km"
    except Exception as e:
        return f"Error during distance calculation: {e}"

# --- AI Model Configuration ---

def configure_travel_model():
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GOOGLE_API_KEY in .env")
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        tools=[local_time,  
               calculate_distance,
               get_location_info,
               suggest_packing_list]
    )
    return model
