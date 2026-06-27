import os
import time
import streamlit as st
import google.generativeai as genai
from datetime import datetime
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import pytz
import pycountry
import timezonefinder

load_dotenv()

geolocator = Nominatim(user_agent="travel_ai_tool")

TRAVEL_SYSTEM_PROMPT = """
You are a knowledgeable and friendly travel assistant with expertise in global destinations,
trip planning, local customs, travel logistics, and safety.

Your responsibilities:
- Help users plan trips, build itineraries, and discover destinations
- Provide accurate local time, distances, and location details
- Suggest packing lists tailored to destination and travel style
- Advise on visa requirements and travel documents
- Offer currency conversion guidance
- Always ask for travel dates, duration, and interests before building full itineraries
- Warn about travel advisories or safety concerns when relevant

Tone: warm, enthusiastic, and helpful — like a well-travelled friend giving honest advice.
"""


# ── Retry helper ──────────────────────────────────────────────────────────────

def _retry(fn, retries=3, delay=2):
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(delay * (2 ** attempt))


# ── Location Info ─────────────────────────────────────────────────────────────

def get_location_info(location: str) -> str:
    """
    Returns timezone, country, and local time for a given location.

    Args:
        location (str): City or place name.

    Returns:
        str: Timezone, country, and current local time.
    """
    try:
        loc = _retry(lambda: geolocator.geocode(location))
        if not loc:
            return f"Could not find location: {location}"

        tf = timezonefinder.TimezoneFinder()
        timezone_str = tf.timezone_at(lat=loc.latitude, lng=loc.longitude)

        reverse = _retry(lambda: geolocator.reverse((loc.latitude, loc.longitude), language="en"))
        address = reverse.raw.get("address", {}) if reverse else {}
        country_name = address.get("country", "Unknown")

        # Look up ISO currency code from country name
        country_obj = pycountry.countries.get(name=country_name)
        if country_obj:
            currencies = [
                c.alpha_3 for c in pycountry.currencies
                if hasattr(c, "numeric") and c.numeric
            ]
            # Simple fallback — just show country code
            country_code = country_obj.alpha_2
        else:
            country_code = "N/A"

        local_time = ""
        if timezone_str:
            tz = pytz.timezone(timezone_str)
            local_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z")

        return (
            f"📍 {location}\n"
            f"  Country: {country_name} ({country_code})\n"
            f"  Timezone: {timezone_str or 'Unknown'}\n"
            f"  Local time: {local_time or 'N/A'}"
        )
    except Exception as e:
        return f"Error fetching location info: {e}"


# ── Local Time ────────────────────────────────────────────────────────────────

def local_time(timezone: str) -> str:
    """
    Returns the current local time for a given timezone string.

    Args:
        timezone (str): IANA timezone string, e.g. 'Asia/Dubai' or 'Europe/Paris'.

    Returns:
        str: Current date and time in that timezone.
    """
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        return f"🕐 Current time in {timezone}: {now.strftime('%A, %d %B %Y  %H:%M:%S %Z')}"
    except pytz.UnknownTimeZoneError:
        return f"Unknown timezone '{timezone}'. Use IANA format like 'Asia/Dubai' or 'America/New_York'."


# ── Distance ──────────────────────────────────────────────────────────────────

def calculate_distance(origin: str, destination: str) -> str:
    """
    Calculates the straight-line distance between two locations.

    Args:
        origin (str): Starting location name.
        destination (str): Destination location name.

    Returns:
        str: Distance in kilometres and miles.
    """
    try:
        loc1 = _retry(lambda: geolocator.geocode(origin))
        loc2 = _retry(lambda: geolocator.geocode(destination))
        if not loc1 or not loc2:
            return "One or both locations could not be found."
        km = geodesic((loc1.latitude, loc1.longitude), (loc2.latitude, loc2.longitude)).kilometers
        miles = km * 0.621371
        return f"📏 Distance: {origin} → {destination}:  {km:.0f} km  ({miles:.0f} miles)"
    except Exception as e:
        return f"Error calculating distance: {e}"


# ── Packing List ──────────────────────────────────────────────────────────────

def suggest_packing_list(destination: str, travel_style: str = "casual", duration_days: int = 7) -> str:
    """
    Generates a tailored packing list for a destination and travel style using AI.

    Args:
        destination (str): Travel destination (city or country).
        travel_style (str): Style of travel — 'casual', 'business', 'adventure', or 'beach'. Default 'casual'.
        duration_days (int): Length of trip in days. Default 7.

    Returns:
        str: Formatted packing list.
    """
    from google.generativeai import GenerativeModel
    model = GenerativeModel(model_name="gemini-2.5-flash")

    prompt = (
        f"Create a practical packing list for a {duration_days}-day {travel_style} trip to {destination}. "
        "Organise it into categories: Clothing, Toiletries, Documents, Electronics, and Extras. "
        "Keep each category to 5–8 bullet points. Be specific to the destination's climate and culture."
    )
    response = model.generate_content(prompt)
    return f"🧳 Packing List — {destination} ({travel_style}, {duration_days} days)\n\n{response.text.strip()}"


# ── Currency Conversion ───────────────────────────────────────────────────────

def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """
    Converts an amount between two currencies using AI-estimated rates with a disclaimer.

    Args:
        amount (float): Amount to convert.
        from_currency (str): Source currency code, e.g. 'USD', 'EUR', 'AED'.
        to_currency (str): Target currency code, e.g. 'GBP', 'JPY', 'INR'.

    Returns:
        str: Converted amount with rate and disclaimer.
    """
    from google.generativeai import GenerativeModel
    model = GenerativeModel(model_name="gemini-2.5-flash")

    prompt = (
        f"Convert {amount} {from_currency.upper()} to {to_currency.upper()}. "
        "Use your knowledge of approximate current exchange rates. "
        "Show: the estimated rate, the converted amount, and a note that the user should verify with a live source like Google or XE.com. "
        "Keep it to 2-3 sentences."
    )
    response = model.generate_content(prompt)
    return f"💱 Currency Conversion\n{response.text.strip()}"


# ── Visa Requirements ─────────────────────────────────────────────────────────

def get_visa_requirements(passport_country: str, destination_country: str) -> str:
    """
    Provides general visa requirement information for a passport holder travelling to a destination.

    Args:
        passport_country (str): Country of the traveller's passport (e.g. 'United Kingdom', 'India').
        destination_country (str): Country the traveller wants to visit (e.g. 'Japan', 'USA').

    Returns:
        str: General visa requirements and key notes.
    """
    from google.generativeai import GenerativeModel
    model = GenerativeModel(model_name="gemini-2.5-flash")

    prompt = (
        f"What are the visa requirements for a {passport_country} passport holder travelling to {destination_country}? "
        "Cover: whether a visa is required, if visa-on-arrival or e-visa is available, typical stay duration, "
        "and any key conditions. Keep it to 3-5 sentences and advise the user to verify with the official embassy or consulate."
    )
    response = model.generate_content(prompt)
    return f"🛂 Visa Requirements — {passport_country} → {destination_country}\n{response.text.strip()}"


# ── Itinerary Suggestion ──────────────────────────────────────────────────────

def suggest_itinerary(destination: str, days: int, interests: str = "culture, food, sightseeing") -> str:
    """
    Generates a day-by-day travel itinerary for a destination.

    Args:
        destination (str): Travel destination (city or region).
        days (int): Number of days for the trip.
        interests (str): Comma-separated list of traveller interests. Default 'culture, food, sightseeing'.

    Returns:
        str: Day-by-day itinerary.
    """
    from google.generativeai import GenerativeModel
    model = GenerativeModel(model_name="gemini-2.5-flash")

    prompt = (
        f"Create a {days}-day travel itinerary for {destination}. "
        f"The traveller is interested in: {interests}. "
        "Format as Day 1, Day 2, etc. with morning, afternoon, and evening activities. "
        "Include specific places, restaurants, and practical tips. Keep each day concise."
    )
    response = model.generate_content(prompt)
    return f"🗺️ {days}-Day Itinerary — {destination}\n\n{response.text.strip()}"


# ── Streamlit UI ──────────────────────────────────────────────────────────────

def run_travel_model():
    st.subheader("✈️ Travel Assistant")

    try:
        model = _configure_travel_model()
    except ValueError as ve:
        st.error(str(ve))
        return

    if "travel_chat" not in st.session_state:
        st.session_state.travel_chat = model.start_chat(enable_automatic_function_calling=True)
        st.session_state.travel_history = []

    # Render history first so new messages append at the bottom (bug fix)
    for user_msg, bot_msg in st.session_state.travel_history:
        with st.chat_message("user"):
            st.markdown(user_msg)
        with st.chat_message("assistant"):
            st.markdown(bot_msg)

    user_input = st.chat_input("Ask your travel assistant...")

    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = st.session_state.travel_chat.send_message(user_input)
                    bot_reply = response.text.strip()
                    st.markdown(bot_reply)
                    st.session_state.travel_history.append((user_input, bot_reply))
                except Exception as e:
                    st.error(f"Error: {e}")

    if st.session_state.travel_history:
        if st.button("🗑️ Clear conversation", key="clear_travel"):
            st.session_state.travel_chat = None
            st.session_state.travel_history = []
            st.rerun()


# ── Model Configuration ───────────────────────────────────────────────────────

def _configure_travel_model():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GOOGLE_API_KEY in .env")
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=TRAVEL_SYSTEM_PROMPT,
        tools=[
            local_time,
            calculate_distance,
            get_location_info,
            suggest_packing_list,
            convert_currency,
            get_visa_requirements,
            suggest_itinerary,
        ]
    )
    return model
